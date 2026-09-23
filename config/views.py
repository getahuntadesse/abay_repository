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
from pathlib import Path

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
    API: system logs for admin dashboard.

    Query params:
      q / search  – case-insensitive substring filter
      level       – INFO|WARNING|ERROR|DEBUG|CRITICAL|AUTH|PAYMENT|all
      limit       – max entries (default 300, max 2000)
      rotated     – if 1, also read logs.txt.1 … rotated backups
    """
    search = (request.GET.get('q') or request.GET.get('search') or '').strip()
    level_filter = (request.GET.get('level') or 'all').strip().upper()
    include_rotated = request.GET.get('rotated', '1') in ('1', 'true', 'yes')
    try:
        limit = int(request.GET.get('limit') or 300)
    except (TypeError, ValueError):
        limit = 300
    limit = max(1, min(limit, 2000))

    primary = Path(getattr(settings, 'LOG_FILE_PATH', Path(settings.BASE_DIR) / 'logs.txt'))
    files = []
    try:
        if primary.exists() and primary.is_file():
            files.append(primary)
        if include_rotated:
            # RotatingFileHandler creates logs.txt.1 … logs.txt.N
            backup_count = int(getattr(settings, 'LOG_BACKUP_COUNT', 10) or 10)
            for i in range(1, backup_count + 1):
                rotated = Path(str(primary) + f'.{i}')
                if rotated.exists() and rotated.is_file():
                    files.append(rotated)
        # Extra fallbacks
        for extra in (
            Path(settings.BASE_DIR) / 'logs' / 'django.log',
            Path(settings.BASE_DIR) / 'logs' / 'security.log',
        ):
            if extra.exists() and extra.is_file() and extra not in files:
                files.append(extra)
    except OSError as e:
        logger.exception('Failed to resolve log files')
        return JsonResponse({
            'success': False,
            'logs': [],
            'count': 0,
            'file_size': 0,
            'message': f'Cannot access log files: {e}',
            'error': str(e),
        }, status=500)

    if not files:
        return JsonResponse({
            'success': True,
            'logs': [],
            'count': 0,
            'file_size': 0,
            'file_path': str(primary.name),
            'message': 'No log file found (expected logs.txt in project root)',
            'search': search,
            'level': level_filter,
        })

    log_pattern = re.compile(
        r'^\[(?P<ts>[^\]]+)\]\s+(?:(?P<tag>AUTH|PAYMENT|SECURITY)\s+)?'
        r'(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|EXCEPTION)\s+[-:]?\s*(?P<msg>.*)$',
        re.IGNORECASE,
    )
    level_map = {'WARN': 'WARNING', 'EXCEPTION': 'ERROR'}

    def parse_line(raw: str, source: str):
        raw = raw.rstrip('\n\r')
        if not raw.strip() or raw.strip().startswith('#'):
            return None
        match = log_pattern.match(raw.strip())
        if match:
            ts_str = match.group('ts')
            level = match.group('level').upper()
            level = level_map.get(level, level)
            tag = match.group('tag')
            message = (match.group('msg') or '').strip()
            if tag:
                message = f'{tag} | {message}'
            timestamp = None
            for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
                try:
                    timestamp = datetime.strptime(ts_str, fmt)
                    break
                except ValueError:
                    continue
            if timestamp is None:
                timestamp = timezone.now()
            return {
                'timestamp': timestamp.isoformat(),
                'level': level,
                'message': message or raw,
                'source': source,
            }
        upper = raw.upper()
        level = 'INFO'
        if 'CRITICAL' in upper:
            level = 'CRITICAL'
        elif 'ERROR' in upper or 'EXCEPTION' in upper:
            level = 'ERROR'
        elif 'WARNING' in upper or 'WARN' in upper:
            level = 'WARNING'
        elif 'DEBUG' in upper:
            level = 'DEBUG'
        msg = raw
        if 'PAYMENT' in upper:
            msg = 'PAYMENT | ' + raw
        elif 'AUTH' in upper:
            msg = 'AUTH | ' + raw
        return {
            'timestamp': timezone.now().isoformat(),
            'level': level,
            'message': msg,
            'source': source,
        }

    logs = []
    total_size = 0
    read_errors = []

    # Read oldest rotated first, then primary last so chronological order is natural
    ordered = list(reversed(files[1:])) + files[:1] if len(files) > 1 else files
    for fpath in ordered:
        try:
            total_size += fpath.stat().st_size
            with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    entry = parse_line(line, fpath.name)
                    if entry:
                        logs.append(entry)
        except OSError as e:
            read_errors.append(f'{fpath.name}: {e}')
            logger.warning('Could not read log file %s: %s', fpath, e)
        except Exception as e:
            read_errors.append(f'{fpath.name}: {e}')
            logger.exception('Unexpected error reading %s', fpath)

    # Filters
    if level_filter and level_filter != 'ALL':
        if level_filter in ('AUTH', 'PAYMENT', 'SECURITY'):
            logs = [x for x in logs if level_filter in (x.get('message') or '').upper()]
        else:
            logs = [x for x in logs if (x.get('level') or '').upper() == level_filter]

    if search:
        q = search.lower()
        logs = [
            x for x in logs
            if q in (x.get('message') or '').lower()
            or q in (x.get('level') or '').lower()
            or q in (x.get('source') or '').lower()
        ]

    # Newest first, then limit
    def sort_key(item):
        return item.get('timestamp') or ''

    logs.sort(key=sort_key, reverse=True)
    truncated = len(logs) > limit
    logs = logs[:limit]

    return JsonResponse({
        'success': True,
        'logs': logs,
        'count': len(logs),
        'file_size': total_size,
        'file_path': primary.name,
        'files_read': [f.name for f in files],
        'rotated_count': max(0, len(files) - 1),
        'search': search,
        'level': level_filter,
        'truncated': truncated,
        'message': (
            f'Loaded {len(logs)} log(s) from {len(files)} file(s)'
            + (f'; search="{search}"' if search else '')
            + (f'; warnings: {"; ".join(read_errors)}' if read_errors else '')
        ),
        'warnings': read_errors,
    })



@login_required
def dashboard_redirect(request):
    """
    Redirect users to their role-based dashboard.
    """
    user = request.user
    role_redirects = {
        'admin': 'accounts:admin_dashboard',
        'author': 'accounts:author_dashboard',
        # checker and maker dashboards live canonically in the books app
        'checker': 'books:checker_dashboard',
        'maker': 'books:maker_dashboard',
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


# ---------------------------------------------------------------------------
# Media security: block XSS types + enforce paywall / authorization
# ---------------------------------------------------------------------------
BLOCKED_MEDIA_EXTENSIONS = {
    ".svg", ".svgz", ".html", ".htm", ".xhtml", ".xml", ".xsl", ".xslt",
    ".php", ".phtml", ".php3", ".php4", ".php5", ".php7", ".phar",
    ".asp", ".aspx", ".jsp", ".jspx", ".js", ".mjs", ".ts",
    ".exe", ".dll", ".so", ".bat", ".cmd", ".com", ".msi",
    ".sh", ".bash", ".ps1", ".vbs", ".wsf", ".cgi",
    ".pl", ".py", ".rb", ".jar", ".war", ".class",
    ".htaccess", ".htpasswd", ".shtml", ".cfg", ".ini",
    ".wasm", ".swf", ".xap",
}

PROTECTED_MEDIA_PREFIXES = (
    "books/files/",
    "books/samples/",
    "books/versions/",
)


def _user_may_access_book_file(user, relative_path: str) -> bool:
    """
    Authorization for manuscript / sample files.
    Staff (admin/maker/checker): allowed
    Book author: allowed
    Client with completed purchase of a published book: allowed
    Free published books: allowed for authenticated users
    Rejected/draft/unpurchased paid: denied
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    role = getattr(user, "role", None)
    if role in ("admin", "maker", "checker") or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True

    try:
        from books.models import Book
        from payments.models import Purchase

        book = (
            Book.objects.filter(file=relative_path).first()
            or Book.objects.filter(sample_file=relative_path).first()
        )
        if book is None:
            return False

        if getattr(book, "author_id", None) == user.id:
            return True

        if getattr(book, "status", None) != getattr(Book, "STATUS_PUBLISHED", "published"):
            return False

        if getattr(book, "is_free", False) or book.price == 0:
            return True

        return Purchase.objects.filter(
            user=user, book=book, status="completed"
        ).exists()
    except Exception as exc:
        logger.exception("Authorization check failed for %s: %s", relative_path, exc)
        return False


def secure_media_serve(request, path):
    """
    Secure media handler — only safe way to serve /media/.

    Fixes:
      - Stored XSS via SVG (block scriptable types)
      - Missing Authorization / Paywall Bypass (auth + purchase required for manuscripts)
    """
    import mimetypes
    import os
    from django.conf import settings
    from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden

    # 1. Path traversal
    if ".." in path or path.startswith("/") or "\\" in path:
        raise Http404()

    full = os.path.normpath(os.path.join(settings.MEDIA_ROOT, path))
    media_root = os.path.normpath(settings.MEDIA_ROOT)
    if not full.startswith(media_root + os.sep) and full != media_root:
        raise Http404()
    if not os.path.isfile(full):
        raise Http404()

    ext = os.path.splitext(full)[1].lower()

    # 2. Block dangerous extensions (Stored XSS)
    if ext in BLOCKED_MEDIA_EXTENSIONS:
        logger.warning(
            "Blocked media request for dangerous type: path=%s ip=%s",
            path, request.META.get("REMOTE_ADDR"),
        )
        return HttpResponse(
            "This file type cannot be served.",
            status=403,
            content_type="text/plain",
        )

    # 3. Authorization for protected manuscript paths
    normalized = path.replace("\\", "/").lstrip("/")
    if any(normalized.startswith(prefix) for prefix in PROTECTED_MEDIA_PREFIXES):
        if not _user_may_access_book_file(request.user, normalized):
            logger.warning(
                "Unauthorized media access: path=%s user=%s ip=%s",
                path,
                getattr(request.user, "username", "anon"),
                request.META.get("REMOTE_ADDR"),
            )
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            return HttpResponseForbidden(
                "You do not have permission to access this file. "
                "Purchase the book or contact support."
            )

    # 4. Safe content-type
    content_type, _ = mimetypes.guess_type(full)
    content_type = content_type or "application/octet-stream"
    if any(x in content_type.lower() for x in ("html", "svg", "javascript", "xml")):
        content_type = "application/octet-stream"

    response = FileResponse(open(full, "rb"), content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["X-Frame-Options"] = "DENY"
    response["Cache-Control"] = "private, no-store"

    if content_type == "application/octet-stream":
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(full)}"'
        )
    return response
