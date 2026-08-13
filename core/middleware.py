# core/middleware.py
"""
Custom middleware for production-grade security headers.

Applies comprehensive HTTP security headers to all HTML responses:
  - Content-Security-Policy (CSP)
  - Strict-Transport-Security (HSTS)
  - X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
  - Referrer-Policy
  - Permissions-Policy
  - Cross-Origin-* headers
  - Cache-Control (prevents sensitive pages from being cached)
"""

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Comprehensive security headers middleware.
    Only applies to HTML responses, not static/media files.
    """

    def process_response(self, request, response):
        # Skip for static files and media files — they don't need security headers
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return response

        # Only inject security headers on HTML responses
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response

        self._add_basic_security_headers(request, response)
        self._add_csp_headers(request, response)
        self._add_permissions_policy(response)
        self._add_cross_origin_headers(response)
        self._add_cache_control(request, response)
        self._remove_sensitive_headers(response)

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_basic_security_headers(self, request, response):
        """Add foundational security headers."""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = getattr(settings, 'X_FRAME_OPTIONS', 'DENY')
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = getattr(
            settings, 'SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin'
        )

        # HSTS — only meaningful over HTTPS
        if request.is_secure() or getattr(settings, 'SECURE_SSL_REDIRECT', False):
            hsts_max_age = getattr(settings, 'SECURE_HSTS_SECONDS', 31536000)
            hsts_header = f'max-age={hsts_max_age}'
            if getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', True):
                hsts_header += '; includeSubDomains'
            if getattr(settings, 'SECURE_HSTS_PRELOAD', True):
                hsts_header += '; preload'
            response['Strict-Transport-Security'] = hsts_header

    def _add_csp_headers(self, request, response):
        """Build and set Content-Security-Policy header."""
        # Skip if django-csp is managing this
        if 'csp' in getattr(settings, 'INSTALLED_APPS', []):
            return

        base_url = getattr(settings, 'BASE_URL', 'http://localhost:3000')
        debug = getattr(settings, 'DEBUG', False)

        csp_directives = {
            'default-src': ["'self'"],
            'script-src': [
                "'self'",
                "'unsafe-inline'",          # Required for inline scripts in templates
                'https://cdn.jsdelivr.net',
                'https://cdnjs.cloudflare.com',
                'https://code.jquery.com',
                'https://stackpath.bootstrapcdn.com',
            ],
            'style-src': [
                "'self'",
                "'unsafe-inline'",          # Required for inline styles in templates
                'https://cdn.jsdelivr.net',
                'https://cdnjs.cloudflare.com',
                'https://stackpath.bootstrapcdn.com',
                'https://fonts.googleapis.com',
            ],
            'img-src': [
                "'self'",
                'data:',
                'https:',
                base_url,
                'https://via.placeholder.com',
                'https://placehold.co',
            ],
            'font-src': [
                "'self'",
                'https:',
                'data:',
                'https://cdnjs.cloudflare.com',
                'https://fonts.gstatic.com',
            ],
            'connect-src': [
                "'self'",
                base_url,
                'https://esignet.ida.fayda.et',
                'https://196.188.120.3',
                'https://api.telebirr.et',
            ],
            'frame-src': [
                "'self'",
                'https://esignet.ida.fayda.et',
                'https://telebirr.et',
            ],
            'object-src': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
            'frame-ancestors': ["'none'"],
        }

        # Development-only relaxations
        if debug:
            # Allow eval for hot-reloading tools, avoid duplication
            if "'unsafe-eval'" not in csp_directives['script-src']:
                csp_directives['script-src'].append("'unsafe-eval'")
            csp_directives['connect-src'].extend([
                'http://localhost:3000',
                'ws://localhost:3000',
                'ws://127.0.0.1:3000',
            ])
        else:
            # Production: tell browsers to upgrade mixed content
            csp_directives['upgrade-insecure-requests'] = []

        # Build CSP string — directives with no values (like upgrade-insecure-requests)
        # are emitted as a bare name
        parts = []
        for directive, values in csp_directives.items():
            if values:
                parts.append(f"{directive} {' '.join(values)}")
            else:
                parts.append(directive)

        response['Content-Security-Policy'] = '; '.join(parts)

    def _add_permissions_policy(self, response):
        """Disable browser features that are not required by this application."""
        response['Permissions-Policy'] = (
            'accelerometer=(), '
            'ambient-light-sensor=(), '
            'autoplay=(), '
            'battery=(), '
            'camera=(), '
            'display-capture=(), '
            'document-domain=(), '
            'encrypted-media=(), '
            'fullscreen=(), '
            'geolocation=(), '
            'gyroscope=(), '
            'magnetometer=(), '
            'microphone=(), '
            'midi=(), '
            'payment=(), '
            'picture-in-picture=(), '
            'publickey-credentials-get=(), '
            'screen-wake-lock=(), '
            'speaker-selection=(), '
            'usb=(), '
            'web-share=(), '
            'xr-spatial-tracking=()'
        )

    def _add_cross_origin_headers(self, response):
        """Add cross-origin isolation headers."""
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'

    def _add_cache_control(self, request, response):
        """
        Prevent sensitive authenticated pages from being stored in browser or
        proxy caches.  Public pages keep their existing cache headers.
        """
        # Only enforce no-store on authenticated user sessions
        if request.user.is_authenticated:
            # Don't override if the view already set explicit cache directives
            if 'Cache-Control' not in response:
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'

    def _remove_sensitive_headers(self, response):
        """Strip headers that leak server technology details."""
        for header in ('Server', 'X-Powered-By'):
            if header in response:
                del response[header]