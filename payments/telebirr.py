# payments/telebirr.py
import json
import requests
import base64
import hashlib
import hmac
import time
import uuid
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class TelebirrService:
    """
    Telebirr Payment Gateway Integration Service
    Based on Ethiotelecom API specification
    """
    
    def __init__(self):
        # Load configuration from settings
        self.base_url = getattr(settings, 'TELEBIRR_BASE_URL', 'https://196.188.120.3:38443/apiaccess/payment/gateway')
        self.fabric_app_id = getattr(settings, 'TELEBIRR_FABRIC_APP_ID', 'c4182ef8-9249-458a-985e-06d191f4d505')
        self.app_secret = getattr(settings, 'TELEBIRR_APP_SECRET', 'fad0f06383c6297f545876694b974599')
        self.merchant_app_id = getattr(settings, 'TELEBIRR_MERCHANT_APP_ID', '930231098009602')
        self.merchant_code = getattr(settings, 'TELEBIRR_MERCHANT_CODE', '101011')
        self.private_key = getattr(settings, 'TELEBIRR_PRIVATE_KEY', '')
        self.public_key = getattr(settings, 'TELEBIRR_PUBLIC_KEY', '')
        
        # Token cache
        self._fabric_token = None
        self._token_expiry = None
        
        # Load private key
        self._rsa_private_key = None
        if self.private_key:
            try:
                self._rsa_private_key = serialization.load_pem_private_key(
                    self.private_key.encode('utf-8'),
                    password=None
                )
            except Exception as e:
                logger.error(f"Failed to load private key: {str(e)}")
    
    def _generate_signature(self, data):
        """
        Generate HMAC SHA256 signature for API requests
        """
        # Sort data by key
        sorted_data = dict(sorted(data.items()))
        # Convert to query string
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_data.items()])
        # Generate HMAC using app_secret
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _rsa_sign(self, data):
        """
        Sign data using RSA private key
        """
        if not self._rsa_private_key:
            logger.warning("RSA private key not available for signing")
            return None
        
        try:
            signature = self._rsa_private_key.sign(
                data.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except Exception as e:
            logger.error(f"RSA signing error: {str(e)}")
            return None
    
    def _get_headers(self, token=None):
        """
        Get headers for API requests
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Merchant-App-ID': self.merchant_app_id,
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers
    
    def apply_fabric_token(self):
        """
        Apply for fabric token (authentication)
        Endpoint: /fabric/token/apply
        """
        try:
            # Generate timestamp
            timestamp = int(time.time() * 1000)
            
            # Prepare request data
            data = {
                'fabricAppId': self.fabric_app_id,
                'appSecret': self.app_secret,
                'merchantAppId': self.merchant_app_id,
                'timestamp': timestamp
            }
            
            # Generate signature
            data['signature'] = self._generate_signature(data)
            
            # Make request
            response = requests.post(
                f"{self.base_url}/fabric/token/apply",
                json=data,
                headers=self._get_headers(),
                timeout=30,
                verify=False  # For testing with self-signed certificates
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0000':
                    token_data = result.get('data', {})
                    self._fabric_token = token_data.get('fabricToken')
                    self._token_expiry = time.time() + token_data.get('expiresIn', 3600)
                    logger.info("Fabric token obtained successfully")
                    return True, token_data
                else:
                    logger.error(f"Token application failed: {result}")
                    return False, {'error': result.get('message', 'Token application failed')}
            else:
                logger.error(f"Token API error: {response.status_code} - {response.text}")
                return False, {'error': f'API error: {response.status_code}'}
                
        except requests.exceptions.Timeout:
            return False, {'error': 'Request timed out'}
        except requests.exceptions.ConnectionError:
            return False, {'error': 'Connection error'}
        except Exception as e:
            logger.error(f"Token application error: {str(e)}")
            return False, {'error': str(e)}
    
    def get_fabric_token(self):
        """
        Get valid fabric token (refresh if expired)
        """
        if not self._fabric_token or (self._token_expiry and time.time() > self._token_expiry - 60):
            success, result = self.apply_fabric_token()
            if not success:
                return None
        return self._fabric_token
    
    def initiate_payment(self, amount, phone_number, description, reference, 
                         customer_name=None, customer_email=None, 
                         timeout_seconds=300):
        """
        Initiate a payment
        Endpoint: /payment/initiate
        """
        # Get fabric token
        token = self.get_fabric_token()
        if not token:
            return False, {'error': 'Failed to obtain fabric token'}
        
        # Generate transaction ID
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8]}"
        
        # Prepare request data
        data = {
            'merchantAppId': self.merchant_app_id,
            'merchantCode': self.merchant_code,
            'transactionId': transaction_id,
            'amount': str(amount),
            'phoneNumber': phone_number,
            'description': description,
            'reference': reference,
            'timestamp': int(time.time() * 1000),
            'timeoutSeconds': timeout_seconds,
        }
        
        # Add optional fields
        if customer_name:
            data['customerName'] = customer_name
        if customer_email:
            data['customerEmail'] = customer_email
        
        # Generate signature
        data['signature'] = self._generate_signature(data)
        
        # RSA sign (if available)
        rsa_signature = self._rsa_sign(json.dumps(data))
        if rsa_signature:
            data['rsaSignature'] = rsa_signature
        
        try:
            response = requests.post(
                f"{self.base_url}/payment/initiate",
                json=data,
                headers=self._get_headers(token),
                timeout=30,
                verify=False  # For testing with self-signed certificates
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0000':
                    payment_data = result.get('data', {})
                    return True, {
                        'transaction_id': transaction_id,
                        'payment_id': payment_data.get('paymentId'),
                        'status': 'pending',
                        'message': payment_data.get('message', 'Payment initiated successfully'),
                        'payment_url': payment_data.get('paymentUrl'),
                        'qr_code': payment_data.get('qrCode'),
                        'expires_at': payment_data.get('expiresAt'),
                    }
                else:
                    return False, {'error': result.get('message', 'Payment initiation failed')}
            else:
                logger.error(f"Payment API error: {response.status_code} - {response.text}")
                return False, {'error': f'API error: {response.status_code}'}
                
        except requests.exceptions.Timeout:
            return False, {'error': 'Payment request timed out'}
        except requests.exceptions.ConnectionError:
            return False, {'error': 'Connection error'}
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return False, {'error': str(e)}
    
    def check_payment_status(self, transaction_id):
        """
        Check payment status
        Endpoint: /payment/status
        """
        token = self.get_fabric_token()
        if not token:
            return False, {'error': 'Failed to obtain fabric token'}
        
        data = {
            'merchantAppId': self.merchant_app_id,
            'merchantCode': self.merchant_code,
            'transactionId': transaction_id,
            'timestamp': int(time.time() * 1000),
        }
        
        data['signature'] = self._generate_signature(data)
        
        try:
            response = requests.post(
                f"{self.base_url}/payment/status",
                json=data,
                headers=self._get_headers(token),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0000':
                    status_data = result.get('data', {})
                    return True, {
                        'status': status_data.get('status'),
                        'transaction_id': transaction_id,
                        'amount': status_data.get('amount'),
                        'payment_date': status_data.get('paymentDate'),
                        'message': status_data.get('message'),
                    }
                else:
                    return False, {'error': result.get('message', 'Status check failed')}
            else:
                return False, {'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Status check error: {str(e)}")
            return False, {'error': str(e)}
    
    def cancel_payment(self, transaction_id):
        """
        Cancel a pending payment
        Endpoint: /payment/cancel
        """
        token = self.get_fabric_token()
        if not token:
            return False, {'error': 'Failed to obtain fabric token'}
        
        data = {
            'merchantAppId': self.merchant_app_id,
            'merchantCode': self.merchant_code,
            'transactionId': transaction_id,
            'timestamp': int(time.time() * 1000),
        }
        
        data['signature'] = self._generate_signature(data)
        
        try:
            response = requests.post(
                f"{self.base_url}/payment/cancel",
                json=data,
                headers=self._get_headers(token),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0000':
                    return True, result.get('data', {})
                else:
                    return False, {'error': result.get('message', 'Cancellation failed')}
            else:
                return False, {'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Cancel error: {str(e)}")
            return False, {'error': str(e)}
    
    def refund_payment(self, transaction_id, amount, reason):
        """
        Refund a completed payment
        Endpoint: /payment/refund
        """
        token = self.get_fabric_token()
        if not token:
            return False, {'error': 'Failed to obtain fabric token'}
        
        refund_id = f"REF{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8]}"
        
        data = {
            'merchantAppId': self.merchant_app_id,
            'merchantCode': self.merchant_code,
            'transactionId': transaction_id,
            'refundId': refund_id,
            'amount': str(amount),
            'reason': reason,
            'timestamp': int(time.time() * 1000),
        }
        
        data['signature'] = self._generate_signature(data)
        
        try:
            response = requests.post(
                f"{self.base_url}/payment/refund",
                json=data,
                headers=self._get_headers(token),
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == '0000':
                    return True, result.get('data', {})
                else:
                    return False, {'error': result.get('message', 'Refund failed')}
            else:
                return False, {'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Refund error: {str(e)}")
            return False, {'error': str(e)}