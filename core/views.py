# core/views.py
"""
Core views for the application.
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def csp_report(request):
    """
    Endpoint for CSP violation reports.
    Logs CSP violations for monitoring and debugging.
    """
    try:
        data = json.loads(request.body)
        
        # Log the violation
        logger.warning(
            f"CSP Violation Report:\n"
            f"  Document URI: {data.get('document-uri', 'N/A')}\n"
            f"  Violated Directive: {data.get('violated-directive', 'N/A')}\n"
            f"  Blocked URI: {data.get('blocked-uri', 'N/A')}\n"
            f"  Effective Directive: {data.get('effective-directive', 'N/A')}\n"
            f"  Source File: {data.get('source-file', 'N/A')}\n"
            f"  Line Number: {data.get('line-number', 'N/A')}\n"
            f"  Column Number: {data.get('column-number', 'N/A')}"
        )
        
        # In production, you might want to send alerts for critical violations
        if not settings.DEBUG:
            # Example: Send email alert for critical violations
            # send_csp_alert(data)
            pass
        
        return JsonResponse({'status': 'ok'})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in CSP report")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing CSP report: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def security_headers_check(request):
    """
    Endpoint to check if security headers are properly set.
    Useful for testing and monitoring.
    """
    headers = {
        'X-Content-Type-Options': request.headers.get('X-Content-Type-Options'),
        'X-Frame-Options': request.headers.get('X-Frame-Options'),
        'X-XSS-Protection': request.headers.get('X-XSS-Protection'),
        'Referrer-Policy': request.headers.get('Referrer-Policy'),
        'Content-Security-Policy': request.headers.get('Content-Security-Policy'),
        'Strict-Transport-Security': request.headers.get('Strict-Transport-Security'),
        'Permissions-Policy': request.headers.get('Permissions-Policy'),
        'Cross-Origin-Embedder-Policy': request.headers.get('Cross-Origin-Embedder-Policy'),
        'Cross-Origin-Opener-Policy': request.headers.get('Cross-Origin-Opener-Policy'),
        'Cross-Origin-Resource-Policy': request.headers.get('Cross-Origin-Resource-Policy'),
    }
    
    return JsonResponse({
        'status': 'ok',
        'headers': headers,
        'secure': all(value is not None for value in headers.values())
    })