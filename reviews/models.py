from django.db import models
from books.models import Book
from accounts.models import CustomUser

class QualityReview(models.Model):
    REVIEW_TYPE_CHOICES = (
        ('checker', 'Checker Review'),
        ('maker', 'Maker Review'),
    )
    
    RECOMMENDATION_CHOICES = (
        ('approved', 'Approved'),
        ('needs_revision', 'Needs Revision'),
        ('rejected', 'Rejected'),
    )
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='quality_reviews')
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE_CHOICES, default='checker')
    
    # Quality Scores
    content_quality = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    editorial_quality = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    technical_quality = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    overall_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    
    # Review Comments
    comments = models.TextField(blank=True, default='')
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quality_reviews'
        unique_together = ['book', 'review_type']
        indexes = [
            models.Index(fields=['book']),
            models.Index(fields=['reviewer']),
        ]
    
    def __str__(self):
        return f"{self.review_type} review for {self.book.title}"
    
    def calculate_overall_score(self):
        if self.content_quality and self.editorial_quality and self.technical_quality:
            scores = [self.content_quality, self.editorial_quality, self.technical_quality]
            self.overall_score = sum(scores) / len(scores)
            return self.overall_score
        return None