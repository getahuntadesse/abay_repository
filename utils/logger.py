# utils/logger.py
import logging
import json
import traceback
from datetime import datetime
from django.conf import settings

class CustomLogger:
    """Custom logger for the application - writes to logs.txt"""
    
    def __init__(self, name='abay_repository'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
    
    def info(self, message, extra=None):
        """Log info level message"""
        if extra:
            self.logger.info(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.info(message)
    
    def error(self, message, extra=None):
        """Log error level message"""
        if extra:
            self.logger.error(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.error(message)
    
    def warning(self, message, extra=None):
        """Log warning level message"""
        if extra:
            self.logger.warning(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.warning(message)
    
    def debug(self, message, extra=None):
        """Log debug level message"""
        if extra:
            self.logger.debug(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.debug(message)
    
    def critical(self, message, extra=None):
        """Log critical level message"""
        if extra:
            self.logger.critical(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.critical(message)
    
    def exception(self, message, extra=None):
        """Log exception with traceback"""
        if extra:
            self.logger.exception(f"{message} | {json.dumps(extra, default=str)}")
        else:
            self.logger.exception(message)

# Create singleton instance
logger = CustomLogger()

# Payment logger
payment_logger = logging.getLogger('payments')

# Auth logger
auth_logger = logging.getLogger('accounts')

# System logger
system_logger = logging.getLogger('django')

# JSON logger for machine-readable logs
json_logger = logging.getLogger('json_logger')


def log_payment_transaction(transaction_id, user, book, amount, status, payment_method, reference=None, details=None):
    """Log payment transaction details to logs.txt"""
    log_data = {
        'transaction_id': transaction_id,
        'user': user,
        'book': book,
        'amount': amount,
        'currency': 'ETB',
        'status': status,
        'payment_method': payment_method,
        'reference': reference,
        'timestamp': datetime.now().isoformat()
    }
    if details:
        log_data['details'] = details
    
    payment_logger.info(json.dumps(log_data))
    
    # Also log to JSON logger for machine parsing
    json_logger.info(json.dumps({
        'type': 'payment',
        'data': log_data
    }))


def log_auth_event(username, action, status, ip=None, user_agent=None, details=None):
    """Log authentication events to logs.txt"""
    log_data = {
        'username': username,
        'action': action,
        'status': status,
        'ip': ip,
        'user_agent': user_agent,
        'details': details,
        'timestamp': datetime.now().isoformat()
    }
    auth_logger.info(json.dumps(log_data))
    
    # Also log to JSON logger for machine parsing
    json_logger.info(json.dumps({
        'type': 'auth',
        'data': log_data
    }))


def log_system_event(level, module, message, details=None):
    """Log system events to logs.txt"""
    log_data = {
        'module': module,
        'message': message,
        'details': details,
        'timestamp': datetime.now().isoformat()
    }
    log_method = getattr(system_logger, level.lower(), system_logger.info)
    log_method(f"SYSTEM | {json.dumps(log_data)}")
    
    # Also log to JSON logger for machine parsing
    json_logger.info(json.dumps({
        'type': 'system',
        'level': level,
        'data': log_data
    }))


def log_request(request, response=None):
    """Log HTTP request/response"""
    log_data = {
        'method': request.method,
        'path': request.path,
        'user': request.user.username if request.user.is_authenticated else 'anonymous',
        'ip': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT'),
        'timestamp': datetime.now().isoformat()
    }
    if response:
        log_data['status_code'] = response.status_code
    
    system_logger.info(f"REQUEST | {json.dumps(log_data)}")


def log_exception(module, exception, context=None):
    """Log exception with full traceback"""
    log_data = {
        'module': module,
        'exception': str(exception),
        'traceback': traceback.format_exc(),
        'context': context,
        'timestamp': datetime.now().isoformat()
    }
    system_logger.error(f"EXCEPTION | {json.dumps(log_data, default=str)}")