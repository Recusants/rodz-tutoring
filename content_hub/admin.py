from django.contrib import admin
from .models import Subject, ContentItem, Curriculum, Course


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon_symbol', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'grade', 'curriculum', 'content_type', 'category', 'is_free', 'allow_download', 'coin_price', 'created_at')
    list_filter = ('curriculum', 'subject', 'grade', 'content_type', 'category', 'is_free', 'allow_download')
    list_editable = ('is_free', 'allow_download')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'subject', 'grade', 'curriculum', 'bundle_price', 'status', 'created_at')
    list_filter = ('status', 'curriculum', 'subject', 'grade')
    search_fields = ('title', 'creator__email', 'creator__full_name', 'description')
    filter_horizontal = ('items',)
    prepopulated_fields = {'slug': ('title',)}
    actions = ['approve_courses', 'reject_courses']

    def approve_courses(self, request, queryset):
        for course in queryset:
            course.status = 'APPROVED'
            course.reviewed_by = request.user
            course.save()
        self.message_user(request, f"{queryset.count()} course(s) approved and published.")
    approve_courses.short_description = "Approve selected course bundles"

    def reject_courses(self, request, queryset):
        for course in queryset:
            if course.status == 'PENDING':
                course.status = 'REJECTED'
                course.reviewed_by = request.user
                course.admin_notes = "Rejected by administrator."
                course.save()
                # Refund tutor
                if hasattr(course.creator, 'wallet') and course.creation_fee_coins > 0:
                    course.creator.wallet.credit_coins(
                        course.creation_fee_coins,
                        description=f"Course Submission Refund: {course.title}",
                        admin_user=request.user
                    )
        self.message_user(request, f"{queryset.count()} course(s) rejected and creation fees refunded.")
    reject_courses.short_description = "Reject selected course bundles and refund coins"


from .models import AboutContent, ContactInfo, HowToGuide, HowToStep


@admin.register(AboutContent)
class AboutContentAdmin(admin.ModelAdmin):
    list_display = ('heading', 'eyebrow', 'stat_students', 'stat_pass_rate', 'updated_at')


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'whatsapp_number', 'email_address', 'operating_hours', 'updated_at')


class HowToStepInline(admin.TabularInline):
    model = HowToStep
    extra = 1
    fields = ('step_number', 'badge', 'title', 'icon_class', 'description', 'call_to_action_text', 'call_to_action_url', 'order')


@admin.register(HowToGuide)
class HowToGuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge_text', 'slug', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    inlines = [HowToStepInline]


@admin.register(HowToStep)
class HowToStepAdmin(admin.ModelAdmin):
    list_display = ('guide', 'step_number', 'title', 'badge', 'icon_class', 'order')
    list_filter = ('guide',)

