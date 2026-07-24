import random

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail

from massageProject.accounts.managers import AppUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField(
        verbose_name=_('email address'),
        max_length=255,
        unique=True,
        help_text=_('Enter a valid email address'),

    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^(\+359|0)?8[789]\d{7}$',
                message=_('Please correct valid phone number')
            )
        ],
    )

    date_of_birth = models.DateField(
        _("date of birth"),
        null=True,
        blank=True,
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this to disable an account, or to require the user to verify "
            "their email again."
        ),
    )

    date_joined = models.DateTimeField(default=timezone.now)

    objects = AppUserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    class Meta:
        verbose_name = _('Потребител')
        verbose_name_plural = _('Потребители')

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)


OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


class EmailOTPManager(models.Manager):
    def create_for_email(self, email, purpose):
        code = f"{random.randint(0, 999999):06d}"
        otp = self.create(
            email=email,
            code_hash=make_password(code),
            purpose=purpose,
            expires_at=timezone.now() + timezone.timedelta(minutes=OTP_EXPIRY_MINUTES),
        )
        return otp, code

    def live_for_email(self, email):
        return self.filter(
            email__iexact=email,
            consumed_at__isnull=True,
            attempts__lt=OTP_MAX_ATTEMPTS,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at')


class EmailOTP(models.Model):
    PURPOSE_SIGNUP = 'signup'
    PURPOSE_LOGIN = 'login'
    PURPOSE_CHOICES = [
        (PURPOSE_SIGNUP, _('Signup')),
        (PURPOSE_LOGIN, _('Login')),
    ]

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    objects = EmailOTPManager()

    def check_code(self, code):
        return check_password(code, self.code_hash)

    @classmethod
    def verify(cls, email, code):
        """
        Returns (otp, error). error is None on success, or 'no_code' /
        'invalid_code' on failure. On success the matched row is stamped
        consumed_at; on mismatch its attempts counter is incremented.
        """
        otp = cls.objects.live_for_email(email).first()
        if otp is None:
            return None, 'no_code'
        if otp.check_code(code):
            otp.consumed_at = timezone.now()
            otp.save(update_fields=['consumed_at'])
            return otp, None
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        return None, 'invalid_code'
