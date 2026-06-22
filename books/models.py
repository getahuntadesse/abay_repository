from django.db import models
from django.utils import timezone
from accounts.models import CustomUser


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'genres'
    
    def __str__(self):
        return self.name


class Book(models.Model):
    STATUS_CHOICES = (
        ('pending_review', 'Pending Review'),
        ('in_review', 'In Review'),
        ('needs_revision', 'Needs Revision'),
        ('checker_approved', 'Checker Approved'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    )
    
    LANGUAGE_CHOICES = (
        ('English', 'English'),
        ('Amharic', 'Amharic'),
        ('Arabic', 'Arabic'),
        ('French', 'French'),
        ('German', 'German'),
        ('Spanish', 'Spanish'),
    )
    
    # Basic Information
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    isbn = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    # Classification
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='books')
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='English')
    
    # Publication Details
    edition = models.CharField(max_length=50, default='1')
    page_count = models.IntegerField(default=0)
    publication_year = models.IntegerField(default=2024)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False)
    
    # Files
    file = models.FileField(upload_to='books/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='covers/', null=True, blank=True)
    sample_file = models.FileField(upload_to='samples/', null=True, blank=True)
    
    # SEO and Metadata
    keywords = models.TextField(blank=True, default='')
    
    # Statistics
    downloads_count = models.IntegerField(default=0)
    purchase_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.IntegerField(default=0)
    
    # Checker Score
    checker_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    
    # Status and Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    revision_notes = models.TextField(blank=True, default='')
    revision_attempts = models.IntegerField(default=0)
    
    # Timestamps
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    checker_reviewed_at = models.DateTimeField(null=True, blank=True)
    maker_approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'books'
        indexes = [
            models.Index(fields=['author']),
            models.Index(fields=['genre']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    def publish(self):
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()


class Wishlist(models.Model):
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wishlist')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='wishlisted_by')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlists'
        unique_together = ['client', 'book']
    
    def __str__(self):
        return f"{self.client.full_name} - {self.book.title}"