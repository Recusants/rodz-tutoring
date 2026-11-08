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

    def credit_coins(self, amount, description="Manual Admin Credit", admin_user=None, transaction_type='ADMIN_CREDIT', counterparty=None):
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        self.coins += amount
        self.save()
        return CoinTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            created_by=admin_user,
            counterparty=counterparty
        )

    def debit_coins(self, amount, description="Content Unlock", admin_user=None, transaction_type='CONTENT_UNLOCK', counterparty=None):
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        if not self.can_afford(amount):
            raise ValueError("Insufficient coin balance")
        self.coins -= amount
        self.save()
        return CoinTransaction.objects.create(
            wallet=self,
            amount=-amount,
            transaction_type=transaction_type,
            description=description,
            created_by=admin_user,
            counterparty=counterparty
        )

    def transfer_coins_to(self, recipient_user, amount, note=""):
        """
        Instant peer-to-peer coin transfer without requiring admin approval.
        Atomically transfers coins from sender to recipient, and routes the
        applicable platform transfer fee to the System Wallet Treasury.
        """
        from django.db import transaction
        if amount <= 0:
            raise ValueError("Transfer amount must be at least 1 coin.")
        if recipient_user == self.user:
            raise ValueError("You cannot transfer coins to your own account.")

        system_wallet = SystemWallet.get_instance()
        fee = system_wallet.calculate_transfer_fee(amount)
        total_required = amount + fee

        if not self.can_afford(total_required):
            raise ValueError(
                f"Insufficient coin balance! Transferring {amount} coins requires a {fee} coin network fee "
                f"(Total: {total_required} coins). You currently have {self.coins} coins."
            )

        with transaction.atomic():
            recipient_wallet, _ = StudentWallet.objects.select_for_update().get_or_create(user=recipient_user)
            sender_wallet = StudentWallet.objects.select_for_update().get(id=self.id)
            if not sender_wallet.can_afford(total_required):
                raise ValueError(
                    f"Insufficient coin balance! Total required is {total_required} coins (Amount: {amount} + Fee: {fee}). "
                    f"You have {sender_wallet.coins} coins."
                )

            # Deduct amount + fee from sender
            sender_wallet.coins -= total_required
            sender_wallet.save()

            # Credit recipient with amount
            recipient_wallet.coins += amount
            recipient_wallet.save()

            # Credit System Wallet Treasury with fee
            system_wallet.collect_fee(
                amount=fee,
                description=f"P2P Transfer Fee: {amount} coins sent from {self.user.email} to {recipient_user.email}",
                source_user=self.user
            )

            sender_desc = f"Transfer to {recipient_user.full_name or recipient_user.email} (Fee: {fee} coins)"
            if note:
                sender_desc += f" [Note: {note}]"

            recipient_desc = f"Transfer from {self.user.full_name or self.user.email}"
            if note:
                recipient_desc += f" [Note: {note}]"

            tx_sender = CoinTransaction.objects.create(
                wallet=sender_wallet,
                amount=-total_required,
                transaction_type='TRANSFER_SENT',
                description=sender_desc,
                counterparty=recipient_user,
                created_by=self.user
            )

            tx_recipient = CoinTransaction.objects.create(
                wallet=recipient_wallet,
                amount=amount,
                transaction_type='TRANSFER_RECEIVED',
                description=recipient_desc,
                counterparty=self.user,
                created_by=self.user
            )

            # Sync current in-memory balance
            self.coins = sender_wallet.coins

            return tx_sender, tx_recipient


# CoinWallet alias for general wallet references across students, tutors, and staff
CoinWallet = StudentWallet


class SystemWallet(models.Model):
    name = models.CharField(max_length=120, default="Rodz Central System Treasury")
    coins = models.BigIntegerField(
        default=1000000, 
        help_text="Central coin reserves. Coins deducted when users buy, added when users sell or pay fees."
    )
    currency_code = models.CharField(
        max_length=10, 
        default="ZAR", 
        help_text="Standard currency code e.g. ZAR, USD, EUR, GBP"
    )
    currency_symbol = models.CharField(
        max_length=10, 
        default="R", 
        help_text="Display currency symbol e.g. R, $, €, £"
    )
    transfer_fee_coins = models.PositiveIntegerField(
        default=2, 
        help_text="Flat fee in coins charged per peer-to-peer transfer (credited to system wallet)"
    )
    transfer_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Optional percentage fee on peer transfers (0 = flat fee only)"
    )
    cashout_rate_per_coin = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0.8000,
        help_text="Redemption rate: currency payout per coin when selling/cashing out"
    )
    min_cashout_coins = models.PositiveIntegerField(
        default=50, 
        help_text="Minimum coins required to request cash-out / redemption"
    )
    total_coins_distributed = models.BigIntegerField(
        default=0, 
        help_text="Total coins bought/issued to users"
    )
    total_coins_redeemed = models.BigIntegerField(
        default=0, 
        help_text="Total coins sold back / cashed out by users"
    )
    total_fees_collected = models.BigIntegerField(
        default=0, 
        help_text="Total transfer and service fees accumulated"
    )
    total_creator_earnings_processed = models.BigIntegerField(
        default=0, 
        help_text="Total course unlock coins routed to course creators"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Wallet Treasury"
        verbose_name_plural = "System Wallet Treasury"

    def __str__(self):
        return f"{self.name} ({self.coins:,} Coins Pool | {self.currency_symbol} {self.currency_code})"

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(id=1, defaults={
            'name': 'Rodz Central System Treasury',
            'coins': 1000000,
            'currency_code': 'ZAR',
            'currency_symbol': 'R',
            'transfer_fee_coins': 2,
            'cashout_rate_per_coin': 0.8000,
            'min_cashout_coins': 50,
        })
        return obj

    def calculate_transfer_fee(self, amount):
        fee = self.transfer_fee_coins
        if self.transfer_fee_percentage > 0:
            pct_fee = int(round(amount * (float(self.transfer_fee_percentage) / 100.0)))
            fee = max(fee, pct_fee)
        return fee

    def deduct_for_purchase(self, buyer_wallet, amount, description, admin_user=None):
        """
        Deducts coins from the central system treasury and credits them to buyer_wallet.
        """
        self.coins = max(0, self.coins - amount)
        self.total_coins_distributed += amount
        self.save()
        return buyer_wallet.credit_coins(
            amount=amount,
            description=description,
            admin_user=admin_user,
            transaction_type='PAYMENT_APPROVED'
        )

    def add_from_sale(self, seller_wallet, amount, payout_amount=0, description="Coin Cash-out / Sale", user=None):
        """
        Deducts coins from user wallet and returns them to the central system treasury.
        """
        seller_wallet.debit_coins(
            amount=amount,
            description=description,
            transaction_type='COIN_SALE'
        )
        self.coins += amount
        self.total_coins_redeemed += amount
        self.save()

    def collect_fee(self, amount, description, source_user=None):
        """
        Collects transfer fee or platform commission into the system wallet.
        """
        if amount > 0:
            self.coins += amount
            self.total_fees_collected += amount
            self.save()


class CoinTransaction(models.Model):
    TYPE_CHOICES = [
        ('ADMIN_CREDIT', 'Admin Manual Credit'),
        ('PAYMENT_APPROVED', 'EFT / POP Approved Deposit'),
        ('CONTENT_UNLOCK', 'Resource Single Unlock'),
        ('COURSE_UNLOCK', 'Course Bundle Unlock'),
        ('CREATOR_EARNING', 'Course Creator Earning'),
        ('COURSE_FEE', 'Course Creation Deposit'),
        ('TRANSFER_SENT', 'Transfer Sent'),
        ('TRANSFER_RECEIVED', 'Transfer Received'),
        ('TRANSFER_FEE', 'Transfer Platform Fee'),
        ('COIN_SALE', 'Coins Sold / Cashed Out'),
        ('REFUND', 'Admin Refund'),
        ('BONUS', 'Promotional Bonus Coins'),
    ]

    wallet = models.ForeignKey(StudentWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.IntegerField(help_text="Positive for additions, negative for deductions")
    transaction_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='ADMIN_CREDIT')
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='issued_transactions',
        help_text="User or Admin who authorized this transaction"
    )
    counterparty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counterparty_transactions',
        help_text="Peer user in user-to-user coin transfers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.transaction_type}] {self.wallet.user.email}: {self.amount:+d} coins ({self.description})"

    @property
    def is_credit(self):
        return self.amount > 0

    @property
    def is_debit(self):
        return self.amount < 0

    @property
    def is_transfer(self):
        return self.transaction_type in ['TRANSFER_SENT', 'TRANSFER_RECEIVED'] or bool(self.counterparty)

    @property
    def formatted_amount(self):
        return f"+{self.amount}" if self.amount > 0 else f"{self.amount}"

    @property
    def get_clean_description(self):
        """
        Sanitizes description for non-admin viewers so that admin email addresses
        (e.g., 'Admin Credit by admin@example.com: Note') are never displayed.
        """
        import re
        desc = self.description or ""
        # Remove patterns like "Admin Credit by admin@...: " or "by admin@..."
        cleaned = re.sub(r'(?:Admin\s+(?:Credit|Debit)\s+)?by\s+[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+:\s*', '', desc, flags=re.I)
        cleaned = re.sub(r'\s*by\s+[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', cleaned, flags=re.I)
        return cleaned.strip() or desc


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


class CourseUnlock(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='unlocked_courses'
    )
    course = models.ForeignKey(
        'content_hub.Course', 
        on_delete=models.CASCADE, 
        related_name='unlocked_by_users'
    )
    coins_spent = models.PositiveIntegerField(default=0)
    unlocked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Expiry date for course retention (defaults to end of academic school year)"
    )

    class Meta:
        unique_together = ('user', 'course')
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
        return f"{self.user.email} unlocked course '{self.course.title}' ({self.coins_spent} coins) [{status}]"


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

    @property
    def rate_per_coin(self):
        if self.coins and self.coins > 0:
            return round(self.price_zar / self.coins, 4)
        return 0

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
    rate_per_coin = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0.0000, 
        help_text="Historical rate in ZAR per coin frozen at purchase time"
    )
    bundle_name_snapshot = models.CharField(
        max_length=120, 
        blank=True, 
        help_text="Frozen bundle title at purchase time"
    )
    bundle_price_snapshot = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        help_text="Frozen bundle price at purchase time"
    )
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

    def save(self, *args, **kwargs):
        if self.bundle and not self.bundle_name_snapshot:
            self.bundle_name_snapshot = self.bundle.name
        if self.bundle and (not self.bundle_price_snapshot or self.bundle_price_snapshot == 0):
            self.bundle_price_snapshot = self.bundle.price_zar
        if self.coins_to_credit and self.amount_paid:
            self.rate_per_coin = round(self.amount_paid / self.coins_to_credit, 4)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Request #{self.id} - {self.student.email} ({self.coins_to_credit} coins @ R{self.rate_per_coin}/coin) [{self.status}]"


class CoinPriceChangeLog(models.Model):
    bundle = models.ForeignKey(
        CoinBundle, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='price_logs'
    )
    bundle_name = models.CharField(max_length=120)
    coins = models.PositiveIntegerField(help_text="Coins in bundle at time of price change")
    old_price_zar = models.DecimalField(max_digits=10, decimal_places=2)
    new_price_zar = models.DecimalField(max_digits=10, decimal_places=2)
    old_rate_per_coin = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    new_rate_per_coin = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='coin_price_changes',
        help_text="Admin who adjusted the price"
    )
    change_reason = models.CharField(max_length=255, blank=True, help_text="Reason for price adjustment")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.bundle_name}] R{self.old_price_zar} -> R{self.new_price_zar} by {self.changed_by}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_wallet(sender, instance, **kwargs):
    StudentWallet.objects.get_or_create(user=instance)

