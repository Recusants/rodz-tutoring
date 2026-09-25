from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    class Meta:
        unique_together = ('user', 'content_item')
        ordering = ['-unlocked_at']

    def __str__(self):
        return f"{self.user.email} unlocked '{self.content_item.title}' ({self.coins_spent} coins)"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        StudentWallet.objects.get_or_create(user=instance)
