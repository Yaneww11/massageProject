from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class VerificationAwareBackend(ModelBackend):
    """
    Lets is_active=False users authenticate() (so confirm_login_allowed can
    surface the "please verify your email" message), but leaves get_user()
    and user_can_authenticate() untouched, so deactivating an account still
    invalidates that user's existing sessions on their next request.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user.
            UserModel().set_password(password)
        else:
            if user.check_password(password):
                return user
