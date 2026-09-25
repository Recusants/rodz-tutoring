from django.contrib import admin
from .models import StudentWallet, CoinTransaction, ContentUnlock, PaymentMethod, CoinBundle, CoinPaymentRequest


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('title', 'bank_name', 'account_number', 'account_holder', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('title', 'bank_name', 'account_number')


@admin.register(CoinBundle)
class CoinBundleAdmin(admin.ModelAdmin):
    list_display = ('name', 'coins', 'price_zar', 'badge', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('name',)


@admin.register(CoinPaymentRequest)
class CoinPaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'bundle', 'coins_to_credit', 'amount_paid', 'reference_number', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('student__email', 'reference_number')


@admin.register(StudentWallet)
class StudentWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'coins', 'updated_at')
    search_fields = ('user__email', 'user__full_name')


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'amount', 'transaction_type', 'description', 'created_by', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('wallet__user__email', 'description')


@admin.register(ContentUnlock)
class ContentUnlockAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_item', 'coins_spent', 'unlocked_at')
    list_filter = ('unlocked_at',)
    search_fields = ('user__email', 'content_item__title')
