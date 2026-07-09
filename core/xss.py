# core/xss.py
import bleach
from django.utils.html import escape
from bleach.sanitizer import Cleaner

class XSSProtection:
    @staticmethod
    def sanitize_html(content):
        """Sanitize HTML content to prevent XSS"""
        if not content:
            return content
        
        # Allowed HTML tags and attributes
        allowed_tags = [
            'p', 'br', 'b', 'i', 'u', 'strong', 'em',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'pre',
            'code', 'span', 'div', 'a', 'img'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title', 'target', 'rel'],
            'img': ['src', 'alt', 'width', 'height'],
            'span': ['style'],
            'div': ['style', 'class'],
            '*': ['class']
        }
        
        # Clean HTML
        cleaner = Cleaner(
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True,
            strip_comments=True
        )
        
        cleaned = cleaner.clean(content)
        return cleaned
    
    @staticmethod
    def escape_json(data):
        """Escape JSON data for safe output"""
        if isinstance(data, dict):
            return {k: XSSProtection.escape_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [XSSProtection.escape_json(item) for item in data]
        elif isinstance(data, str):
            return escape(data)
        else:
            return data
    
    @staticmethod
    def validate_url(url):
        """Validate URL to prevent javascript: scheme"""
        if not url:
            return ''
        
        # Block javascript: and data: schemes
        blocked_schemes = ['javascript:', 'data:', 'vbscript:', 'mhtml:']
        url_lower = url.lower()
        
        for scheme in blocked_schemes:
            if url_lower.startswith(scheme):
                return ''
        
        # Allow only http and https
        if not url_lower.startswith(('http://', 'https://', '/')):
            return ''
        
        return url