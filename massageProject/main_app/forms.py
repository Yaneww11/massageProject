import zipfile
from datetime import datetime, time, timedelta

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from massageProject.main_app.mixins import DisableFieldMixin
from massageProject.main_app.models import Reservation, Comment, Specialist, TimeOff


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


TIME_OFF_TIME_CHOICES = [('', '—')] + [
    (f'{h:02d}:{m:02d}', f'{h:02d}:{m:02d}') for h in range(24) for m in (0, 30)
]


class TimeOffForm(forms.ModelForm):
    """Dates + optional 30-minute times, turned into the model's start/end.
    Pass `specialist` to fix the entry to that Specialist (specialist role);
    without it the form offers a Specialist dropdown (staff role)."""
    start_date = forms.DateField(label=_('От дата'), widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label=_('До дата'), widget=forms.DateInput(attrs={'type': 'date'}))
    all_day = forms.BooleanField(label=_('Цели дни'), required=False)
    start_time = forms.ChoiceField(label=_('От час'), choices=TIME_OFF_TIME_CHOICES, required=False)
    end_time = forms.ChoiceField(label=_('До час'), choices=TIME_OFF_TIME_CHOICES, required=False)

    class Meta:
        model = TimeOff
        fields = ['specialist', 'note']
        labels = {'note': _('Бележка (по избор)')}

    def __init__(self, *args, specialist=None, **kwargs):
        super().__init__(*args, **kwargs)
        if specialist is not None:
            del self.fields['specialist']
            self.instance.specialist = specialist
        else:
            self.fields['specialist'].queryset = Specialist.objects.order_by('name')
        for field in self.fields.values():
            field.error_messages['required'] = _('Полето е задължително.')
            if not isinstance(field, forms.BooleanField):
                field.widget.attrs.setdefault('class', 'form-textarea')

    def clean(self):
        cleaned = super().clean()
        start_date, end_date = cleaned.get('start_date'), cleaned.get('end_date')
        if not (start_date and end_date):
            return cleaned
        if cleaned.get('all_day'):
            start = datetime.combine(start_date, time.min)
            end = datetime.combine(end_date + timedelta(days=1), time.min)
        else:
            start_time, end_time = cleaned.get('start_time'), cleaned.get('end_time')
            if not (start_time and end_time):
                raise ValidationError(_('Изберете начален и краен час или отметнете „Цели дни“.'))
            start = datetime.combine(start_date, datetime.strptime(start_time, '%H:%M').time())
            end = datetime.combine(end_date, datetime.strptime(end_time, '%H:%M').time())
        self.instance.start = timezone.make_aware(start)
        self.instance.end = timezone.make_aware(end)
        return cleaned


class ProofingGalleryUploadForm(forms.Form):
    reservation = forms.ModelChoiceField(queryset=Reservation.objects.none(), label=_('Резервация'))
    images = MultipleFileField(label=_('Снимки'))

    def __init__(self, *args, reservation_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if reservation_queryset is not None:
            self.fields['reservation'].queryset = reservation_queryset
        self.fields['reservation'].label_from_instance = lambda r: (
            f"{r.specialist.name} — {r.date} {r.time.strftime('%H:%M')} — {r.service.name} — "
            f"{r.user.get_full_name() or r.user.phone_number or r.user.email}"
        )
        self.fields['reservation'].widget.attrs.update({'class': 'form-textarea'})
        self.fields['images'].widget.attrs.update({'class': 'form-textarea'})


class ProofingLabelForm(forms.Form):
    name = forms.CharField(
        max_length=100, required=False, label=_('Етикет'),
        widget=forms.TextInput(attrs={'class': 'form-textarea'}),
    )

ProofingLabelFormSet = forms.formset_factory(ProofingLabelForm, extra=3)


FINAL_IMAGE_EXTENSIONS = frozenset({
    'jpg', 'jpeg', 'png', 'tif', 'tiff', 'webp', 'heic', 'dng',
    'cr2', 'cr3', 'nef', 'arw', 'orf', 'rw2', 'raf', 'srw', 'pef',
})


def _is_zip_junk(name):
    parts = name.split('/')
    return name.endswith('/') or parts[0] == '__MACOSX' or parts[-1] == '.DS_Store'


def validate_finals_zip(zip_file):
    """Raises ValidationError unless the upload is a sound ZIP holding only
    images. Leaves the file rewound for the caller."""
    try:
        with zipfile.ZipFile(zip_file) as archive:
            if archive.testzip() is not None:
                raise ValidationError(_('ZIP архивът е повреден. Създайте го отново и опитайте пак.'))
            names = [n for n in archive.namelist() if not _is_zip_junk(n)]
    except zipfile.BadZipFile:
        raise ValidationError(_('Файлът не е валиден ZIP архив.'))
    finally:
        zip_file.seek(0)
    if not names:
        raise ValidationError(_('ZIP архивът не съдържа файлове.'))
    not_images = [n for n in names if n.rsplit('.', 1)[-1].lower() not in FINAL_IMAGE_EXTENSIONS or '.' not in n]
    if not_images:
        raise ValidationError(
            _('ZIP архивът трябва да съдържа само снимки. Недопустим файл: %(name)s'),
            params={'name': not_images[0]},
        )


class FinalZipUploadForm(forms.Form):
    reservation = forms.ModelChoiceField(queryset=Reservation.objects.none(), label=_('Резервация'))
    zip_file = forms.FileField(label=_('ZIP архив с финалните снимки'))

    def __init__(self, *args, reservation_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if reservation_queryset is not None:
            self.fields['reservation'].queryset = reservation_queryset
        self.fields['reservation'].label_from_instance = lambda r: (
            f"{r.specialist.name} — {r.date} {r.time.strftime('%H:%M')} — {r.service.name} — "
            f"{r.user.get_full_name() or r.user.phone_number or r.user.email}"
        )
        self.fields['reservation'].widget.attrs.update({'class': 'form-textarea'})
        self.fields['zip_file'].widget.attrs.update({
            'class': 'form-textarea', 'accept': '.zip,application/zip',
            'data-max-bytes': settings.FINAL_ZIP_MAX_MB * 1024 * 1024,
        })
        self.fields['zip_file'].help_text = _(
            'Най-много %(max)d MB. Архивирайте обработените файлове в ZIP, без да ги конвертирате.'
        ) % {'max': settings.FINAL_ZIP_MAX_MB}

    def clean_zip_file(self):
        zip_file = self.cleaned_data['zip_file']
        if zip_file.size > settings.FINAL_ZIP_MAX_MB * 1024 * 1024:
            raise ValidationError(
                _('Файлът е твърде голям. Максимумът е %(max)d MB.'), params={'max': settings.FINAL_ZIP_MAX_MB},
            )
        validate_finals_zip(zip_file)
        return zip_file
