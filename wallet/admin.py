from django.contrib import admin
from .models import StudentWallet, CoinTransaction, ContentUnlock


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
