import hashlib
import json
import base64
import uuid
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import requests


class TelebirrPaymentService:
    """Telebirr payment integration service"""
    
    def __init__(self):
        self.app_id = settings.TELEBIRR_CONFIG['APP_ID']
        self.app_key = settings.TELEBIRR_CONFIG['APP_KEY']
        self.short_code = settings.TELEBIRR_CONFIG['SHORT_CODE']
        self.public_key = settings.TELEBIRR_CONFIG['PUBLIC_KEY']
        self.notify_url = settings.TELEBIRR_CONFIG['NOTIFY_URL']
        self.return_url = settings.TELEBIRR_CONFIG['RETURN_URL']
        self.api_url = settings.TELEBIRR_CONFIG['API_URL']
    
    def _generate_nonce(self):
        """Generate a unique nonce for the transaction"""
        return str(uuid.uuid4()).replace('-', '')[:32]
    
    def _generate_out_trade_no(self):
        """Generate a unique transaction ID"""
        return f"AL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    def _encrypt_data(self, data):
        """Encrypt data using RSA public key"""
        # This requires the cryptography library
        # pip install cryptography
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        public_key = serialization.load_pem_public_key(
            self.public_key.encode(),
            backend=default_backend()
        )
        
        encrypted = public_key.encrypt(
            data.encode(),
            padding.PKCS1v15()
        )
        
        return base64.b64encode(encrypted).decode()
    
    def _generate_signature(self, params):
        """Generate SHA256 signature for request"""
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())
        
        # Create stringA
        string_a = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Generate SHA256 hash
        return hashlib.sha256(string_a.encode()).hexdigest().upper()
    
    def create_payment(self, amount, subject, receive_name, customer_phone=None):
        """
        Create a Telebirr payment request
        
        Args:
            amount: Payment amount in ETB
            subject: Payment subject/description
            receive_name: Name of the receiver
            customer_phone: Customer phone number (optional)
        
        Returns:
            dict: Contains payment_url and transaction_id
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        nonce = self._generate_nonce()
        out_trade_no = self._generate_out_trade_no()
        
        # Prepare payment parameters
        params = {
            'appId': self.app_id,
            'appKey': self.app_key,
            'nonce': nonce,
            'notifyUrl': self.notify_url,
            'outTradeNo': out_trade_no,
            'receiveName': receive_name,
            'returnUrl': self.return_url,
            'shortCode': self.short_code,
            'subject': subject,
            'timeoutExpress': '30m',
            'timestamp': timestamp,
            'totalAmount': str(amount),
        }
        
        # Add customer phone if provided
        if customer_phone:
            params['customerPhone'] = customer_phone
        
        # Create JSON payload
        payload = json.dumps(params)
        
        # Encrypt data
        encrypted_data = self._encrypt_data(payload)
        
        # Generate signature
        signature = self._generate_signature(params)
        
        # Prepare final request
        request_data = {
            'appId': self.app_id,
            'encrypted': encrypted_data,
            'sign': signature,
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=request_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            result = response.json()
            
            if result.get('code') == 0:
                return {
                    'success': True,
                    'payment_url': result['data']['toPayUrl'],
                    'transaction_id': out_trade_no,
                    'gateway_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Payment creation failed'),
                    'transaction_id': out_trade_no,
                    'gateway_response': result
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transaction_id': out_trade_no
            }
    
    def decrypt_notification(self, encrypted_data):
        """Decrypt incoming payment notification from Telebirr"""
        try:
            # Decrypt the data
            decrypted = self._decrypt_data(encrypted_data)
            return json.loads(decrypted)
        except Exception as e:
            return None
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt data using RSA private key"""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        private_key = serialization.load_pem_private_key(
            settings.TELEBIRR_CONFIG['PRIVATE_KEY'].encode(),
            password=None,
            backend=default_backend()
        )
        
        encrypted_bytes = base64.b64decode(encrypted_data)
        decrypted = private_key.decrypt(encrypted_bytes, padding.PKCS1v15())
        
        return decrypted.decode()


class CBEBirrPaymentService:
    """CBE Birr payment integration service"""
    
    def __init__(self):
        self.merchant_id = settings.CBE_BIRR_CONFIG['MERCHANT_ID']
        self.terminal_id = settings.CBE_BIRR_CONFIG['TERMINAL_ID']
        self.public_key = settings.CBE_BIRR_CONFIG['PUBLIC_KEY']
        self.notify_url = settings.CBE_BIRR_CONFIG['NOTIFY_URL']
        self.return_url = settings.CBE_BIRR_CONFIG['RETURN_URL']
        self.api_url = settings.CBE_BIRR_CONFIG['API_URL']
    
    def create_payment(self, amount, order_id, customer_name, customer_phone, customer_email):
        """
        Create a CBE Birr payment request
        
        Args:
            amount: Payment amount in ETB
            order_id: Unique order identifier
            customer_name: Customer's full name
            customer_phone: Customer's phone number
            customer_email: Customer's email address
        
        Returns:
            dict: Contains payment_url and transaction_id
        """
        # Prepare payment parameters
        params = {
            'merchantId': self.merchant_id,
            'terminalId': self.terminal_id,
            'orderId': order_id,
            'amount': str(amount),
            'currency': 'ETB',
            'customerName': customer_name,
            'customerPhone': customer_phone,
            'customerEmail': customer_email,
            'returnUrl': self.return_url,
            'notifyUrl': self.notify_url,
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=params,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            result = response.json()
            
            if result.get('status') == 'success':
                return {
                    'success': True,
                    'payment_url': result.get('paymentUrl'),
                    'transaction_id': order_id,
                    'gateway_response': result
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message', 'Payment creation failed'),
                    'transaction_id': order_id,
                    'gateway_response': result
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'transaction_id': order_id
            }