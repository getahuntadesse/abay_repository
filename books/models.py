from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from accounts.models import CustomUser
import os


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'genres'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


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
        ('Oromo', 'Oromo'),
        ('Tigrinya', 'Tigrinya'),
        ('Somali', 'Somali'),
        ('Other', 'Other'),
    )
    
    # Basic Information
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    isbn = models.CharField(max_length=20, unique=True, null=True, blank=True)  # ← FIXED: Allows null/blank
    
    # Classification
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='books')
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, related_name='books')
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='English')
    
    # Publication Details
    edition = models.CharField(max_length=50, default='1')
    page_count = models.IntegerField(default=0)
    publication_year = models.IntegerField(default=2024)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False)
    
    # Files
    file = models.FileField(upload_to='books/files/%Y/%m/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='books/covers/%Y/%m/', null=True, blank=True)
    sample_file = models.FileField(upload_to='books/samples/%Y/%m/', null=True, blank=True)
    
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
            models.Index(fields=['is_free']),
            models.Index(fields=['published_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    @property
    def is_free_book(self):
        return self.is_free
    
    @property
    def file_extension(self):
        """Get the file extension of the book file"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return ''
    
    @property
    def is_pdf(self):
        return self.file_extension == '.pdf'
    
    @property
    def is_epub(self):
        return self.file_extension == '.epub'
    
    @property
    def is_mobi(self):
        return self.file_extension == '.mobi'
    
    @property
    def is_txt(self):
        return self.file_extension == '.txt'
    
    @property
    def is_docx(self):
        return self.file_extension == '.docx'
    
    @property
    def is_audio(self):
        audio_extensions = ['.mp3', '.m4a', '.aac', '.wav', '.flac']
        return self.file_extension in audio_extensions
    
    @property
    def is_video(self):
        video_extensions = ['.mp4', '.webm', '.avi', '.mov', '.mkv']
        return self.file_extension in video_extensions
    
    @property
    def file_size_display(self):
        if self.file and self.file.size:
            size = self.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return 'N/A'
    
    @property
    def file_type_display(self):
        ext = self.file_extension
        type_map = {
            '.pdf': 'PDF Document',
            '.epub': 'EPUB E-book',
            '.mobi': 'MOBI E-book',
            '.txt': 'Text File',
            '.docx': 'Word Document',
            '.mp3': 'Audio File',
            '.mp4': 'Video File',
        }
        return type_map.get(ext, ext.upper() + ' File')
    
    def publish(self):
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
    
    def increment_downloads(self):
        self.downloads_count += 1
        self.save()
    
    def increment_views(self):
        self.views_count += 1
        self.save()
    
    def increment_purchases(self):
        self.purchase_count += 1
        self.save()
    
    def get_reading_progress(self, user):
        try:
            from .models import ReadingProgress
            progress = ReadingProgress.objects.get(user=user, book=self)
            return progress.progress_percentage
        except:
            return 0
    
    def get_bookmarks_count(self, user):
        try:
            from .models import Bookmark
            return Bookmark.objects.filter(user=user, book=self).count()
        except:
            return 0


class Wishlist(models.Model):
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wishlist')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='wishlisted_by')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlists'
        unique_together = ['client', 'book']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.client.full_name} - {self.book.title}"


class ReadingProgress(models.Model):
    """Track reading progress for users"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reading_progress')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reading_progress')
    current_page = models.IntegerField(default=0)
    progress_percentage = models.IntegerField(default=0)
    last_read_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reading_progress'
        unique_together = ['user', 'book']
        ordering = ['-last_read_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} ({self.progress_percentage}%)"
    
    def update_progress(self, page, total_pages):
        self.current_page = page
        if total_pages > 0:
            self.progress_percentage = int((page / total_pages) * 100)
        self.save()


class Bookmark(models.Model):
    """Bookmarks for users"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='bookmarks')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='bookmarks')
    page_number = models.IntegerField(default=0)
    location = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bookmarks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} (Page {self.page_number})"


class ReadingHistory(models.Model):
    """Track reading history for users"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reading_history')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reading_history')
    action = models.CharField(max_length=20, choices=[
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('purchased', 'Purchased'),
        ('finished', 'Finished'),
    ])
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reading_history'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} ({self.action})"


class BookReview(models.Model):
    """User reviews for books"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='book_reviews')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='user_reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=255, blank=True, default='')
    content = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'book_reviews'
        unique_together = ['user', 'book']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.book.title} ({self.rating} stars)"
    
    def get_rating_display(self):
        return '⭐' * self.rating + '☆' * (5 - self.rating)