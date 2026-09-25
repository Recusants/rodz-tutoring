from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser
from .forms import RegistrationForm, LoginForm
from wallet.models import StudentWallet, ContentUnlock, CoinTransaction
from content_hub.models import ContentItem
from quizzes.models import QuizAttempt


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to Rodz Tutoring, {user.full_name or user.email}! Your account has been created.')
            return redirect('accounts:dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.full_name or user.email}!')
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'accounts:dashboard')
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been successfully logged out.')
    return redirect('home')


@login_required
def switch_mode_view(request, mode):
    """
    Switches active role mode (Student, Tutor, Admin) for multi-role users.
    Validates that user possesses the requested role.
    """
    mode = mode.lower().strip()
    available = request.user.available_roles
    if mode in available:
        request.session['active_role_mode'] = mode
        messages.success(request, f"✓ Switched to {mode.capitalize()} Mode.")
    else:
        messages.error(request, f"You do not possess the {mode.capitalize()} role.")

    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and '/accounts/switch-mode/' not in next_url:
        return redirect(next_url)
    return redirect('accounts:dashboard')


@login_required
def dashboard_view(request):
    user = request.user
    active_mode = user.get_active_mode(request)
    wallet, _ = StudentWallet.objects.get_or_create(user=user)

    context = {
        'user': user,
        'wallet': wallet,
        'active_mode': active_mode,
    }

    if active_mode == 'student':
        from django.db.models import Q
        from django.utils import timezone
        unlocked_records = ContentUnlock.objects.filter(user=user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        ).select_related('content_item', 'content_item__subject')

        unlocked_ids = {u.content_item_id for u in unlocked_records}
        recommended_items = []
        if user.grade:
            recommended_items = ContentItem.objects.filter(
                grade=user.grade
            ).exclude(id__in=unlocked_ids).select_related('subject')[:6]

        recent_transactions = CoinTransaction.objects.filter(wallet=wallet)[:8]
        quiz_attempts = QuizAttempt.objects.filter(student=user).select_related('quiz', 'quiz__content_item')[:6]

        context.update({
            'unlocked_records': unlocked_records,
            'recommended_items': recommended_items,
            'recent_transactions': recent_transactions,
            'quiz_attempts': quiz_attempts,
        })
    elif active_mode == 'tutor':
        tutor_content_count = ContentItem.objects.count()
        recent_items = ContentItem.objects.select_related('subject')[:10]
        context.update({
            'tutor_content_count': tutor_content_count,
            'recent_items': recent_items,
        })
    elif active_mode == 'admin':
        from wallet.models import CoinPaymentRequest
        total_users = CustomUser.objects.count()
        student_count = CustomUser.objects.filter(is_student=True).count()
        tutor_count = CustomUser.objects.filter(is_tutor=True).count()
        pending_payments = CoinPaymentRequest.objects.filter(status='PENDING').count()
        recent_users = CustomUser.objects.order_by('-date_joined')[:6]
        recent_payments = CoinPaymentRequest.objects.filter(status='PENDING')[:5]

        context.update({
            'total_users': total_users,
            'student_count': student_count,
            'tutor_count': tutor_count,
            'pending_payments': pending_payments,
            'recent_users': recent_users,
            'recent_payments': recent_payments,
        })

    return render(request, 'accounts/dashboard.html', context)


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.urls import reverse_lazy
from django.core.mail import send_mail
from .forms import (
    UserProfileForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    AdminSystemSettingsForm
)
from .env_manager import read_env_file, update_env_file


@login_required
def profile_view(request):
    user = request.user
    profile_form = UserProfileForm(instance=user)
    password_form = StyledPasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile details have been successfully updated.')
                return redirect('accounts:profile')
        elif action == 'change_password':
            password_form = StyledPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'user': user,
        'profile_form': profile_form,
        'password_form': password_form,
    })


class RodzPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/emails/password_reset_email.html'
    subject_template_name = 'accounts/emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')
    form_class = StyledPasswordResetForm


class RodzPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class RodzPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy('accounts:password_reset_complete')


class RodzPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


def is_admin_or_staff(user):
    return user.is_authenticated and (user.is_admin_role or user.is_staff or user.is_superuser)


from django.contrib.auth.decorators import user_passes_test


@user_passes_test(is_admin_or_staff)
def admin_system_settings_view(request):
    env_data = read_env_file()

    initial_data = {
        'system_email': env_data.get('SYSTEM_EMAIL', 'info@rodztutoring.co.za'),
        'notification_email': env_data.get('NOTIFICATION_EMAIL', 'admin@rodztutoring.co.za'),
        'email_host': env_data.get('EMAIL_HOST', 'smtp.gmail.com'),
        'email_port': int(env_data.get('EMAIL_PORT', 587)),
        'email_host_user': env_data.get('EMAIL_HOST_USER', ''),
        'email_use_tls': env_data.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1'),
        'whatsapp_phone': env_data.get('WHATSAPP_PHONE', '27745685212'),
        'whatsapp_display_phone': env_data.get('WHATSAPP_DISPLAY_PHONE', '+27 74 568 5212'),
    }

    if request.method == 'POST':
        if 'test_email' in request.POST:
            test_recipient = request.POST.get('test_recipient', '').strip() or request.user.email
            try:
                send_mail(
                    subject='[Rodz Tutoring] SMTP Test Diagnostic',
                    message='This is a verification test email from your Rodz Tutoring system settings configuration. SMTP delivery is working perfectly!',
                    from_email=None,
                    recipient_list=[test_recipient],
                    fail_silently=False
                )
                messages.success(request, f"✓ Diagnostic test email successfully sent to {test_recipient}!")
            except Exception as e:
                messages.error(request, f"SMTP Test Failed: {e}")
            return redirect('accounts:system_settings')

        form = AdminSystemSettingsForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            updates = {
                'SYSTEM_EMAIL': cleaned['system_email'],
                'NOTIFICATION_EMAIL': cleaned['notification_email'],
                'EMAIL_HOST': cleaned['email_host'],
                'EMAIL_PORT': str(cleaned['email_port']),
                'EMAIL_HOST_USER': cleaned['email_host_user'],
                'EMAIL_USE_TLS': 'True' if cleaned['email_use_tls'] else 'False',
                'WHATSAPP_PHONE': cleaned['whatsapp_phone'],
                'WHATSAPP_DISPLAY_PHONE': cleaned['whatsapp_display_phone'],
            }
            # Only update password if a new one was provided
            new_password = cleaned.get('email_host_password')
            if new_password:
                updates['EMAIL_HOST_PASSWORD'] = new_password

            update_env_file(updates)
            messages.success(request, 'System settings and .env configuration updated successfully!')
            return redirect('accounts:system_settings')
    else:
        form = AdminSystemSettingsForm(initial=initial_data)

    has_configured_password = bool(env_data.get('EMAIL_HOST_PASSWORD'))

    return render(request, 'accounts/admin_system_settings.html', {
        'form': form,
        'has_configured_password': has_configured_password,
        'current_system_email': env_data.get('SYSTEM_EMAIL', 'info@rodztutoring.co.za'),
        'current_whatsapp': env_data.get('WHATSAPP_DISPLAY_PHONE', '+27 74 568 5212'),
    })


from django.db.models import Q
from .forms import (
    AdminUserEditForm,
    AdminUserCreateForm,
    AdminDirectPasswordResetForm,
    AdminWalletAdjustForm,
    AdminGrantUnlockForm
)
from wallet.models import calculate_academic_year_expiry


@user_passes_test(is_admin_or_staff)
def admin_user_list_view(request):
    search_q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', 'ALL')
    grade_filter = request.GET.get('grade', 'ALL')
    status_filter = request.GET.get('status', 'ALL')

    users_qs = CustomUser.objects.all().order_by('-date_joined')

    if search_q:
        users_qs = users_qs.filter(
            Q(email__icontains=search_q) |
            Q(full_name__icontains=search_q) |
            Q(phone_number__icontains=search_q)
        )

    if role_filter == 'STUDENT':
        users_qs = users_qs.filter(is_student=True)
    elif role_filter == 'TUTOR':
        users_qs = users_qs.filter(is_tutor=True)
    elif role_filter == 'ADMIN':
        users_qs = users_qs.filter(Q(is_admin_role=True) | Q(is_staff=True) | Q(is_superuser=True))

    if grade_filter != 'ALL':
        users_qs = users_qs.filter(grade=grade_filter)

    if status_filter == 'ACTIVE':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'SUSPENDED':
        users_qs = users_qs.filter(is_active=False)

    total_count = CustomUser.objects.count()
    student_count = CustomUser.objects.filter(is_student=True).count()
    tutor_count = CustomUser.objects.filter(is_tutor=True).count()
    admin_count = CustomUser.objects.filter(Q(is_admin_role=True) | Q(is_staff=True)).count()

    return render(request, 'accounts/admin_user_list.html', {
        'users': users_qs,
        'search_q': search_q,
        'role_filter': role_filter,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'total_count': total_count,
        'student_count': student_count,
        'tutor_count': tutor_count,
        'admin_count': admin_count,
        'grade_choices': CustomUser.GRADE_CHOICES,
    })


@user_passes_test(is_admin_or_staff)
def admin_user_detail_view(request, user_id):
    from django.shortcuts import get_object_or_404
    target_user = get_object_or_404(CustomUser, id=user_id)
    target_wallet, _ = StudentWallet.objects.get_or_create(user=target_user)

    profile_form = AdminUserEditForm(instance=target_user)
    password_form = AdminDirectPasswordResetForm()
    wallet_form = AdminWalletAdjustForm()
    grant_unlock_form = AdminGrantUnlockForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'edit_profile':
            profile_form = AdminUserEditForm(request.POST, instance=target_user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, f"✓ Profile and roles for {target_user.email} updated successfully!")
                return redirect('accounts:admin_user_detail', user_id=target_user.id)
            else:
                messages.error(request, "Please correct the errors in the profile form.")

        elif action == 'direct_password':
            password_form = AdminDirectPasswordResetForm(request.POST)
            if password_form.is_valid():
                new_pw = password_form.cleaned_data['new_password']
                target_user.set_password(new_pw)
                target_user.save()
                messages.success(request, f"✓ Password for {target_user.email} successfully updated to new password!")
                return redirect('accounts:admin_user_detail', user_id=target_user.id)
            else:
                messages.error(request, "Failed to update password. Please check the requirements.")

        elif action == 'adjust_wallet':
            wallet_form = AdminWalletAdjustForm(request.POST)
            if wallet_form.is_valid():
                act = wallet_form.cleaned_data['action_type']
                amt = wallet_form.cleaned_data['coins']
                desc = wallet_form.cleaned_data['description']
                if act == 'CREDIT':
                    target_wallet.credit_coins(amt, description=f"Admin Credit by {request.user.email}: {desc}")
                    messages.success(request, f"✓ Credited {amt} coins to {target_user.email}.")
                elif act == 'DEBIT':
                    target_wallet.debit_coins(amt, description=f"Admin Debit by {request.user.email}: {desc}")
                    messages.success(request, f"✓ Deducted {amt} coins from {target_user.email}.")
                return redirect('accounts:admin_user_detail', user_id=target_user.id)

        elif action == 'grant_unlock':
            grant_unlock_form = AdminGrantUnlockForm(request.POST)
            if grant_unlock_form.is_valid():
                item = grant_unlock_form.cleaned_data['content_item']
                unlock, created = ContentUnlock.objects.get_or_create(
                    user=target_user,
                    content_item=item,
                    defaults={'coins_spent': 0, 'expires_at': calculate_academic_year_expiry()}
                )
                if not created:
                    unlock.expires_at = calculate_academic_year_expiry()
                    unlock.save()
                    messages.info(request, f"Renewed active academic access for '{item.title}'.")
                else:
                    messages.success(request, f"✓ Granted access to '{item.title}' for {target_user.email}!")
                return redirect('accounts:admin_user_detail', user_id=target_user.id)

        elif action == 'revoke_unlock':
            unlock_id = request.POST.get('unlock_id')
            unlock = get_object_or_404(ContentUnlock, id=unlock_id, user=target_user)
            item_title = unlock.content_item.title
            unlock.delete()
            messages.success(request, f"✓ Access to '{item_title}' revoked for {target_user.email}.")
            return redirect('accounts:admin_user_detail', user_id=target_user.id)

        elif action == 'toggle_status':
            if target_user == request.user:
                messages.error(request, "Safety alert: You cannot suspend your own account.")
            else:
                target_user.is_active = not target_user.is_active
                target_user.save()
                status_str = "activated" if target_user.is_active else "suspended"
                messages.success(request, f"Account for {target_user.email} has been {status_str}.")
            return redirect('accounts:admin_user_detail', user_id=target_user.id)

    user_unlocks = ContentUnlock.objects.filter(user=target_user).select_related('content_item', 'content_item__subject')
    user_transactions = CoinTransaction.objects.filter(wallet=target_wallet).order_by('-created_at')[:20]
    user_quizzes = QuizAttempt.objects.filter(student=target_user).select_related('quiz')[:10]

    return render(request, 'accounts/admin_user_detail.html', {
        'target_user': target_user,
        'target_wallet': target_wallet,
        'profile_form': profile_form,
        'password_form': password_form,
        'wallet_form': wallet_form,
        'grant_unlock_form': grant_unlock_form,
        'user_unlocks': user_unlocks,
        'user_transactions': user_transactions,
        'user_quizzes': user_quizzes,
    })


@user_passes_test(is_admin_or_staff)
def admin_user_create_view(request):
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            initial_coins = form.cleaned_data.get('initial_coins') or 0
            if initial_coins > 0:
                wallet, _ = StudentWallet.objects.get_or_create(user=new_user)
                wallet.credit_coins(initial_coins, description=f"Initial welcome allocation by {request.user.email}")
            messages.success(request, f"✓ Account for {new_user.email} successfully created!")
            return redirect('accounts:admin_user_detail', user_id=new_user.id)
    else:
        form = AdminUserCreateForm()

    return render(request, 'accounts/admin_user_create.html', {'form': form})


@user_passes_test(is_admin_or_staff)
def admin_user_delete_view(request, user_id):
    from django.shortcuts import get_object_or_404
    target_user = get_object_or_404(CustomUser, id=user_id)
    if target_user == request.user:
        messages.error(request, "Safety alert: You cannot delete your own account.")
        return redirect('accounts:admin_user_detail', user_id=user_id)

    if request.method == 'POST':
        email = target_user.email
        target_user.delete()
        messages.success(request, f"Account {email} has been permanently deleted.")
        return redirect('accounts:admin_user_list')

    return redirect('accounts:admin_user_detail', user_id=user_id)
