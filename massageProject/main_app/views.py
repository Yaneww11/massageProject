from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView

from massageProject.main_app.forms import ReservationCreateForm, ReservationEditForm, \
    ReservationDeleteForm, CommentForm
from massageProject.main_app.models import Massage, HomePage, Masseur, MessageStudio, MessageReservation, Comment


# Create your views here.
class Index(TemplateView):
    template_name = 'pages/home.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['page'] = HomePage.objects.first()
        context['massages'] = Massage.objects.filter(home_page=True)[:3]
        if context['page']:
            context['images'] = context['page'].gallery.images.all()
        return self.render_to_response(context)

class MassagesDashboard(ListView):
    model = Massage
    template_name = 'pages/massages_page.html'
    context_object_name = 'massages'

class ReservationPage(CreateView):
    model = MessageReservation
    template_name = 'pages/reservation.html'
    form_class = ReservationCreateForm
    success_url = reverse_lazy('profile_page')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'pk' in self.kwargs:
            massage_instance = Massage.objects.get(pk=self.kwargs['pk'])
            context['form'] = self.form_class(initial={'massage': massage_instance})
        return context

class AboutPage(TemplateView):
    template_name = 'pages/about.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['masseur'] = Masseur.objects.first()
        context['studio'] = MessageStudio.objects.values('description', 'main_image').first()
        context['comments'] = Comment.objects.all().order_by('-created_at')[:5]
        context['form'] = CommentForm()
        return self.render_to_response(context)


    def post(self, request, *args, **kwargs):
        form = CommentForm(request.POST)

        if form.is_valid():
            if form.cleaned_data:
                comment = form.save(commit=False)
                comment.author = self.request.user.get_full_name()
                form.save()

            return redirect('about_page')

        context = self.get_context_data()
        context['form'] = form

        return self.render_to_response(context)

class ProfilePage(TemplateView):
    template_name = 'pages/my_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reservations'] = MessageReservation.objects.filter(user=self.request.user).order_by('date', 'time')[:3]
        return context

class MassageDetail(TemplateView):
    template_name = 'pages/massage_detail.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['massage'] = Massage.objects.get(pk=kwargs['pk'])
        return self.render_to_response(context)

def edit_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)

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

def delete_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)
    form = ReservationDeleteForm(instance=reservation)

    if request.method == 'POST':
        reservation.delete()
        return redirect('profile_page')

    context = {
        "reservation": reservation,
        "form": form,
    }

    return render(request, 'reservation/delete-reservation.html', context)
