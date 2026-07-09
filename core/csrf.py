# core/csrf.py
from django.middleware.csrf import CsrfViewMiddleware
from django.http import JsonResponse
from django.core.cache import cache
import hashlib
import time

class EnhancedCsrfMiddleware(CsrfViewMiddleware):
    """Enhanced CSRF protection with additional checks"""
    
    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Skip CSRF for API endpoints with token authentication
        if request.path.startswith('/api/'):
            # Check for API token instead
            api_token = request.headers.get('X-API-TOKEN')
            if api_token:
                if self.validate_api_token(api_token, request.user):
                    return None
        
        # Check for duplicate CSRF token usage (prevent replay attacks)
        csrf_token = request.POST.get('csrfmiddlewaretoken')
        if csrf_token:
            token_hash = hashlib.sha256(csrf_token.encode()).hexdigest()
            cache_key = f"csrf_used_{token_hash}"
            
            if cache.get(cache_key):
                return JsonResponse({'error': 'CSRF token already used.'}, status=403)
            
            # Store used token for 5 minutes
            cache.set(cache_key, True, 300)
        
        # Call parent method
        return super().process_view(request, callback, callback_args, callback_kwargs)
    
    def validate_api_token(self, token, user):
        """Validate API token"""
        # Implementation depends on your token system
        from core.models import APIToken
        try:
            api_token = APIToken.objects.get(token=token)
            return api_token.is_valid()
        except APIToken.DoesNotExist:
            return False