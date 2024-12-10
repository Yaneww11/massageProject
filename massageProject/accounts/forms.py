from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError


class CustomUserForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('phone_number', 'email')

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