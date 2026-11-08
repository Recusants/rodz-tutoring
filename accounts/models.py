from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin_role', True)
        extra_fields.setdefault('is_tutor', True)
        extra_fields.setdefault('tutor_status', 'APPROVED')
        extra_fields.setdefault('is_student', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    GRADE_CHOICES = [
        ('Grade 7', 'Grade 7'),
        ('Grade 8', 'Grade 8'),
        ('Grade 9', 'Grade 9'),
        ('Grade 10', 'Grade 10'),
        ('Grade 11', 'Grade 11'),
        ('Grade 12', 'Grade 12'),
        ('Alumni/Other', 'Alumni / Other'),
    ]

    CURRICULUM_CHOICES = [
        ('CAPS', 'CAPS'),
        ('IEB', 'IEB'),
        ('Cambridge', 'Cambridge'),
        ('Combined', 'Combined / Other'),
    ]

    TUTOR_STATUS_CHOICES = [
        ('NONE', 'Not Applied'),
        ('PENDING', 'Pending Admin Review'),
        ('APPROVED', 'Approved Tutor'),
        ('REJECTED', 'Application Rejected'),
    ]

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=30, blank=True, help_text="WhatsApp contact number")
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES, default='Grade 12', blank=True)
    curriculum = models.CharField(max_length=20, choices=CURRICULUM_CHOICES, default='CAPS', blank=True)

    # Roles - can be single or any combination!
    is_student = models.BooleanField(default=True, help_text="Designates whether the user has student access")
    is_tutor = models.BooleanField(default=False, help_text="Designates whether the user can tutor and manage student content")
    is_admin_role = models.BooleanField(default=False, help_text="Designates whether the user has staff admin operational access")

    # Tutor application & review fields
    profile_picture = models.ImageField(upload_to='tutor_profiles/', blank=True, null=True, help_text="Profile picture for tutors/applicants")
    bio = models.TextField(blank=True, help_text="Tutor biography, subjects taught, or qualifications")
    tutor_status = models.CharField(max_length=20, choices=TUTOR_STATUS_CHOICES, default='NONE', blank=True, db_index=True)
    tutor_applied_at = models.DateTimeField(null=True, blank=True)
    tutor_approved_at = models.DateTimeField(null=True, blank=True)
    tutor_rejection_reason = models.TextField(blank=True)
    tutor_reviewed_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_tutors')

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.full_name or 'No Name'})"

    @property
    def roles_display(self):
        roles = []
        if self.is_admin_role or self.is_superuser:
            roles.append('Admin')
        if self.is_tutor:
            roles.append('Tutor')
        if self.is_student:
            roles.append('Student')
        return ", ".join(roles) if roles else "Standard User"

    def has_unlocked(self, content_item):
        if not self.is_authenticated:
            return False
        if content_item.is_free or self.is_tutor or self.is_admin_role or self.is_staff or self.is_superuser:
            return True
        from wallet.models import ContentUnlock
        unlock = ContentUnlock.objects.filter(user=self, content_item=content_item).first()
        if unlock and unlock.is_active:
            return True
        return False

    @property
    def available_roles(self):
        roles = []
        if self.is_admin_role or self.is_staff or self.is_superuser:
            roles.append('admin')
        if self.is_tutor:
            roles.append('tutor')
        if self.is_student:
            roles.append('student')
        return roles

    @property
    def has_multiple_roles(self):
        return len(self.available_roles) > 1

    @property
    def default_role_mode(self):
        roles = self.available_roles
        if not roles:
            return 'student'
        if 'admin' in roles:
            return 'admin'
        if 'tutor' in roles:
            return 'tutor'
        return 'student'

    def get_active_mode(self, request):
        if not self.is_authenticated:
            return 'student'
        roles = self.available_roles
        if not roles:
            return 'student'
        if len(roles) == 1:
            return roles[0]
        mode = request.session.get('active_role_mode')
        if mode in roles:
            return mode
        default_mode = self.default_role_mode
        request.session['active_role_mode'] = default_mode
        return default_mode
