from functools import wraps

from django import forms
from django.http import Http404

class DisableFieldMixin(forms.Form):
    disabled_fields = ()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if self.disabled_fields[0] == '__all__' or field_name in self.disabled_fields:
                field.disabled = True


class BookingEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().booking_enabled:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def booking_enabled_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().booking_enabled:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper