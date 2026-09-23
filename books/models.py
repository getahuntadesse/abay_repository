# books/models.py
from django.db import models

def validate_book_file_field(value):
    from books.utils.secure_upload import validate_book_file
    ok, err = validate_book_file(value)
    if not ok:
        from django.core.exceptions import ValidationError
        raise ValidationError(err)

def validate_cover_image_field(value):
    from books.utils.secure_upload import validate_cover_image
    ok, err = validate_cover_image(value)
    if not ok:
        from django.core.exceptions import ValidationError
        raise ValidationError(err)


from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
import uuid
import os

User = get_user_model()


class Genre(models.Model):
    """Book genre/category model"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon class")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'genres'
        db_table = 'genres'
        ordering = ['name']
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('books:genre_books', kwargs={'genre_slug': self.slug})


class Book(models.Model):
    """Main Book model for the repository"""
    
    # Status Constants
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_INITIAL_REVIEW = 'initial_review'
    STATUS_AWAITING_CHECKER = 'awaiting_checker'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_REVIEW_COMPLETED = 'review_completed'
    STATUS_REVISION_REQUIRED = 'revision_required'
    STATUS_AUTHOR_REVISION = 'author_revision'
    STATUS_RESUBMITTED = 'resubmitted'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_PENDING_PUBLICATION = 'pending_publication'
    STATUS_PUBLISHED = 'published'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_INITIAL_REVIEW, 'Initial Review'),
        (STATUS_AWAITING_CHECKER, 'Awaiting Checker'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_REVIEW_COMPLETED, 'Review Completed'),
        (STATUS_REVISION_REQUIRED, 'Revision Required'),
        (STATUS_AUTHOR_REVISION, 'Author Revision'),
        (STATUS_RESUBMITTED, 'Resubmitted'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_PENDING_PUBLICATION, 'Pending Publication'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    # Basic Information
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    keywords = models.CharField(max_length=500, blank=True, help_text="Comma-separated keywords")
    
    # Metadata
    isbn = models.CharField(max_length=20, blank=True, null=True, unique=True)
    edition = models.CharField(max_length=20, default='1')
    page_count = models.PositiveIntegerField(default=0)
    publication_year = models.PositiveIntegerField(default=2024)
    language = models.CharField(max_length=50, default='English')
    
    # Relationships
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, related_name='books')
    
    # Files
    file = models.FileField(upload_to='books/files/%Y/%m/', blank=True, null=True, validators=[validate_book_file_field])
    cover_image = models.ImageField(upload_to='books/covers/%Y/%m/', blank=True, null=True, validators=[validate_cover_image_field])
    sample_file = models.FileField(upload_to='books/samples/%Y/%m/', blank=True, null=True, help_text="Sample/Preview file", validators=[validate_book_file_field])
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Book price in ETB. Must be >= 0.",
    )
    is_free = models.BooleanField(default=False)
    
    # Status and Workflow
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="When the book was submitted for review")
    published_at = models.DateTimeField(null=True, blank=True)
    checker_reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Workflow Tracking
    current_version = models.PositiveIntegerField(default=0)
    revision_count = models.PositiveIntegerField(default=0)
    revision_attempts = models.PositiveIntegerField(default=0)
    revision_notes = models.TextField(blank=True)
    maker_notes = models.TextField(blank=True)
    
    # Quality Metrics
    checker_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    quality_score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    # Assignments
    checker_assigned = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_books'
    )
    maker_assigned = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='maker_books'
    )
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0)
    downloads_count = models.PositiveIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    rating_avg = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'books'
        db_table = 'books'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['genre', 'status']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['-views_count']),
            models.Index(fields=['-downloads_count']),
        ]
        verbose_name = 'Book'
        verbose_name_plural = 'Books'

    def __str__(self):
        return f"{self.title} by {self.author.get_full_name() or self.author.username}"

    def get_absolute_url(self):
        return reverse('books:detail', kwargs={'book_id': self.id})

    def is_published(self):
        return self.status == self.STATUS_PUBLISHED

    def is_free_download(self):
        return self.is_free or self.price == 0

    def get_file_extension(self):
        if self.file:
            name, ext = os.path.splitext(self.file.name)
            return ext.lower()
        return ''

    def get_file_size(self):
        if self.file and hasattr(self.file, 'size'):
            return self.file.size
        return 0

    def get_formatted_file_size(self):
        size = self.get_file_size()
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def get_author_name(self):
        return self.author.get_full_name() or self.author.username

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def get_quality_score_display(self):
        if self.quality_score is None:
            return "Not Rated"
        return f"{self.quality_score:.1f}/10"

    def get_total_earnings(self):
        try:
            from payments.models import Payment
            return Payment.objects.filter(
                book=self,
                status='paid'
            ).aggregate(total=models.Sum('final_amount'))['total'] or 0
        except:
            return 0

    def get_pending_earnings(self):
        try:
            from payments.models import Payment
            return Payment.objects.filter(
                book=self,
                status__in=['calculated', 'pending']
            ).aggregate(total=models.Sum('final_amount'))['total'] or 0
        except:
            return 0

    def can_edit(self, user):
        """Check if a user can edit this book"""
        if not user.is_authenticated:
            return False
        if user.role in ['admin', 'maker']:
            return True
        return user == self.author and self.status in [self.STATUS_DRAFT, self.STATUS_SUBMITTED]

    def can_delete(self, user):
        """Check if a user can delete this book"""
        if not user.is_authenticated:
            return False
        return user == self.author and self.status in [self.STATUS_DRAFT, self.STATUS_CANCELLED]

    def can_download(self, user):
        """Check if a user can download this book"""
        if not user.is_authenticated:
            return False
        
        # Free books can be downloaded by anyone
        if self.is_free or self.price == 0:
            return True
        
        # Check if user has purchased
        try:
            from payments.models import Purchase
            return Purchase.objects.filter(
                user=user,
                book=self,
                status='completed'
            ).exists()
        except:
            return False

    def get_workflow_status(self):
        """Get detailed workflow status"""
        status_map = {
            self.STATUS_DRAFT: {'label': 'Draft', 'color': 'secondary', 'icon': 'fa-pen'},
            self.STATUS_SUBMITTED: {'label': 'Submitted', 'color': 'info', 'icon': 'fa-upload'},
            self.STATUS_INITIAL_REVIEW: {'label': 'Initial Review', 'color': 'warning', 'icon': 'fa-search'},
            self.STATUS_AWAITING_CHECKER: {'label': 'Awaiting Checker', 'color': 'primary', 'icon': 'fa-user-clock'},
            self.STATUS_UNDER_REVIEW: {'label': 'Under Review', 'color': 'info', 'icon': 'fa-spinner'},
            self.STATUS_REVIEW_COMPLETED: {'label': 'Review Completed', 'color': 'success', 'icon': 'fa-check-circle'},
            self.STATUS_REVISION_REQUIRED: {'label': 'Revision Required', 'color': 'danger', 'icon': 'fa-edit'},
            self.STATUS_AUTHOR_REVISION: {'label': 'Author Revision', 'color': 'warning', 'icon': 'fa-pen'},
            self.STATUS_RESUBMITTED: {'label': 'Resubmitted', 'color': 'info', 'icon': 'fa-sync-alt'},
            self.STATUS_ACCEPTED: {'label': 'Accepted', 'color': 'success', 'icon': 'fa-check'},
            self.STATUS_REJECTED: {'label': 'Rejected', 'color': 'danger', 'icon': 'fa-times'},
            self.STATUS_PENDING_PUBLICATION: {'label': 'Pending Publication', 'color': 'warning', 'icon': 'fa-clock'},
            self.STATUS_PUBLISHED: {'label': 'Published', 'color': 'success', 'icon': 'fa-book-open'},
            self.STATUS_CANCELLED: {'label': 'Cancelled', 'color': 'secondary', 'icon': 'fa-ban'},
        }
        return status_map.get(self.status, {'label': self.status, 'color': 'secondary', 'icon': 'fa-circle'})

    def clean(self):
        """Reject negative prices (Improper Validation of Book Price fix)."""
        super().clean()
        if self.price is not None and self.price < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError({"price": "Book price cannot be negative."})
        if getattr(self, "is_free", False):
            self.price = Decimal("0.00")

    def save(self, *args, **kwargs):
        # Auto-set submitted_at when status changes to SUBMITTED
        if self.status == self.STATUS_SUBMITTED and not self.submitted_at:
            self.submitted_at = timezone.now()

        # Auto-set published_at when status changes to PUBLISHED
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        # Enforce non-negative price even if clean() was skipped
        if self.price is not None and self.price < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError("Book price cannot be negative.")

        # If book is free, set price to 0
        if self.is_free or self.price == 0:
            self.price = Decimal("0.00")

        super().save(*args, **kwargs)


class BookVersion(models.Model):
    """Track different versions of a book"""
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    file = models.FileField(upload_to='books/versions/%Y/%m/')
    cover_image = models.ImageField(upload_to='books/versions/covers/%Y/%m/', blank=True, null=True)
    sample_file = models.FileField(upload_to='books/versions/samples/%Y/%m/', blank=True, null=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_versions')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    revision_notes = models.TextField(blank=True)
    parent_version = models.PositiveIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    
    file_size = models.PositiveIntegerField(default=0)
    file_hash = models.CharField(max_length=64, blank=True)
    
    # Version metadata
    changes_summary = models.TextField(blank=True)
    is_major_revision = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'book_versions'
        db_table = 'book_versions'
        ordering = ['-version_number']
        unique_together = ['book', 'version_number']

    def __str__(self):
        return f"{self.book.title} - v{self.version_number}"

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class Wishlist(models.Model):
    """User wishlist items"""
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlists'
        db_table = 'wishlists'
        unique_together = ['client', 'book']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.client.username} - {self.book.title}"


class BookReview(models.Model):
    """User reviews for books"""
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_reviews')
    
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    
    is_approved = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'book_reviews'
        db_table = 'book_reviews'
        ordering = ['-created_at']
        unique_together = ['book', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.rating}/5)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update book rating
        from django.db.models import Avg
        avg = self.book.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
        if avg:
            self.book.rating_avg = avg
            self.book.rating_count = self.book.reviews.filter(is_approved=True).count()
            self.book.save()


class BookActivityLog(models.Model):
    """Log all book-related activities"""
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='activity_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='book_activities')
    
    action = models.CharField(max_length=100)
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'book_activity_logs'
        db_table = 'book_activity_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['book', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.book.title}"


class ReviewAssignment(models.Model):
    """Assignment of a book to a checker for review"""
    
    STATUS_ASSIGNED = 'assigned'
    STATUS_ACCEPTED = 'accepted'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_DECLINED = 'declined'
    STATUS_CONFLICT = 'conflict'
    
    STATUS_CHOICES = (
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_CONFLICT, 'Conflict'),
    )
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='review_assignments')
    book_version = models.ForeignKey(BookVersion, on_delete=models.CASCADE, related_name='review_assignments')
    checker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checker_assignments')
    maker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='maker_assignments')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ASSIGNED)
    assignment_type = models.CharField(max_length=20, default='initial')
    
    due_date = models.DateTimeField()
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    instructions = models.TextField(blank=True)
    decline_reason = models.TextField(blank=True)
    conflict_reason = models.TextField(blank=True)
    
    is_overdue = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'review_assignments'
        db_table = 'review_assignments'
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['checker', 'status']),
            models.Index(fields=['book', 'status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.book.title} - {self.checker.username}"

    def accept(self, checker):
        """Accept the assignment"""
        if checker != self.checker:
            raise ValueError("Only the assigned checker can accept this assignment")
        self.status = self.STATUS_ACCEPTED
        self.accepted_at = timezone.now()
        self.save()

    def decline(self, checker, reason):
        """Decline the assignment"""
        if checker != self.checker:
            raise ValueError("Only the assigned checker can decline this assignment")
        self.status = self.STATUS_DECLINED
        self.decline_reason = reason
        self.save()

    def declare_conflict(self, checker, reason):
        """Declare conflict of interest"""
        if checker != self.checker:
            raise ValueError("Only the assigned checker can declare conflict")
        self.status = self.STATUS_CONFLICT
        self.conflict_reason = reason
        self.save()

    def complete(self):
        """Mark assignment as completed"""
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def check_overdue(self):
        """Check if assignment is overdue"""
        if self.due_date and timezone.now() > self.due_date:
            self.is_overdue = True
            self.save()
            return True
        return False


class CheckerReview(models.Model):
    """Review submitted by a checker"""
    
    RECOMMENDATION_ACCEPT = 'accept'
    RECOMMENDATION_MAJOR_REVISION = 'major_revision'
    RECOMMENDATION_MINOR_REVISION = 'minor_revision'
    RECOMMENDATION_REJECT = 'reject'
    RECOMMENDATION_NEEDS_REVISION = 'needs_revision'
    
    RECOMMENDATION_CHOICES = (
        (RECOMMENDATION_ACCEPT, 'Accept'),
        (RECOMMENDATION_MAJOR_REVISION, 'Major Revision'),
        (RECOMMENDATION_MINOR_REVISION, 'Minor Revision'),
        (RECOMMENDATION_REJECT, 'Reject'),
        (RECOMMENDATION_NEEDS_REVISION, 'Needs Revision'),
    )
    
    assignment = models.ForeignKey(ReviewAssignment, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='checker_reviews')
    book_version = models.ForeignKey(BookVersion, on_delete=models.CASCADE, related_name='checker_reviews', null=True)
    checker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checker_reviews')
    
    # Review scores (0-10 scale, stored as integers)
    content_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    originality = models.PositiveSmallIntegerField(null=True, blank=True)
    completeness = models.PositiveSmallIntegerField(null=True, blank=True)
    structure = models.PositiveSmallIntegerField(null=True, blank=True)
    language_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    technical_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    
    overall_score = models.FloatField(null=True, blank=True)
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES)
    
    # Comments
    overall_comment = models.TextField()
    author_visible_comments = models.TextField(blank=True)
    internal_comments = models.TextField(blank=True)
    required_corrections = models.TextField(blank=True)
    
    # Files
    annotated_file = models.FileField(upload_to='books/reviews/annotated/%Y/%m/', blank=True, null=True)
    
    # Status
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Conflicts
    has_conflict = models.BooleanField(default=False)
    conflict_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'checker_reviews'
        db_table = 'checker_reviews'
        ordering = ['-submitted_at']
        unique_together = ['assignment', 'checker']

    def __str__(self):
        return f"Review by {self.checker.username} - {self.book.title}"

    def submit(self):
        """Submit the review"""
        self.is_submitted = True
        self.submitted_at = timezone.now()
        self.save()
        
        # Update book status based on recommendation
        if self.recommendation == self.RECOMMENDATION_ACCEPT:
            self.book.status = Book.STATUS_REVIEW_COMPLETED
        elif self.recommendation in [self.RECOMMENDATION_MAJOR_REVISION, self.RECOMMENDATION_MINOR_REVISION, self.RECOMMENDATION_NEEDS_REVISION]:
            self.book.status = Book.STATUS_REVISION_REQUIRED
            self.book.revision_notes = self.required_corrections or self.overall_comment
        elif self.recommendation == self.RECOMMENDATION_REJECT:
            self.book.status = Book.STATUS_REJECTED
        
        self.book.checker_score = self.overall_score
        self.book.checker_reviewed_at = timezone.now()
        self.book.save()
        
        # Update assignment if exists
        if self.assignment:
            self.assignment.complete()


class RevisionRequest(models.Model):
    """Request for revision from maker to author"""
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='revision_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='revision_requests_made')
    
    required_changes = models.TextField()
    reviewer_comments = models.TextField(blank=True)
    maker_instructions = models.TextField(blank=True)
    
    revision_deadline = models.DateTimeField(null=True, blank=True)
    re_review_required = models.BooleanField(default=False)
    re_review_checkers = models.ManyToManyField(User, blank=True, related_name='re_review_assignments')
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'revision_requests'
        db_table = 'revision_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Revision request for {self.book.title}"


class EditorialDecision(models.Model):
    """Final editorial decision by maker"""
    
    DECISION_ACCEPT = 'accept'
    DECISION_REJECT = 'reject'
    DECISION_NEEDS_REVISION = 'needs_revision'
    DECISION_DEFER = 'defer'
    
    DECISION_CHOICES = (
        (DECISION_ACCEPT, 'Accept'),
        (DECISION_REJECT, 'Reject'),
        (DECISION_NEEDS_REVISION, 'Needs Revision'),
        (DECISION_DEFER, 'Defer'),
    )
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='editorial_decisions')
    maker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='editorial_decisions')
    
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'editorial_decisions'
        db_table = 'editorial_decisions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.decision} - {self.book.title}"


class PublicationRecord(models.Model):
    """Record of book publication"""
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='publication_records')
    published_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='publications')
    
    publication_date = models.DateTimeField()
    version = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'publication_records'
        db_table = 'publication_records'
        ordering = ['-publication_date']

    def __str__(self):
        return f"{self.book.title} - v{self.version}"


class BookNotification(models.Model):
    """Notifications for book-related events"""
    
    NOTIFICATION_TYPES = (
        ('new_submission', 'New Submission'),
        ('checker_assigned', 'Checker Assigned'),
        ('review_completed', 'Review Completed'),
        ('book_accepted', 'Book Accepted'),
        ('book_rejected', 'Book Rejected'),
        ('revision_needed', 'Revision Needed'),
        ('revision_submitted', 'Revision Submitted'),
        ('book_published', 'Book Published'),
        ('book_accepted_initial', 'Book Accepted Initial'),
    )
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_notifications')
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'book_notifications'
        db_table = 'book_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class BookEmailEvent(models.Model):
    """Track email events related to books"""
    
    EVENT_TYPES = (
        ('submission_confirmation', 'Submission Confirmation'),
        ('review_assignment', 'Review Assignment'),
        ('review_completed', 'Review Completed'),
        ('decision_made', 'Decision Made'),
        ('revision_requested', 'Revision Requested'),
        ('publication_notification', 'Publication Notification'),
    )
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='email_events')
    recipient = models.EmailField()
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    
    subject = models.CharField(max_length=255)
    body = models.TextField()
    
    sent_at = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'email_events'
        db_table = 'email_events'
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.event_type} - {self.recipient}"


class AuthorResponse(models.Model):
    """Response from author to revision request"""
    
    revision_request = models.ForeignKey(RevisionRequest, on_delete=models.CASCADE, related_name='author_responses')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='revision_responses')
    
    response_notes = models.TextField()
    file = models.FileField(upload_to='books/revisions/responses/%Y/%m/')
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_complete = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'author_responses'
        db_table = 'author_responses'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Response to revision request for {self.revision_request.book.title}"