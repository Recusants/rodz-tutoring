from django.urls import path
from . import views
from content_hub import views as content_views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('switch-mode/<str:mode>/', views.switch_mode_view, name='switch_mode'),
    path('system-settings/', views.admin_system_settings_view, name='system_settings'),

    # Tutor Application & Admin Review
    path('tutor-apply/', views.tutor_apply_view, name='tutor_apply'),
    path('admin/tutor-approvals/', views.admin_tutor_approvals_view, name='admin_tutor_approvals'),

    # Admin Total Account Control & CMS
    path('admin/users/', views.admin_user_list_view, name='admin_user_list'),
    path('admin/users/create/', views.admin_user_create_view, name='admin_user_create'),
    path('admin/users/<int:user_id>/', views.admin_user_detail_view, name='admin_user_detail'),
    path('admin/users/<int:user_id>/delete/', views.admin_user_delete_view, name='admin_user_delete'),
    path('admin/site-content/', content_views.admin_site_content_view, name='admin_site_content'),

    # Password Recovery Flow
    path('password-reset/', views.RodzPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.RodzPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.RodzPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', views.RodzPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
