from django.db import models
from books.models import Book
from accounts.models import CustomUser
from payments.models import Purchase

class PaymentRequest(models.Model):
    PAYMENT_METHODS = (
        ('bank', 'Bank Transfer'),
        ('telebirr', 'Telebirr'),
        ('chapa', 'Chapa'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payment_requests')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='ETB')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='bank')
    
    # Bank Details
    bank_account_name = models.CharField(max_length=100, blank=True, default='')
    bank_account_number = models.CharField(max_length=50, blank=True, default='')
    bank_name = models.CharField(max_length=100, blank=True, default='')
    
    # Mobile Money
    telebirr_phone = models.CharField(max_length=20, blank=True, default='')
    chapa_email = models.EmailField(blank=True, default='')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, default='')
    user_notes = models.TextField(blank=True, default='')
    transaction_reference = models.CharField(max_length=100, blank=True, default='')
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Approvers
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    processed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_requests')
    
    class Meta:
        db_table = 'payment_requests'
    
    def __str__(self):
        return f"Payment Request - {self.author.full_name} - {self.amount} ETB"


class Royalty(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )
    
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='royalties')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='royalties')
    purchase = models.ForeignKey(Purchase, on_delete=models.SET_NULL, null=True, blank=True, related_name='royalties')
    
    # Sales Data
    total_sales = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Period
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    
    # Payment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'royalties'
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['book', 'status']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"Royalty for {self.book.title} - {self.net_payment} ETB"