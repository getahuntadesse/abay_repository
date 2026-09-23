# config/settings.py — ensure these values exist

# ---------------------------------------------------------------------------
# Upload restrictions (no SVG)
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".epub", ".jpg", ".jpeg", ".png"]
ALLOWED_UPLOAD_MIME_TYPES = [
    "application/pdf",
    "application/epub+zip",
    "image/jpeg",
    "image/png",
]

# ---------------------------------------------------------------------------
# Login lockout (shared cache required across workers)
# ---------------------------------------------------------------------------
LOGIN_MAX_ATTEMPTS = 5          # failures before lockout
LOGIN_LOCKOUT_SECONDS = 900     # 15 minutes

# Prefer Redis in production so lockout state is shared by all gunicorn workers
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/1",
#     }
# }

# ---------------------------------------------------------------------------
# Media — never let nginx alias MEDIA_ROOT directly
# MEDIA_URL stays /media/ but must be proxied to Django secure_media_serve
# ---------------------------------------------------------------------------
MEDIA_URL = "/media/"
# MEDIA_ROOT = ...

# ---------------------------------------------------------------------------
# Security headers (already present via core.middleware.SecurityHeadersMiddleware)
# Ensure middleware order includes:
#   'core.middleware.SecurityHeadersMiddleware',
# ---------------------------------------------------------------------------
