from allauth.socialaccount.forms import SignupForm as SocialSignupFormBase
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _


class CustomAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'inactive': _(
            "Моля, потвърдете имейла си, преди да влезете. Проверете пощата си "
            "за линк за потвърждение, или поискайте нов по-долу."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Имейл')
        self.fields['username'].widget.attrs.update({
            'placeholder': 'example@email.com',
            'autocomplete': 'email',
        })


class PhoneClaimFormMixin:
    """
    If a phone number already belongs to a passwordless (e.g. staff-created)
    user record, attach that record as self.instance so saving the form
    updates/"claims" it instead of failing the uniqueness check.
    """
    error_messages = {
        'already_registered': _('Този телефонен номер вече е регистриран. Моля, влезте в профила си.'),
    }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            return phone_number

        User = get_user_model()
        normalized_phone = User.objects.normalize_phone_number(phone_number)

        try:
            # Locked here and held through the caller's save() (both run
            # inside one transaction.atomic() block) so a concurrent claim
            # of the same passwordless record can't race this one.
            existing_user = User.objects.select_for_update().get(phone_number__iexact=normalized_phone)
            if existing_user.has_usable_password():
                raise ValidationError(self.error_messages['already_registered'])
            self.instance = existing_user
        except User.DoesNotExist:
            pass

        return normalized_phone


class BookingRegistrationForm(PhoneClaimFormMixin, forms.ModelForm):
    password = forms.CharField(
        label=_('Парола'),
        strip=False,
        widget=forms.PasswordInput,
    )
    middle_name = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'phone_number', 'date_of_birth')

    def __init__(self, *args, email=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._email = email
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['date_of_birth'].required = False
        self.fields['phone_number'].widget.attrs.update({'placeholder': '0899999999'})
        for field in self.fields.values():
            field.help_text = None

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password, self.instance)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if not self._email:
            raise ValidationError(_('Имейлът не е потвърден.'))
        return cleaned_data

    def save(self, commit=True):
        # The claimed/new instance may not have had its email set yet, or may
        # have had a placeholder one -- the verified session email always wins.
        user = super().save(commit=False)
        user.email = self._email
        user.is_active = True
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class SocialCompleteProfileForm(SocialSignupFormBase):
    """Complete-profile step shown to first-time Google users: Google supplies
    a verified email and names, but reservations need a phone number."""

    first_name = forms.CharField(label=_('Име'), max_length=50)
    last_name = forms.CharField(label=_('Фамилия'), max_length=50)
    phone_number = forms.CharField(
        label=_('Телефон'),
        max_length=15,
        validators=get_user_model()._meta.get_field('phone_number').validators,
        widget=forms.TextInput(attrs={'placeholder': '0899999999'}),
    )
    date_of_birth = forms.DateField(
        label=_('Дата на раждане (незадължително)'),
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._claimed_user = None
        # The email comes verified from Google and must not be edited.
        if 'email' in self.fields:
            self.fields['email'].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'auth-modal-input')

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        User = get_user_model()
        normalized = User.objects.normalize_phone_number(phone_number)
        try:
            existing_user = User.objects.get(phone_number__iexact=normalized)
        except User.DoesNotExist:
            pass
        else:
            if existing_user.has_usable_password():
                raise ValidationError(
                    PhoneClaimFormMixin.error_messages['already_registered']
                )
            self._claimed_user = existing_user
        return normalized

    def save(self, request):
        if self._claimed_user is not None:
            # A passwordless (staff-created) record owns this phone number:
            # claim it instead of creating a duplicate. The verified Google
            # email wins, mirroring BookingRegistrationForm.save().
            with transaction.atomic():
                # Re-fetch and lock, then re-check has_usable_password():
                # clean_phone_number() ran this same check earlier but
                # unlocked, so a concurrent claim could have set a password
                # in between. Failing loudly here beats silently
                # overwriting that user's data.
                User = get_user_model()
                user = User.objects.select_for_update().get(pk=self._claimed_user.pk)
                if user.has_usable_password():
                    raise ValidationError(PhoneClaimFormMixin.error_messages['already_registered'])
                user.first_name = self.cleaned_data['first_name']
                user.last_name = self.cleaned_data['last_name']
                user.phone_number = self.cleaned_data['phone_number']
                if self.cleaned_data.get('date_of_birth'):
                    user.date_of_birth = self.cleaned_data['date_of_birth']
                user.email = self.sociallogin.user.email or user.email
                user.is_active = True
                user.save()
            self.sociallogin.connect(request, user)
            return user

        # Set the extra fields on the pending user BEFORE the allauth adapter
        # saves it, so the row never exists without a phone number. The
        # adapter copies first/last name and email from cleaned_data itself.
        self.sociallogin.user.phone_number = self.cleaned_data['phone_number']
        self.sociallogin.user.date_of_birth = self.cleaned_data.get('date_of_birth')
        return super().save(request)