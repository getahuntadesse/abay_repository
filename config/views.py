# config/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound, HttpResponseServerError, FileResponse, StreamingHttpResponse
from django.template import loader
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from datetime import datetime, timedelta
import logging
from pathlib import Path
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


def _is_admin_user(user):
    """True if user can access admin log tools."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return getattr(user, "role", None) == "admin"


def _resolve_log_file():
    """Prefer settings.LOG_FILE_PATH (logs.txt), fall back to common paths."""
    candidates = []
    log_path = getattr(settings, "LOG_FILE_PATH", None)
    if log_path:
        candidates.append(Path(log_path) if not isinstance(log_path, Path) else log_path)
    base = Path(settings.BASE_DIR)
    candidates.extend([
        base / "logs.txt",
        base / "logs" / "logs.txt",
        base / "logs" / "abay_repository.log",
        base / "logs" / "django.log",
    ])
    for path in candidates:
        try:
            if path.exists() and path.is_file():
                return path
        except OSError:
            continue
    # Default write target even if missing
    return Path(log_path) if log_path else (base / "logs.txt")


def _parse_log_lines(lines, limit=500):
    """Parse log lines into structured entries (newest first)."""
    # Formats supported:
    # [2026-08-13 14:58:39] ERROR django.server - message
    # [2026-08-13 14:58:39] LEVEL name - message
    # [2026-08-13 14:58:39] PAYMENT INFO - message
    patterns = [
        re.compile(
            r"^\[(?P<ts>[^\]]+)\]\s+(?P<tag>PAYMENT|AUTH|SECURITY)\s+(?P<level>\w+)\s+-\s+(?P<msg>.*)$"
        ),
        re.compile(
            r"^\[(?P<ts>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<name>[\w.]+)\s+-\s+(?P<msg>.*)$"
        ),
        re.compile(
            r"^\[(?P<ts>[^\]]+)\]\s+(?P<level>\w+)\s+-\s+(?P<msg>.*)$"
        ),
        re.compile(
            r"^\[(?P<ts>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<msg>.*)$"
        ),
    ]
    logs = []
    slice_lines = lines[-limit:] if len(lines) > limit else lines
    for raw in slice_lines:
        line = raw.rstrip("\n\r")
        if not line.strip() or line.strip().startswith("#"):
            continue
        matched = False
        for pat in patterns:
            m = pat.match(line)
            if not m:
                continue
            gd = m.groupdict()
            ts_str = gd.get("ts", "")
            level = (gd.get("level") or "INFO").upper()
            tag = (gd.get("tag") or "").upper()
            message = gd.get("msg") or line
            # Map special tags to filter levels used in UI
            if tag in ("PAYMENT", "AUTH", "SECURITY"):
                display_level = tag
            else:
                display_level = level
            iso_ts = timezone.now().isoformat()
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    iso_ts = datetime.strptime(ts_str.strip(), fmt).isoformat()
                    break
                except ValueError:
                    continue
            logs.append({
                "timestamp": iso_ts,
                "level": display_level,
                "message": message.strip(),
                "raw": line,
            })
            matched = True
            break
        if not matched:
            level = "INFO"
            upper = line.upper()
            if "CRITICAL" in upper:
                level = "CRITICAL"
            elif "ERROR" in upper or "EXCEPTION" in upper:
                level = "ERROR"
            elif "WARNING" in upper or "WARN" in upper:
                level = "WARNING"
            elif "PAYMENT" in upper:
                level = "PAYMENT"
            elif "AUTH" in upper:
                level = "AUTH"
            elif "DEBUG" in upper:
                level = "DEBUG"
            logs.append({
                "timestamp": timezone.now().isoformat(),
                "level": level,
                "message": line,
                "raw": line,
            })
    logs.reverse()
    return logs


@login_required
def admin_logs(request):
    """
    API: fetch system logs from logs.txt for the admin dashboard.
    GET /api/admin/logs/?limit=300&level=ERROR
    """
    if not _is_admin_user(request.user):
        return JsonResponse({"success": False, "message": "Forbidden", "logs": []}, status=403)

    log_file = _resolve_log_file()
    try:
        limit = int(request.GET.get("limit", 300))
    except ValueError:
        limit = 300
    limit = max(50, min(limit, 2000))
    level_filter = (request.GET.get("level") or "").upper().strip()

    if not log_file.exists():
        return JsonResponse({
            "success": True,
            "logs": [],
            "message": f"No log file yet at {log_file.name}",
            "count": 0,
            "file_size": 0,
            "file_name": log_file.name,
        })

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        logs = _parse_log_lines(lines, limit=limit)
        if level_filter and level_filter != "ALL":
            logs = [x for x in logs if x.get("level") == level_filter]
        try:
            file_size = log_file.stat().st_size
        except OSError:
            file_size = 0
        return JsonResponse({
            "success": True,
            "logs": logs,
            "count": len(logs),
            "file_size": file_size,
            "file_name": log_file.name,
            "file_path": str(log_file.name),
        })
    except Exception as e:
        logger.exception("Error reading log file")
        return JsonResponse({
            "success": False,
            "message": str(e),
            "logs": [],
            "count": 0,
        }, status=500)


@login_required
def admin_logs_export(request):
    """
    Download logs.txt (or filtered text export).
    GET /api/admin/logs/export/?format=txt|csv
    """
    if not _is_admin_user(request.user):
        return JsonResponse({"success": False, "message": "Forbidden"}, status=403)

    log_file = _resolve_log_file()
    fmt = (request.GET.get("format") or "txt").lower()
    level_filter = (request.GET.get("level") or "").upper().strip()

    if not log_file.exists():
        return JsonResponse({"success": False, "message": "Log file not found"}, status=404)

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.splitlines(True)

        if level_filter and level_filter != "ALL":
            parsed = _parse_log_lines(lines, limit=50000)
            parsed = [x for x in parsed if x.get("level") == level_filter]
            # export in chronological order
            parsed.reverse()
            if fmt == "csv":
                import csv
                from io import StringIO
                buf = StringIO()
                writer = csv.writer(buf)
                writer.writerow(["timestamp", "level", "message"])
                for row in parsed:
                    writer.writerow([row.get("timestamp", ""), row.get("level", ""), row.get("message", "")])
                data = buf.getvalue()
                resp = HttpResponse(data, content_type="text/csv; charset=utf-8")
                resp["Content-Disposition"] = f'attachment; filename="abay_logs_{level_filter.lower()}.csv"'
                return resp
            data = "\n".join(x.get("raw") or x.get("message", "") for x in parsed)
            resp = HttpResponse(data, content_type="text/plain; charset=utf-8")
            resp["Content-Disposition"] = f'attachment; filename="abay_logs_{level_filter.lower()}.txt"'
            return resp

        # Full file download
        if fmt == "csv":
            parsed = _parse_log_lines(lines, limit=50000)
            parsed.reverse()
            import csv
            from io import StringIO
            buf = StringIO()
            writer = csv.writer(buf)
            writer.writerow(["timestamp", "level", "message"])
            for row in parsed:
                writer.writerow([row.get("timestamp", ""), row.get("level", ""), row.get("message", "")])
            resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
            resp["Content-Disposition"] = 'attachment; filename="abay_logs.csv"'
            return resp

        resp = HttpResponse(content, content_type="text/plain; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{log_file.name}"'
        return resp
    except Exception as e:
        logger.exception("Log export failed")
        return JsonResponse({"success": False, "message": str(e)}, status=500)



@login_required

def admin_logs_stream(request):
    """
    Real-time log streaming via Server-Sent Events (SSE).
    GET /api/admin/logs/stream/
    """
    if not _is_admin_user(request.user):
        return JsonResponse({"success": False, "message": "Forbidden"}, status=403)

    import json
    import time

    log_file = _resolve_log_file()
    try:
        initial_limit = int(request.GET.get("limit", 150))
    except ValueError:
        initial_limit = 150
    initial_limit = max(20, min(initial_limit, 500))
    max_seconds = int(request.GET.get("max_seconds", 300))
    max_seconds = max(60, min(max_seconds, 1800))
    poll_interval = 0.6

    def _sse(event, data_obj):
        return "event: %s\ndata: %s\n\n" % (event, json.dumps(data_obj))

    def event_stream():
        start_t = time.time()
        position = 0
        try:
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    position = f.tell()
                parsed = _parse_log_lines(lines, limit=initial_limit)
                try:
                    fsize = log_file.stat().st_size
                except OSError:
                    fsize = 0
                yield _sse("snapshot", {"logs": parsed, "file_size": fsize})
            else:
                yield _sse("snapshot", {"logs": [], "file_size": 0})
        except Exception as e:
            yield _sse("error", {"message": str(e)})

        last_ping = time.time()
        while time.time() - start_t < max_seconds:
            try:
                if not log_file.exists():
                    time.sleep(poll_interval)
                    continue
                size = log_file.stat().st_size
                if size < position:
                    position = 0
                    yield _sse("reset", {"message": "log file rotated"})
                if size > position:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(position)
                        chunk = f.read()
                        position = f.tell()
                    new_lines = [ln for ln in chunk.splitlines() if ln.strip()]
                    if new_lines:
                        parsed = _parse_log_lines(new_lines, limit=len(new_lines) + 5)
                        parsed.reverse()
                        for entry in parsed:
                            yield _sse("log", entry)
                now = time.time()
                if now - last_ping >= 15:
                    yield _sse("ping", {"ts": now, "file_size": size})
                    last_ping = now
            except GeneratorExit:
                break
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                time.sleep(2)
            time.sleep(poll_interval)
        yield _sse("done", {"message": "stream timeout - reconnect"})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Accel-Buffering"] = "no"
    response["Connection"] = "keep-alive"
    return response



def reader_service_worker(request):
    """Serve reader service worker with correct scope header."""
    from django.contrib.staticfiles.finders import find
    from django.http import HttpResponse
    import os
    path = find("js/reader-sw.js")
    if not path:
        path = os.path.join(settings.BASE_DIR, "static", "js", "reader-sw.js")
    try:
        with open(path, "r", encoding="utf-8") as f:
            body = f.read()
    except OSError:
        return HttpResponse("Service worker not found", status=404)
    resp = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


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