# books/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Book, Genre, BookVersion, ReviewAssignment, CheckerReview,
    RevisionRequest, AuthorResponse, EditorialDecision, PublicationRecord,
    BookActivityLog, BookNotification, BookEmailEvent, Wishlist, BookReview
)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'slug', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'author', 'status_badge', 
        'current_version', 'revision_count', 'created_at'
    ]
    list_filter = ['status', 'is_free', 'language', 'genre', 'created_at']
    search_fields = [
        'title', 'subtitle', 'description', 
        'isbn', 'author__full_name', 'author__username'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'submitted_at', 'published_at',
        'checker_reviewed_at', 'current_version', 'revision_count'
    ]
    raw_id_fields = ['author', 'genre', 'checker_assigned', 'maker_assigned']
    fieldsets = (
        ('Book Information', {
            'fields': (
                'title', 'subtitle', 'description',
                'genre', 'language', 'edition', 'page_count', 
                'publication_year', 'isbn', 'keywords'
            )
        }),
        ('Author & Status', {
            'fields': ('author', 'status', 'current_version', 'revision_count')
        }),
        ('Pricing', {
            'fields': ('price', 'is_free')
        }),
        ('Files', {
            'fields': ('file', 'cover_image', 'sample_file')
        }),
        ('Workflow', {
            'fields': (
                'checker_assigned', 'maker_assigned', 'checker_reviewed_at',
                'submitted_at', 'published_at'
            )
        }),
        ('Quality Scores', {
            'fields': ('checker_score', 'quality_score')
        }),
        ('Revision', {
            'fields': ('revision_notes', 'revision_attempts')
        }),
        ('Statistics', {
            'fields': ('downloads_count', 'views_count', 'purchase_count', 'rating_count', 'rating_avg')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'draft': '#6c757d',
            'submitted': '#17a2b8',
            'initial_review': '#ffc107',
            'awaiting_checker': '#6f42c1',
            'under_review': '#17a2b8',
            'review_completed': '#28a745',
            'revision_required': '#fd7e14',
            'author_revision': '#fd7e14',
            'resubmitted': '#17a2b8',
            'accepted': '#28a745',
            'rejected': '#dc3545',
            'pending_publication': '#ffc107',
            'published': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_published', 'mark_as_rejected', 'mark_as_accepted']
    
    def mark_as_published(self, request, queryset):
        updated = queryset.update(status='published', published_at=timezone.now())
        self.message_user(request, f"{updated} book(s) marked as published.")
    mark_as_published.short_description = "Mark selected as Published"
    
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} book(s) marked as rejected.")
    mark_as_rejected.short_description = "Mark selected as Rejected"
    
    def mark_as_accepted(self, request, queryset):
        updated = queryset.update(status='accepted')
        self.message_user(request, f"{updated} book(s) marked as accepted.")
    mark_as_accepted.short_description = "Mark selected as Accepted"


@admin.register(BookVersion)
class BookVersionAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'version_number', 'uploaded_by', 'uploaded_at', 'is_current']
    list_filter = ['is_current', 'uploaded_at']
    search_fields = ['book__title', 'uploaded_by__full_name']
    raw_id_fields = ['book', 'uploaded_by']
    readonly_fields = ['uploaded_at', 'file_size']


@admin.register(ReviewAssignment)
class ReviewAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'book', 'checker', 'maker', 'status_badge', 
        'assigned_at', 'due_date', 'is_overdue'
    ]
    list_filter = ['status', 'assignment_type', 'assigned_at', 'due_date']
    search_fields = ['book__title', 'checker__full_name', 'maker__full_name']
    raw_id_fields = ['book', 'book_version', 'checker', 'maker']
    readonly_fields = ['assigned_at', 'accepted_at', 'completed_at']
    
    def status_badge(self, obj):
        colors = {
            'assigned': '#17a2b8',
            'accepted': '#28a745',
            'declined': '#dc3545',
            'conflict': '#dc3545',
            'in_progress': '#ffc107',
            'completed': '#28a745',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(CheckerReview)
class CheckerReviewAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'book', 'checker', 'recommendation_badge', 
        'overall_score', 'is_submitted', 'submitted_at'
    ]
    list_filter = ['recommendation', 'is_submitted', 'has_conflict', 'submitted_at']
    search_fields = ['book__title', 'checker__full_name', 'overall_comment']
    raw_id_fields = ['assignment', 'book', 'book_version', 'checker']
    readonly_fields = ['created_at', 'updated_at', 'submitted_at']
    
    def recommendation_badge(self, obj):
        colors = {
            'accept': '#28a745',
            'minor_revision': '#ffc107',
            'major_revision': '#fd7e14',
            'reject': '#dc3545',
            'needs_revision': '#fd7e14',
        }
        color = colors.get(obj.recommendation, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_recommendation_display()
        )
    recommendation_badge.short_description = 'Recommendation'


@admin.register(RevisionRequest)
class RevisionRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'requested_by', 'created_at', 'is_completed']
    list_filter = ['is_completed', 're_review_required', 'created_at']
    search_fields = ['book__title', 'requested_by__full_name', 'required_changes']
    raw_id_fields = ['book', 'requested_by']
    readonly_fields = ['created_at', 'completed_at']
    filter_horizontal = ['re_review_checkers']


@admin.register(AuthorResponse)
class AuthorResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'revision_request', 'author', 'submitted_at', 'is_complete']
    list_filter = ['is_complete', 'submitted_at']
    search_fields = ['revision_request__book__title', 'author__full_name', 'response_notes']
    raw_id_fields = ['revision_request', 'author']
    readonly_fields = ['submitted_at']


@admin.register(EditorialDecision)
class EditorialDecisionAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'maker', 'decision_badge', 'created_at']
    list_filter = ['decision', 'created_at']
    search_fields = ['book__title', 'maker__full_name', 'comment']
    raw_id_fields = ['book', 'maker']
    readonly_fields = ['created_at', 'approved_at']
    
    def decision_badge(self, obj):
        colors = {
            'accept': '#28a745',
            'reject': '#dc3545',
            'needs_revision': '#fd7e14',
            'defer': '#ffc107',
        }
        color = colors.get(obj.decision, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_decision_display()
        )
    decision_badge.short_description = 'Decision'


@admin.register(PublicationRecord)
class PublicationRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'published_by', 'publication_date', 'version', 'created_at']
    list_filter = ['publication_date', 'created_at']
    search_fields = ['book__title', 'published_by__full_name', 'notes']
    raw_id_fields = ['book', 'published_by']
    readonly_fields = ['created_at']


@admin.register(BookActivityLog)
class BookActivityLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'user', 'action', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['book__title', 'user__full_name', 'notes']
    raw_id_fields = ['book', 'user']
    readonly_fields = ['created_at']


@admin.register(BookNotification)
class BookNotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'book', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__full_name', 'title', 'message']
    raw_id_fields = ['book', 'user']
    readonly_fields = ['created_at', 'read_at']
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{updated} notifications marked as read.')
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False, read_at=None)
        self.message_user(request, f'{updated} notifications marked as unread.')
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(BookEmailEvent)
class BookEmailEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'recipient', 'event_type', 'subject', 'sent_at', 'is_successful']
    list_filter = ['event_type', 'is_successful', 'sent_at']
    search_fields = ['book__title', 'recipient', 'subject']
    raw_id_fields = ['book']
    readonly_fields = ['sent_at']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'book', 'added_at']
    list_filter = ['added_at']
    search_fields = ['client__full_name', 'client__username', 'book__title']
    raw_id_fields = ['client', 'book']
    readonly_fields = ['added_at']


@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'book', 'user', 'rating', 'is_approved', 'helpful_count', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_featured', 'created_at']
    search_fields = ['book__title', 'user__full_name', 'comment']
    raw_id_fields = ['book', 'user']
    readonly_fields = ['created_at', 'updated_at', 'helpful_count', 'unhelpful_count']
    
    actions = ['approve_reviews', 'unapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews approved.')
    approve_reviews.short_description = "Approve selected reviews"
    
    def unapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews unapproved.')
    unapprove_reviews.short_description = "Unapprove selected reviews"


# ============================================
# CUSTOM ADMIN SITE CONFIGURATION
# ============================================

admin.site.site_header = 'Abay Repository Admin'
admin.site.site_title = 'Abay Repository'
admin.site.index_title = 'Dashboard'