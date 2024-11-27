from django.shortcuts import render
from django.views.generic import TemplateView


# Create your views here.
class Index(TemplateView):
    template_name = 'pages/home.html'

class MassagesDashboard(TemplateView):
    template_name = 'pages/massages_page.html'