# core/two_factor.py
import pyotp
import qrcode
import base64
from io import BytesIO
from django.core.cache import cache
from django.utils import timezone
import hashlib

class TwoFactorAuth:
    @staticmethod
    def generate_secret():
        """Generate a new 2FA secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def get_totp(secret):
        """Get TOTP instance"""
        return pyotp.TOTP(secret)
    
    @staticmethod
    def verify_code(secret, code):
        """Verify 2FA code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def generate_qr_code(secret, username, issuer="Abrehot Library"):
        """Generate QR code for 2FA setup"""
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=username, issuer_name=issuer)
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            'qr_code': img_str,
            'secret': secret,
            'provisioning_uri': provisioning_uri
        }
    
    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup codes for emergency access"""
        import random
        import string
        
        codes = []
        for _ in range(count):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            # Hash codes for storage
            hashed = hashlib.sha256(code.encode()).hexdigest()
            codes.append({'code': code, 'hashed': hashed})
        
        return codes