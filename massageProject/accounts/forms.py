from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


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