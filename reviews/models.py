# reviews/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# Use string reference to avoid circular import
# from books.models import Book  # REMOVE THIS LINE


class QualityReview(models.Model):
    """Quality review model for books"""
    REVIEW_TYPES = (
        ('checker', 'Checker Review'),
        ('maker', 'Maker Review'),
        ('admin', 'Admin Review'),
    )
    
    RECOMMENDATION_CHOICES = (
        ('approved', 'Approved'),
        ('needs_revision', 'Needs Revision'),
        ('rejected', 'Rejected'),
    )
    
    # Use string reference to avoid circular import
    book = models.ForeignKey(
        'books.Book',
        on_delete=models.CASCADE,
        related_name='quality_reviews'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quality_reviews'
    )
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES, default='checker')
    
    # Review scores (0-10)
    content_quality = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Content quality score (0-10)"
    )
    editorial_quality = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Editorial quality score (0-10)"
    )
    technical_quality = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Technical quality score (0-10)"
    )
    copyright_compliance = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Copyright compliance score (0-10)"
    )
    community_guidelines = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Community guidelines score (0-10)"
    )
    overall_score = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        default=0,
        help_text="Overall quality score (0-10)"
    )
    
    comments = models.TextField(blank=True, default='')
    recommendation = models.CharField(
        max_length=20, 
        choices=RECOMMENDATION_CHOICES, 
        default='needs_revision'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quality_reviews'
        ordering = ['-created_at']
        unique_together = ['book', 'reviewer', 'review_type']
    
    def __str__(self):
        return f"Review for {self.book.title} by {self.reviewer.username}"
    
    def calculate_overall_score(self):
        """Calculate the overall score from individual scores"""
        scores = [
            self.content_quality,
            self.editorial_quality,
            self.technical_quality,
            self.copyright_compliance,
            self.community_guidelines
        ]
        # Average of all scores
        total = sum(scores)
        count = len([s for s in scores if s > 0])  # Only count non-zero scores
        if count > 0:
            self.overall_score = round(total / count, 1)
        else:
            self.overall_score = 0
        return self.overall_score