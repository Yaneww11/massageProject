from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import datetime, timedelta, time
from django.contrib import messages
from django.http import JsonResponse
import json

from massageProject.main_app.forms import ReservationCreateForm, ReservationEditForm, \
    ReservationDeleteForm, CommentForm, UserNameForm
from massageProject.main_app.models import Massage, HomePage, Masseur, MessageStudio, MessageReservation, Comment, WorkingHours


def check_availability(request):
    masseur_id = request.GET.get('masseur_id')
    date_str = request.GET.get('date')
    massage_id = request.GET.get('massage_id')

    if not all([masseur_id, date_str, massage_id]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        massage = Massage.objects.get(pk=massage_id)
        masseur = Masseur.objects.get(pk=masseur_id)
    except (ValueError, Massage.DoesNotExist, Masseur.DoesNotExist):
        return JsonResponse({'error': 'Invalid parameters'}, status=400)

    # 1. Get working hours for the day
    day_of_week = date_obj.weekday()
    working_hours = WorkingHours.objects.filter(masseur=masseur, day_of_week=day_of_week).first()

    if not working_hours:
        return JsonResponse({'slots': []})  # Not working

    # 2. Generate 30-min slots
    slots = []
    current_dt = datetime.combine(date_obj, working_hours.start_time)
    end_dt = datetime.combine(date_obj, working_hours.end_time)
    
    # Lead time check (2 hours)
    min_time = timezone.localtime(timezone.now()) + timedelta(hours=2)

    duration = timedelta(minutes=massage.duration_in_minutes)

    # 3. Get existing reservations for overlap check
    existing_reservations = MessageReservation.objects.filter(
        masseur=masseur,
        date=date_obj,
        status=MessageReservation.STATUS_ACTIVE
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
                res_end = res_start + timedelta(minutes=res.massage.duration_in_minutes)
                
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
        context['page'] = HomePage.objects.first()
        context['massages'] = Massage.objects.filter(home_page=True)[:3]
        if context['page']:
            context['images'] = context['page'].gallery.images.all()
        context['comments'] = Comment.objects.filter(is_reviewed=True).order_by('-created_at')[:3]
        return self.render_to_response(context)

class PrivacyPolicyView(TemplateView):
    template_name = 'pages/privacy_policy.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = HomePage.objects.first()
        return context

class MassagesDashboard(ListView):
    model = Massage
    template_name = 'pages/massages_page.html'
    context_object_name = 'massages'

class ReservationPage(LoginRequiredMixin, CreateView):
    model = MessageReservation
    template_name = 'pages/reservation.html'
    form_class = ReservationCreateForm
    success_url = reverse_lazy('profile_page')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not (user.first_name and user.last_name) and 'name_form' not in context:
            context['name_form'] = UserNameForm()
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

        extra = {'form': form}
        if name_form is not None:
            extra['name_form'] = name_form
        return self.render_to_response(self.get_context_data(**extra))

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        if 'pk' in self.kwargs:
            initial['massage'] = self.kwargs['pk']
        return initial

class AboutPage(TemplateView):
    template_name = 'pages/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['masseur'] = Masseur.objects.first()
        context['studio'] = MessageStudio.objects.values('description', 'main_image').first()
        context['comments'] = Comment.objects.filter(is_reviewed=True).order_by('-created_at')[:15]
        context['total_comments_count'] = Comment.objects.filter(is_reviewed=True).count()
        if 'form' not in context:
            context['form'] = CommentForm()
        
        user = self.request.user
        if user.is_authenticated and not (user.first_name and user.last_name) and 'name_form' not in context:
            context['name_form'] = UserNameForm()
        return context

    def post(self, request, *args, **kwargs):
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

class AllCommentsView(ListView):
    model = Comment
    template_name = 'pages/all_comments.html'
    context_object_name = 'comments'
    paginate_by = 15

    def get_queryset(self):
        return Comment.objects.filter(is_reviewed=True).order_by('-created_at')

class ProfilePage(LoginRequiredMixin, TemplateView):
    template_name = 'pages/my_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.has_perm('main_app.view_all_reservations'):
            context['active_reservations'] = MessageReservation.objects.active().order_by('date', 'time')[:15]
            context['past_reservations'] = MessageReservation.objects.past().order_by('-date', '-time')[:15]
            context['title'] = _('Управление на резервации')
        else:
            user_reservations = MessageReservation.objects.filter(user=self.request.user)
            context['active_reservations'] = user_reservations.active().order_by('date', 'time')
            context['past_reservations'] = user_reservations.past().order_by('-date', '-time')[:5]
            context['title'] = f'{user.get_full_name()} - {_("резервации")}'
        return context

class MassageDetail(TemplateView):
    template_name = 'pages/massage_detail.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['massage'] = Massage.objects.get(pk=kwargs['pk'])
        return self.render_to_response(context)

@login_required
def edit_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)

    # Ownership check
    if reservation.user != request.user:
        raise PermissionDenied

    # 24-hour rule
    reservation_datetime = timezone.make_aware(datetime.combine(reservation.date, reservation.time))
    if reservation_datetime < timezone.now() + timedelta(hours=24):
        messages.error(request, _("Не можете да променяте резервация по-малко от 24 часа преди часа."))
        return redirect('profile_page')

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

@login_required
def delete_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)

    # Ownership check
    if reservation.user != request.user:
        raise PermissionDenied

    # 24-hour rule
    reservation_datetime = timezone.make_aware(datetime.combine(reservation.date, reservation.time))
    if reservation_datetime < timezone.now() + timedelta(hours=24):
        messages.error(request, _("Не можете да отменяте резервация по-малко от 24 часа преди часа."))
        return redirect('profile_page')

    form = ReservationDeleteForm(instance=reservation)

    if request.method == 'POST':
        reservation.change_status(MessageReservation.STATUS_DELETED, user=request.user)
        messages.success(request, _("Резервацията беше отменена успешно."))
        return redirect('profile_page')

    context = {
        "reservation": reservation,
        "form": form,
    }

    return render(request, 'reservation/delete-reservation.html', context)
