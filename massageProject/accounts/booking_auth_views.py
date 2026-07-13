from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

User = get_user_model()


@require_POST
def check_email(request):
    email = request.POST.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'error': _('Въведете имейл адрес.')}, status=400)
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'success': True, 'exists': exists})
