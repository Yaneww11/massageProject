from django import forms
from django.core.validators import RegexValidator

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import MessageReservation, Comment

_NAME_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-zА-Яа-яЁё\s\-]+$',
    message='Моля, въведете само букви (кирилица или латиница), интервали и тирета.',
)


class UserNameForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        min_length=2,
        label='Първо име',
        validators=[_NAME_VALIDATOR],
        error_messages={
            'required': 'Полето е задължително.',
            'min_length': 'Минималната дължина е %(limit_value)d символа.',
            'max_length': 'Максималната дължина е %(limit_value)d символа.',
        },
    )
    last_name = forms.CharField(
        max_length=50,
        min_length=2,
        label='Фамилия',
        validators=[_NAME_VALIDATOR],
        error_messages={
            'required': 'Полето е задължително.',
            'min_length': 'Минималната дължина е %(limit_value)d символа.',
            'max_length': 'Максималната дължина е %(limit_value)d символа.',
        },
    )


class ReservationBaseForm(forms.ModelForm):
    class Meta:
        model = MessageReservation
        fields = ['massage', 'masseur', 'date', 'time', 'additional_text']

        error_messages = {
            'massage': {
                'required': 'Тове поле е задължително',
            },
            'masseur': {
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
    disabled_fields = ['massage', 'masseur', 'date', 'time', 'additional_text']

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