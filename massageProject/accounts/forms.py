from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError


class CustomUserForm(UserCreationForm):
    error_messages = {
        "password_mismatch": ("Паролите не съвпадат."),
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

    def clean_username(self):
        """Reject usernames that differ only in case."""
        username = self.cleaned_data.get("phone_number")
        if (
            username
            and self._meta.model.objects.filter(phone_number__iexact=username).exists()
        ):
            self._update_errors(
                ValidationError(
                    {
                        "phone_number": self.instance.unique_error_message(
                            self._meta.model, ["phone_number"]
                        )
                    }
                )
            )
        else:
            return username