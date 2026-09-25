from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
def dashboard_view(request):
    user = request.user
    wallet, _ = StudentWallet.objects.get_or_create(user=user)

    # Student Data
    unlocked_records = ContentUnlock.objects.filter(user=user).select_related('content_item', 'content_item__subject')
    recent_transactions = CoinTransaction.objects.filter(wallet=wallet)[:8]
    quiz_attempts = QuizAttempt.objects.filter(student=user).select_related('quiz', 'quiz__content_item')[:6]

    # Tutor Data (if tutor role enabled)
    tutor_content_count = 0
    if user.is_tutor:
        tutor_content_count = ContentItem.objects.count()

    context = {
        'user': user,
        'wallet': wallet,
        'unlocked_records': unlocked_records,
        'recent_transactions': recent_transactions,
        'quiz_attempts': quiz_attempts,
        'tutor_content_count': tutor_content_count,
    }
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
