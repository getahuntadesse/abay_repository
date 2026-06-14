from django.db import models
from django.utils import timezone
from books.models import Book
from accounts.models import CustomUser


class Purchase(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    transaction_id = models.CharField(max_length=100, unique=True)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='purchases')
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='purchases')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'purchases'
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['completed_at']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"Purchase {self.transaction_id} - {self.book.title if self.book else 'Unknown'}"