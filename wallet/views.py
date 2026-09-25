from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from urllib.parse import quote
from .models import StudentWallet, ContentUnlock, CoinTransaction, CoinBundle, PaymentMethod, CoinPaymentRequest
from .forms import CoinPaymentActivationForm
from content_hub.models import ContentItem
from accounts.models import CustomUser


def is_admin_or_staff(user):
    return user.is_authenticated and (user.is_admin_role or user.is_staff or user.is_superuser)


@login_required
def buy_coins_view(request):
    wallet, _ = StudentWallet.objects.get_or_create(user=request.user)
    whatsapp_phone = getattr(settings, 'WHATSAPP_PHONE', '27745685212')

    bundles = CoinBundle.objects.filter(is_active=True).order_by('order', 'price_zar')
    payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('order')
    my_requests = CoinPaymentRequest.objects.filter(student=request.user).order_by('-created_at')[:10]

    # Pre-populate bundle if passed in query param ?bundle_id=...
    initial_bundle = None
    bundle_id = request.GET.get('bundle')
    if bundle_id:
        initial_bundle = bundles.filter(id=bundle_id).first()

    if request.method == 'POST':
        form = CoinPaymentActivationForm(request.POST, request.FILES)
        if form.is_valid():
            req_obj = form.save(commit=False)
            req_obj.student = request.user
            req_obj.coins_to_credit = req_obj.bundle.coins
            req_obj.amount_paid = req_obj.bundle.price_zar
            req_obj.save()
            messages.success(
                request,
                f"🎉 Payment activation request for {req_obj.coins_to_credit} coins (R{req_obj.amount_paid}) has been submitted! "
                f"Our admin team will verify your Proof of Payment and credit your wallet."
            )
            return redirect('wallet:buy_coins')
        else:
            messages.error(request, "Please correct the errors in the activation form below.")
    else:
        form = CoinPaymentActivationForm(initial={'bundle': initial_bundle} if initial_bundle else None)

    # WhatsApp fallback message link
    wa_msg = (
        f"Hello Rodz Tutoring! 👋\n"
        f"I would like to inquire about purchasing coins for my student account:\n"
        f"Student: {request.user.full_name or 'Learner'} ({request.user.email})\n"
        f"Grade: {request.user.grade or 'Not set'}"
    )
    wa_link = f"https://wa.me/{whatsapp_phone}?text={quote(wa_msg)}"

    return render(request, 'wallet/buy_coins.html', {
        'wallet': wallet,
        'bundles': bundles,
        'payment_methods': payment_methods,
        'form': form,
        'my_requests': my_requests,
        'wa_link': wa_link,
        'whatsapp_phone': whatsapp_phone,
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
                f"Please top up your coins below."
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


@user_passes_test(is_admin_or_staff)
def admin_payment_requests_view(request):
    status_filter = request.GET.get('status', 'PENDING')
    search_q = request.GET.get('q', '').strip()

    requests_qs = CoinPaymentRequest.objects.select_related('student', 'bundle', 'payment_method', 'reviewed_by')

    if status_filter != 'ALL':
        requests_qs = requests_qs.filter(status=status_filter)

    if search_q:
        requests_qs = requests_qs.filter(
            reference_number__icontains=search_q
        ) | requests_qs.filter(
            student__email__icontains=search_q
        ) | requests_qs.filter(
            student__full_name__icontains=search_q
        )

    pending_count = CoinPaymentRequest.objects.filter(status='PENDING').count()

    if request.method == 'POST':
        action = request.POST.get('action')
        req_id = request.POST.get('request_id')
        admin_note = request.POST.get('admin_notes', '').strip()

        coin_req = get_object_or_404(CoinPaymentRequest, id=req_id)

        if action == 'approve':
            if coin_req.status == 'APPROVED':
                messages.warning(request, f"Request #{coin_req.id} is already approved.")
            else:
                coin_req.status = 'APPROVED'
                coin_req.reviewed_by = request.user
                coin_req.reviewed_at = timezone.now()
                if admin_note:
                    coin_req.admin_notes = admin_note
                coin_req.save()

                # Credit student wallet
                student_wallet, _ = StudentWallet.objects.get_or_create(user=coin_req.student)
                bundle_title = coin_req.bundle.name if coin_req.bundle else 'Coin Pack'
                tx_desc = f"Payment Approved: {bundle_title} (Ref: {coin_req.reference_number})"
                student_wallet.credit_coins(coin_req.coins_to_credit, description=tx_desc, admin_user=request.user)

                messages.success(
                    request,
                    f"✅ Request #{coin_req.id} APPROVED! Credited {coin_req.coins_to_credit} coins to {coin_req.student.email}. "
                    f"New wallet balance: {student_wallet.coins} coins."
                )
            return redirect(f"{request.path}?status={status_filter}")

        elif action == 'reject':
            coin_req.status = 'REJECTED'
            coin_req.reviewed_by = request.user
            coin_req.reviewed_at = timezone.now()
            coin_req.admin_notes = admin_note or 'Proof of payment could not be verified.'
            coin_req.save()
            messages.info(request, f"❌ Request #{coin_req.id} for {coin_req.student.email} has been marked as DECLINED.")
            return redirect(f"{request.path}?status={status_filter}")

    return render(request, 'wallet/admin_payment_requests.html', {
        'payment_requests': requests_qs,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'search_q': search_q,
    })


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
