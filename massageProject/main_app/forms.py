from django import forms

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import MessageReservation


class ReservationBaseForm(forms.ModelForm):
    class Meta:
        model = MessageReservation
        fields = ['massage','date', 'time', 'additional_text']

        error_messages = {
            'massage': {
                'required': 'Тове поле е задължително',
            },
            'date': {
                'required': 'Тове поле е задължително',
            },
            'time': {
                'required': 'Тове поле е задължително',
            }
        }

class ReservationCreateForm(ReservationBaseForm):
    pass

class ReservationEditForm(ReservationBaseForm):
    pass

class ReservationDeleteForm(ReservationBaseForm, DisableFieldMixin):
    disabled_fields = ['massage','date', 'time', 'additional_text']