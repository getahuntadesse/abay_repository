# core/middleware.py
import logging
import hashlib
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings
import time
from django.core.cache import cache

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # X-Content-Type-Options - Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # X-Frame-Options - Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Referrer-Policy - Control referrer information
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions-Policy - Restrict browser features
        response['Permissions-Policy'] = (
            'geolocation=(), '
            'microphone=(), '
            'camera=(), '
            'payment=(), '
            'usb=(), '
            'bluetooth=(), '
            'autoplay=(self)'
        )
        
        # Cross-Origin-Opener-Policy - Prevent cross-origin attacks
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        
        # Cross-Origin-Embedder-Policy
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        
        # Clear-Site-Data (when logging out)
        if request.path == '/logout/':
            response['Clear-Site-Data'] = '"cache", "cookies", "storage", "executionContexts"'
        
        # Server header removal (hide technology)
        response['Server'] = 'Secure Server'
        
        return response

class AuditLogMiddleware(MiddlewareMixin):
    """Log all significant actions for auditing"""
    
    def process_request(self, request):
        # Log authentication attempts
        if request.path.startswith('/accounts/login/'):
            logger.info(
                f"Login attempt: IP={self.get_client_ip(request)}, "
                f"User-Agent={request.META.get('HTTP_USER_AGENT', 'Unknown')}"
            )
        
        # Log sensitive operations
        sensitive_paths = ['/admin/', '/dashboard/royalties/', '/dashboard/books/']
        if any(path in request.path for path in sensitive_paths) and request.user.is_authenticated:
            logger.info(
                f"Sensitive access: User={request.user.username}, "
                f"Path={request.path}, IP={self.get_client_ip(request)}"
            )
    
    def process_response(self, request, response):
        # Log logout events
        if request.path == '/accounts/logout/' and request.user.is_authenticated:
            logger.info(
                f"Logout: User={request.user.username}, IP={self.get_client_ip(request)}"
            )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting for sensitive endpoints"""
    
    def process_request(self, request):
        # Rate limit for login attempts
        if request.path.startswith('/accounts/login/'):
            ip = self.get_client_ip(request)
            key = f"login_attempts_{ip}"
            attempts = cache.get(key, 0)
            
            if attempts >= 5:
                return JsonResponse(
                    {'error': 'Too many login attempts. Please try again later.'},
                    status=429
                )
            
            cache.set(key, attempts + 1, 600)  # 10 minutes
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class SessionTimeoutMiddleware(MiddlewareMixin):
    """Auto logout inactive users"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            now = time.time()
            
            if last_activity:
                idle_time = now - last_activity
                if idle_time > settings.SESSION_COOKIE_AGE:
                    from django.contrib.auth import logout
                    logout(request)
                    return
        
        request.session['last_activity'] = time.time()