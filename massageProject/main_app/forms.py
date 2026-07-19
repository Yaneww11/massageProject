from django import forms
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import MessageReservation, Comment

_NAME_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-zА-Яа-яЁё\s\-]+$',
    message=_('Моля, въведете само букви (кирилица или латиница), интервали и тирета.'),
)


class UserNameForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        min_length=2,
        label=_('Първо име'),
        validators=[_NAME_VALIDATOR],
        error_messages={
            'required': _('Полето е задължително.'),
            'min_length': _('Минималната дължина е %(limit_value)d символа.'),
            'max_length': _('Максималната дължина е %(limit_value)d символа.'),
        },
    )
    last_name = forms.CharField(
        max_length=50,
        min_length=2,
        label=_('Фамилия'),
        validators=[_NAME_VALIDATOR],
        error_messages={
            'required': _('Полето е задължително.'),
            'min_length': _('Минималната дължина е %(limit_value)d символа.'),
            'max_length': _('Максималната дължина е %(limit_value)d символа.'),
        },
    )


class ReservationBaseForm(forms.ModelForm):
    class Meta:
        model = MessageReservation
        fields = ['service', 'masseur', 'date', 'time', 'additional_text']

        error_messages = {
            'service': {
                'required': _('Тове поле е задължително'),
            },
            'masseur': {
                'required': _('Тове поле е задължително'),
            },
            'date': {
                'required': _('Тове поле е задължително'),
            },
            'time': {
                'required': _('Тове поле е задължително'),
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].label_from_instance = lambda obj: f"{obj.name} ({obj.duration_in_minutes} {_('мин')})"

class ReservationCreateForm(ReservationBaseForm):
    pass

class ReservationEditForm(ReservationBaseForm):
    pass

class ReservationDeleteForm(ReservationBaseForm, DisableFieldMixin):
    disabled_fields = ['service', 'masseur', 'date', 'time', 'additional_text']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']

        labels = {
            'content': '',
        }

        error_messages = {
            'content': {
                'required': _('Въведете коментар'),
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['content'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _('Твоя коментар'),
        })