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
