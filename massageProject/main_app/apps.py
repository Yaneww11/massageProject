from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'massageProject.main_app'
    verbose_name = _('Основни данни')
