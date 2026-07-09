# core/db.py - Database security utilities
from django.db import connection
from django.core.exceptions import ValidationError
import re

class SQLInjectionProtection:
    @staticmethod
    def validate_input(input_value):
        """Validate input for potential SQL injection"""
        if not input_value:
            return input_value
        
        # SQL injection patterns
        patterns = [
            r'(\bSELECT\b.*\bFROM\b)',
            r'(\bINSERT\b.*\bINTO\b)',
            r'(\bUPDATE\b.*\bSET\b)',
            r'(\bDELETE\b.*\bFROM\b)',
            r'(\bDROP\b.*\bTABLE\b)',
            r'(\bUNION\b.*\bSELECT\b)',
            r'(\bOR\s+1\s*=\s*1\b)',
            r'(\bOR\s+true\b)',
            r'(\b;\s*--\b)',
            r'(\b/\*.*\*/)',
        ]
        
        for pattern in patterns:
            if re.search(pattern, str(input_value), re.IGNORECASE):
                raise ValidationError("Input contains potentially malicious SQL patterns.")
        
        return input_value
    
    @staticmethod
    def escape_string(value):
        """Escape string for SQL queries (fallback)"""
        if not value:
            return value
        
        # Use Django's built-in escaping
        from django.utils.html import escape
        
        # Additional escaping for SQL
        value = value.replace("'", "''")
        value = value.replace("\\", "\\\\")
        value = value.replace("\0", "\\0")
        value = value.replace("\n", "\\n")
        value = value.replace("\r", "\\r")
        value = value.replace("\x1a", "\\Z")
        
        return value

    @staticmethod
    def validate_order_by(order_by, allowed_fields):
        """Validate ORDER BY field to prevent injection"""
        if order_by not in allowed_fields:
            raise ValidationError(f"Invalid order by field: {order_by}")
        return order_by