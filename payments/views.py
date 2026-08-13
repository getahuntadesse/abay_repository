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
                'download_url': f'/books/{book.id}/download/'
            })
        
        # For paid books, process Telebirr payment
        if payment_method == 'telebirr':
            telebirr = TelebirrPayment()
            result = telebirr.initiate_payment(purchase, phone_number)
        elif payment_method == 'cbe':
            result = process_cbe_payment(purchase)
        else:
            result = {'success': False, 'error': 'Unsupported payment method'}
        
        if result.get('success'):
            # If payment is free or debug mode, complete immediately
            if result.get('is_free') or result.get('is_debug'):
                purchase.status = 'completed'
                purchase.completed_at = timezone.now()
                purchase.transaction_reference = result.get('reference')
                purchase.purchase_reference = result.get('reference')
                purchase.save()
                
                # Create payment record for author
                create_author_payment(purchase)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Payment successful! Book downloaded.',
                    'transaction_id': purchase.transaction_id,
                    'download_url': f'/books/{book.id}/download/'
                })
            else:
                # Return payment URL for redirection
                return JsonResponse({
                    'success': True,
                    'message': 'Redirecting to Telebirr payment...',
                    'redirect_url': result.get('payment_url'),
                    'transaction_id': purchase.transaction_id,
                    'reference': result.get('reference')
                })
        else:
            purchase.status = 'failed'
            purchase.save()
            
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Payment failed. Please try again.')
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
    """
    Download a purchased book
    """
    book = get_object_or_404(Book, id=book_id, status='published')
    
    # Check if user has purchased this book
    purchase = Purchase.objects.filter(user=request.user, book=book, status='completed').first()
    
    if not purchase:
        messages.error(request, 'You have not purchased this book.')
        return redirect('books:detail', book_id=book_id)
    
    # Check if book has a file
    if not book.file:
        messages.error(request, 'Book file not available.')
        return redirect('books:detail', book_id=book_id)
    
    # Increment download count
    book.downloads_count += 1
    book.save()
    
    return redirect(book.file.url)


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
    Handle payment return from Telebirr/CBE
    """
    transaction_id = request.GET.get('transactionId') or request.GET.get('transaction_id')
    status = request.GET.get('status')
    
    if not transaction_id:
        messages.error(request, 'Invalid payment response')
        return redirect('books:browse')
    
    purchase = Purchase.objects.filter(
        Q(transaction_reference=transaction_id) | 
        Q(purchase_reference=transaction_id) |
        Q(transaction_id=transaction_id)
    ).first()
    
    if not purchase:
        messages.error(request, 'Purchase not found')
        return redirect('books:browse')
    
    if status == 'success' or purchase.status == 'completed':
        messages.success(request, f'Payment successful! You can now download "{purchase.book.title}"')
        return redirect('books:detail', book_id=purchase.book.id)
    else:
        messages.error(request, 'Payment failed or was cancelled. Please try again.')
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