# payments/payment_processor.py
import requests
import json
import hashlib
import hmac
import time
import base64
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def generate_telebirr_signature(data, secret_key):
    """Generate HMAC signature for Telebirr"""
    message = json.dumps(data, sort_keys=True)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def process_telebirr_payment(payment, account_details):
    """
    Process payment via Telebirr
    account_details: {'phone_number': '09XXXXXXXX', 'amount': Decimal}
    """
    try:
        # Get Telebirr configuration
        app_id = getattr(settings, 'TELEBIRR_APP_ID', '')
        app_key = getattr(settings, 'TELEBIRR_APP_KEY', '')
        short_code = getattr(settings, 'TELEBIRR_SHORT_CODE', '')
        api_url = getattr(settings, 'TELEBIRR_API_URL', 'https://sandbox.telebirr.et/api/v1/payment')
        
        if not all([app_id, app_key, short_code]):
            return {
                'success': False,
                'error': 'Telebirr configuration missing'
            }
        
        # Prepare payment data
        phone_number = account_details.get('phone_number')
        if not phone_number:
            return {
                'success': False,
                'error': 'Phone number is required for Telebirr payment'
            }
        
        amount = float(payment.final_amount)
        reference = f"PAY{payment.id}{int(time.time())}"
        
        # Prepare request data
        payment_data = {
            'app_id': app_id,
            'short_code': short_code,
            'phone_number': phone_number,
            'amount': str(amount),
            'reference': reference,
            'description': f'Payment for book: {payment.book.title}',
        }
        
        # Generate signature
        signature = generate_telebirr_signature(payment_data, app_key)
        payment_data['signature'] = signature
        
        # Send payment request
        response = requests.post(
            api_url,
            json=payment_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        result = response.json()
        
        if response.status_code == 200 and result.get('status') == 'success':
            return {
                'success': True,
                'reference': result.get('transaction_id', reference),
                'message': 'Payment processed successfully',
                'response': result
            }
        else:
            return {
                'success': False,
                'error': result.get('message', 'Payment failed'),
                'response': result
            }
            
    except Exception as e:
        logger.error(f"Telebirr payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def process_cbe_payment(payment, account_details):
    """
    Process payment via CBE Birr
    account_details: {'account_number': '1234567890', 'amount': Decimal}
    """
    try:
        # Get CBE configuration
        merchant_id = getattr(settings, 'CBE_MERCHANT_ID', '')
        terminal_id = getattr(settings, 'CBE_TERMINAL_ID', '')
        api_url = getattr(settings, 'CBE_API_URL', 'https://sandbox.cbe.com.et/api/v1/payment')
        
        if not all([merchant_id, terminal_id]):
            return {
                'success': False,
                'error': 'CBE configuration missing'
            }
        
        # Prepare payment data
        account_number = account_details.get('account_number')
        if not account_number:
            return {
                'success': False,
                'error': 'Account number is required for CBE payment'
            }
        
        amount = float(payment.final_amount)
        reference = f"PAY{payment.id}{int(time.time())}"
        
        # Prepare request data
        payment_data = {
            'merchant_id': merchant_id,
            'terminal_id': terminal_id,
            'account_number': account_number,
            'amount': str(amount),
            'reference': reference,
            'description': f'Payment for book: {payment.book.title}',
        }
        
        # Send payment request
        response = requests.post(
            api_url,
            json=payment_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        result = response.json()
        
        if response.status_code == 200 and result.get('status') == 'success':
            return {
                'success': True,
                'reference': result.get('transaction_id', reference),
                'message': 'Payment processed successfully',
                'response': result
            }
        else:
            return {
                'success': False,
                'error': result.get('message', 'Payment failed'),
                'response': result
            }
            
    except Exception as e:
        logger.error(f"CBE payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def process_batch_payment(batch):
    """
    Process a batch of payments
    """
    try:
        total_amount = float(batch.total_amount)
        reference = f"BATCH{batch.id}{int(time.time())}"
        
        # Process based on payment method
        if batch.payment_method == 'telebirr':
            # For Telebirr batch, process each payment individually
            success_count = 0
            failed_count = 0
            results = []
            
            for payment in batch.payments.all():
                account_details = {
                    'phone_number': payment.author.phone
                }
                result = process_telebirr_payment(payment, account_details)
                results.append(result)
                
                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1
            
            return {
                'success': True,
                'batch_reference': reference,
                'total': len(results),
                'success_count': success_count,
                'failed_count': failed_count,
                'results': results
            }
            
        elif batch.payment_method == 'cbe':
            # For CBE batch, process as a single transaction
            result = {
                'success': True,
                'batch_reference': reference,
                'message': f'Batch payment of {total_amount} ETB processed',
                'total_payments': batch.total_payments
            }
            return result
            
        else:
            return {
                'success': False,
                'error': f'Unsupported payment method: {batch.payment_method}'
            }
            
    except Exception as e:
        logger.error(f"Batch payment error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }