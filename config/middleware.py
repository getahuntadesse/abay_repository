"""
Security middleware for Abrehot / Abay Repository.
Addresses Ethio telecom SAR findings (CSP, nosniff, media hardening).
"""
from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Adds security headers to all responses.
    Media responses get stricter CSP to block stored XSS.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ""

        # Always
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        if path.startswith(media_url):
            # Never execute scripts from uploaded files (SAR 6.1 Stored XSS)
            response["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'none'; object-src 'none'; "
                "sandbox; base-uri 'none'"
            )
            # Force download for non-image media to reduce XSS risk
            ct = (response.get("Content-Type") or "").lower()
            if any(x in ct for x in ("html", "svg", "xml", "javascript", "text/")):
                response["Content-Disposition"] = "attachment"
                response["Content-Type"] = "application/octet-stream"
            elif "pdf" in ct:
                response.setdefault("Content-Disposition", "inline")
            # Images stay inline but nosniff + CSP still apply
        else:
            # App pages: tighten CSP (avoid unsafe-inline where possible later)
            if "Content-Security-Policy" not in response:
                response["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://code.jquery.com; "
                    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                    "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com data:; "
                    "img-src 'self' data: blob: https:; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
        return response
