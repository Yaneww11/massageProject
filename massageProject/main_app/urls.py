from django.urls import path, include

from massageProject.main_app.views import Index, MassagesDashboard

urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('massages/', MassagesDashboard.as_view(), name='massages_dashboard'),
]