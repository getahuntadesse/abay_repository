# payments/views.py
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

from .models import Purchase, Payment, PaymentBatch, PaymentTransaction
from books.models import Book
from accounts.models import CustomUser

logger = logging.getLogger(__name__)


@login_required
def purchase_book(request, book_id):
    """
    Process a book purchase
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
        
        # Create purchase record
        purchase = Purchase.objects.create(
            user=user,
            book=book,
            amount=price,
            status='pending',
            transaction_id=f"PUR-{uuid.uuid4().hex[:12].upper()}",
            payment_method=request.POST.get('payment_method', 'telebirr')
        )
        
        # If book is free, complete immediately
        if price == Decimal('0.00'):
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.save()
            
            # Create payment record for author
            create_author_payment(purchase)
            
            return JsonResponse({
                'success': True,
                'message': 'Book downloaded successfully!',
                'free': True,
                'download_url': f'/books/{book.id}/download/'
            })
        
        # For paid books, process payment
        payment_method = purchase.payment_method
        
        if payment_method == 'telebirr':
            result = process_telebirr_payment(purchase)
        elif payment_method == 'cbe':
            result = process_cbe_payment(purchase)
        else:
            result = {'success': False, 'error': 'Unsupported payment method'}
        
        if result.get('success'):
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.transaction_reference = result.get('reference')
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
        
        # Royalty rate from settings or default 70%
        royalty_rate = getattr(settings, 'ROYALTY_RATE', 70)
        abrehot_rate = 100 - royalty_rate
        
        # Calculate author royalty
        author_royalty = gross_amount * (Decimal(royalty_rate) / Decimal(100))
        
        # Calculate Abrehot share
        abrehot_share = gross_amount * (Decimal(abrehot_rate) / Decimal(100))
        
        # Determine tax rate based on book genre
        tax_rate = get_tax_rate_from_book(book)
        
        # Calculate tax (only on author royalty)
        tax_amount = Decimal('0.00')
        is_taxable = False
        
        # Tax threshold
        tax_threshold = getattr(settings, 'TAX_THRESHOLD', 500)
        
        if author_royalty >= Decimal(str(tax_threshold)):
            is_taxable = True
            tax_amount = author_royalty * (Decimal(tax_rate) / Decimal(100))
        
        # Final amount (author royalty - tax)
        final_amount = author_royalty - tax_amount
        
        # Create payment record
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
    Process payment via Telebirr
    """
    try:
        # In production, integrate with Telebirr API
        # For now, simulate successful payment
        return {
            'success': True,
            'reference': f"TEL-{uuid.uuid4().hex[:8].upper()}",
            'message': 'Telebirr payment processed successfully'
        }
    except Exception as e:
        logger.error(f"Telebirr payment error: {str(e)}")
        return {'success': False, 'error': str(e)}


def process_cbe_payment(purchase):
    """
    Process payment via CBE Birr
    """
    try:
        # In production, integrate with CBE API
        # For now, simulate successful payment
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
    
    # Get all payments
    payments = Payment.objects.all()
    
    total_earnings = payments.aggregate(total=Sum('final_amount'))['total'] or 0
    total_paid = payments.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
    total_pending = payments.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
    total_tax = payments.aggregate(total=Sum('tax_amount'))['total'] or 0
    
    # Get authors with payment summary
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
    
    # Recent payments
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
    
    # Get all completed purchases without payments
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
    
    # Get pending payments for this author
    payments = Payment.objects.filter(
        author=author,
        status__in=['calculated', 'pending']
    )
    
    if not payments.exists():
        messages.warning(request, f'No pending payments for {author.full_name}.')
        return redirect('payments:dashboard')
    
    # Process each payment
    processed = 0
    for payment in payments:
        if payment_method == 'telebirr':
            result = process_telebirr_payment(payment)
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
    
    # Check permission
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
                    result = process_telebirr_payment(payment)
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
        # Process callback data
        try:
            data = json.loads(request.body) if request.body else request.POST
        except:
            data = request.POST
        
        transaction_id = data.get('transactionId')
        status = data.get('status')
        
        if transaction_id and status:
            try:
                purchase = Purchase.objects.get(transaction_id=transaction_id)
                
                if status == 'success':
                    purchase.status = 'completed'
                    purchase.completed_at = timezone.now()
                    purchase.save()
                    
                    # Create author payment
                    create_author_payment(purchase)
                    
                    return JsonResponse({'success': True})
                else:
                    purchase.status = 'failed'
                    purchase.save()
                    return JsonResponse({'success': False})
                    
            except Purchase.DoesNotExist:
                pass
    
    return JsonResponse({'success': False})