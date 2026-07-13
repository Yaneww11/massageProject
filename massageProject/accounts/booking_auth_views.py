from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from massageProject.accounts.emails import send_otp_email
from massageProject.accounts.models import EmailOTP
from massageProject.accounts.turnstile import verify_turnstile_token

User = get_user_model()


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
