from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('buy-coins/', views.buy_coins_view, name='buy_coins'),
    path('unlock/<slug:item_slug>/', views.unlock_item_view, name='unlock_item'),
    path('unlock-course/<slug:course_slug>/', views.unlock_course_view, name='unlock_course'),
    path('history/', views.coin_history_view, name='coin_history'),
    path('transactions/', views.coin_history_view, name='transactions'),
    path('transfer/', views.transfer_coins_view, name='transfer_coins'),
    path('sell/', views.sell_coins_view, name='sell_coins'),
    path('admin/pricing/', views.admin_coin_pricing_view, name='admin_pricing'),
    path('admin-credits/', views.admin_credit_panel_view, name='admin_credit_panel'),
    path('payment-requests/', views.admin_payment_requests_view, name='admin_payment_requests'),
]
