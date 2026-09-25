from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'phone_number', 'grade', 'curriculum', 'roles_display', 'is_staff', 'is_active')
    list_filter = ('is_student', 'is_tutor', 'is_admin_role', 'grade', 'curriculum', 'is_staff', 'is_active')
    ordering = ('email',)
    search_fields = ('email', 'full_name', 'phone_number')

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
