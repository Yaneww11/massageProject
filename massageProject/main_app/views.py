from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib import messages


# Create your views here.
class Index(TemplateView):
    template_name = 'pages/home.html'

class MassagesDashboard(TemplateView):
    template_name = 'pages/massages_page.html'

class ReservationPage(TemplateView):
    template_name = 'pages/reservation.html'

class AboutPage(TemplateView):
    template_name = 'pages/about.html'

class ProfilePage(TemplateView):
    template_name = 'pages/my_profile.html'
