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


class AboutContent(models.Model):
    eyebrow = models.CharField(max_length=120, default='OUR HERITAGE & MISSION')
    heading = models.CharField(max_length=255, default='EMPOWERING ACADEMIC EXCELLENCE')
    subheading = models.CharField(max_length=255, default='Providing high-impact, curriculum-aligned academic support for Grades 7 to 12.')
    story_title = models.CharField(max_length=255, default='Dedicated to building confidence, mastery, and top marks.')
    story_paragraph_1 = models.TextField(
        default="At Rodz Tutoring, we believe that every student has the capacity to grasp difficult subjects when taught with patience, clarity, and systematic problem-solving methods."
    )
    story_paragraph_2 = models.TextField(
        default="Whether a learner is struggling with foundational algebra, technical physical sciences, or advanced accounting principles, our curriculum-specialized tutors provide the exact scaffolding needed to transform marks from 40% to 80%+."
    )
    pillars_title = models.CharField(max_length=255, default='The Rodz Standard')
    pillars_content = models.TextField(
        default="Qualified & Vetted Tutors: Specialists in CAPS, IEB, and Cambridge curricula.\nExam-Oriented Pedagogy: Real past-paper dissecting and examiner guidance.\nNon-Downloadable Secure Portal: Premium study notes, worked video solutions, and quizzes.\nFlexible Online Delivery: Safe, live interactive classes right from your home.",
        help_text="One bullet point per line or colon-separated bold prefix."
    )
    stat_students = models.CharField(max_length=50, default='500+', help_text="e.g. 500+")
    stat_pass_rate = models.CharField(max_length=50, default='95%', help_text="e.g. 95%")
    stat_papers = models.CharField(max_length=50, default='1000+', help_text="e.g. 1000+")
    stat_hours = models.CharField(max_length=50, default='2000+', help_text="e.g. 2000+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'About Page Content'
        verbose_name_plural = 'About Page Content'

    def __str__(self):
        return f"About Content (Updated: {self.updated_at.strftime('%Y-%m-%d') if self.updated_at else 'Initial'})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class ContactInfo(models.Model):
    phone_number = models.CharField(max_length=60, default='+27 74 568 5212', help_text="Display phone e.g. +27 74 568 5212")
    whatsapp_number = models.CharField(max_length=30, default='27745685212', help_text="Numeric country code format for wa.me links, e.g. 27745685212")
    email_address = models.EmailField(default='info@rodztutoring.co.za', help_text="Primary public inquiry email")
    support_email = models.EmailField(default='support@rodztutoring.co.za', help_text="Technical & student support email")
    physical_address = models.CharField(max_length=255, default='Johannesburg, South Africa & Worldwide Online')
    operating_hours = models.CharField(max_length=120, default='Mon – Sun: 07:00 – 21:00')
    whatsapp_community_url = models.URLField(blank=True, default='https://chat.whatsapp.com/sample', help_text="Invite link to free student WhatsApp community")
    contact_notice = models.TextField(
        default="Our academic advisory team responds within 15 minutes during operating hours. WhatsApp inquiries receive priority same-day response.",
        blank=True
    )
    facebook_url = models.URLField(blank=True, default='https://facebook.com')
    instagram_url = models.URLField(blank=True, default='https://instagram.com')
    linkedin_url = models.URLField(blank=True, default='https://linkedin.com')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contact & Support Info'
        verbose_name_plural = 'Contact & Support Info'

    def __str__(self):
        return f"Contact Info ({self.phone_number})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class HowToGuide(models.Model):
    title = models.CharField(max_length=200, default='How Rodz Tutoring Works')
    slug = models.SlugField(max_length=220, unique=True, default='how-it-works')
    badge_text = models.CharField(max_length=60, default='STUDENT ONBOARDING GUIDE')
    subtitle = models.TextField(default='Follow this simple step-by-step guide to get enrolled, acquire study coins, unlock non-downloadable materials, and excel in exams.')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


class HowToStep(models.Model):
    guide = models.ForeignKey(HowToGuide, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveIntegerField(default=1)
    badge = models.CharField(max_length=40, default='STEP 1')
    title = models.CharField(max_length=200)
    icon_class = models.CharField(max_length=80, default='fa-solid fa-user-plus', help_text="FontAwesome icon class e.g. fa-solid fa-coins, fa-solid fa-book-open")
    description = models.TextField()
    call_to_action_text = models.CharField(max_length=100, blank=True, help_text="e.g. Enrol Free, Buy Coins, View Packs")
    call_to_action_url = models.CharField(max_length=255, blank=True, help_text="Relative or absolute URL e.g. /accounts/register/ or /wallet/buy-coins/")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'step_number']

    def __str__(self):
        return f"Step {self.step_number}: {self.title}"


