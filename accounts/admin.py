from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from wallet.models import StudentWallet, ContentUnlock


class StudentWalletInline(admin.StackedInline):
    model = StudentWallet
    can_delete = False
    extra = 0
    fields = ('coins', 'updated_at')
    readonly_fields = ('updated_at',)


class ContentUnlockInline(admin.TabularInline):
    model = ContentUnlock
    extra = 0
    fields = ('content_item', 'coins_spent', 'unlocked_at', 'expires_at')
    readonly_fields = ('unlocked_at',)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'phone_number', 'grade', 'curriculum', 'roles_display', 'is_staff', 'is_active')
    list_filter = ('is_student', 'is_tutor', 'is_admin_role', 'grade', 'curriculum', 'is_staff', 'is_active')
    ordering = ('email',)
    search_fields = ('email', 'full_name', 'phone_number')
    inlines = [StudentWalletInline, ContentUnlockInline]
    actions = ['activate_users', 'suspend_users', 'credit_50_coins']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number', 'grade', 'curriculum')}),
        ('Roles & Permissions', {'fields': (
            'is_student', 'is_tutor', 'is_admin_role',
            'is_active', 'is_staff', 'is_superuser',
            'groups', 'user_permissions'
        )}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password', 'is_student', 'is_tutor', 'is_admin_role', 'is_staff', 'is_superuser'),
        }),
    )

    @admin.action(description="✓ Activate selected accounts")
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} accounts successfully activated.")

    @admin.action(description="⚠ Suspend / Deactivate selected accounts")
    def suspend_users(self, request, queryset):
        safe_qs = queryset.exclude(id=request.user.id)
        count = safe_qs.update(is_active=False)
        self.message_user(request, f"{count} accounts suspended.")

    @admin.action(description="🪙 Credit +50 study coins to selected learners")
    def credit_50_coins(self, request, queryset):
        credited = 0
        for u in queryset:
            wallet, _ = StudentWallet.objects.get_or_create(user=u)
            wallet.credit_coins(50, description=f"Bulk Admin Credit by {request.user.email}")
            credited += 1
        self.message_user(request, f"Credited 50 coins to {credited} learner wallets.")
