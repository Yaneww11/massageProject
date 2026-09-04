import hashlib
import logging
import os
import zipfile
from io import BytesIO

from django.conf import settings
from django import forms as django_forms
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http.request import validate_host
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import datetime, timedelta, date
from django.db.models import Count, Q
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, FileResponse, JsonResponse, Http404
from PIL import Image as PILImage, ImageDraw, ImageFont

from massageProject.main_app.context_processors import get_cached_homepage
from massageProject.main_app.emails import send_gallery_ready_email, send_marks_finalized_email, \
    send_final_delivery_email
from massageProject.main_app.ics import build_reservation_ics
from massageProject.main_app.forms import ReservationCreateForm, ReservationEditForm, \
    ReservationDeleteForm, CommentForm, UserNameForm, ProofingGalleryUploadForm, \
    ProofingLabelFormSet, FinalGalleryUploadForm
from massageProject.main_app.mixins import BookingEnabledMixin, booking_enabled_required, \
    CommentsEnabledMixin, comments_enabled_required, PhotographerModeMixin
from massageProject.main_app.models import Service, Specialist, Reservation, Comment, WorkingHours, ServiceGroup, \
    Gallery, Image, ImageProof, PhotoLabel

logger = logging.getLogger(__name__)


@booking_enabled_required
@login_required
def check_availability(request):
    specialist_id = request.GET.get('specialist_id')
    date_str = request.GET.get('date')
    service_id = request.GET.get('service_id')

    if not all([specialist_id, date_str, service_id]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        service = Service.objects.get(pk=service_id)
        specialist = Specialist.objects.get(pk=specialist_id)
    except (ValueError, Service.DoesNotExist, Specialist.DoesNotExist):
        return JsonResponse({'error': 'Invalid parameters'}, status=400)

    # 1. Get working hours for the day
    day_of_week = date_obj.weekday()
    working_hours = WorkingHours.objects.filter(specialist=specialist, day_of_week=day_of_week).first()

    if not working_hours:
        return JsonResponse({'slots': []})  # Not working

    # 2. Generate 30-min slots
    slots = []
    current_dt = datetime.combine(date_obj, working_hours.start_time)
    end_dt = datetime.combine(date_obj, working_hours.end_time)
    
    # Lead time check (2 hours)
    min_time = timezone.localtime(timezone.now()) + timedelta(hours=2)

    duration = timedelta(minutes=service.duration_in_minutes)

    # 3. Get existing reservations for overlap check
    existing_reservations = Reservation.objects.select_related('service').filter(
        specialist=specialist,
        date=date_obj,
        status=Reservation.STATUS_ACTIVE
    )

    while current_dt + duration <= end_dt:
        slot_time = current_dt.time()
        slot_end_dt = current_dt + duration
        
        is_available = True
        reason = None

        # Check lead time
        if timezone.make_aware(current_dt) < min_time:
            is_available = False
            reason = 'past'
        else:
            # Check overlap
            for res in existing_reservations:
                res_start = datetime.combine(date_obj, res.time)
                res_end = res_start + timedelta(minutes=res.service.duration_in_minutes)
                
                # Overlap if: (StartA < EndB) and (EndA > StartB)
                if current_dt < res_end and slot_end_dt > res_start:
                    is_available = False
                    reason = 'taken'
                    break

        slots.append({
            'time': slot_time.strftime('%H:%M'),
            'available': is_available,
            'reason': reason
        })
        
        current_dt += timedelta(minutes=30)

    return JsonResponse({'slots': slots})


# Create your views here.
class Index(TemplateView):
    template_name = 'pages/home.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['is_photographer_website'] = settings.IS_PHOTOGRAPHER_WEBSITE
        context['page'] = get_cached_homepage()
        services = list(Service.objects.filter(home_page=True)[:3])
        context['services'] = services
        context['featured_has_images'] = bool(services) and all(m.image for m in services)
        if context['page']:
            gallery = context['page'].gallery
            context['gallery'] = gallery
            context['gallery_images'] = gallery.images.all()[:3]
        context['comments'] = Comment.objects.filter(is_reviewed=True).order_by('-created_at')[:10]
        return self.render_to_response(context)

class PrivacyPolicyView(TemplateView):
    template_name = 'pages/privacy_policy.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = get_cached_homepage()
        return context

class ServicesDashboard(ListView):
    model = Service
    template_name = 'pages/services_page.html'
    context_object_name = 'services'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = ServiceGroup.objects.filter(services__isnull=False).distinct()
        return context

class ReservationPage(BookingEnabledMixin, LoginRequiredMixin, CreateView):
    model = Reservation
    template_name = 'pages/reservation.html'
    form_class = ReservationCreateForm
    success_url = reverse_lazy('profile_page')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not (user.first_name and user.last_name) and 'name_form' not in context:
            context['name_form'] = UserNameForm()
        context['specialists'] = Specialist.objects.all()
        context['services_data'] = [
            {
                'id': m.pk,
                'name': m.name,
                'duration': m.duration_in_minutes,
                'price': str(m.price).rstrip('0').rstrip('.') if m.price else '',
                'desc': m.short_description or (m.description[:100] if m.description else ''),
            }
            for m in Service.objects.all()
        ]
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        user = request.user
        name_form = None
        name_valid = True

        if not (user.first_name and user.last_name):
            name_form = UserNameForm(request.POST)
            if name_form.is_valid():
                user.first_name = name_form.cleaned_data['first_name']
                user.last_name = name_form.cleaned_data['last_name']
                user.save(update_fields=['first_name', 'last_name'])
                name_form = None
            else:
                name_valid = False

        form = self.get_form()

        if form.is_valid() and name_valid:
            return self.form_valid(form)

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            all_errors = {}
            for f, e in form.errors.items():
                all_errors[f] = list(e)
            if name_form is not None:
                for f, e in name_form.errors.items():
                    all_errors[f] = list(e)
            return JsonResponse({'success': False, 'errors': all_errors}, status=400)

        extra = {'form': form}
        if name_form is not None:
            extra['name_form'] = name_form
        return self.render_to_response(self.get_context_data(**extra))

    def form_valid(self, form):
        form.instance.user = self.request.user
        self.object = form.save()
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            r = self.object
            price = r.service.price
            price_str = str(price).rstrip('0').rstrip('.') if price else ''
            return JsonResponse({
                'success': True,
                'booking': {
                    'service': r.service.name,
                    'duration': f"{r.service.duration_in_minutes} мин",
                    'price': f"{price_str} €" if price_str else '',
                    'specialist': r.specialist.name,
                    'date': r.date.strftime('%d.%m.%Y'),
                    'time': r.time.strftime('%H:%M'),
                },
                'contact': str(self.request.user.email or self.request.user.phone_number),
            })
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        if 'pk' in self.kwargs:
            initial['service'] = self.kwargs['pk']
        elif self.request.GET.get('service'):
            initial['service'] = self.request.GET.get('service')
        return initial

class AboutPage(TemplateView):
    template_name = 'pages/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = Comment.objects.filter(is_reviewed=True).order_by('-created_at')[:15]
        context['total_comments_count'] = Comment.objects.filter(is_reviewed=True).count()
        if 'form' not in context:
            context['form'] = CommentForm()

        user = self.request.user
        if user.is_authenticated and not (user.first_name and user.last_name) and 'name_form' not in context:
            context['name_form'] = UserNameForm()
        return context

    def post(self, request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().comments_enabled:
            raise Http404
        user = request.user
        name_form = None
        name_valid = True

        if user.is_authenticated and not (user.first_name and user.last_name):
            name_form = UserNameForm(request.POST)
            if name_form.is_valid():
                user.first_name = name_form.cleaned_data['first_name']
                user.last_name = name_form.cleaned_data['last_name']
                user.save(update_fields=['first_name', 'last_name'])
                name_form = None
            else:
                name_valid = False

        form = CommentForm(request.POST)

        if form.is_valid() and name_valid:
            comment = form.save(commit=False)
            if user.is_authenticated:
                comment.user = user
                comment.author = user.get_full_name() or user.phone_number
            comment.save()
            messages.success(request, _('Вашият коментар е изпратен успешно и ще бъде публикуван след преглед.'))
            return redirect('about_page')

        extra = {'form': form}
        if name_form:
            extra['name_form'] = name_form

        return self.render_to_response(self.get_context_data(**extra))

from django.views.decorators.http import require_POST

@comments_enabled_required
@login_required
@require_POST
def submit_comment(request):
    # Rate limit: 1 comment per 60 seconds per IP
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    ip = ip.split(',')[0].strip()
    cache_key = f'comment_rl_{ip}'
    if cache.get(cache_key):
        return JsonResponse({'success': False, 'error': _('Моля, изчакайте преди да изпратите нов коментар.')}, status=429)
    cache.set(cache_key, 1, timeout=60)

    content = request.POST.get('content', '').strip()
    try:
        rating = max(1, min(5, int(request.POST.get('rating', 5))))
    except (ValueError, TypeError):
        rating = 5

    if not content:
        return JsonResponse({'success': False, 'error': _('Въведете мнение')}, status=400)

    if len(content) > 2000:
        return JsonResponse({'success': False, 'error': _('Мнението не може да надвишава 2000 символа.')}, status=400)

    comment = Comment(content=content, rating=rating, is_reviewed=False)
    user = request.user
    comment.user = user
    comment.author = user.get_full_name() or str(user.phone_number)
    reservation_id = request.POST.get('reservation_id')
    if reservation_id:
        try:
            comment.reservation = Reservation.all_objects.get(pk=reservation_id, user=user)
        except (Reservation.DoesNotExist, ValueError):
            pass

    comment.save()
    return JsonResponse({'success': True})


class AllCommentsView(CommentsEnabledMixin, ListView):
    model = Comment
    template_name = 'pages/all_comments.html'
    context_object_name = 'comments'
    paginate_by = 15

    def get_queryset(self):
        return Comment.objects.filter(is_reviewed=True).order_by('-created_at')


def _resolve_photo_workflow_scope(user):
    """(is_staff_mode, specialist) for the photographer-mode photo-workflow
    views — staff full-access takes precedence, mirroring ProfilePage's role
    resolution. Returns (None, None) if the user has neither."""
    if user.has_perm('main_app.view_all_reservations'):
        return True, None
    specialist_link = getattr(user, 'specialist_profile', None)
    if specialist_link and user.has_perm('main_app.view_specialist_reservations'):
        return False, specialist_link
    return None, None


class ProofingGalleryUploadView(PhotographerModeMixin, LoginRequiredMixin, TemplateView):
    template_name = 'pages/proofing_gallery_upload.html'

    def _load_scope(self):
        is_staff_mode, specialist = _resolve_photo_workflow_scope(self.request.user)
        if is_staff_mode is None:
            raise PermissionDenied
        self.is_staff_mode = is_staff_mode
        self.specialist = specialist

    def _reservation_queryset(self):
        qs = Reservation.objects.filter(gallery__isnull=True).select_related('specialist', 'service', 'user')
        if not self.is_staff_mode:
            qs = qs.filter(specialist=self.specialist)
        return qs.order_by('-date', '-time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Качване на галерия за преглед')
        if 'upload_form' not in context:
            initial = {}
            reservation_id = self.request.GET.get('reservation_id')
            if reservation_id:
                initial['reservation'] = reservation_id
            context['upload_form'] = ProofingGalleryUploadForm(
                reservation_queryset=self._reservation_queryset(), initial=initial,
            )
        if 'label_formset' not in context:
            context['label_formset'] = ProofingLabelFormSet(prefix='labels')
        return context

    def get(self, request, *args, **kwargs):
        self._load_scope()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._load_scope()
        upload_form = ProofingGalleryUploadForm(
            request.POST, request.FILES, reservation_queryset=self._reservation_queryset(),
        )
        label_formset = ProofingLabelFormSet(request.POST, prefix='labels')

        if upload_form.is_valid() and label_formset.is_valid():
            reservation = upload_form.cleaned_data['reservation']
            gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
            image_validator = django_forms.ImageField()
            uploaded = 0
            for order, uploaded_file in enumerate(upload_form.cleaned_data['images']):
                try:
                    image_validator.clean(uploaded_file)
                    image = Image(gallery=gallery, image=uploaded_file, order=order)
                    image.full_clean()
                    image.save()
                except ValidationError as exc:
                    messages.error(request, _('Пропусната %(name)s: %(error)s') % {
                        'name': uploaded_file.name, 'error': '; '.join(exc.messages),
                    })
                    continue
                uploaded += 1

            if uploaded == 0:
                gallery.delete()
                messages.error(request, _('Нито една снимка не беше качена успешно.'))
                return self.render_to_response(
                    self.get_context_data(upload_form=upload_form, label_formset=label_formset)
                )

            label_order = 0
            for label_form in label_formset:
                if not label_form.cleaned_data:
                    continue
                name = label_form.cleaned_data.get('name')
                cap = label_form.cleaned_data.get('cap')
                if name and cap:
                    PhotoLabel.objects.create(gallery=gallery, name=name, cap=cap, order=label_order)
                    label_order += 1

            reservation.gallery = gallery
            reservation.need_client_review = True
            try:
                reservation.save(update_fields=['gallery', 'need_client_review'])
            except ValidationError as exc:
                gallery.delete()
                messages.error(request, _('Резервацията не можа да бъде обновена: %(error)s') % {
                    'error': '; '.join(exc.messages),
                })
                return self.render_to_response(
                    self.get_context_data(upload_form=upload_form, label_formset=label_formset)
                )

            if not send_gallery_ready_email(request, reservation):
                messages.warning(request, _(
                    'Галерията е качена успешно (%(count)d снимки), но имейлът до клиента не бе изпратен.'
                ) % {'count': uploaded})
            else:
                messages.success(request, _('Галерията е качена успешно (%(count)d снимки).') % {'count': uploaded})
            return redirect('profile_page')

        return self.render_to_response(
            self.get_context_data(upload_form=upload_form, label_formset=label_formset)
        )


def _get_owned_reservation_for_photo_workflow(request, reservation_id):
    """Ownership + role check shared by the Marked Photos view and its
    downloads: the owning specialist, or staff on behalf of any specialist."""
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    is_staff_mode, specialist = _resolve_photo_workflow_scope(request.user)
    if is_staff_mode is None:
        raise PermissionDenied
    if not is_staff_mode and reservation.specialist_id != specialist.pk:
        raise PermissionDenied
    return reservation


def _marked_images_queryset(reservation):
    if not reservation.gallery_id:
        return Image.objects.none()
    return (
        Image.objects.filter(gallery=reservation.gallery, proof__is_marked=True)
        .select_related('proof').prefetch_related('proof__labels').order_by('order')
    )


class MarkedPhotosView(PhotographerModeMixin, LoginRequiredMixin, TemplateView):
    template_name = 'pages/marked_photos.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = _get_owned_reservation_for_photo_workflow(self.request, self.kwargs['reservation_id'])
        context['title'] = _('Маркирани снимки')
        context['reservation'] = reservation
        context['marked_images'] = list(_marked_images_queryset(reservation))
        return context


@login_required
def serve_marked_photo_image(request, reservation_id, image_id):
    if not settings.IS_PHOTOGRAPHER_WEBSITE:
        raise Http404
    reservation = _get_owned_reservation_for_photo_workflow(request, reservation_id)
    image = get_object_or_404(_marked_images_queryset(reservation), pk=image_id)
    return FileResponse(image.image.open('rb'), content_type='image/webp')


@login_required
def download_marked_photo(request, reservation_id, image_id):
    if not settings.IS_PHOTOGRAPHER_WEBSITE:
        raise Http404
    reservation = _get_owned_reservation_for_photo_workflow(request, reservation_id)
    image = get_object_or_404(_marked_images_queryset(reservation), pk=image_id)
    filename = os.path.basename(image.image.name)
    return FileResponse(image.image.open('rb'), as_attachment=True, filename=filename)


def _zip_images_response(images, filename):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
        used_names = set()
        for image in images:
            name = os.path.basename(image.image.name)
            if name in used_names:
                name = f'{image.pk}-{name}'
            used_names.add(name)
            with image.image.open('rb') as source:
                archive.writestr(name, source.read())
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def download_marked_photos_zip(request, reservation_id):
    if not settings.IS_PHOTOGRAPHER_WEBSITE:
        raise Http404
    reservation = _get_owned_reservation_for_photo_workflow(request, reservation_id)
    images = _marked_images_queryset(reservation)
    return _zip_images_response(images, f'marked-photos-reservation-{reservation.pk}.zip')


class FinalGalleryUploadView(PhotographerModeMixin, LoginRequiredMixin, TemplateView):
    template_name = 'pages/final_gallery_upload.html'

    def _load_scope(self):
        is_staff_mode, specialist = _resolve_photo_workflow_scope(self.request.user)
        if is_staff_mode is None:
            raise PermissionDenied
        self.is_staff_mode = is_staff_mode
        self.specialist = specialist

    def _reservation_queryset(self):
        qs = Reservation.objects.filter(
            proofing_finalized_at__isnull=False, final_gallery__isnull=True,
        ).select_related('specialist', 'service', 'user')
        if not self.is_staff_mode:
            qs = qs.filter(specialist=self.specialist)
        return qs.order_by('-date', '-time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Качване на финална галерия')
        if 'upload_form' not in context:
            initial = {}
            reservation_id = self.request.GET.get('reservation_id')
            if reservation_id:
                initial['reservation'] = reservation_id
            context['upload_form'] = FinalGalleryUploadForm(
                reservation_queryset=self._reservation_queryset(), initial=initial,
            )
        return context

    def get(self, request, *args, **kwargs):
        self._load_scope()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._load_scope()
        upload_form = FinalGalleryUploadForm(
            request.POST, request.FILES, reservation_queryset=self._reservation_queryset(),
        )

        if upload_form.is_valid():
            reservation = upload_form.cleaned_data['reservation']
            gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_FINAL)
            image_validator = django_forms.ImageField()
            uploaded = 0
            for order, uploaded_file in enumerate(upload_form.cleaned_data['images']):
                try:
                    image_validator.clean(uploaded_file)
                    image = Image(gallery=gallery, image=uploaded_file, order=order)
                    image.full_clean()
                    image.save()
                except ValidationError as exc:
                    messages.error(request, _('Пропусната %(name)s: %(error)s') % {
                        'name': uploaded_file.name, 'error': '; '.join(exc.messages),
                    })
                    continue
                uploaded += 1

            if uploaded == 0:
                gallery.delete()
                messages.error(request, _('Нито една снимка не беше качена успешно.'))
                return self.render_to_response(self.get_context_data(upload_form=upload_form))

            reservation.final_gallery = gallery
            try:
                reservation.save(update_fields=['final_gallery'])
            except ValidationError as exc:
                gallery.delete()
                messages.error(request, _('Резервацията не можа да бъде обновена: %(error)s') % {
                    'error': '; '.join(exc.messages),
                })
                return self.render_to_response(self.get_context_data(upload_form=upload_form))

            if send_final_delivery_email(request, reservation):
                messages.success(
                    request,
                    _('Финалната галерия е качена и доставена успешно (%(count)d снимки).') % {'count': uploaded},
                )
            else:
                messages.warning(request, _(
                    'Финалната галерия е качена успешно (%(count)d снимки), но имейлът до клиента не бе изпратен.'
                ) % {'count': uploaded})
            return redirect('profile_page')

        return self.render_to_response(self.get_context_data(upload_form=upload_form))


def _get_owned_final_gallery_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, user=request.user)
    if not reservation.final_gallery_id:
        raise Http404
    return reservation


@login_required
def serve_final_gallery_image(request, reservation_id, image_id):
    if not settings.IS_PHOTOGRAPHER_WEBSITE:
        raise Http404
    reservation = _get_owned_final_gallery_reservation(request, reservation_id)
    image = get_object_or_404(Image, pk=image_id, gallery=reservation.final_gallery)
    return FileResponse(image.image.open('rb'), content_type='image/webp')


@login_required
def download_final_gallery(request, reservation_id):
    if not settings.IS_PHOTOGRAPHER_WEBSITE:
        raise Http404
    reservation = _get_owned_final_gallery_reservation(request, reservation_id)
    images = reservation.final_gallery.images.order_by('order')
    return _zip_images_response(images, f'final-photos-reservation-{reservation.pk}.zip')


class ProfilePage(LoginRequiredMixin, TemplateView):
    template_name = 'pages/my_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_photographer_website'] = settings.IS_PHOTOGRAPHER_WEBSITE

        specialist_link = getattr(user, 'specialist_profile', None)

        if user.has_perm('main_app.view_all_reservations'):
            context['role'] = 'staff'
            context['title'] = _('Управление на резервации')
            context['specialists'] = list(Specialist.objects.order_by('name'))
            base_qs = Reservation.objects.all()
            context.update(_build_reservations_table_context(self.request, base_qs, is_staff=True))
        elif specialist_link and user.has_perm('main_app.view_specialist_reservations'):
            context['role'] = 'specialist'
            # _("график") is nested in an f-string; makemessages can't extract it — the .po/.mo entries for it are maintained by hand.
            context['title'] = f'{user.get_full_name()} - {_("график")}'
            base_qs = Reservation.objects.filter(specialist=specialist_link)
            context.update(_build_reservations_table_context(self.request, base_qs, is_staff=False))
        else:
            context['role'] = 'client'
            user_qs = Reservation.objects.filter(user=user)
            active_reservations = list(user_qs.active().order_by('date', 'time'))
            past_reservations = list(user_qs.past().order_by('-date', '-time')[:5])
            context['title'] = f'{user.get_full_name()} - {_("резервации")}'

            context['active_reservations'] = active_reservations
            context['past_reservations'] = past_reservations
            context['next_reservation'] = active_reservations[0] if active_reservations else None
            context['today'] = date.today()

            # Metrics
            context['total_visits'] = Reservation.all_objects.filter(user=user, status='completed').count()
            context['upcoming_count'] = len(active_reservations)
            fav = (Reservation.objects.filter(user=user)
                   .values('service__name').annotate(c=Count('id')).order_by('-c').first())
            context['favorite_service'] = fav['service__name'] if fav else None
            context['client_since'] = user.date_joined.year

            # Studio info and working hours -- business_info is already supplied
            # globally by the admin_branding context processor, no need to
            # re-fetch it here.
            homepage = get_cached_homepage()
            context['working_hours'] = list(homepage.business_working_hours.order_by('order')) if homepage else []

            # Map of reviewed past reservations {reservation_id: comment}
            reviewed = Comment.objects.filter(reservation__in=past_reservations).select_related('reservation')
            context['reviewed_map'] = {c.reservation_id: c for c in reviewed}

        return context


def _build_reservations_table_context(request, base_qs, is_staff):
    """Filterable/sortable reservations table shared by the specialist and
    staff branches of the profile page. Default sort is soonest-upcoming
    first: reservations still to come, soonest first, then past ones, most
    recent first — mirroring the client profile's active/past convention."""
    is_photographer = settings.IS_PHOTOGRAPHER_WEBSITE

    qs = base_qs.select_related('service', 'specialist', 'user')

    phase_choices = list(Reservation.PHOTO_PHASE_CHOICES) if is_photographer else []
    phase_choices += [c for c in Reservation.STATUS_CHOICES if c[0] != Reservation.STATUS_DELETED]

    selected_phase = request.GET.get('phase', '')
    if selected_phase:
        phase_q = Reservation.phase_query(selected_phase)
        if phase_q is not None:
            qs = qs.filter(phase_q)
        else:
            selected_phase = ''

    date_from = request.GET.get('date_from', '')
    if date_from:
        try:
            qs = qs.filter(date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            date_from = ''

    date_to = request.GET.get('date_to', '')
    if date_to:
        try:
            qs = qs.filter(date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            date_to = ''

    service_id = request.GET.get('service_id', '')
    if service_id:
        if service_id.isdigit():
            qs = qs.filter(service_id=service_id)
        else:
            service_id = ''

    specialist_id = ''
    if is_staff:
        specialist_id = request.GET.get('specialist_id', '')
        if specialist_id:
            if specialist_id.isdigit():
                qs = qs.filter(specialist_id=specialist_id)
            else:
                specialist_id = ''

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) |
            Q(user__phone_number__icontains=query)
        )

    now = timezone.localtime()
    today, current_time = now.date(), now.time()
    upcoming_q = Q(date__gt=today) | Q(date=today, time__gte=current_time)
    upcoming = list(qs.filter(upcoming_q).order_by('date', 'time'))
    past = list(qs.exclude(upcoming_q).order_by('-date', '-time'))

    return {
        'reservations': upcoming + past,
        'phase_choices': phase_choices,
        'selected_phase': selected_phase,
        'date_from': date_from,
        'date_to': date_to,
        'services': list(Service.objects.order_by('name')),
        'service_id': service_id,
        'specialist_id': specialist_id,
        'query': query,
    }


@login_required
def download_reservation_ics(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if reservation.user != request.user:
        raise PermissionDenied
    ics_content = build_reservation_ics(request, reservation)
    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="reservation-{reservation.pk}.ics"'
    return response


def _get_current_proofing_reservation(user):
    return (
        Reservation.objects.filter(user=user, need_client_review=True, gallery__isnull=False)
        .select_related('gallery', 'service', 'specialist')
        .order_by('-date', '-time')
        .first()
    )


def _get_owned_proofing_image(request, image_id):
    image = get_object_or_404(Image, pk=image_id)
    try:
        reservation = image.gallery.reservations
    except Reservation.DoesNotExist:
        raise Http404
    if reservation.user_id != request.user.id:
        raise Http404
    return image, reservation


PROOF_IMAGE_SALT = 'photo_proofing_image'
PROOF_IMAGE_MAX_AGE = 60 * 60 * 6  # 6 hours — one browsing session's worth


def _proof_image_token(image_id, user_id):
    return signing.dumps({'image_id': image_id, 'user_id': user_id}, salt=PROOF_IMAGE_SALT)


def _proof_derivative_path(image_id, user_id):
    digest = hashlib.sha256(f'{image_id}:{user_id}:{settings.SECRET_KEY}'.encode()).hexdigest()[:32]
    return f'proof_derivatives/{image_id}/{digest}.jpg'


def _generate_proof_derivative(image, user, watermark_identifier):
    path = _proof_derivative_path(image.pk, user.pk)
    if default_storage.exists(path):
        return path

    with image.image.open('rb') as source:
        original = PILImage.open(source).convert('RGB')
        original.load()

    original.thumbnail((1600, 1600), PILImage.LANCZOS)
    width, height = original.size

    layer = PILImage.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size=max(width // 40, 14))
    except OSError:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(layer)
    step_x, step_y = 320, 160
    for y in range(0, layer.height, step_y):
        for x in range(0, layer.width, step_x):
            draw.text((x, y), watermark_identifier, fill=(255, 255, 255, 90), font=font)
    layer = layer.rotate(-30, expand=False, resample=PILImage.BICUBIC)
    layer = layer.crop((width // 2, height // 2, width // 2 + width, height // 2 + height))

    watermarked = PILImage.alpha_composite(original.convert('RGBA'), layer).convert('RGB')
    buffer = BytesIO()
    watermarked.save(buffer, format='JPEG', quality=82)
    buffer.seek(0)
    default_storage.save(path, ContentFile(buffer.read()))
    return path


@login_required
def serve_proof_image(request, token):
    try:
        data = signing.loads(token, salt=PROOF_IMAGE_SALT, max_age=PROOF_IMAGE_MAX_AGE)
    except signing.BadSignature:
        raise PermissionDenied

    if data['user_id'] != request.user.id:
        raise PermissionDenied

    referer = request.META.get('HTTP_REFERER')
    if referer:
        referer_host = referer.split('//', 1)[-1].split('/', 1)[0].split(':', 1)[0].lower()
        if not validate_host(referer_host, settings.ALLOWED_HOSTS):
            raise PermissionDenied

    image, reservation = _get_owned_proofing_image(request, data['image_id'])
    watermark_identifier = f'{request.user.get_full_name() or request.user.phone_number} · #{reservation.pk}'
    path = _generate_proof_derivative(image, request.user, watermark_identifier)
    try:
        image_url = default_storage.url(path, expire=300)
    except TypeError:
        # The active storage backend (e.g. local FileSystemStorage in dev) doesn't
        # support signed/expiring URLs — fall back to its plain url().
        logger.warning('Storage backend does not support expiring URLs; serving a non-expiring URL for %s', path)
        image_url = default_storage.url(path)
    return redirect(image_url)


def _reject_if_finalized(reservation):
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът е финализиран.')}, status=403)
    return None


class PhotoProofingGallery(LoginRequiredMixin, TemplateView):
    template_name = 'pages/photo_proofing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        reservation = _get_current_proofing_reservation(user)

        if reservation:
            proofs = {
                p.image_id: p for p in
                ImageProof.objects.filter(image__gallery=reservation.gallery).prefetch_related('labels')
            }
            photos = []
            for img in reservation.gallery.images.all():
                proof = proofs.get(img.pk)
                photos.append({
                    'id': img.pk,
                    'url': reverse('photo_proofing_image', args=[_proof_image_token(img.pk, user.pk)]),
                    'alt': img.alt_text,
                    'is_marked': proof.is_marked if proof else False,
                    'comment': proof.comment if proof else '',
                    'label_keys': [label.pk for label in proof.labels.all()] if proof else [],
                })
            labels_config = [
                {'key': label.pk, 'name': label.name, 'cap': label.cap}
                for label in reservation.gallery.photo_labels.all()
            ]
            watermark_identifier = f'{user.get_full_name() or user.phone_number} · #{reservation.pk}'
        else:
            photos = []
            labels_config = []
            watermark_identifier = ''

        context['title'] = _('Проверка на снимки')
        context['reservation'] = reservation
        context['is_finalized'] = reservation.is_proofing_finalized if reservation else False
        context['photos'] = photos
        context['watermark_identifier'] = watermark_identifier
        context['labels_config'] = labels_config
        return context


@login_required
@require_POST
def mark_photo(request, image_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    blocked = _reject_if_finalized(reservation)
    if blocked:
        return blocked
    proof, _created = ImageProof.objects.get_or_create(image=image)
    proof.is_marked = not proof.is_marked
    proof.save(update_fields=['is_marked', 'updated_at'])
    return JsonResponse({'success': True, 'is_marked': proof.is_marked})


@login_required
@require_POST
def toggle_photo_label(request, image_id, label_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    blocked = _reject_if_finalized(reservation)
    if blocked:
        return blocked
    label = get_object_or_404(PhotoLabel, pk=label_id, gallery=reservation.gallery)
    proof, _created = ImageProof.objects.get_or_create(image=image)
    is_active = label in proof.labels.all()
    if not is_active:
        current_count = ImageProof.objects.filter(image__gallery=reservation.gallery, labels=label).count()
        if current_count >= label.cap:
            return JsonResponse({'success': False, 'error': _('Достигнат е максималният брой за този етикет.')}, status=400)
        proof.labels.add(label)
    else:
        proof.labels.remove(label)
    return JsonResponse({'success': True, 'is_active': not is_active})


@login_required
@require_POST
def save_photo_comment(request, image_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    blocked = _reject_if_finalized(reservation)
    if blocked:
        return blocked
    content = request.POST.get('content', '').strip()
    if len(content) > 2000:
        return JsonResponse({'success': False, 'error': _('Бележката не може да надвишава 2000 символа.')}, status=400)
    proof, _created = ImageProof.objects.get_or_create(image=image)
    proof.comment = content
    proof.save(update_fields=['comment', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def finalize_photo_proofing(request):
    reservation = _get_current_proofing_reservation(request.user)
    if not reservation:
        raise Http404
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът вече е финализиран.')}, status=403)
    marked_count = ImageProof.objects.filter(image__gallery=reservation.gallery, is_marked=True).count()
    if marked_count == 0:
        return JsonResponse({'success': False, 'error': _('Маркирайте поне една снимка.')}, status=400)
    reservation.finalize_proofing()
    if settings.IS_PHOTOGRAPHER_WEBSITE:
        send_marks_finalized_email(request, reservation)
    return JsonResponse({'success': True})


def _blocked_by_edit_window(request, reservation, error_message):
    """Ownership + 24-hour rule shared by edit/delete reservation views.
    Returns a redirect response if the change should be blocked, else None."""
    if reservation.user != request.user:
        raise PermissionDenied

    reservation_datetime = timezone.make_aware(datetime.combine(reservation.date, reservation.time))
    if reservation_datetime < timezone.now() + timedelta(hours=24):
        messages.error(request, error_message)
        return redirect('profile_page')
    return None

@booking_enabled_required
@login_required
def edit_reservation(request, pk: int):
    reservation = get_object_or_404(Reservation, pk=pk)

    blocked = _blocked_by_edit_window(
        request, reservation,
        _("Не можете да променяте резервация по-малко от 24 часа преди часа."),
    )
    if blocked:
        return blocked

    if request.method == 'POST':
        form = ReservationEditForm(request.POST, instance=reservation)

        if form.is_valid():
            form.save()
            return redirect('profile_page')
    else:
        form = ReservationEditForm(instance=reservation)

    context = {
        "form": form,
        "reservation": reservation,
    }

    return render(request, 'reservation/edit-reservation.html', context)

@booking_enabled_required
@login_required
def delete_reservation(request, pk: int):
    reservation = get_object_or_404(Reservation, pk=pk)

    blocked = _blocked_by_edit_window(
        request, reservation,
        _("Не можете да отменяте резервация по-малко от 24 часа преди часа."),
    )
    if blocked:
        return blocked

    form = ReservationDeleteForm(instance=reservation)

    if request.method == 'POST':
        reservation.change_status(Reservation.STATUS_DELETED, user=request.user)
        messages.success(request, _("Резервацията беше отменена успешно."))
        return redirect('profile_page')

    context = {
        "reservation": reservation,
        "form": form,
    }

    return render(request, 'reservation/delete-reservation.html', context)


class GalleryView(TemplateView):
    template_name = 'pages/gallery.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_photographer_website'] = settings.IS_PHOTOGRAPHER_WEBSITE
        ctx['albums'] = list(
            Gallery.objects.filter(gallery_type=Gallery.TYPE_ALBUM)
            .order_by('order').prefetch_related('images')
        )
        return ctx


class GalleryAlbumView(TemplateView):
    template_name = 'pages/gallery_album.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_photographer_website'] = settings.IS_PHOTOGRAPHER_WEBSITE
        album = get_object_or_404(Gallery, slug=kwargs['slug'], gallery_type=Gallery.TYPE_ALBUM)
        ctx['album'] = album
        ctx['photos'] = album.images.order_by('order')
        return ctx

