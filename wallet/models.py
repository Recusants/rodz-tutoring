from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import datetime


class StudentWallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='wallet'
    )
    coins = models.PositiveIntegerField(
        default=0, 
        help_text="Current available coin balance for unlocking premium content"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email}'s Wallet ({self.coins} Coins)"

    def can_afford(self, amount):
        return self.coins >= amount

    def credit_coins(self, amount, description="Manual Admin Credit", admin_user=None):
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        self.coins += amount
        self.save()
        CoinTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='ADMIN_CREDIT',
            description=description,
            created_by=admin_user
        )

    def debit_coins(self, amount, description="Content Unlock"):
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        if not self.can_afford(amount):
            raise ValueError("Insufficient coin balance")
        self.coins -= amount
        self.save()
        CoinTransaction.objects.create(
            wallet=self,
            amount=-amount,
            transaction_type='CONTENT_UNLOCK',
            description=description
        )


class CoinTransaction(models.Model):
    TYPE_CHOICES = [
        ('ADMIN_CREDIT', 'Admin Manual Credit (WhatsApp/Cash)'),
        ('CONTENT_UNLOCK', 'Resource Unlock Debit'),
        ('REFUND', 'Admin Refund'),
        ('BONUS', 'Promotional Bonus Coins'),
    ]

    wallet = models.ForeignKey(StudentWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.IntegerField(help_text="Positive for additions, negative for deductions")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='ADMIN_CREDIT')
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='issued_transactions',
        help_text="Admin user who authorized this transaction"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.transaction_type}] {self.wallet.user.email}: {self.amount:+d} coins ({self.description})"


def calculate_academic_year_expiry():
    now = timezone.now()
    target_year = now.year if now.month < 10 else now.year + 1
    return timezone.make_aware(
        datetime.datetime(target_year, 12, 31, 23, 59, 59)
    )


class ContentUnlock(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='unlocked_resources'
    )
    content_item = models.ForeignKey(
        'content_hub.ContentItem', 
        on_delete=models.CASCADE, 
        related_name='unlocked_by_users'
    )
    coins_spent = models.PositiveIntegerField(default=0)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Expiry date for content retention (defaults to end of academic school year)"
    )

    class Meta:
        unique_together = ('user', 'content_item')
        ordering = ['-unlocked_at']

    @property
    def is_active(self):
        if not self.expires_at:
            return True
        return timezone.now() <= self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = calculate_academic_year_expiry()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Expired"
        return f"{self.user.email} unlocked '{self.content_item.title}' ({self.coins_spent} coins) [{status}]"


class PaymentMethod(models.Model):
    title = models.CharField(max_length=120, help_text="e.g. FNB Bank EFT, Standard Bank, Capitec, e-Wallet")
    bank_name = models.CharField(max_length=100, blank=True)
    account_holder = models.CharField(max_length=120, default="Rodz Tutoring")
    account_number = models.CharField(max_length=60)
    branch_code = models.CharField(max_length=40, blank=True, default="250655")
    account_type = models.CharField(max_length=50, default="Cheque / Current")
    reference_instructions = models.CharField(
        max_length=255, 
        default="Use your Student Email or WhatsApp Phone as payment reference."
    )
    additional_notes = models.TextField(blank=True, help_text="Any additional deposit instructions")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.title} ({self.account_number})"


class CoinBundle(models.Model):
    name = models.CharField(max_length=100)
    coins = models.PositiveIntegerField(help_text="Coins granted on activation")
    price_zar = models.DecimalField(max_digits=8, decimal_places=2, help_text="Price in ZAR")
    badge = models.CharField(max_length=50, blank=True, default="POPULAR")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'price_zar']

    def __str__(self):
        return f"{self.name} - {self.coins} Coins (R{self.price_zar})"


class CoinPaymentRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('APPROVED', 'Approved & Credited'),
        ('REJECTED', 'Declined'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coin_requests')
    bundle = models.ForeignKey(CoinBundle, null=True, blank=True, on_delete=models.SET_NULL, related_name='requests')
    payment_method = models.ForeignKey(PaymentMethod, null=True, blank=True, on_delete=models.SET_NULL, related_name='requests')
    coins_to_credit = models.PositiveIntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    reference_number = models.CharField(max_length=120, help_text="Payment transaction ID or deposit reference")
    proof_of_payment = models.FileField(upload_to='payment_proofs/', help_text="Receipt screenshot or PDF")
    student_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='reviewed_coin_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request #{self.id} - {self.student.email} ({self.coins_to_credit} coins) [{self.status}]"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        StudentWallet.objects.get_or_create(user=instance)
