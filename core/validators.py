# core/validators.py
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomPasswordValidator:
    def validate(self, password, user=None):
        # Check for common patterns
        common_patterns = [
            'password', '123456', 'qwerty', 'admin', 'letmein',
            'welcome', 'monkey', 'dragon', 'master', 'hello'
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                raise ValidationError(
                    _("This password is too common. Please choose a more secure password."),
                    code='password_too_common',
                )
        
        # Check for keyboard patterns
        keyboard_patterns = [
            r'qwerty', r'asdfgh', r'zxcvbn', r'123456',
            r'qwertyuiop', r'asdfghjkl', r'zxcvbnm'
        ]
        
        for pattern in keyboard_patterns:
            if re.search(pattern, password_lower):
                raise ValidationError(
                    _("This password contains a keyboard pattern. Please choose a more secure password."),
                    code='password_keyboard_pattern',
                )
        
        # Check for repeated characters (more than 3 times)
        if re.search(r'(.)\1{3,}', password):
            raise ValidationError(
                _("This password has too many repeated characters."),
                code='password_repeated_characters',
            )

    def get_help_text(self):
        return _(
            "Your password must be at least 10 characters long, "
            "contain both uppercase and lowercase letters, numbers, "
            "and special characters. Avoid common patterns."
        )