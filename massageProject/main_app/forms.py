from django import forms

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import MessageReservation, Comment


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

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']

        labels = {
            'content': '',
        }

        error_messages = {
            'content': {
                'required': 'Въведете коментар',
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['content'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Твоя коментар',
        })