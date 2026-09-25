from django.conf import settings
from wallet.models import ContentUnlock

def brand_context(request):
    ctx = {
        'BRAND_NAME': 'Rodz Tutoring',
        'WHATSAPP_PHONE': getattr(settings, 'WHATSAPP_PHONE', '27745685212'),
        'WHATSAPP_DISPLAY_PHONE': getattr(settings, 'WHATSAPP_DISPLAY_PHONE', '+27 74 568 5212'),
        'INFO_EMAIL': getattr(settings, 'INFO_EMAIL', 'info@rodztutoring.co.za'),
    }

    if request.user.is_authenticated:
        # Get user's wallet
        wallet = getattr(request.user, 'wallet', None)
        ctx['user_coins'] = wallet.coins if wallet else 0
        
        # Fast set of unlocked item IDs for template badges
        unlocked_ids = set(ContentUnlock.objects.filter(user=request.user).values_list('content_item_id', flat=True))
        ctx['user_unlocked_ids'] = unlocked_ids
    else:
        ctx['user_coins'] = 0
        ctx['user_unlocked_ids'] = set()

    return ctx
