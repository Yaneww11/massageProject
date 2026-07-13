from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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


class CustomUserForm(UserCreationForm):
    error_messages = {
        "password_mismatch": _("Паролите не съвпадат."),
        "already_registered": _("Този телефонен номер вече е регистриран. Моля, влезте в профила си."),
    }
    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'phone_number', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        
        # Iterate over all fields and remove the help_text
        for field_name, field in self.fields.items():
            field.help_text = None

            if field_name == 'phone_number':
                field.widget.attrs.update({
                    'placeholder': '0899999999'
                })

    def clean_phone_number(self):
        """
        Check if a user with this phone number already exists.
        If the user exists and has a password, reject with a custom message.
        If the user exists but has NO password, attach that user instance to this form
        so it can be "claimed" and updated.
        """
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            return phone_number

        User = get_user_model()
        # Normalize phone number before checking
        normalized_phone = User.objects.normalize_phone_number(phone_number)
        
        try:
            existing_user = User.objects.get(phone_number__iexact=normalized_phone)
            if existing_user.has_usable_password():
                raise ValidationError(self.error_messages["already_registered"])
            else:
                # Set the existing user as the instance for this form.
                # This allows ModelForm to update the existing record instead of creating a new one,
                # and it bypasses the unique constraint validation for this specific record.
                self.instance = existing_user
        except User.DoesNotExist:
            pass

        return normalized_phone


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label=_('Имейл'))


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
            existing_user = User.objects.get(phone_number__iexact=normalized_phone)
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