# payments/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid
import hashlib

User = get_user_model()


class Purchase(models.Model):
    """Model for book purchases by users"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('telebirr', 'Telebirr'),
        ('chapa', 'Chapa'),
        ('paypal', 'PayPal'),
        ('cbe', 'CBE Birr'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='purchases',
        help_text="User who made the purchase"
    )
    book = models.ForeignKey(
        'books.Book', 
        on_delete=models.CASCADE, 
        related_name='purchases',
        help_text="Book that was purchased"
    )
    
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Purchase amount"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Purchase status"
    )
    
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        default='telebirr',
        help_text="Payment method used"
    )
    
    # Transaction fields - all allow NULL
    transaction_id = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Unique transaction ID"
    )
    
    transaction_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        default=None,
        help_text="External transaction reference"
    )
    
    purchase_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        default=None,
        help_text="Purchase reference"
    )
    
    completed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the purchase was completed"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the purchase was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the purchase was last updated"
    )
    
    class Meta:
        db_table = 'purchases'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['book', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['purchase_reference']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Purchase #{self.id} - {self.book.title} by {self.user.username}"
    
    def save(self, *args, **kwargs):
        # Generate transaction_id if not set
        if not self.transaction_id:
            self.transaction_id = f"PUR-{uuid.uuid4().hex[:12].upper()}"
        
        # Set empty strings to None
        if self.transaction_reference == '':
            self.transaction_reference = None
        if self.purchase_reference == '':
            self.purchase_reference = None
        
        super().save(*args, **kwargs)
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_pending(self):
        return self.status == 'pending'


class Payment(models.Model):
    """Model for author payments (royalties)"""
    STATUS_CHOICES = (
        ('calculated', 'Calculated'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    book = models.ForeignKey(
        'books.Book', 
        on_delete=models.CASCADE, 
        related_name='payments',
        help_text="Book that generated the payment"
    )
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='payments',
        help_text="Author receiving the payment"
    )
    purchase = models.ForeignKey(
        Purchase, 
        on_delete=models.CASCADE, 
        related_name='payments',
        null=True, 
        blank=True,
        help_text="Purchase that generated this payment"
    )
    
    # Amount breakdown
    gross_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Gross purchase amount"
    )
    author_royalty = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Author's royalty amount (before tax)"
    )
    abrehot_share = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Abrehot platform share"
    )
    abrehot_share_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=30.00,
        help_text="Abrehot share percentage"
    )
    royalty_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=70.00,
        help_text="Author royalty percentage"
    )
    
    # Tax
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Tax rate applied (5% culture, 10% other)"
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Tax amount withheld"
    )
    is_taxable = models.BooleanField(
        default=False,
        help_text="Whether tax was applied"
    )
    
    # Final amount
    final_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Final amount to be paid to author (after tax)"
    )
    
    # Status and tracking
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='calculated',
        help_text="Payment status"
    )
    
    transaction_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="External transaction reference"
    )
    
    paid_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the payment was made"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the payment was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the payment was last updated"
    )
    
    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['book']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment #{self.id} - {self.author.username} - {self.final_amount} ETB"


class PaymentBatch(models.Model):
    """Model for batch payments"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('telebirr', 'Telebirr'),
        ('chapa', 'Chapa'),
        ('paypal', 'PayPal'),
        ('cbe', 'CBE Birr'),
        ('bank_transfer', 'Bank Transfer'),
    )
    
    batch_reference = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique batch reference"
    )
    
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES, 
        default='telebirr',
        help_text="Payment method for this batch"
    )
    
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Total amount in this batch"
    )
    
    total_payments = models.IntegerField(
        default=0,
        help_text="Number of payments in this batch"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Batch status"
    )
    
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_batches',
        help_text="User who processed this batch"
    )
    
    processed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the batch was processed"
    )
    
    notes = models.TextField(
        blank=True, 
        default='',
        help_text="Additional notes"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the batch was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the batch was last updated"
    )
    
    class Meta:
        db_table = 'payment_batches'
        indexes = [
            models.Index(fields=['batch_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch #{self.batch_reference} - {self.total_payments} payments"
    
    def save(self, *args, **kwargs):
        if not self.batch_reference:
            self.batch_reference = f"BATCH-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)


class PaymentTransaction(models.Model):
    """Model for individual payment transactions within a batch"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    batch = models.ForeignKey(
        PaymentBatch, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        help_text="Batch this transaction belongs to"
    )
    
    payment = models.ForeignKey(
        Payment, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        help_text="Payment this transaction is for"
    )
    
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Transaction amount"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Transaction status"
    )
    
    transaction_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="External transaction reference"
    )
    
    response_data = models.JSONField(
        blank=True, 
        null=True,
        help_text="Raw response from payment gateway"
    )
    
    error_message = models.TextField(
        blank=True, 
        default='',
        help_text="Error message if transaction failed"
    )
    
    completed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the transaction was completed"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the transaction was created"
    )
    
    class Meta:
        db_table = 'payment_transactions'
        indexes = [
            models.Index(fields=['batch', 'status']),
            models.Index(fields=['payment']),
            models.Index(fields=['transaction_reference']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Transaction #{self.id} - {self.payment.author.username} - {self.amount} ETB"


def get_tax_rate(book):
    """
    Determine tax rate based on book genre
    5% for culture-related genres, 10% for others
    """
    culture_genres = [
        'culture', 'cultural', 'history', 'heritage', 'tradition',
        'ethiopian', 'amharic', 'oromo', 'tigrinya', 'somali',
        'african', 'folklore', 'mythology', 'traditional',
        'language', 'literature', 'poetry', 'religious',
        'spiritual', 'custom', 'ritual', 'celebration'
    ]
    
    genre = book.genre.name.lower() if book.genre and hasattr(book.genre, 'name') else ''
    if any(g in genre for g in culture_genres):
        return 5
    return 10


class FinanceSettings(models.Model):
    """
    Singleton-style finance configuration editable by finance officers.
    Rates are percentages (0-100). Not hardcoded in settings.py.
    """
    royalty_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("70.00"),
        help_text="Author royalty share of gross sale (%)",
    )
    platform_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("30.00"),
        help_text="Platform (Abrehot) share of gross sale (%)",
    )
    tax_rate_default = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("10.00"),
        help_text="Default withholding tax on author royalty (%)",
    )
    tax_rate_culture = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"),
        help_text="Withholding tax for culture-related genres (%)",
    )
    tax_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("500.00"),
        help_text="Royalty amount above which tax applies (ETB)",
    )
    culture_genres = models.TextField(
        default="culture,cultural,history,heritage,tradition,ethiopian,amharic,oromo,tigrinya,somali,african,folklore,mythology,traditional,language,literature,poetry,religious,spiritual,custom,ritual,celebration",
        help_text="Comma-separated genre keywords that use culture tax rate",
    )
    currency = models.CharField(max_length=8, default="ETB")
    notes = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_settings_updates"
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "finance_settings"
        verbose_name = "Finance settings"
        verbose_name_plural = "Finance settings"

    def __str__(self):
        return f"FinanceSettings royalty={self.royalty_rate}% tax={self.tax_rate_default}%"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.royalty_rate + self.platform_rate != Decimal("100.00"):
            # auto-balance platform to 100 - royalty
            self.platform_rate = Decimal("100.00") - self.royalty_rate

    def save(self, *args, **kwargs):
        self.platform_rate = Decimal("100.00") - Decimal(str(self.royalty_rate))
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by("id").first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def genre_keywords(self):
        return [g.strip().lower() for g in (self.culture_genres or "").split(",") if g.strip()]


class FinanceReport(models.Model):
    """Generated weekly / monthly / annual finance reports."""
    PERIOD_WEEKLY = "weekly"
    PERIOD_MONTHLY = "monthly"
    PERIOD_ANNUAL = "annual"
    PERIOD_CUSTOM = "custom"
    PERIOD_CHOICES = (
        (PERIOD_WEEKLY, "Weekly"),
        (PERIOD_MONTHLY, "Monthly"),
        (PERIOD_ANNUAL, "Annual"),
        (PERIOD_CUSTOM, "Custom"),
    )

    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    title = models.CharField(max_length=200, blank=True, default="")

    # Aggregates (ETB)
    total_gross = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_royalty = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_platform = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_net_authors = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_pending = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    purchase_count = models.PositiveIntegerField(default=0)
    payment_count = models.PositiveIntegerField(default=0)
    author_count = models.PositiveIntegerField(default=0)

    # Snapshot of rates used when generating
    royalty_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("70.00"))
    platform_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("30.00"))
    tax_threshold_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("500.00"))

    # JSON breakdown (authors, daily series, etc.)
    details = models.JSONField(default=dict, blank=True)

    generated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_reports"
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "finance_reports"
        ordering = ["-period_end", "-generated_at"]
        indexes = [
            models.Index(fields=["period_type", "period_start", "period_end"]),
        ]

    def __str__(self):
        return self.title or f"{self.period_type} {self.period_start} → {self.period_end}"
