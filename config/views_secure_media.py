# config/views.py  — REPLACE secure_media_serve with this version
# Fixes:
#   1. Stored XSS via SVG (block scriptable types)
#   2. Missing Authorization / Paywall Bypass (book manuscripts require auth + purchase)

from django.shortcuts import render
from django.http import (
    JsonResponse, HttpResponseNotFound, HttpResponseServerError,
    FileResponse, Http404, HttpResponse, HttpResponseForbidden,
)
from django.template import loader
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
import os
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocked / dangerous extensions (stored XSS + executables)
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

# Paths under MEDIA_ROOT that contain protected manuscripts / samples
PROTECTED_MEDIA_PREFIXES = (
    "books/files/",
    "books/samples/",
    "books/versions/",
)


def _user_may_access_book_file(user, relative_path: str) -> bool:
    """
    Authorization for manuscript / sample files.
    - Staff (admin/maker/checker): allowed
    - Book author: allowed
    - Client with completed purchase of a published book: allowed
    - Free published books: allowed for authenticated users
    - Everything else (rejected, draft, unpurchased paid): denied
    """
    if not user or not user.is_authenticated:
        return False

    role = getattr(user, "role", None)
    if role in ("admin", "maker", "checker") or user.is_staff or user.is_superuser:
        return True

    try:
        from books.models import Book
        from payments.models import Purchase

        # Match Book.file or Book.sample_file by stored name
        book = (
            Book.objects.filter(file=relative_path).first()
            or Book.objects.filter(sample_file=relative_path).first()
        )
        if book is None:
            # Orphan / unknown file — deny
            return False

        # Author of the book
        if getattr(book, "author_id", None) == user.id:
            return True

        # Only published books are readable by clients
        if getattr(book, "status", None) != getattr(Book, "STATUS_PUBLISHED", "published"):
            return False

        if book.is_free or book.price == 0:
            return True

        return Purchase.objects.filter(
            user=user, book=book, status="completed"
        ).exists()
    except Exception as exc:
        logger.exception("Authorization check failed for %s: %s", relative_path, exc)
        return False


def secure_media_serve(request, path):
    """
    Secure media handler — MUST be the only way /media/ is served.

    - Blocks path traversal
    - Blocks SVG/HTML/JS and other scriptable/executable types (XSS fix)
    - Requires authentication + purchase (or author/staff) for book manuscripts
    - Forces safe Content-Type and CSP sandbox
    """
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

    # 2. Block dangerous extensions (Stored XSS via SVG, etc.)
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

    # Force download for unknown / octet-stream
    if content_type == "application/octet-stream":
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(full)}"'
        )

    return response
