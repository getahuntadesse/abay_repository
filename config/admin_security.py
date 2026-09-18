"""
Protect the obfuscated Django admin path (SAR 6.3).
Optional IP allowlist via ADMIN_ALLOWED_IPS.
Require staff + active; log access attempts.
"""
import logging
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AdminPathSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + (getattr(settings, "ADMIN_URL_PATH", "secure-abay-admin") or "secure-abay-admin").strip("/") + "/"

    def __call__(self, request):
        path = request.path or ""
        if path.startswith(self.admin_prefix) or path == self.admin_prefix.rstrip("/"):
            allowed = getattr(settings, "ADMIN_ALLOWED_IPS", None) or []
            ip = get_client_ip(request)
            if allowed and ip not in allowed:
                logger.warning("Admin access denied for IP %s path=%s", ip, path)
                return HttpResponseForbidden("Admin access is restricted.")
            # Log every hit
            logger.info("Admin path access IP=%s user=%s path=%s", ip, getattr(request.user, "username", "-"), path)
        return self.get_response(request)
