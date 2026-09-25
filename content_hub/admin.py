from django.contrib import admin
from .models import Subject, ContentItem


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon_symbol', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'grade', 'curriculum', 'content_type', 'category', 'is_free', 'coin_price', 'created_at')
    list_filter = ('subject', 'grade', 'curriculum', 'content_type', 'category', 'is_free')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
