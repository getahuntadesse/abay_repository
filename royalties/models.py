# royalties/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

# Import from payments.models
from payments.models import Purchase

User = get_user_model()


class Royalty(models.Model):
    """Model to track royalties for authors"""
    ROYALTY_STATUS = [
        ('pending', 'Pending'),
        ('calculated', 'Calculated'),
        ('paid', 'Paid'),
    ]
    
    # Relationship to the purchase
    purchase = models.OneToOneField(Purchase, on_delete=models.CASCADE, related_name='royalty')
    book = models.ForeignKey('books.Book', on_delete=models.CASCADE, related_name='royalties')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='royalties')
    
    # Amount fields
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    royalty_rate = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    royalty_amount = models.DecimalField(max_digits=10, decimal_places=2)
    abrehot_share = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Tax
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=ROYALTY_STATUS, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['book', 'status']),
        ]
    
    def __str__(self):
        return f"Royalty #{self.id} - {self.book.title} - {self.author.username}"
    
    def calculate_royalty(self):
        """Calculate royalty amounts"""
        self.royalty_amount = self.gross_amount * (self.royalty_rate / 100)
        self.abrehot_share = self.gross_amount - self.royalty_amount
        return self.royalty_amount
    
    def calculate_tax(self, tax_rate=15):
        """Calculate tax on royalty"""
        if self.royalty_amount >= Decimal('500.00'):
            self.tax_rate = tax_rate
            self.tax_amount = self.royalty_amount * (tax_rate / 100)
            self.final_amount = self.royalty_amount - self.tax_amount
        else:
            self.tax_rate = 0
            self.tax_amount = 0
            self.final_amount = self.royalty_amount
        return self.tax_amount
    
    def mark_as_paid(self):
        """Mark royalty as paid"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()