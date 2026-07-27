import base64
import hashlib
import logging
from io import BytesIO

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
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
from django.db.models import Count
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse, Http404
from PIL import Image as PILImage, ImageDraw, ImageFont

from massageProject.main_app.context_processors import get_cached_homepage
from massageProject.main_app.forms import ReservationCreateForm, ReservationEditForm, \
    ReservationDeleteForm, CommentForm, UserNameForm
from massageProject.main_app.mixins import BookingEnabledMixin, booking_enabled_required, \
    CommentsEnabledMixin, comments_enabled_required
from massageProject.main_app.models import Service, Specialist, Reservation, Comment, WorkingHours, ServiceGroup, \
    Gallery, SiteConfiguration, Image, ImageProof, PhotoLabel

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


def _time_to_minutes(t):
    return t.hour * 60 + t.minute


def _build_week_calendar(specialist, week_start):
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    working_hours_by_day = {
        wh.day_of_week: wh
        for wh in WorkingHours.objects.filter(specialist=specialist)
    }

    reservations = list(
        Reservation.objects.active()
        .filter(specialist=specialist, date__range=(week_days[0], week_days[-1]))
        .select_related('user')
        .order_by('time')
    )
    reservations_by_date = {}
    for r in reservations:
        reservations_by_date.setdefault(r.date, []).append(r)

    user_ids = {r.user_id for r in reservations}
    visit_counts = {}
    if user_ids:
        visit_counts = {
            row['user_id']: row['c']
            for row in Reservation.all_objects.filter(
                specialist=specialist, user_id__in=user_ids, status=Reservation.STATUS_COMPLETED,
            ).values('user_id').annotate(c=Count('id'))
        }

    if working_hours_by_day:
        window_start = min(_time_to_minutes(wh.start_time) for wh in working_hours_by_day.values())
        window_end = max(_time_to_minutes(wh.end_time) for wh in working_hours_by_day.values())
    else:
        window_start, window_end = 8 * 60, 20 * 60
    window_span = (window_end - window_start) or 1

    days = []
    for day_date in week_days:
        wh = working_hours_by_day.get(day_date.weekday())
        day_entries = []
        for r in reservations_by_date.get(day_date, []):
            start_minutes = _time_to_minutes(r.time)
            end_minutes = _time_to_minutes(r.end_time)
            day_entries.append({
                'reservation': r,
                'top_pct': round(min(100.0, max(0.0, (start_minutes - window_start) / window_span * 100)), 2),
                'height_pct': round(min(100.0, max(0.0, (end_minutes - start_minutes) / window_span * 100)), 2),
                'visit_count': visit_counts.get(r.user_id, 0),
            })
        days.append({'date': day_date, 'working_hours': wh, 'reservations': day_entries})

    hour_marks = []
    first_hour = window_start // 60
    last_hour = -(-window_end // 60)
    for h in range(first_hour, last_hour + 1):
        minute = h * 60
        if minute < window_start or minute > window_end:
            continue
        hour_marks.append({
            'label': '%02d:00' % h,
            'top_pct': round((minute - window_start) / window_span * 100, 2),
        })

    return {'days': days, 'hour_marks': hour_marks}


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
            specialists = list(Specialist.objects.order_by('name'))
            context['specialists'] = specialists
            selected_id = self.request.GET.get('specialist_id')
            selected = None
            if selected_id:
                selected = next((s for s in specialists if str(s.pk) == selected_id), None)
            if selected is None and specialists:
                selected = specialists[0]
            self._add_calendar_context(context, selected)
        elif specialist_link and user.has_perm('main_app.view_specialist_reservations'):
            context['role'] = 'specialist'
            # _("график") is nested in an f-string; makemessages can't extract it — the .po/.mo entries for it are maintained by hand.
            context['title'] = f'{user.get_full_name()} - {_("график")}'
            self._add_calendar_context(context, specialist_link)
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

    def _add_calendar_context(self, context, specialist):
        today = date.today()
        context['today'] = today

        week_param = self.request.GET.get('week')
        requested = today
        if week_param:
            try:
                requested = datetime.strptime(week_param, '%Y-%m-%d').date()
            except ValueError:
                requested = today
        week_start = requested - timedelta(days=requested.weekday())

        context['calendar_specialist'] = specialist
        context['week_start'] = week_start
        context['prev_week'] = week_start - timedelta(days=7)
        context['next_week'] = week_start + timedelta(days=7)

        if specialist is None:
            context['calendar'] = None
            context['bookings_today'] = 0
            context['bookings_this_week'] = 0
            context['next_client_reservation'] = None
            return

        context['calendar'] = _build_week_calendar(specialist, week_start)

        week_end = week_start + timedelta(days=6)
        context['week_end'] = week_end
        week_reservations = Reservation.objects.active().filter(
            specialist=specialist, date__range=(week_start, week_end),
        )
        context['bookings_this_week'] = week_reservations.count()

        today_and_future = Reservation.objects.active().filter(specialist=specialist, date__gte=today)
        context['bookings_today'] = today_and_future.filter(date=today).count()
        context['next_client_reservation'] = today_and_future.order_by('date', 'time').first()


def _get_current_proofing_reservation(user):
    return (
        Reservation.objects.filter(user=user, gallery__isnull=False)
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


# Placeholder photos shown only when the signed-in user has no reservation
# with an attached gallery yet (the admin-side gallery workflow is new and
# most existing reservations predate it). Generated as gradients from the
# live SiteConfiguration palette so the demo never depends on stray media
# files and always matches the current theme. Remove once real galleries
# are the norm.
def _demo_proofing_photos(site_config):
    palette = [
        site_config.primary_color, site_config.primary_light_color,
        site_config.secondary_color, site_config.accent_color,
    ]
    photos = []
    for i in range(10):
        color_start, color_end = palette[i % len(palette)], palette[(i + 1) % len(palette)]
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="600">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{color_start}"/>'
            f'<stop offset="1" stop-color="{color_end}"/>'
            '</linearGradient></defs>'
            '<rect width="480" height="600" fill="url(#g)"/></svg>'
        )
        data_url = 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode('utf-8')).decode('ascii')
        photos.append({'id': f'demo-{i + 1}', 'url': data_url, 'alt': _('Примерна снимка от сесия')})
    return photos


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
                    'url': img.image.url,
                    'alt': img.alt_text,
                    'is_marked': proof.is_marked if proof else False,
                    'comment': proof.comment if proof else '',
                    'label_keys': [label.pk for label in proof.labels.all()] if proof else [],
                })
            is_demo = False
            labels_config = [
                {'key': label.pk, 'name': label.name, 'cap': label.cap}
                for label in reservation.gallery.photo_labels.all()
            ]
        else:
            photos = _demo_proofing_photos(SiteConfiguration.get_solo())
            is_demo = True
            labels_config = [
                {'key': 'print', 'name': _('За печат'), 'cap': 5},
                {'key': 'album', 'name': _('Албум'), 'cap': 10},
                {'key': 'social', 'name': _('Социални мрежи'), 'cap': 3},
            ]

        context['title'] = _('Проверка на снимки')
        context['reservation'] = reservation
        context['is_demo'] = is_demo
        context['is_finalized'] = reservation.is_proofing_finalized if reservation else False
        context['photos'] = photos
        session_tag = f'#{reservation.pk}' if reservation else _('ДЕМО ПРЕГЛЕД')
        context['watermark_identifier'] = f'{user.get_full_name() or user.phone_number} · {session_tag}'
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
    reservation.finalize_proofing(request.user)
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
        ctx['albums'] = list(
            Gallery.objects.filter(gallery_type=Gallery.TYPE_ALBUM)
            .order_by('order').prefetch_related('images')
        )
        return ctx


class GalleryAlbumView(TemplateView):
    template_name = 'pages/gallery_album.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        album = get_object_or_404(Gallery, slug=kwargs['slug'], gallery_type=Gallery.TYPE_ALBUM)
        ctx['album'] = album
        ctx['photos'] = album.images.order_by('order')
        return ctx

