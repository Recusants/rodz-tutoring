from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
import re


class Curriculum(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Curricula'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    icon_symbol = models.CharField(max_length=20, default='▤', help_text="Symbol or icon e.g. √x, ⚛, ▣")
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ContentItem(models.Model):
    TYPE_CHOICES = [
        ('PDF', 'Protected PDF Study Pack'),
        ('VIDEO', 'In-App YouTube Stream'),
        ('QUIZ', 'Interactive Assessment Quiz'),
    ]

    CATEGORY_CHOICES = [
        ('Notes', 'Notes & Theory'),
        ('Past Papers', 'Past Examination Papers'),
        ('Worksheets', 'Topic Worksheets & Solutions'),
        ('Study Guides', 'Comprehensive Study Guides'),
        ('Video Lessons', 'Video Lessons'),
        ('Exam Prep', 'Intensive Exam Preparation'),
        ('Quiz', 'Interactive Quiz'),
    ]

    GRADE_CHOICES = [
        ('Grade 7', 'Grade 7'),
        ('Grade 8', 'Grade 8'),
        ('Grade 9', 'Grade 9'),
        ('Grade 10', 'Grade 10'),
        ('Grade 11', 'Grade 11'),
        ('Grade 12', 'Grade 12'),
        ('All Grades', 'All Grades (General)'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='content_items')
    curriculum = models.CharField(max_length=80, default='CAPS & IEB', help_text="Curriculum programme e.g. Cambridge, CAPS, IEB, IB, etc.")
    curriculum_ref = models.ForeignKey(Curriculum, on_delete=models.SET_NULL, null=True, blank=True, related_name='content_items')
    grade = models.CharField(max_length=30, choices=GRADE_CHOICES, default='Grade 12')
    content_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='PDF')
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default='Notes')
    description = models.TextField(blank=True)
    
    # Visual Cover
    cover_svg_name = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Name of SVG cover in static/assets/resource-covers/ (e.g. 'caps-g12-maths.svg')"
    )

    # Monetization / Coins
    is_free = models.BooleanField(default=False, help_text="If True, any student can view without spending coins")
    coin_price = models.PositiveIntegerField(
        default=50, 
        help_text="Amount of coins required to permanently unlock this resource"
    )

    # Content files / links
    pdf_file = models.FileField(
        upload_to='protected_pdfs/', 
        blank=True, 
        null=True, 
        help_text="Protected PDF stored securely away from public direct download"
    )
    youtube_url = models.URLField(
        blank=True, 
        null=True, 
        help_text="YouTube video link for streaming inside the app (e.g. https://www.youtube.com/watch?v=...)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.grade}-{self.subject.name}-{self.title}")[:250]
            self.slug = base_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.grade} - {self.subject.name}] {self.title} ({self.content_type})"

    @property
    def youtube_embed_id(self):
        if not self.youtube_url:
            return ""
        # Match standard youtube watch URLs or short links
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", self.youtube_url)
        return match.group(1) if match else ""

    @property
    def is_locked_by_default(self):
        return not self.is_free and self.coin_price > 0


class Course(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Admin Approval'),
        ('APPROVED', 'Approved & Published'),
        ('REJECTED', 'Rejected'),
    ]

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_courses',
        help_text="Tutor or Admin who organized this course bundle"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='courses')
    curriculum = models.CharField(max_length=80, default='CAPS & IEB', help_text="Curriculum programme e.g. Cambridge, CAPS, IEB, IB")
    curriculum_ref = models.ForeignKey(Curriculum, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    grade = models.CharField(max_length=30, choices=ContentItem.GRADE_CHOICES, default='Grade 12')
    description = models.TextField(blank=True, help_text="What will students master in this course bundle?")
    cover_svg_name = models.CharField(
        max_length=100, 
        blank=True, 
        default='caps-g12-maths.svg',
        help_text="Name of SVG cover in static/assets/resource-covers/"
    )

    # Bundled resources (Videos, PDFs, Quizzes)
    items = models.ManyToManyField(
        ContentItem, 
        related_name='courses', 
        blank=True,
        help_text="Single items included in this bundle (can also be bought individually)"
    )

    # Monetization
    bundle_price = models.PositiveIntegerField(
        default=120,
        help_text="Selling price in coins set by the tutor for this complete bundle"
    )
    creation_fee_coins = models.PositiveIntegerField(
        default=50,
        help_text="Coins required from tutor wallet to submit course for approval"
    )

    # Admin Review Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True, help_text="Admin review feedback or reason if rejected")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_courses'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"course-{self.grade}-{self.subject.name}-{self.title}")[:250]
            self.slug = base_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.grade} - {self.subject.name}] {self.title} ({self.bundle_price} coins) [{self.status}]"

    def get_pricing_for_user(self, user=None):
        """
        Dynamic bundle pricing:
        If items in the bundle have already been unlocked by the student (or are free),
        their individual values are subtracted from the course bundle price!
        Formula: max(0, bundle_price - sum(value_of_already_owned_items))
        """
        total_items = self.items.count()
        if not user or not user.is_authenticated:
            return {
                'original_bundle_price': self.bundle_price,
                'owned_items_count': 0,
                'total_items_count': total_items,
                'owned_items_value': 0,
                'final_price': self.bundle_price,
                'is_fully_owned': False,
                'owned_item_ids': set(),
            }

        # Check if user already unlocked the course itself
        from wallet.models import CourseUnlock, ContentUnlock
        now = timezone.now()
        course_unlock = CourseUnlock.objects.filter(
            user=user, 
            course=self
        ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)).first()

        if course_unlock:
            return {
                'original_bundle_price': self.bundle_price,
                'owned_items_count': total_items,
                'total_items_count': total_items,
                'owned_items_value': self.bundle_price,
                'final_price': 0,
                'is_fully_owned': True,
                'owned_item_ids': set(self.items.values_list('id', flat=True)),
            }

        # Check individual item unlocks
        bundle_item_ids = list(self.items.values_list('id', flat=True))
        active_item_unlocks = ContentUnlock.objects.filter(
            user=user,
            content_item_id__in=bundle_item_ids
        ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=now)).values_list('content_item_id', flat=True)

        owned_item_ids = set(active_item_unlocks)
        free_item_ids = set(self.items.filter(is_free=True).values_list('id', flat=True))
        owned_item_ids.update(free_item_ids)

        owned_items = self.items.filter(id__in=owned_item_ids)
        owned_items_value = sum(item.coin_price for item in owned_items if not item.is_free)

        # Dynamic Discount calculation:
        final_price = max(0, self.bundle_price - owned_items_value)
        is_fully_owned = (len(owned_item_ids) >= total_items) if total_items > 0 else False

        return {
            'original_bundle_price': self.bundle_price,
            'owned_items_count': len(owned_item_ids),
            'total_items_count': total_items,
            'owned_items_value': owned_items_value,
            'final_price': final_price,
            'is_fully_owned': is_fully_owned,
            'owned_item_ids': owned_item_ids,
        }

