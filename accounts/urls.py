from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('system-settings/', views.admin_system_settings_view, name='system_settings'),

    # Password Recovery Flow
    path('password-reset/', views.RodzPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.RodzPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.RodzPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', views.RodzPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
