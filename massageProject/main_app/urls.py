from django.urls import path, include

from massageProject.main_app.views import Index

urlpatterns = [
    path('', Index.as_view(), name='index'),
]