from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from books.models import Book, Genre
from accounts.models import CustomUser
from payments.models import Purchase


@staff_member_required
def admin_analytics(request):
    """Comprehensive analytics view for admin"""
    
    # Date ranges
    today = timezone.now().date()
    month_ago = today - timedelta(days=30)
    
    # User Statistics
    total_users = CustomUser.objects.count()
    total_authors = CustomUser.objects.filter(role='author').count()
    total_readers = CustomUser.objects.filter(role='client').count()
    total_checkers = CustomUser.objects.filter(role='checker').count()
    total_makers = CustomUser.objects.filter(role='maker').count()
    total_admins = CustomUser.objects.filter(role='admin').count()
    
    # New users this month
    new_users_month = CustomUser.objects.filter(date_joined__gte=month_ago).count()
    new_authors_month = CustomUser.objects.filter(role='author', date_joined__gte=month_ago).count()
    new_readers_month = CustomUser.objects.filter(role='client', date_joined__gte=month_ago).count()
    
    # Book Statistics
    total_books = Book.objects.count()
    published_books = Book.objects.filter(status='published').count()
    pending_review = Book.objects.filter(status='pending_review').count()
    in_review = Book.objects.filter(status='in_review').count()
    needs_revision = Book.objects.filter(status='needs_revision').count()
    rejected_books = Book.objects.filter(status='rejected').count()
    
    # Books published this month
    books_published_month = Book.objects.filter(
        status='published', 
        published_at__gte=month_ago
    ).count()
    
    # Free vs Paid books
    free_books = Book.objects.filter(is_free=True, status='published').count()
    paid_books = Book.objects.filter(is_free=False, status='published').count()
    
    # Download Statistics
    total_downloads = Book.objects.aggregate(total=Sum('downloads_count'))['total'] or 0
    total_views = Book.objects.aggregate(total=Sum('views_count'))['total'] or 0
    
    # Downloads this month
    downloads_month = Book.objects.filter(
        status='published',
        published_at__gte=month_ago
    ).aggregate(total=Sum('downloads_count'))['total'] or 0
    
    # Financial Statistics
    total_sales = Purchase.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    
    # Sales this month
    sales_month = Purchase.objects.filter(
        status='completed',
        completed_at__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Top selling books
    top_books = Book.objects.filter(status='published').order_by('-purchase_count')[:10]
    
    # Top downloaded books
    top_downloaded = Book.objects.filter(status='published').order_by('-downloads_count')[:10]
    
    # Genre Statistics
    genres = Genre.objects.filter(is_active=True).annotate(
        book_count=Count('book', filter=Q(book__status='published'))
    ).order_by('-book_count')[:10]
    
    # Review Statistics
    total_reviews = 0
    avg_checker_score = 0
    try:
        from reviews.models import QualityReview
        total_reviews = QualityReview.objects.count()
        avg_checker_score = QualityReview.objects.filter(
            review_type='checker'
        ).aggregate(avg=Avg('overall_score'))['avg'] or 0
    except Exception:
        pass
    
    # Recent activity
    recent_books = Book.objects.filter(status='published').order_by('-published_at')[:10]
    recent_users = CustomUser.objects.order_by('-date_joined')[:10]
    
    context = {
        # User Stats
        'total_users': total_users,
        'total_authors': total_authors,
        'total_readers': total_readers,
        'total_checkers': total_checkers,
        'total_makers': total_makers,
        'total_admins': total_admins,
        'new_users_month': new_users_month,
        'new_authors_month': new_authors_month,
        'new_readers_month': new_readers_month,
        
        # Book Stats
        'total_books': total_books,
        'published_books': published_books,
        'pending_review': pending_review,
        'in_review': in_review,
        'needs_revision': needs_revision,
        'rejected_books': rejected_books,
        'books_published_month': books_published_month,
        'free_books': free_books,
        'paid_books': paid_books,
        
        # Download Stats
        'total_downloads': total_downloads,
        'total_views': total_views,
        'downloads_month': downloads_month,
        
        # Financial Stats
        'total_sales': total_sales,
        'sales_month': sales_month,
        
        # Lists
        'top_books': top_books,
        'top_downloaded': top_downloaded,
        'genres': genres,
        'recent_books': recent_books,
        'recent_users': recent_users,
        
        # Review Stats
        'total_reviews': total_reviews,
        'avg_checker_score': avg_checker_score,
    }
    
    return render(request, 'admin/analytics.html', context)