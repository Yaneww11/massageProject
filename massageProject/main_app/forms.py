from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import Reservation, Comment


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """FileField that accepts and cleans a list of files (Django's
    documented recipe for native multi-file <input> support — Django has no
    built-in multi-file form field)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        if self.required and not result:
            raise ValidationError(self.error_messages['required'], code='required')
        return result

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
        model = Reservation
        fields = ['service', 'specialist', 'date', 'time', 'additional_text']

        error_messages = {
            'service': {
                'required': _('Тове поле е задължително'),
            },
            'specialist': {
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
    disabled_fields = ['service', 'specialist', 'date', 'time', 'additional_text']

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


class ProofingGalleryUploadForm(forms.Form):
    reservation = forms.ModelChoiceField(queryset=Reservation.objects.none(), label=_('Резервация'))
    images = MultipleFileField(label=_('Снимки'))

    def __init__(self, *args, reservation_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if reservation_queryset is not None:
            self.fields['reservation'].queryset = reservation_queryset
        self.fields['reservation'].label_from_instance = lambda r: (
            f"{r.specialist.name} — {r.date} {r.time.strftime('%H:%M')} — {r.service.name} — "
            f"{r.user.get_full_name() or r.user.phone_number}"
        )
        self.fields['reservation'].widget.attrs.update({'class': 'form-textarea'})
        self.fields['images'].widget.attrs.update({'class': 'form-textarea'})


class FinalGalleryUploadForm(ProofingGalleryUploadForm):
    """Same reservation + images shape as ProofingGalleryUploadForm — the
    view scopes `reservation_queryset` to reservations awaiting a Final
    Gallery instead of a Proofing Gallery."""
    pass


class ProofingLabelForm(forms.Form):
    name = forms.CharField(
        max_length=100, required=False, label=_('Етикет'),
        widget=forms.TextInput(attrs={'class': 'form-textarea'}),
    )
    cap = forms.IntegerField(
        required=False, validators=[MinValueValidator(1)], label=_('Максимален брой'),
        widget=forms.NumberInput(attrs={'class': 'form-textarea'}),
    )

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name')
        cap = cleaned.get('cap')
        if name and not cap:
            raise ValidationError(
                _('Въведете максимален брой за етикета "%(name)s".') % {'name': name}
            )
        if cap and not name:
            raise ValidationError(_('Въведете име за етикета.'))
        return cleaned


ProofingLabelFormSet = forms.formset_factory(ProofingLabelForm, extra=3)