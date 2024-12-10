from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView


from massageProject.main_app.models import Massage, HomePage, Masseur, MessageStudio


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


class ReservationPage(TemplateView):
    template_name = 'pages/reservation.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if 'pk' in kwargs:
            context['massage'] = Massage.objects.get(pk=kwargs['pk'])
        else:
            context['massage'] = None
        return self.render_to_response(context)

class AboutPage(TemplateView):
    template_name = 'pages/about.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['masseur'] = Masseur.objects.first()
        context['studio'] = MessageStudio.objects.values('description', 'main_image').first()
        return self.render_to_response(context)

class ProfilePage(TemplateView):
    template_name = 'pages/my_profile.html'

class MassageDetail(TemplateView):
    template_name = 'pages/massage_detail.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context['massage'] = Massage.objects.get(pk=kwargs['pk'])
        return self.render_to_response(context)
