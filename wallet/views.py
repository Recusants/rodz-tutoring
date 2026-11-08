import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from urllib.parse import quote
from decimal import Decimal
from django.http import JsonResponse
from .models import (
    StudentWallet, ContentUnlock, CourseUnlock, CoinTransaction, 
    CoinBundle, PaymentMethod, CoinPaymentRequest, CoinPriceChangeLog, CoinWallet, SystemWallet
)
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
            req_obj.bundle_name_snapshot = req_obj.bundle.name
            req_obj.bundle_price_snapshot = req_obj.bundle.price_zar
            req_obj.rate_per_coin = round(req_obj.bundle.price_zar / req_obj.bundle.coins, 4) if req_obj.bundle.coins else 0
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
        wallet.debit_coins(item.coin_price, description=f"Unlocked: {item.title}", transaction_type='CONTENT_UNLOCK')
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


@login_required
def unlock_course_view(request, course_slug):
    from content_hub.models import Course
    course = get_object_or_404(Course, slug=course_slug)
    wallet, _ = StudentWallet.objects.get_or_create(user=request.user)

    # Creators and staff get direct access
    if request.user == course.creator or request.user.is_admin_role or request.user.is_staff:
        messages.info(request, f"You have tutor/management access to '{course.title}'.")
        return redirect('content_hub:course_detail', slug=course.slug)

    pricing = course.get_pricing_for_user(request.user)
    if pricing['is_fully_owned']:
        messages.info(request, f"You already own all materials in '{course.title}'!")
        return redirect('content_hub:course_detail', slug=course.slug)

    final_price = pricing['final_price']

    if request.method == 'POST':
        if not wallet.can_afford(final_price):
            messages.error(
                request,
                f"You need {final_price} coins to unlock this course bundle, but currently have {wallet.coins} coins. "
                f"Please top up below."
            )
            return redirect('wallet:buy_coins')

        # Debit coins from student, and credit coins to the course creator!
        if final_price > 0:
            wallet.debit_coins(
                final_price, 
                description=f"Course Bundle Unlock: {course.title}", 
                transaction_type='COURSE_UNLOCK',
                counterparty=course.creator
            )
            if course.creator and course.creator != request.user:
                creator_wallet, _ = StudentWallet.objects.get_or_create(user=course.creator)
                creator_wallet.credit_coins(
                    final_price,
                    description=f"Course Sale Earning: '{course.title}' unlocked by student",
                    transaction_type='CREATOR_EARNING',
                    counterparty=request.user
                )
                system_wallet = SystemWallet.get_instance()
                system_wallet.total_creator_earnings_processed += final_price
                system_wallet.save()

        course_unlock = CourseUnlock.objects.create(
            user=request.user,
            course=course,
            coins_spent=final_price
        )

        # Grant access to all bundled resources
        for item in course.items.all():
            if not request.user.has_unlocked(item):
                ContentUnlock.objects.create(
                    user=request.user,
                    content_item=item,
                    coins_spent=0,
                    expires_at=course_unlock.expires_at
                )

        messages.success(
            request, 
            f"🎉 Congratulations! You have successfully unlocked the complete course bundle '{course.title}' for {final_price} coins!"
        )
        return redirect('content_hub:course_detail', slug=course.slug)

    return render(request, 'wallet/confirm_course_unlock.html', {
        'course': course,
        'pricing': pricing,
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

                # Credit student wallet by deducting from System Wallet Treasury
                student_wallet, _ = StudentWallet.objects.get_or_create(user=coin_req.student)
                bundle_title = coin_req.bundle.name if coin_req.bundle else 'Coin Pack'
                tx_desc = f"Payment Approved: {bundle_title} (Ref: {coin_req.reference_number})"
                system_wallet = SystemWallet.get_instance()
                system_wallet.deduct_for_purchase(student_wallet, coin_req.coins_to_credit, description=tx_desc, admin_user=request.user)

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


@login_required
def coin_history_view(request):
    """
    Dedicated Coin History & Global Ledger page.
    - Admins see comprehensive platform ledger across ALL users with a wallet.
    - Students / Tutors see their personal coin transaction ledger.
    - Admins can toggle between 'all' users and 'my' personal wallet.
    - Supports full-text search, type filtering, date filtering, sorting, and pagination.
    """
    user = request.user
    active_role = request.session.get('active_role_mode', user.default_role_mode)
    is_admin = (active_role == 'admin') and (user.is_admin_role or user.is_staff or user.is_superuser)

    # Determine view scope: 'all' (all users' wallets) or 'my' (current user)
    requested_view = request.GET.get('view')
    if is_admin:
        view_scope = requested_view if requested_view in ['all', 'my'] else 'all'
    else:
        view_scope = 'my'

    # Base Queryset
    if view_scope == 'all':
        transactions_qs = CoinTransaction.objects.select_related('wallet__user', 'created_by', 'counterparty').all()
    else:
        wallet, _ = StudentWallet.objects.get_or_create(user=user)
        transactions_qs = CoinTransaction.objects.select_related('wallet__user', 'created_by', 'counterparty').filter(wallet=wallet)

    # Search filter (User name/email or transaction description)
    q = request.GET.get('q', '').strip()
    if q:
        transactions_qs = transactions_qs.filter(
            Q(wallet__user__email__icontains=q) |
            Q(wallet__user__full_name__icontains=q) |
            Q(description__icontains=q) |
            Q(counterparty__email__icontains=q) |
            Q(counterparty__full_name__icontains=q)
        )

    # Specific user filter (for admin inspecting a specific learner's wallet)
    user_id = request.GET.get('user_id', '').strip()
    target_user = None
    if user_id and is_admin:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            transactions_qs = transactions_qs.filter(wallet__user=target_user)
        except (CustomUser.DoesNotExist, ValueError):
            pass

    # Type filter: 'ALL', 'CREDIT', 'DEBIT', 'TRANSFER', or specific transaction_type code
    type_filter = request.GET.get('type', 'ALL').strip().upper()
    if type_filter and type_filter != 'ALL':
        if type_filter == 'CREDIT':
            transactions_qs = transactions_qs.filter(amount__gt=0)
        elif type_filter == 'DEBIT':
            transactions_qs = transactions_qs.filter(amount__lt=0)
        elif type_filter == 'TRANSFER':
            transactions_qs = transactions_qs.filter(transaction_type__in=['TRANSFER_SENT', 'TRANSFER_RECEIVED'])
        else:
            transactions_qs = transactions_qs.filter(transaction_type=type_filter)

    # Time / days filter
    days_filter = request.GET.get('days', 'ALL').strip().upper()
    if days_filter and days_filter != 'ALL':
        try:
            days_int = int(days_filter)
            since = timezone.now() - datetime.timedelta(days=days_int)
            transactions_qs = transactions_qs.filter(created_at__gte=since)
        except ValueError:
            pass

    # Ordering
    sort = request.GET.get('sort', 'newest')
    if sort == 'oldest':
        transactions_qs = transactions_qs.order_by('created_at')
    elif sort == 'highest':
        transactions_qs = transactions_qs.order_by('-amount')
    elif sort == 'lowest':
        transactions_qs = transactions_qs.order_by('amount')
    else:
        transactions_qs = transactions_qs.order_by('-created_at')

    # Platform-wide statistics (for all wallets)
    all_wallets = StudentWallet.objects.select_related('user')
    total_wallets_count = all_wallets.count()
    coins_in_circulation = all_wallets.aggregate(total=Sum('coins'))['total'] or 0

    all_tx = CoinTransaction.objects.all()
    global_total_credited = all_tx.filter(amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
    global_total_debited = abs(all_tx.filter(amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0)
    global_total_tx_count = all_tx.count()

    # User's personal stats
    user_wallet, _ = StudentWallet.objects.get_or_create(user=user)
    my_tx = CoinTransaction.objects.filter(wallet=user_wallet)
    my_total_credited = my_tx.filter(amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
    my_total_debited = abs(my_tx.filter(amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0)
    my_total_tx_count = my_tx.count()

    # Pagination: 25 items per page
    paginator = Paginator(transactions_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # All users that have a wallet (for quick jump dropdown in admin mode)
    wallets_list = all_wallets.order_by('user__email')[:100] if is_admin else []

    return render(request, 'wallet/coin_history.html', {
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'view_scope': view_scope,
        'is_admin': is_admin,
        'q': q,
        'type_filter': type_filter,
        'days_filter': days_filter,
        'sort': sort,
        'target_user': target_user,
        'wallets_list': wallets_list,
        # Stat counters
        'total_wallets_count': total_wallets_count,
        'coins_in_circulation': coins_in_circulation,
        'global_total_credited': global_total_credited,
        'global_total_debited': global_total_debited,
        'global_total_tx_count': global_total_tx_count,
        'my_wallet': user_wallet,
        'my_total_credited': my_total_credited,
        'my_total_debited': my_total_debited,
        'my_total_tx_count': my_total_tx_count,
        'TYPE_CHOICES': CoinTransaction.TYPE_CHOICES,
    })


@login_required
def transfer_coins_view(request):
    """
    Instant user-to-user coin transfer without requiring admin approval.
    Allows students, tutors, and staff to send coins directly to any other registered user.
    Supports both SweetAlert2 AJAX requests and standard POST fallback.
    """
    user = request.user
    wallet, _ = StudentWallet.objects.get_or_create(user=user)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

    # Pre-filled recipient from query param ?to=email
    prefilled_to = request.GET.get('to', '').strip()

    if request.method == 'POST':
        recipient_identifier = (request.POST.get('recipient') or request.POST.get('recipient_email') or '').strip()
        coin_amount = request.POST.get('amount', '').strip()
        note = request.POST.get('note', '').strip()

        # Validate Recipient
        if not recipient_identifier:
            msg = "Please enter the recipient's registered email address."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:transfer_coins')

        recipient_user = CustomUser.objects.filter(
            Q(email__iexact=recipient_identifier) | 
            Q(phone_number__iexact=recipient_identifier)
        ).first()

        if not recipient_user:
            msg = f"User '{recipient_identifier}' was not found. Please double-check their registered account email."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=404)
            messages.error(request, msg)
            return redirect('wallet:transfer_coins')

        if recipient_user == user:
            msg = "You cannot transfer coins to your own account."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:transfer_coins')

        # Validate Amount & Transfer Fee
        system_wallet = SystemWallet.get_instance()
        try:
            amount = int(coin_amount)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            msg = "Please enter a valid coin amount of at least 1 coin."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:transfer_coins')

        transfer_fee = system_wallet.calculate_transfer_fee(amount)
        total_deducted = amount + transfer_fee

        if not wallet.can_afford(total_deducted):
            msg = f"Insufficient coins! Transferring {amount} coins requires a {transfer_fee} coin platform fee (Total: {total_deducted} coins). You only have {wallet.coins} coins."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:transfer_coins')

        # Execute atomic transfer (zero admin approval needed)
        try:
            tx_sender, tx_recipient = wallet.transfer_coins_to(recipient_user, amount, note=note)
            success_msg = f"🎉 Successfully transferred {amount} coins to {recipient_user.full_name or recipient_user.email} (Platform fee: {transfer_fee} coins)!"
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'new_balance': wallet.coins,
                    'remaining_coins': wallet.coins,
                    'amount': amount,
                    'fee': transfer_fee,
                    'total_deducted': total_deducted,
                    'recipient_name': recipient_user.full_name or recipient_user.email,
                    'message': success_msg,
                })
            messages.success(request, success_msg)
            return redirect('wallet:coin_history')
        except Exception as e:
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=400)
            messages.error(request, f"Transfer failed: {str(e)}")
            return redirect('wallet:transfer_coins')

    # GET: Load recent peer transfers made by this user
    system_wallet = SystemWallet.get_instance()
    recent_transfers = CoinTransaction.objects.filter(
        wallet=wallet,
        transaction_type__in=['TRANSFER_SENT', 'TRANSFER_RECEIVED']
    ).select_related('counterparty').order_by('-created_at')[:8]

    return render(request, 'wallet/transfer_coins.html', {
        'wallet': wallet,
        'recent_transfers': recent_transfers,
        'prefilled_to': prefilled_to,
        'transfer_fee': system_wallet.transfer_fee_coins,
        'system_wallet': system_wallet,
    })


@login_required
def sell_coins_view(request):
    """
    Allows tutors and students to cash out / sell coins back to the platform treasury.
    Coins are deducted from the user's wallet and returned to the System Wallet Treasury.
    """
    wallet, _ = StudentWallet.objects.get_or_create(user=request.user)
    system_wallet = SystemWallet.get_instance()
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

    if request.method == 'POST':
        coin_amount_raw = request.POST.get('coins', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        account_number = request.POST.get('account_number', '').strip()
        account_holder = request.POST.get('account_holder', '').strip()
        notes = request.POST.get('notes', '').strip()

        try:
            coins_to_sell = int(coin_amount_raw)
            if coins_to_sell < system_wallet.min_cashout_coins:
                raise ValueError(f"Minimum cash-out is {system_wallet.min_cashout_coins} coins.")
        except ValueError as ve:
            msg = str(ve) if "Minimum" in str(ve) else f"Please enter a valid coin amount of at least {system_wallet.min_cashout_coins} coins."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:sell_coins')

        if not wallet.can_afford(coins_to_sell):
            msg = f"Insufficient coin balance! You only have {wallet.coins} coins."
            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('wallet:sell_coins')

        # Calculate cash payout
        payout_amount = round(Decimal(str(coins_to_sell)) * system_wallet.cashout_rate_per_coin, 2)

        # Debit user wallet & add coins to SystemWallet
        desc = f"Coins Cashed Out: {coins_to_sell} coins -> {system_wallet.currency_symbol}{payout_amount} ({bank_name} {account_number})"
        system_wallet.add_from_sale(wallet, coins_to_sell, payout_amount=payout_amount, description=desc, user=request.user)

        success_msg = f"🎉 Successfully sold {coins_to_sell} coins for {system_wallet.currency_symbol}{payout_amount}! Payout has been queued to your bank account."
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': success_msg,
                'remaining_coins': wallet.coins,
                'coins_sold': coins_to_sell,
                'payout_amount': str(payout_amount),
                'currency_symbol': system_wallet.currency_symbol,
            })
        messages.success(request, success_msg)
        return redirect('wallet:coin_history')

    recent_sales = CoinTransaction.objects.filter(
        wallet=wallet,
        transaction_type='COIN_SALE'
    ).order_by('-created_at')[:8]

    return render(request, 'wallet/sell_coins.html', {
        'wallet': wallet,
        'system_wallet': system_wallet,
        'recent_sales': recent_sales,
    })


@user_passes_test(is_admin_or_staff)
def admin_coin_pricing_view(request):
    """
    Comprehensive Admin control center:
    1. Adjust platform financial settings (Currency Code, Currency Symbol, Transfer Fees, Cash-out Price).
    2. Full Coin Bundle Editor (adjust Name, Coins, Price, Badge, Description, Order, Active/Inactive).
    3. Create and delete coin bundles.
    4. View Central System Wallet Treasury reserves and price change audit logs.
    """
    bundles = CoinBundle.objects.all().order_by('order', 'price_zar')
    system_wallet = SystemWallet.get_instance()
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Update Platform Financial Settings (Currency, Fees, Cashout Price)
        if action == 'save_financial_settings':
            currency_code = request.POST.get('currency_code', 'ZAR').strip().upper()
            currency_symbol = request.POST.get('currency_symbol', 'R').strip()
            transfer_fee_coins_raw = request.POST.get('transfer_fee_coins', '2').strip()
            cashout_rate_raw = request.POST.get('cashout_rate_per_coin', '0.80').strip()
            min_cashout_raw = request.POST.get('min_cashout_coins', '50').strip()

            try:
                system_wallet.currency_code = currency_code or 'ZAR'
                system_wallet.currency_symbol = currency_symbol or 'R'
                system_wallet.transfer_fee_coins = max(0, int(transfer_fee_coins_raw))
                system_wallet.cashout_rate_per_coin = Decimal(cashout_rate_raw)
                system_wallet.min_cashout_coins = max(1, int(min_cashout_raw))
                system_wallet.save()

                msg = f"✓ Platform Financial Settings updated: Currency is {system_wallet.currency_symbol} ({system_wallet.currency_code}), Transfer Fee is {system_wallet.transfer_fee_coins} coins, Cash-out Rate is {system_wallet.currency_symbol}{system_wallet.cashout_rate_per_coin}/coin."
                if is_ajax:
                    return JsonResponse({'status': 'success', 'success': True, 'message': msg})
                messages.success(request, msg)
                return redirect('wallet:admin_pricing')
            except Exception as e:
                err_msg = f"Error saving financial settings: {str(e)}"
                if is_ajax:
                    return JsonResponse({'status': 'error', 'success': False, 'message': err_msg}, status=400)
                messages.error(request, err_msg)
                return redirect('wallet:admin_pricing')

        # 2. Create New Bundle
        elif action == 'create_bundle':
            name = request.POST.get('name', '').strip()
            coins_raw = request.POST.get('coins', '').strip()
            price_raw = request.POST.get('price_zar', '').strip()
            badge = request.POST.get('badge', '').strip()
            description = request.POST.get('description', '').strip()
            order_raw = request.POST.get('order', '0').strip()
            is_active = request.POST.get('is_active') in ['1', 'true', 'True', 'on']

            if not name or not coins_raw or not price_raw:
                err = "Name, Coins, and Price are required fields."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'success': False, 'message': err}, status=400)
                messages.error(request, err)
                return redirect('wallet:admin_pricing')

            try:
                new_bundle = CoinBundle.objects.create(
                    name=name,
                    coins=int(coins_raw),
                    price_zar=Decimal(price_raw),
                    badge=badge,
                    description=description,
                    order=int(order_raw or 0),
                    is_active=is_active
                )
                CoinPriceChangeLog.objects.create(
                    bundle=new_bundle,
                    bundle_name=new_bundle.name,
                    coins=new_bundle.coins,
                    old_price_zar=Decimal('0.00'),
                    new_price_zar=new_bundle.price_zar,
                    old_rate_per_coin=Decimal('0.0000'),
                    new_rate_per_coin=new_bundle.rate_per_coin,
                    changed_by=request.user,
                    change_reason="Initial Bundle Creation"
                )
                msg = f"✓ Created new bundle '{new_bundle.name}' ({new_bundle.coins} coins for {system_wallet.currency_symbol}{new_bundle.price_zar})."
                if is_ajax:
                    return JsonResponse({'status': 'success', 'success': True, 'message': msg})
                messages.success(request, msg)
                return redirect('wallet:admin_pricing')
            except Exception as e:
                err = f"Failed to create bundle: {str(e)}"
                if is_ajax:
                    return JsonResponse({'status': 'error', 'success': False, 'message': err}, status=400)
                messages.error(request, err)
                return redirect('wallet:admin_pricing')

        # 3. Full Bundle Update (Edit All Fields)
        elif action == 'save_bundle':
            bundle_id = request.POST.get('bundle_id')
            bundle = get_object_or_404(CoinBundle, id=bundle_id)

            name = request.POST.get('name', bundle.name).strip()
            coins_raw = request.POST.get('coins', str(bundle.coins)).strip()
            price_raw = request.POST.get('price_zar', str(bundle.price_zar)).strip()
            badge = request.POST.get('badge', bundle.badge).strip()
            description = request.POST.get('description', bundle.description).strip()
            order_raw = request.POST.get('order', str(bundle.order)).strip()
            is_active = request.POST.get('is_active') in ['1', 'true', 'True', 'on']
            reason = request.POST.get('change_reason', '').strip()

            try:
                new_coins = int(coins_raw)
                new_price = Decimal(price_raw)
                old_price = bundle.price_zar
                old_coins = bundle.coins

                price_or_coins_changed = (new_price != old_price) or (new_coins != old_coins)

                bundle.name = name
                bundle.coins = new_coins
                bundle.price_zar = new_price
                bundle.badge = badge
                bundle.description = description
                bundle.order = int(order_raw or 0)
                bundle.is_active = is_active
                bundle.save()

                if price_or_coins_changed:
                    old_rate = round(old_price / old_coins, 4) if old_coins else Decimal('0.0000')
                    new_rate = round(new_price / new_coins, 4) if new_coins else Decimal('0.0000')
                    CoinPriceChangeLog.objects.create(
                        bundle=bundle,
                        bundle_name=bundle.name,
                        coins=bundle.coins,
                        old_price_zar=old_price,
                        new_price_zar=new_price,
                        old_rate_per_coin=old_rate,
                        new_rate_per_coin=new_rate,
                        changed_by=request.user,
                        change_reason=reason or "Admin Bundle Specifications Update"
                    )

                msg = f"✓ Bundle '{bundle.name}' updated successfully!"
                if is_ajax:
                    return JsonResponse({'status': 'success', 'success': True, 'message': msg})
                messages.success(request, msg)
                return redirect('wallet:admin_pricing')
            except Exception as e:
                err = f"Failed to update bundle: {str(e)}"
                if is_ajax:
                    return JsonResponse({'status': 'error', 'success': False, 'message': err}, status=400)
                messages.error(request, err)
                return redirect('wallet:admin_pricing')

        # 4. Delete Bundle
        elif action == 'delete_bundle':
            bundle_id = request.POST.get('bundle_id')
            bundle = get_object_or_404(CoinBundle, id=bundle_id)
            bundle_name = bundle.name
            bundle.delete()
            msg = f"✓ Bundle '{bundle_name}' has been deleted."
            if is_ajax:
                return JsonResponse({'status': 'success', 'success': True, 'message': msg})
            messages.success(request, msg)
            return redirect('wallet:admin_pricing')

        # 5. Quick Price Update (Backward Compatibility)
        else:
            bundle_id = request.POST.get('bundle_id')
            new_price_raw = (request.POST.get('new_price') or request.POST.get('price_zar') or '').strip()
            reason = request.POST.get('change_reason', '').strip()

            bundle = get_object_or_404(CoinBundle, id=bundle_id)

            try:
                new_price = Decimal(new_price_raw)
                if new_price <= 0:
                    raise ValueError("Price must be greater than zero")
            except Exception:
                msg = "Please enter a valid positive decimal price."
                if is_ajax:
                    return JsonResponse({'status': 'error', 'success': False, 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('wallet:admin_pricing')

            old_price = bundle.price_zar
            old_rate = round(old_price / bundle.coins, 4) if bundle.coins else Decimal('0.0000')
            new_rate = round(new_price / bundle.coins, 4) if bundle.coins else Decimal('0.0000')

            # Log price change
            CoinPriceChangeLog.objects.create(
                bundle=bundle,
                bundle_name=bundle.name,
                coins=bundle.coins,
                old_price_zar=old_price,
                new_price_zar=new_price,
                old_rate_per_coin=old_rate,
                new_rate_per_coin=new_rate,
                changed_by=request.user,
                change_reason=reason or "Admin Price Adjustment"
            )

            # Update bundle price
            bundle.price_zar = new_price
            bundle.save()

            success_msg = f"✓ Price for '{bundle.name}' ({bundle.coins} coins) updated to {system_wallet.currency_symbol}{new_price} (Rate: {system_wallet.currency_symbol}{new_rate}/coin)."
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'message': success_msg,
                    'bundle_id': bundle.id,
                    'new_price': str(new_price),
                    'new_rate': str(new_rate),
                })
            messages.success(request, success_msg)
            return redirect('wallet:admin_pricing')

    # Load price change history audit log
    price_logs = CoinPriceChangeLog.objects.select_related('bundle', 'changed_by').order_by('-created_at')[:60]

    return render(request, 'wallet/admin_coin_pricing.html', {
        'bundles': bundles,
        'price_logs': price_logs,
        'system_wallet': system_wallet,
    })


