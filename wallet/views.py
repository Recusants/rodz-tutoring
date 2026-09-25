from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from urllib.parse import quote
from .models import StudentWallet, ContentUnlock, CoinTransaction
from content_hub.models import ContentItem
from accounts.models import CustomUser


COIN_PACKAGES = [
    {
        'id': 'starter',
        'name': 'Starter Pack',
        'coins': 60,
        'price_zar': 60,
        'badge': 'ESSENTIAL',
        'description': 'Ideal for a single study pack or past-paper pack.'
    },
    {
        'id': 'term',
        'name': 'Term Booster',
        'coins': 120,
        'price_zar': 110,
        'badge': 'MOST POPULAR',
        'description': 'Great for 2–3 subject revision packs with discount savings.'
    },
    {
        'id': 'exam',
        'name': 'Exam Master Pack',
        'coins': 250,
        'price_zar': 220,
        'badge': 'BEST VALUE',
        'description': 'Comprehensive pack for full exam preparation across subjects.'
    },
    {
        'id': 'annual',
        'name': 'Full Year Academic Access',
        'coins': 500,
        'price_zar': 420,
        'badge': 'PREMIUM',
        'description': 'Access all grade packs, notes, worked exams and streaming lessons.'
    },
]


@login_required
def buy_coins_view(request):
    wallet, _ = StudentWallet.objects.get_or_create(user=request.user)
    whatsapp_phone = getattr(settings, 'WHATSAPP_PHONE', '27745685212')

    packages_with_links = []
    for pkg in COIN_PACKAGES:
        raw_msg = (
            f"Hello Rodz Tutoring! 👋\n"
            f"I want to buy coins for my account:\n\n"
            f"• Package: {pkg['name']} ({pkg['coins']} Coins for R{pkg['price_zar']})\n"
            f"• Student Name: {request.user.full_name or 'Learner'}\n"
            f"• Student Email: {request.user.email}\n"
            f"• Grade: {request.user.grade}\n\n"
            f"Please send the banking/payment details so I can transfer and receive my coins."
        )
        wa_link = f"https://wa.me/{whatsapp_phone}?text={quote(raw_msg)}"
        packages_with_links.append({**pkg, 'wa_link': wa_link})

    return render(request, 'wallet/buy_coins.html', {
        'wallet': wallet,
        'packages': packages_with_links,
    })


@login_required
def unlock_item_view(request, item_slug):
    item = get_object_or_404(ContentItem, slug=item_slug)
    wallet, _ = StudentWallet.objects.get_or_create(user=request.user)

    # Check if already unlocked or free or staff
    if item.is_free or request.user.is_tutor or request.user.is_admin_role or request.user.is_staff:
        return redirect('content_hub:view_content', item_slug=item.slug)

    already_unlocked = ContentUnlock.objects.filter(user=request.user, content_item=item).exists()
    if already_unlocked:
        return redirect('content_hub:view_content', item_slug=item.slug)

    if request.method == 'POST':
        if not wallet.can_afford(item.coin_price):
            messages.error(
                request,
                f"You need {item.coin_price} coins to unlock this resource, but only have {wallet.coins} coins. "
                f"Please request a coin top-up via WhatsApp."
            )
            return redirect('wallet:buy_coins')

        # Deduct coins and create unlock record
        wallet.debit_coins(item.coin_price, description=f"Unlocked: {item.title}")
        ContentUnlock.objects.create(
            user=request.user,
            content_item=item,
            coins_spent=item.coin_price
        )
        messages.success(request, f"🎉 Successfully unlocked '{item.title}'! You can now view all materials.")
        return redirect('content_hub:view_content', item_slug=item.slug)

    return render(request, 'wallet/confirm_unlock.html', {
        'item': item,
        'wallet': wallet,
    })


def is_admin_or_staff(user):
    return user.is_authenticated and (user.is_admin_role or user.is_staff or user.is_superuser)


@user_passes_test(is_admin_or_staff)
def admin_credit_panel_view(request):
    search_query = request.GET.get('q', '').strip()
    users = CustomUser.objects.filter(is_student=True).select_related('wallet')

    if search_query:
        users = users.filter(email__icontains=search_query) | users.filter(full_name__icontains=search_query)

    users = users[:25]

    if request.method == 'POST':
        student_email = request.POST.get('student_email', '').strip()
        coin_amount = request.POST.get('coin_amount', '0')
        note = request.POST.get('note', 'Admin Manual Credit').strip()

        try:
            amount = int(coin_amount)
            if amount <= 0:
                messages.error(request, "Coin amount must be a positive number.")
            else:
                target_user = CustomUser.objects.get(email=student_email)
                target_wallet, _ = StudentWallet.objects.get_or_create(user=target_user)
                target_wallet.credit_coins(amount, description=note, admin_user=request.user)
                messages.success(
                    request, 
                    f"Successfully credited {amount} coins to {target_user.email}! New balance: {target_wallet.coins} coins."
                )
                return redirect('wallet:admin_credit_panel')
        except CustomUser.DoesNotExist:
            messages.error(request, f"Student with email '{student_email}' was not found.")
        except ValueError:
            messages.error(request, "Invalid coin amount entered.")

    recent_transactions = CoinTransaction.objects.select_related('wallet', 'wallet__user', 'created_by')[:20]

    return render(request, 'wallet/admin_credit_panel.html', {
        'users': users,
        'search_query': search_query,
        'recent_transactions': recent_transactions,
    })
