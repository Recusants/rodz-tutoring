from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('buy-coins/', views.buy_coins_view, name='buy_coins'),
    path('unlock/<slug:item_slug>/', views.unlock_item_view, name='unlock_item'),
    path('unlock-course/<slug:course_slug>/', views.unlock_course_view, name='unlock_course'),
    path('admin-credits/', views.admin_credit_panel_view, name='admin_credit_panel'),
    path('payment-requests/', views.admin_payment_requests_view, name='admin_payment_requests'),
]
