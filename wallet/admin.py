from django.contrib import admin
from decimal import Decimal
from .models import (
    StudentWallet, CoinTransaction, ContentUnlock, CourseUnlock, 
    PaymentMethod, CoinBundle, CoinPaymentRequest, CoinPriceChangeLog
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('title', 'bank_name', 'account_number', 'account_holder', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('title', 'bank_name', 'account_number')


@admin.register(CoinBundle)
class CoinBundleAdmin(admin.ModelAdmin):
    list_display = ('name', 'coins', 'price_zar', 'rate_per_coin_display', 'badge', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('name',)

    def rate_per_coin_display(self, obj):
        if obj.coins:
            return f"R{round(obj.price_zar / obj.coins, 4)}/c"
        return "R0.00/c"
    rate_per_coin_display.short_description = "Rate / Coin"

    def save_model(self, request, obj, form, change):
        if change and 'price_zar' in form.changed_data:
            old_price = form.initial.get('price_zar', obj.price_zar)
            old_rate = round(old_price / obj.coins, 4) if obj.coins else Decimal('0.0000')
            new_rate = round(obj.price_zar / obj.coins, 4) if obj.coins else Decimal('0.0000')
            CoinPriceChangeLog.objects.create(
                bundle=obj,
                bundle_name=obj.name,
                coins=obj.coins,
                old_price_zar=old_price,
                new_price_zar=obj.price_zar,
                old_rate_per_coin=old_rate,
                new_rate_per_coin=new_rate,
                changed_by=request.user,
                change_reason="Django Admin Change"
            )
        super().save_model(request, obj, form, change)


@admin.register(CoinPriceChangeLog)
class CoinPriceChangeLogAdmin(admin.ModelAdmin):
    list_display = ('bundle_name', 'coins', 'old_price_zar', 'new_price_zar', 'old_rate_per_coin', 'new_rate_per_coin', 'changed_by', 'created_at')
    list_filter = ('bundle', 'created_at')
    search_fields = ('bundle_name', 'change_reason', 'changed_by__email')
    readonly_fields = ('bundle', 'bundle_name', 'coins', 'old_price_zar', 'new_price_zar', 'old_rate_per_coin', 'new_rate_per_coin', 'changed_by', 'change_reason', 'created_at')


@admin.register(CoinPaymentRequest)
class CoinPaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'bundle', 'coins_to_credit', 'amount_paid', 'rate_per_coin', 'reference_number', 'status', 'created_at')
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
    list_display = ('user', 'content_item', 'coins_spent', 'unlocked_at', 'expires_at')
    list_filter = ('unlocked_at', 'expires_at')
    search_fields = ('user__email', 'content_item__title')


@admin.register(CourseUnlock)
class CourseUnlockAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'coins_spent', 'unlocked_at', 'expires_at')
    list_filter = ('unlocked_at', 'expires_at')
    search_fields = ('user__email', 'course__title')

