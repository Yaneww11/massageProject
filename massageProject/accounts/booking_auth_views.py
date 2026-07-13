from datetime import datetime

from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from massageProject.accounts.emails import send_otp_email
from massageProject.accounts.forms import BookingRegistrationForm, CustomAuthenticationForm
from massageProject.accounts.models import EmailOTP
from massageProject.accounts.turnstile import verify_turnstile_token

User = get_user_model()

SIGNUP_EMAIL_SESSION_KEY = 'verified_signup_email'
SIGNUP_EMAIL_SESSION_TTL_SECONDS = 15 * 60


@require_POST
def check_email(request):
    email = request.POST.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'error': _('Въведете имейл адрес.')}, status=400)
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'success': True, 'exists': exists})


@require_POST
@ratelimit(key='ip', rate='5/m', block=False)
@ratelimit(key='post:email', rate='3/m', block=False)
def send_code(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    email = request.POST.get('email', '').strip().lower()
    turnstile_token = request.POST.get('turnstile_token', '')

    if not email:
        return JsonResponse({'success': False, 'error': _('Въведете имейл адрес.')}, status=400)

    if not verify_turnstile_token(turnstile_token, remote_ip=request.META.get('REMOTE_ADDR')):
        return JsonResponse({'success': False, 'error': _('Проверката за робот не е успешна. Опитайте отново.')}, status=400)

    purpose = EmailOTP.PURPOSE_LOGIN if User.objects.filter(email__iexact=email).exists() else EmailOTP.PURPOSE_SIGNUP
    otp, code = EmailOTP.objects.create_for_email(email, purpose)
    send_otp_email(request, email, code)

    return JsonResponse({'success': True})


@require_POST
@ratelimit(key='ip', rate='10/m', block=False)
@ratelimit(key='post:email', rate='8/m', block=False)
def verify_code(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    email = request.POST.get('email', '').strip().lower()
    code = request.POST.get('code', '').strip()
    next_url = request.POST.get('next') or reverse('reservation_page')

    if not email or not code:
        return JsonResponse({'success': False, 'error': _('Въведете имейл и код.')}, status=400)

    otp, error = EmailOTP.verify(email, code)
    if error:
        message = (
            _('Кодът е грешен или е изтекъл.') if error == 'invalid_code'
            else _('Няма активен код за този имейл. Изпратете нов.')
        )
        return JsonResponse({'success': False, 'error': str(message)}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        request.session[SIGNUP_EMAIL_SESSION_KEY] = email
        request.session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(seconds=SIGNUP_EMAIL_SESSION_TTL_SECONDS)
        ).isoformat()
        return JsonResponse({'success': True, 'status': 'verified', 'next': 'register'})

    if not user.is_active:
        return JsonResponse({
            'success': False,
            'error': str(CustomAuthenticationForm.error_messages['inactive']),
        }, status=403)

    login(request, user, backend='massageProject.accounts.backends.VerificationAwareBackend')
    return JsonResponse({'success': True, 'status': 'logged_in', 'redirect': next_url})


@require_POST
@ratelimit(key='ip', rate='5/m', block=False)
def register_via_modal(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    next_url = request.POST.get('next') or reverse('reservation_page')

    email = request.session.get(SIGNUP_EMAIL_SESSION_KEY)
    expires_raw = request.session.get(SIGNUP_EMAIL_SESSION_KEY + '_expires')
    if not email or not expires_raw or timezone.now() > datetime.fromisoformat(expires_raw):
        return JsonResponse({'success': False, 'error': _('Имейлът не е потвърден или потвърждението е изтекло.')}, status=403)

    if request.POST.get('middle_name', ''):
        # Honeypot tripped -- pretend success, create nothing.
        return JsonResponse({'success': True, 'status': 'registered', 'redirect': next_url})

    if not verify_turnstile_token(request.POST.get('turnstile_token', ''), remote_ip=request.META.get('REMOTE_ADDR')):
        return JsonResponse({'success': False, 'error': _('Проверката за робот не е успешна. Опитайте отново.')}, status=400)

    form = BookingRegistrationForm(data=request.POST, email=email)
    if not form.is_valid():
        errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    user = form.save()
    del request.session[SIGNUP_EMAIL_SESSION_KEY]
    del request.session[SIGNUP_EMAIL_SESSION_KEY + '_expires']
    login(request, user, backend='massageProject.accounts.backends.VerificationAwareBackend')

    return JsonResponse({'success': True, 'status': 'registered', 'redirect': next_url})
