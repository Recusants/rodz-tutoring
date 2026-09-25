from django.db import models
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
