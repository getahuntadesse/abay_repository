"""
Protect the obfuscated Django admin path (SAR 6.3).
"""
import logging
from django.conf import settings
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AdminPathSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        path = (getattr(settings, "ADMIN_URL_PATH", "secure-abay-admin") or "secure-abay-admin").strip("/")
        self.admin_prefix = "/" + path + "/"

    def __call__(self, request):
        try:
            path = request.path or ""
            if path.startswith(self.admin_prefix) or path.rstrip("/") == self.admin_prefix.rstrip("/"):
                allowed = getattr(settings, "ADMIN_ALLOWED_IPS", None) or []
                ip = get_client_ip(request)
                if allowed and ip not in allowed:
                    logger.warning("Admin access denied for IP %s path=%s", ip, path)
                    return HttpResponseForbidden("Admin access is restricted.")
                user = getattr(request, "user", None)
                uname = getattr(user, "username", "-") if user is not None else "-"
                logger.info("Admin path access IP=%s user=%s path=%s", ip, uname, path)
        except Exception as e:
            logger.exception("AdminPathSecurityMiddleware error: %s", e)
        return self.get_response(request)
