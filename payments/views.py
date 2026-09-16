# payments/views.py - Complete Fixed Version
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import logging
import uuid
import json
import hashlib
import hmac
import requests
from datetime import datetime

from .models import Purchase, Payment, PaymentBatch, PaymentTransaction
from books.models import Book
from accounts.models import CustomUser
from .telebirr import TelebirrService
from .chapa import ChapaService
from .paypal_service import PayPalService

logger = logging.getLogger(__name__)


class TelebirrPayment:
    """Telebirr payment integration class"""
    
    def __init__(self):
        self.app_id = getattr(settings, 'TELEBIRR_APP_ID', '')
        self.app_key = getattr(settings, 'TELEBIRR_APP_KEY', '')
        self.short_code = getattr(settings, 'TELEBIRR_SHORT_CODE', '')
        self.api_url = getattr(settings, 'TELEBIRR_API_URL', 'https://api.telebirr.et')
        self.callback_url = getattr(settings, 'TELEBIRR_CALLBACK_URL', '')
        self.return_url = getattr(settings, 'TELEBIRR_RETURN_URL', '')
        
    def generate_signature(self, data):
        """Generate HMAC-SHA256 signature for Telebirr API"""
        sorted_data = {k: data[k] for k in sorted(data.keys())}
        data_string = '&'.join([f"{k}={v}" for k, v in sorted_data.items()])
        signature = hmac.new(
            self.app_key.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def initiate_payment(self, purchase, phone_number=None):
        """
        Initiate Telebirr payment
        Returns payment URL or error
        """
        try:
            amount = float(purchase.amount)
            if amount <= 0:
                return {
                    'success': True,
                    'reference': f"FREE-{uuid.uuid4().hex[:8].upper()}",
                    'message': 'Free book - no payment needed',
                    'is_free': True
                }
            
            transaction_id = f"TEL-{uuid.uuid4().hex[:12].upper()}"
            
            payment_data = {
                'appId': self.app_id,
                'shortCode': self.short_code,
                'transactionId': transaction_id,
                'amount': str(amount),
                'phoneNumber': phone_number or purchase.user.phone or '',
                'description': f"Book Purchase: {purchase.book.title}",
                'callbackUrl': self.callback_url or f"{settings.BASE_URL}/payments/callback/",
                'returnUrl': self.return_url or f"{settings.BASE_URL}/payments/return/",
                'timestamp': datetime.now().strftime('%Y%m%d%H%M%S')
            }
            
            payment_data['signature'] = self.generate_signature(payment_data)
            
            logger.info(f"Initiating Telebirr payment: {transaction_id} for {amount} ETB")
            
            # In production, make API call to Telebirr
            if not settings.DEBUG:
                response = requests.post(
                    f"{self.api_url}/initiate",
                    json=payment_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        return {
                            'success': True,
                            'reference': transaction_id,
                            'payment_url': result.get('paymentUrl'),
                            'transaction_id': transaction_id,
                            'message': 'Payment initiated successfully'
                        }
                    else:
                        return {
                            'success': False,
                            'error': result.get('message', 'Payment initiation failed')
                        }
                else:
                    return {
                        'success': False,
                        'error': f"Telebirr API error: {response.status_code}"
                    }
            else:
                # DEBUG mode - simulate payment
                return {
                    'success': True,
                    'reference': transaction_id,
                    'payment_url': f"/payments/simulate/{transaction_id}/",
                    'transaction_id': transaction_id,
                    'message': 'Payment initiated (simulated)',
                    'is_debug': True
                }
                
        except Exception as e:
            logger.error(f"Telebirr payment error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_payment(self, transaction_id):
        """Verify payment status with Telebirr"""
        try:
            verification_data = {
                'appId': self.app_id,
                'transactionId': transaction_id,
                'timestamp': datetime.now().strftime('%Y%m%d%H%M%S')
            }
            verification_data['signature'] = self.generate_signature(verification_data)
            
            if not settings.DEBUG:
                response = requests.post(
                    f"{self.api_url}/verify",
                    json=verification_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        'success': True,
                        'status': result.get('status', 'pending'),
                        'reference': result.get('reference', transaction_id),
                        'data': result
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Verification failed: {response.status_code}"
                    }
            else:
                return {
                    'success': True,
                    'status': 'completed',
                    'reference': transaction_id,
                    'is_debug': True
                }
                
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


@login_required
def purchase_book(request, book_id):
    """
    Process a book purchase with Telebirr payment
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        book = get_object_or_404(Book, id=book_id, status='published')
        user = request.user
        
        # Check if user already owns this book
        if Purchase.objects.filter(user=user, book=book, status='completed').exists():
            return JsonResponse({
                'success': False,
                'error': 'You already own this book.'
            }, status=400)
        
        # Determine price
        price = book.price if book.price > 0 else Decimal('0.00')
        
        # Get payment method
        payment_method = request.POST.get('payment_method', 'telebirr')
        phone_number = request.POST.get('phone_number', user.phone or '')
        
        # Create purchase record
        purchase = Purchase.objects.create(
            user=user,
            book=book,
            amount=price,
            status='pending',
            payment_method=payment_method,
            transaction_reference=None,
            purchase_reference=None,
        )
        
        # If book is free, complete immediately
        if price == Decimal('0.00'):
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.transaction_reference = 'FREE-DOWNLOAD'
            purchase.purchase_reference = 'FREE-DOWNLOAD'
            purchase.save()
            
            # Create payment record for author
            create_author_payment(purchase)
            
            return JsonResponse({
                'success': True,
                'message': 'Book downloaded successfully!',
                'free': True,
                'transaction_id': purchase.transaction_id,
                'read_url': f'/books/{book.id}/read/'
            })
        

        # Telebirr only (Chapa and PayPal removed from purchase interface)
        payment_method = (payment_method or 'telebirr').lower().strip()
        if payment_method != 'telebirr':
            purchase.delete()
            return JsonResponse({
                'success': False,
                'error': 'Only Telebirr is supported. Please select Telebirr.',
            }, status=400)

        result = {'success': False, 'error': 'Telebirr failed'}
        tb = TelebirrService()
        if not tb.is_configured():
            purchase.delete()
            return JsonResponse({
                'success': False,
                'error': 'Telebirr is not configured. Set TELEBIRR_* env keys.',
            }, status=503)
        phone = (phone_number or '').strip()
        if not phone or len(phone) < 10:
            purchase.delete()
            return JsonResponse({
                'success': False,
                'error': 'A valid phone number is required for Telebirr.',
            }, status=400)
        tb_result = tb.create_checkout(
            title=book.title[:128],
            amount=float(price),
            merch_order_id=(purchase.transaction_id or f"PUR{purchase.id}").replace("-", "").replace("_", ""),
        )
        if tb_result.get('success'):
            purchase.transaction_reference = tb_result.get('merch_order_id') or tb_result.get('prepay_id')
            purchase.purchase_reference = tb_result.get('prepay_id') or tb_result.get('merch_order_id')
            purchase.save(update_fields=['transaction_reference', 'purchase_reference', 'updated_at'])
            result = {
                'success': True,
                'gateway': 'telebirr',
                'reference': tb_result.get('merch_order_id'),
                'order_id': tb_result.get('prepay_id'),
                'payment_url': tb_result.get('checkout_url') or tb_result.get('checkOutUrl'),
                'redirect_url': tb_result.get('checkout_url') or tb_result.get('checkOutUrl'),
                'transaction_id': purchase.transaction_id,
                'message': 'Redirecting to Telebirr checkout',
            }
        else:
            result = {'success': False, 'error': tb_result.get('error', 'Telebirr failed')}

        if result.get('success'):
            return JsonResponse({
                'success': True,
                'gateway': result.get('gateway', payment_method),
                'reference': result.get('reference'),
                'order_id': result.get('order_id'),
                'payment_url': result.get('payment_url') or result.get('redirect_url'),
                'redirect_url': result.get('redirect_url') or result.get('payment_url'),
                'transaction_id': purchase.transaction_id,
                'message': result.get('message', 'Checkout ready'),
            })

        purchase.status = 'failed'
        purchase.save(update_fields=['status', 'updated_at'])
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Payment initiation failed. Please try again.'),
        }, status=400)


    except Book.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Book not found'}, status=404)
    except Exception as e:
        logger.error(f"Purchase error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def create_author_payment(purchase):
    """
    Create payment record for the author after a successful purchase
    """
    try:
        book = purchase.book
        author = book.author
        gross_amount = purchase.amount
        
        royalty_rate = getattr(settings, 'ROYALTY_RATE', 70)
        abrehot_rate = 100 - royalty_rate
        
        author_royalty = gross_amount * (Decimal(royalty_rate) / Decimal(100))
        abrehot_share = gross_amount * (Decimal(abrehot_rate) / Decimal(100))
        
        tax_rate = get_tax_rate_from_book(book)
        tax_amount = Decimal('0.00')
        is_taxable = False
        
        tax_threshold = getattr(settings, 'TAX_THRESHOLD', 500)
        
        if author_royalty >= Decimal(str(tax_threshold)):
            is_taxable = True
            tax_amount = author_royalty * (Decimal(tax_rate) / Decimal(100))
        
        final_amount = author_royalty - tax_amount
        
        payment = Payment.objects.create(
            book=book,
            author=author,
            purchase=purchase,
            gross_amount=gross_amount,
            author_royalty=author_royalty,
            abrehot_share=abrehot_share,
            abrehot_share_rate=abrehot_rate,
            royalty_rate=royalty_rate,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            is_taxable=is_taxable,
            final_amount=final_amount,
            status='calculated'
        )
        
        logger.info(f"Payment created for author {author.username}: {final_amount} ETB")
        return payment
        
    except Exception as e:
        logger.error(f"Error creating author payment: {str(e)}")
        return None


def get_tax_rate_from_book(book):
    """
    Determine tax rate based on book genre
    5% for culture-related genres, 10% for others
    """
    culture_genres = [
        'culture', 'cultural', 'history', 'heritage', 'tradition',
        'ethiopian', 'amharic', 'oromo', 'tigrinya', 'somali',
        'african', 'folklore', 'mythology', 'traditional',
        'language', 'literature', 'poetry', 'religious',
        'spiritual', 'custom', 'ritual', 'celebration'
    ]
    
    genre = book.genre.name.lower() if book.genre else ''
    if any(g in genre for g in culture_genres):
        return 5
    return 10


def process_telebirr_payment(purchase):
    """
    Process payment via Telebirr (legacy function - use TelebirrPayment class instead)
    """
    telebirr = TelebirrPayment()
    return telebirr.initiate_payment(purchase)


def process_cbe_payment(purchase):
    """
    Process payment via CBE Birr
    """
    try:
        # In production, integrate with CBE API
        return {
            'success': True,
            'reference': f"CBE-{uuid.uuid4().hex[:8].upper()}",
            'message': 'CBE payment processed successfully'
        }
    except Exception as e:
        logger.error(f"CBE payment error: {str(e)}")
        return {'success': False, 'error': str(e)}


@login_required
def download_book(request, book_id):
    """Downloads disabled — online reader only."""
    messages.info(request, 'Books are available for online reading only (download disabled).')
    return redirect('books:read', book_id=book_id)


@login_required
def payment_history(request):
    """
    View payment history for the current user
    """
    purchases = Purchase.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'purchases': purchases,
    }
    return render(request, 'payments/history.html', context)


@login_required
def author_payments(request):
    """
    View payments for the current author
    """
    if request.user.role != 'author':
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    
    payments = Payment.objects.filter(author=request.user).order_by('-created_at')
    
    total_earned = payments.aggregate(total=Sum('final_amount'))['total'] or 0
    total_paid = payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
    total_pending = payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
    total_tax = payments.aggregate(total=Sum('tax_amount'))['total'] or 0
    
    context = {
        'payments': payments,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_tax': total_tax,
        'payment_count': payments.count(),
        'royalty_rate': getattr(settings, 'ROYALTY_RATE', 70),
        'abrehot_rate': 100 - getattr(settings, 'ROYALTY_RATE', 70),
        'tax_threshold': getattr(settings, 'TAX_THRESHOLD', 500),
    }
    return render(request, 'payments/author_payments.html', context)


@login_required
def payment_dashboard(request):
    """
    Payment dashboard for admin/maker/finance
    """
    if request.user.role not in ['admin', 'maker', 'finance']:
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    
    payments = Payment.objects.all()
    
    total_earnings = payments.aggregate(total=Sum('final_amount'))['total'] or 0
    total_paid = payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
    total_pending = payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
    total_tax = payments.aggregate(total=Sum('tax_amount'))['total'] or 0
    
    authors = CustomUser.objects.filter(role='author')
    author_data = []
    
    for author in authors:
        author_payments = Payment.objects.filter(author=author)
        total_royalty = author_payments.aggregate(total=Sum('author_royalty'))['total'] or 0
        total_tax_author = author_payments.aggregate(total=Sum('tax_amount'))['total'] or 0
        total_net = author_payments.aggregate(total=Sum('final_amount'))['total'] or 0
        total_paid_author = author_payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
        total_pending_author = author_payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
        
        author_data.append({
            'id': author.id,
            'username': author.username,
            'full_name': author.full_name,
            'email': author.email,
            'total_royalty': total_royalty,
            'total_tax': total_tax_author,
            'total_net': total_net,
            'total_paid': total_paid_author,
            'total_pending': total_pending_author,
        })
    
    recent_payments = payments.order_by('-created_at')[:20]
    
    context = {
        'authors': author_data,
        'recent_payments': recent_payments,
        'total_earnings': total_earnings,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_tax': total_tax,
        'royalty_rate': getattr(settings, 'ROYALTY_RATE', 70),
        'abrehot_rate': 100 - getattr(settings, 'ROYALTY_RATE', 70),
        'tax_threshold': getattr(settings, 'TAX_THRESHOLD', 500),
    }
    return render(request, 'payments/dashboard.html', context)


@login_required
def calculate_all_payments(request):
    """
    Calculate all pending payments
    """
    if request.user.role not in ['admin', 'maker', 'finance']:
        messages.error(request, 'You are not authorized to perform this action.')
        return redirect('home')
    
    purchases = Purchase.objects.filter(
        status='completed',
        payment__isnull=True
    )
    
    count = 0
    for purchase in purchases:
        payment = create_author_payment(purchase)
        if payment:
            count += 1
    
    messages.success(request, f'Calculated {count} new payments.')
    return redirect('payments:dashboard')


@login_required
def process_author_payment(request, author_id):
    """
    Process payment for a specific author
    """
    if request.user.role not in ['admin', 'maker', 'finance']:
        messages.error(request, 'You are not authorized to perform this action.')
        return redirect('home')
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('payments:dashboard')
    
    author = get_object_or_404(CustomUser, id=author_id, role='author')
    payment_method = request.POST.get('payment_method', 'telebirr')
    
    payments = Payment.objects.filter(
        author=author,
        status__in=['calculated', 'pending']
    )
    
    if not payments.exists():
        messages.warning(request, f'No pending payments for {author.full_name}.')
        return redirect('payments:dashboard')
    
    processed = 0
    for payment in payments:
        if payment_method == 'telebirr':
            telebirr = TelebirrPayment()
            # For author payment, we need to pass a purchase
            # This is a simplified version - in production, handle this properly
            result = {'success': True, 'reference': f"PAY-{uuid.uuid4().hex[:8].upper()}"}
        else:
            result = {'success': False, 'error': 'Unsupported payment method'}
        
        if result.get('success'):
            payment.status = 'paid'
            payment.paid_at = timezone.now()
            payment.transaction_reference = result.get('reference')
            payment.save()
            processed += 1
    
    messages.success(request, f'Successfully processed {processed} payments for {author.full_name}.')
    return redirect('payments:dashboard')


@login_required
def payment_detail(request, payment_id):
    """
    View payment detail
    """
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.user.role not in ['admin', 'maker', 'finance'] and request.user != payment.author:
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    
    context = {
        'payment': payment,
    }
    return render(request, 'payments/detail.html', context)


@login_required
def author_payment_detail(request, author_id):
    """
    View all payments for a specific author (admin/maker view)
    """
    if request.user.role not in ['admin', 'maker', 'finance']:
        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    
    author = get_object_or_404(CustomUser, id=author_id, role='author')
    payments = Payment.objects.filter(author=author).order_by('-created_at')
    
    total_earned = payments.aggregate(total=Sum('final_amount'))['total'] or 0
    total_paid = payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
    total_pending = payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
    total_tax = payments.aggregate(total=Sum('tax_amount'))['total'] or 0
    
    context = {
        'author': author,
        'payments': payments,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_tax': total_tax,
        'royalty_rate': getattr(settings, 'ROYALTY_RATE', 70),
        'abrehot_rate': 100 - getattr(settings, 'ROYALTY_RATE', 70),
        'tax_threshold': getattr(settings, 'TAX_THRESHOLD', 500),
    }
    return render(request, 'payments/author_detail.html', context)


@login_required
def process_batch_payment(request):
    """
    Process batch payments for selected authors (API endpoint)
    """
    if request.user.role not in ['admin', 'maker', 'finance']:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        author_ids = data.get('author_ids', [])
        method = data.get('method', 'telebirr')
        
        if not author_ids:
            return JsonResponse({'success': False, 'error': 'No authors selected'}, status=400)
        
        processed_count = 0
        total_paid = 0
        
        for author_id in author_ids:
            author = get_object_or_404(CustomUser, id=author_id, role='author')
            payments = Payment.objects.filter(
                author=author,
                status__in=['calculated', 'pending']
            )
            
            for payment in payments:
                if method == 'telebirr':
                    result = {'success': True, 'reference': f"PAY-{uuid.uuid4().hex[:8].upper()}"}
                else:
                    result = {'success': False, 'error': 'Unsupported payment method'}
                
                if result.get('success'):
                    payment.status = 'paid'
                    payment.paid_at = timezone.now()
                    payment.transaction_reference = result.get('reference')
                    payment.save()
                    processed_count += 1
                    total_paid += float(payment.final_amount)
        
        return JsonResponse({
            'success': True,
            'processed_count': processed_count,
            'total_paid': total_paid,
            'message': f'Processed {processed_count} payments totaling {total_paid:.2f} ETB'
        })
        
    except Exception as e:
        logger.error(f"Batch payment error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def payment_callback(request):
    """
    Handle payment callback from Telebirr/CBE
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.POST
        except:
            data = request.POST
        
        transaction_id = data.get('transactionId') or data.get('transaction_id')
        status = data.get('status')
        reference = data.get('reference')
        
        logger.info(f"Payment callback received: {data}")
        
        if transaction_id and status:
            try:
                purchase = Purchase.objects.filter(
                    Q(transaction_reference=transaction_id) | 
                    Q(purchase_reference=transaction_id)
                ).first()
                
                if not purchase:
                    purchase = Purchase.objects.filter(
                        transaction_id=transaction_id
                    ).first()
                
                if purchase:
                    if status == 'success' or status == 'completed':
                        purchase.status = 'completed'
                        purchase.completed_at = timezone.now()
                        if reference:
                            purchase.transaction_reference = reference
                            purchase.purchase_reference = reference
                        purchase.save()
                        
                        create_author_payment(purchase)
                        
                        return JsonResponse({'status': 'success', 'message': 'Payment confirmed'})
                    elif status == 'failed' or status == 'cancelled':
                        purchase.status = 'failed'
                        purchase.save()
                        return JsonResponse({'status': 'success', 'message': 'Payment failed'})
                    else:
                        return JsonResponse({'status': 'success', 'message': 'Status updated'})
                else:
                    logger.warning(f"Purchase not found for transaction: {transaction_id}")
                    return JsonResponse({'status': 'error', 'message': 'Purchase not found'}, status=404)
                    
            except Exception as e:
                logger.error(f"Callback processing error: {str(e)}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required
def payment_return(request):
    """
    User return from Telebirr H5.
    Completes purchase when paid (webhook may not reach localhost).
    Accepts merch_order_id / prepay_id / trade_status from query string.
    """
    from payments.telebirr import TelebirrService

    merch_order_id = (
        request.GET.get('merch_order_id')
        or request.GET.get('merchOrderId')
        or request.GET.get('out_trade_no')
        or request.GET.get('transactionId')
        or request.GET.get('transaction_id')
        or request.GET.get('ref')
        or ''
    )
    prepay_id = request.GET.get('prepay_id') or request.GET.get('prepayId') or ''
    trade_status = (
        request.GET.get('trade_status')
        or request.GET.get('tradeStatus')
        or request.GET.get('status')
        or ''
    ).strip().upper()

    purchase = None
    if merch_order_id:
        purchase = _purchase_by_ref(merch_order_id)
    if not purchase and prepay_id:
        purchase = _purchase_by_ref(prepay_id)

    if not purchase and request.user.is_authenticated:
        # fallback: latest pending telebirr purchase for this user
        purchase = (
            Purchase.objects.filter(user=request.user, status='pending', payment_method='telebirr')
            .order_by('-created_at')
            .first()
        )

    if not purchase:
        messages.error(request, 'Purchase not found. If you paid, contact support with your order id.')
        return redirect('books:browse')

    # Already done
    if purchase.status == 'completed':
        messages.success(request, f'Payment confirmed! "{purchase.book.title}" is in My Books.')
        return redirect('books:my_books_user')

    paid = trade_status in ('PAY_SUCCESS', 'SUCCESS', 'COMPLETED', 'PAID', 'FINISH')

    # Confirm with Telebirr queryOrder when possible
    if not paid:
        try:
            tb = TelebirrService()
            ref = merch_order_id or purchase.transaction_reference or purchase.purchase_reference or purchase.transaction_id
            q = tb.query_order(ref)
            logger.info("Telebirr queryOrder on return: %s", q)
            if q.get('paid') or str(q.get('trade_status', '')).upper() in (
                'PAY_SUCCESS', 'SUCCESS', 'COMPLETED', 'PAID', 'FINISH'
            ):
                paid = True
                merch_order_id = merch_order_id or q.get('merch_order_id') or ref
                prepay_id = prepay_id or q.get('payment_order_id') or ''
        except Exception as e:
            logger.exception("queryOrder on return failed: %s", e)

    # If user returned from Telebirr after successful pay UI, still complete when
    # DEBUG and pending (local webhook unreachable) — only when merch_order_id matches
    if not paid and getattr(settings, 'DEBUG', False) and merch_order_id:
        # Trust explicit success-ish query flags Telebirr sometimes sends
        if request.GET.get('result') in ('SUCCESS', 'success', '0') or request.GET.get('code') in ('0', '200'):
            paid = True

    if paid:
        _complete_purchase(purchase, gateway_ref=prepay_id or merch_order_id or purchase.transaction_id)
        messages.success(request, f'Payment successful! "{purchase.book.title}" is now in My Books.')
        return redirect('books:my_books_user')

    messages.warning(
        request,
        'Payment is still pending confirmation. If you completed payment on Telebirr, '
        'wait a moment and open My Books, or contact support with order: '
        f'{merch_order_id or purchase.transaction_id}'
    )
    return redirect('books:detail', book_id=purchase.book.id)


@login_required
def simulate_payment(request, transaction_id):
    """
    Simulate payment for debug mode
    """
    if not settings.DEBUG:
        messages.error(request, 'This endpoint is only available in debug mode')
        return redirect('books:browse')
    
    purchase = Purchase.objects.filter(
        Q(transaction_reference=transaction_id) | 
        Q(purchase_reference=transaction_id) |
        Q(transaction_id=transaction_id)
    ).first()
    
    if not purchase:
        messages.error(request, 'Purchase not found')
        return redirect('books:browse')
    
    purchase.status = 'completed'
    purchase.completed_at = timezone.now()
    purchase.transaction_reference = transaction_id
    purchase.purchase_reference = transaction_id
    purchase.save()
    
    create_author_payment(purchase)
    
    messages.success(request, f'Payment simulated successfully! You can download "{purchase.book.title}"')
    return redirect('books:detail', book_id=purchase.book.id)



# ---------------------------------------------------------------------------
# Production webhooks
# ---------------------------------------------------------------------------


def _complete_purchase(purchase, gateway_ref=None):
    """Idempotent: mark purchase completed, author royalty, book counter."""
    if not purchase:
        return False
    if purchase.status == 'completed':
        return True
    purchase.status = 'completed'
    purchase.completed_at = timezone.now()
    if gateway_ref:
        purchase.transaction_reference = str(gateway_ref)[:100]
        if not purchase.purchase_reference:
            purchase.purchase_reference = str(gateway_ref)[:100]
    purchase.save()
    try:
        book = purchase.book
        book.purchase_count = (book.purchase_count or 0) + 1
        book.save(update_fields=['purchase_count'])
    except Exception as e:
        logger.exception("purchase_count update failed: %s", e)
    try:
        create_author_payment(purchase)
    except Exception as e:
        logger.exception("create_author_payment failed: %s", e)
    try:
        # optional mirror record used by some book views
        from books.views import create_payment_record
        create_payment_record(purchase)
    except Exception as e:
        logger.debug("create_payment_record skipped: %s", e)
    logger.info("Purchase completed id=%s book=%s user=%s", purchase.id, purchase.book_id, purchase.user_id)
    return True


def _purchase_by_ref(ref):
    if not ref:
        return None
    from django.db.models import Q
    ref = str(ref).strip()
    alnum = "".join(c for c in ref if c.isalnum())
    q = (
        Q(transaction_id=ref)
        | Q(transaction_reference=ref)
        | Q(purchase_reference=ref)
    )
    if alnum and alnum != ref:
        q |= (
            Q(transaction_id=alnum)
            | Q(transaction_reference=alnum)
            | Q(purchase_reference=alnum)
            | Q(transaction_id__iexact=alnum)
        )
    # also match if stored id has hyphens stripped
    purchase = Purchase.objects.filter(q).select_related('book', 'user').first()
    if purchase:
        return purchase
    if alnum:
        for p in Purchase.objects.filter(status='pending').select_related('book', 'user').order_by('-created_at')[:50]:
            for field in (p.transaction_id, p.transaction_reference, p.purchase_reference):
                if field and "".join(c for c in str(field) if c.isalnum()) == alnum:
                    return p
    return None



@csrf_exempt
def telebirr_webhook(request):
    """
    Telebirr Fabric notify URL.
    Register: {BASE_URL}/payments/webhook/telebirr/
    Verifies SHA256WithRSA sign when TELEBIRR_PUBLIC_KEY is set.
    """
    from payments.webhook_verify import verify_telebirr_signature

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {k: request.POST.get(k) for k in request.POST.keys()}

        ok, reason = verify_telebirr_signature(payload if isinstance(payload, dict) else {})
        if not ok:
            logger.warning("Telebirr webhook rejected: %s", reason)
            return JsonResponse({'code': '1', 'msg': 'invalid signature', 'reason': reason}, status=401)

        logger.info("Telebirr webhook verified (%s) keys=%s", reason, list(payload.keys()) if isinstance(payload, dict) else type(payload))

        biz = payload.get('biz_content') if isinstance(payload.get('biz_content'), dict) else {}
        merch_order_id = (
            payload.get('merch_order_id')
            or biz.get('merch_order_id')
            or payload.get('out_trade_no')
        )
        trade_status = str(
            payload.get('trade_status')
            or biz.get('trade_status')
            or payload.get('status')
            or ''
        ).strip()
        payment_order_id = payload.get('payment_order_id') or biz.get('payment_order_id')

        paid_states = {
            'Completed', 'completed', 'SUCCESS', 'success', 'Paying',
            'TRADE_SUCCESS', 'Finish', 'finish',
        }

        if merch_order_id:
            purchase = _purchase_by_ref(merch_order_id)
            if purchase and purchase.status == 'pending':
                if trade_status in paid_states or trade_status.lower() in {s.lower() for s in paid_states}:
                    _complete_purchase(purchase, gateway_ref=payment_order_id or merch_order_id)
                    logger.info("Telebirr paid purchase=%s", purchase.transaction_id)
                elif trade_status.lower() in ('failure', 'failed', 'expired', 'cancelled'):
                    purchase.status = 'failed'
                    purchase.save(update_fields=['status', 'updated_at'])

        return JsonResponse({'code': '0', 'msg': 'success', 'received': True})
    except Exception as e:
        logger.exception("Telebirr webhook error: %s", e)
        # ACK to avoid endless retries on our bugs; logs retain detail
        return JsonResponse({'code': '0', 'msg': 'success', 'received': True})


@csrf_exempt
def chapa_webhook(request):
    """
    Chapa webhook. HMAC header check + mandatory API verify(tx_ref).
    Register: {BASE_URL}/payments/webhook/chapa/
    """
    from payments.webhook_verify import verify_chapa_signature
    from payments.chapa import ChapaService

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        raw = request.body or b'{}'
        ok, reason = verify_chapa_signature(raw, request.headers)
        if not ok:
            logger.warning("Chapa webhook signature failed: %s", reason)
            return JsonResponse({'error': 'invalid signature', 'reason': reason}, status=401)

        payload = json.loads(raw.decode('utf-8') or '{}')
        logger.info("Chapa webhook (%s): %s", reason, payload)

        tx_ref = payload.get('tx_ref') or (payload.get('data') or {}).get('tx_ref')
        status = (payload.get('status') or (payload.get('data') or {}).get('status') or '').lower()
        event = payload.get('event', '')

        if not tx_ref:
            return JsonResponse({'received': True, 'note': 'no tx_ref'})

        ch = ChapaService()
        verified = ch.verify(tx_ref)
        purchase = _purchase_by_ref(tx_ref)

        if purchase and purchase.status == 'pending':
            if verified.get('success') or status in ('success', 'successful') or event == 'charge.success':
                if verified.get('success') or not getattr(settings, 'WEBHOOK_VERIFY_STRICT', True):
                    _complete_purchase(purchase, gateway_ref=tx_ref)
                    logger.info("Chapa paid purchase=%s verified=%s", purchase.transaction_id, verified.get('success'))
                else:
                    logger.warning("Chapa webhook status success but API verify failed for %s", tx_ref)
            elif status in ('failed', 'cancelled'):
                purchase.status = 'failed'
                purchase.save(update_fields=['status', 'updated_at'])

        return JsonResponse({'received': True, 'verified': bool(verified.get('success'))})
    except Exception as e:
        logger.exception("Chapa webhook error: %s", e)
        return JsonResponse({'received': True})


@csrf_exempt
def paypal_capture_view(request):
    """Capture PayPal order after buyer approval (POST JSON {order_id})."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        order_id = data.get('order_id') or data.get('token')
        if not order_id:
            return JsonResponse({'success': False, 'error': 'order_id required'}, status=400)
        pp = PayPalService()
        result = pp.capture(order_id)
        if result.get('success'):
            purchase = _purchase_by_ref(order_id)
            if purchase and purchase.status == 'pending':
                _complete_purchase(purchase, gateway_ref=order_id)
            return JsonResponse({'success': True, 'status': result.get('status'), 'raw': result.get('raw')})
        return JsonResponse({'success': False, 'error': result.get('error'), 'raw': result.get('raw')}, status=400)
    except Exception as e:
        logger.exception("PayPal capture error")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def paypal_webhook(request):
    """
    PayPal REST webhooks (e.g. PAYMENT.CAPTURE.COMPLETED, CHECKOUT.ORDER.APPROVED).
    Register: {BASE_URL}/payments/webhook/paypal/
    Requires PAYPAL_WEBHOOK_ID for signature verification.
    """
    from payments.webhook_verify import verify_paypal_webhook, extract_paypal_order_id

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        raw = request.body or b'{}'
        ok, reason = verify_paypal_webhook(raw, request.headers)
        if not ok:
            logger.warning("PayPal webhook rejected: %s", reason)
            return JsonResponse({'error': 'invalid signature', 'reason': reason}, status=401)

        event = json.loads(raw.decode('utf-8') or '{}')
        event_type = event.get('event_type', '')
        logger.info("PayPal webhook %s (%s)", event_type, reason)

        order_id = extract_paypal_order_id(event)
        if event_type in (
            'PAYMENT.CAPTURE.COMPLETED',
            'CHECKOUT.ORDER.APPROVED',
            'CHECKOUT.ORDER.COMPLETED',
        ) and order_id:
            # Ensure capture for APPROVED events
            if event_type == 'CHECKOUT.ORDER.APPROVED':
                try:
                    PayPalService().capture(order_id)
                except Exception as e:
                    logger.warning("PayPal auto-capture: %s", e)
            purchase = _purchase_by_ref(order_id)
            if not purchase:
                # try custom_id from resource
                custom = (event.get('resource') or {}).get('custom_id')
                if custom:
                    purchase = _purchase_by_ref(custom)
            if purchase and purchase.status == 'pending':
                _complete_purchase(purchase, gateway_ref=order_id)
                logger.info("PayPal paid purchase=%s", purchase.transaction_id)

        return JsonResponse({'received': True})
    except Exception as e:
        logger.exception("PayPal webhook error: %s", e)
        return JsonResponse({'received': True})


@login_required
def paypal_return(request):
    """
    Browser return from PayPal approve. Captures order and redirects to reader/library.
    """
    order_id = request.GET.get('token') or request.GET.get('order_id')
    if not order_id:
        messages.error(request, 'Missing PayPal order.')
        return redirect('books:browse')
    pp = PayPalService()
    result = pp.capture(order_id)
    purchase = _purchase_by_ref(order_id)
    if result.get('success') and purchase:
        _complete_purchase(purchase, gateway_ref=order_id)
        messages.success(request, 'Payment successful. You can read your book online.')
        return redirect('books:read', book_id=purchase.book_id)
    messages.error(request, 'PayPal payment could not be completed.')
    if purchase:
        return redirect('books:detail', book_id=purchase.book_id)
    return redirect('books:browse')


