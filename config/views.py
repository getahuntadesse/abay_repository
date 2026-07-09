# config/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseServerError
from django.template import loader
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from datetime import datetime, timedelta
import logging
import os
import re
from django.conf import settings

# Set up logger
logger = logging.getLogger(__name__)


@staff_member_required
def admin_analytics(request):
    """
    Comprehensive analytics view for admin dashboard.
    Returns JSON data for admin analytics charts and statistics.
    """
    try:
        # Date ranges
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        week_ago = today - timedelta(days=7)
        
        # Import models safely
        from books.models import Book, Genre
        from accounts.models import CustomUser
        from payments.models import Purchase
        
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
        
        # New users this week
        new_users_week = CustomUser.objects.filter(date_joined__gte=week_ago).count()
        
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
        total_sales_count = Purchase.objects.filter(status='completed').count()
        
        # Sales this month
        sales_month = Purchase.objects.filter(
            status='completed',
            purchased_at__gte=month_ago
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Sales this week
        sales_week = Purchase.objects.filter(
            status='completed',
            purchased_at__gte=week_ago
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Sales today
        sales_today = Purchase.objects.filter(
            status='completed',
            purchased_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Payment method breakdown
        telebirr_sales = 0
        cbe_sales = 0
        chapa_sales = 0
        
        try:
            # Try to get payment method breakdown
            if hasattr(Purchase, 'payment_method'):
                telebirr_sales = Purchase.objects.filter(
                    status='completed',
                    payment_method__icontains='telebirr'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                cbe_sales = Purchase.objects.filter(
                    status='completed',
                    payment_method__icontains='cbe'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                chapa_sales = Purchase.objects.filter(
                    status='completed',
                    payment_method__icontains='chapa'
                ).aggregate(total=Sum('amount'))['total'] or 0
        except Exception:
            pass
        
        # Top selling books
        top_books = Book.objects.filter(status='published').order_by('-purchase_count')[:10]
        top_books_data = [
            {
                'id': book.id,
                'title': book.title,
                'author': book.author.full_name if book.author else 'Unknown',
                'purchase_count': book.purchase_count,
                'price': str(book.price) if book.price else '0',
                'cover_url': book.cover_image.url if book.cover_image else None
            }
            for book in top_books
        ]
        
        # Top downloaded books
        top_downloaded = Book.objects.filter(status='published').order_by('-downloads_count')[:10]
        top_downloaded_data = [
            {
                'id': book.id,
                'title': book.title,
                'author': book.author.full_name if book.author else 'Unknown',
                'downloads_count': book.downloads_count,
                'cover_url': book.cover_image.url if book.cover_image else None
            }
            for book in top_downloaded
        ]
        
        # Genre Statistics
        genres = Genre.objects.filter(is_active=True).annotate(
            book_count=Count('book', filter=Q(book__status='published'))
        ).order_by('-book_count')[:10]
        
        genres_data = [
            {
                'id': genre.id,
                'name': genre.name,
                'book_count': genre.book_count
            }
            for genre in genres
        ]
        
        # Review Statistics
        total_reviews = 0
        avg_checker_score = 0
        try:
            from reviews.models import QualityReview
            total_reviews = QualityReview.objects.count()
            avg_checker_score = QualityReview.objects.filter(
                review_type='checker'
            ).aggregate(avg=Avg('overall_score'))['avg'] or 0
            avg_checker_score = round(avg_checker_score, 1)
        except Exception as e:
            logger.warning(f"Could not fetch review stats: {str(e)}")
        
        # Recent activity
        recent_books = Book.objects.filter(status='published').order_by('-published_at')[:10]
        recent_books_data = [
            {
                'id': book.id,
                'title': book.title,
                'author': book.author.full_name if book.author else 'Unknown',
                'published_at': book.published_at.strftime('%Y-%m-%d %H:%M') if book.published_at else None,
                'cover_url': book.cover_image.url if book.cover_image else None
            }
            for book in recent_books
        ]
        
        recent_users = CustomUser.objects.order_by('-date_joined')[:10]
        recent_users_data = [
            {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'role': user.role,
                'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M') if user.date_joined else None
            }
            for user in recent_users
        ]
        
        # Calculate growth percentages
        previous_month = month_ago - timedelta(days=30)
        users_previous_month = CustomUser.objects.filter(date_joined__gte=previous_month, date_joined__lt=month_ago).count()
        user_growth = ((new_users_month - users_previous_month) / (users_previous_month or 1)) * 100
        
        books_previous_month = Book.objects.filter(
            status='published',
            published_at__gte=previous_month,
            published_at__lt=month_ago
        ).count()
        book_growth = ((books_published_month - books_previous_month) / (books_previous_month or 1)) * 100
        
        sales_previous_month = Purchase.objects.filter(
            status='completed',
            purchased_at__gte=previous_month,
            purchased_at__lt=month_ago
        ).aggregate(total=Sum('amount'))['total'] or 0
        sales_growth = ((sales_month - sales_previous_month) / (sales_previous_month or 1)) * 100
        
        # Return JSON response
        return JsonResponse({
            'success': True,
            'data': {
                # User Stats
                'users': {
                    'total': total_users,
                    'authors': total_authors,
                    'readers': total_readers,
                    'checkers': total_checkers,
                    'makers': total_makers,
                    'admins': total_admins,
                    'new_this_month': new_users_month,
                    'new_this_week': new_users_week,
                    'growth_percentage': round(user_growth, 1),
                },
                
                # Book Stats
                'books': {
                    'total': total_books,
                    'published': published_books,
                    'pending_review': pending_review,
                    'in_review': in_review,
                    'needs_revision': needs_revision,
                    'rejected': rejected_books,
                    'published_this_month': books_published_month,
                    'free_books': free_books,
                    'paid_books': paid_books,
                    'growth_percentage': round(book_growth, 1),
                },
                
                # Download Stats
                'downloads': {
                    'total': total_downloads,
                    'total_views': total_views,
                    'this_month': downloads_month,
                },
                
                # Financial Stats
                'sales': {
                    'total': total_sales,
                    'total_count': total_sales_count,
                    'this_month': sales_month,
                    'this_week': sales_week,
                    'today': sales_today,
                    'growth_percentage': round(sales_growth, 1),
                    'payment_methods': {
                        'telebirr': telebirr_sales,
                        'cbe': cbe_sales,
                        'chapa': chapa_sales,
                    }
                },
                
                # Top Lists
                'top_books': top_books_data,
                'top_downloaded': top_downloaded_data,
                'genres': genres_data,
                'recent_books': recent_books_data,
                'recent_users': recent_users_data,
                
                # Review Stats
                'reviews': {
                    'total': total_reviews,
                    'avg_checker_score': avg_checker_score,
                },
                
                # Timestamps
                'last_updated': timezone.now().isoformat(),
            }
        })
        
    except Exception as e:
        logger.error(f"Error in admin_analytics: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
def admin_logs(request):
    """
    API endpoint to fetch system logs for the admin dashboard.
    Returns the last 200 lines of the log file with parsed timestamps and levels.
    """
    log_file = settings.BASE_DIR / 'logs/abay_repository.log'
    
    if not log_file.exists():
        return JsonResponse({
            'success': True,
            'logs': [],
            'message': 'No log file found',
            'count': 0
        })
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        logs = []
        # Parse log format: [timestamp] LEVEL message
        # Example: [2024-01-01 12:00:00.123] INFO This is a log message
        log_pattern = re.compile(r'\[(.*?)\]\s+(\w+)\s+(.*)')
        
        # Get the last 200 lines
        last_lines = lines[-200:] if len(lines) > 200 else lines
        
        for line in last_lines:
            line = line.strip()
            if not line:
                continue
            
            match = log_pattern.match(line)
            if match:
                timestamp_str, level, message = match.groups()
                try:
                    # Try to parse with milliseconds
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                    logs.append({
                        'timestamp': timestamp.isoformat(),
                        'level': level,
                        'message': message
                    })
                except ValueError:
                    try:
                        # Try without milliseconds
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        logs.append({
                            'timestamp': timestamp.isoformat(),
                            'level': level,
                            'message': message
                        })
                    except ValueError:
                        # If parsing fails, use current time
                        logs.append({
                            'timestamp': timezone.now().isoformat(),
                            'level': level,
                            'message': line
                        })
            else:
                # Fallback for lines without standard format
                # Try to detect level from common patterns
                level = 'INFO'
                if 'ERROR' in line.upper() or 'EXCEPTION' in line.upper():
                    level = 'ERROR'
                elif 'WARNING' in line.upper() or 'WARN' in line.upper():
                    level = 'WARNING'
                elif 'DEBUG' in line.upper():
                    level = 'DEBUG'
                elif 'CRITICAL' in line.upper():
                    level = 'CRITICAL'
                
                logs.append({
                    'timestamp': timezone.now().isoformat(),
                    'level': level,
                    'message': line
                })
        
        # Return logs in reverse order (newest first)
        logs.reverse()
        
        return JsonResponse({
            'success': True,
            'logs': logs,
            'count': len(logs)
        })
        
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e),
            'logs': [],
            'count': 0
        }, status=500)


@login_required
def dashboard_redirect(request):
    """
    Redirect users to their role-based dashboard.
    """
    user = request.user
    role_redirects = {
        'admin': 'accounts:admin_dashboard',
        'author': 'accounts:author_dashboard',
        'checker': 'accounts:checker_dashboard',
        'maker': 'accounts:maker_dashboard',
        'client': 'accounts:client_dashboard',
    }
    redirect_url = role_redirects.get(user.role, 'accounts:client_dashboard')
    return redirect(redirect_url)


def handler404(request, exception):
    """
    Custom 404 error handler
    """
    try:
        template = loader.get_template('errors/404.html')
        context = {
            'request_path': request.path,
        }
        return HttpResponseNotFound(template.render(context, request))
    except Exception:
        # Fallback if template doesn't exist
        return HttpResponseNotFound(f"<h1>404 - Page Not Found</h1><p>The page '{request.path}' does not exist.</p>")


def handler500(request):
    """
    Custom 500 error handler
    """
    try:
        template = loader.get_template('errors/500.html')
        context = {}
        return HttpResponseServerError(template.render(context, request))
    except Exception:
        # Fallback if template doesn't exist
        return HttpResponseServerError("<h1>500 - Server Error</h1><p>An internal server error occurred.</p>")


def handler403(request, exception):
    """
    Custom 403 error handler
    """
    try:
        template = loader.get_template('errors/403.html')
        context = {
            'exception': exception,
        }
        return render(request, 'errors/403.html', context, status=403)
    except Exception:
        # Fallback if template doesn't exist
        return render(request, '403.html', {}, status=403)