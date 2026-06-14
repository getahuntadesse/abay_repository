import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import Purchase
from books.models import Book


@login_required
def initiate_payment(request):
    """Initiate a payment for a book purchase"""
    if request.method != 'POST':
        return redirect('home')
    
    book_id = request.POST.get('book_id')
    payment_method = request.POST.get('payment_method')
    
    # Validate payment method
    if not payment_method:
        messages.error(request, 'Please select a payment method.')
        return redirect('books:detail', book_id=book_id)
    
    # Validate book exists
    if not book_id:
        messages.error(request, 'Book not specified.')
        return redirect('home')
    
    try:
        book = Book.objects.get(id=book_id, status='published')
    except Book.DoesNotExist:
        messages.error(request, 'Book not found.')
        return redirect('home')
    
    # Check if user already purchased the book
    if Purchase.objects.filter(client=request.user, book=book, status='completed').exists():
        messages.warning(request, 'You have already purchased this book.')
        return redirect('books:detail', book_id=book.id)
    
    # Handle free books
    if book.is_free:
        # Create purchase record directly for free books
        purchase = Purchase.objects.create(
            transaction_id=f"FREE_{uuid.uuid4().hex[:12].upper()}",
            book=book,
            client=request.user,
            amount=0,
            status='completed',
            completed_at=timezone.now()
        )
        messages.success(request, f'Book "{book.title}" added to your library!')
        return redirect('books:detail', book_id=book.id)
    
    # For paid books, create pending purchase
    transaction_id = f"{payment_method.upper()}_{uuid.uuid4().hex[:12].upper()}"
    
    purchase = Purchase.objects.create(
        transaction_id=transaction_id,
        book=book,
        client=request.user,
        amount=book.price,
        status='pending'
    )
    
    # Simulate successful payment (in production, integrate with actual payment gateway)
    purchase.status = 'completed'
    purchase.completed_at = timezone.now()
    purchase.save()
    
    messages.success(request, f'Payment successful! You can now download "{book.title}".')
    return redirect('books:detail', book_id=book.id)


@csrf_exempt
@require_http_methods(['POST'])
def telebirr_webhook(request):
    """Handle Telebirr payment notification webhook"""
    try:
        import json
        data = json.loads(request.body)
        
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        
        if transaction_id:
            try:
                purchase = Purchase.objects.get(transaction_id=transaction_id)
                
                if status in ['success', 'completed', 'SUCCESS']:
                    purchase.status = 'completed'
                    purchase.completed_at = timezone.now()
                    purchase.save()
                    return JsonResponse({'status': 'success'})
                elif status in ['failed', 'FAILED']:
                    purchase.status = 'failed'
                    purchase.save()
                    return JsonResponse({'status': 'failed'})
                    
            except Purchase.DoesNotExist:
                return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        return JsonResponse({'error': 'Invalid data'}, status=400)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def cbe_birr_webhook(request):
    """Handle CBE Birr payment notification webhook"""
    try:
        import json
        data = json.loads(request.body)
        
        transaction_id = data.get('transaction_id')
        status = data.get('status')
        
        if transaction_id:
            try:
                purchase = Purchase.objects.get(transaction_id=transaction_id)
                
                if status in ['success', 'completed', 'SUCCESS']:
                    purchase.status = 'completed'
                    purchase.completed_at = timezone.now()
                    purchase.save()
                    return JsonResponse({'status': 'success'})
                elif status in ['failed', 'FAILED']:
                    purchase.status = 'failed'
                    purchase.save()
                    return JsonResponse({'status': 'failed'})
                    
            except Purchase.DoesNotExist:
                return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        return JsonResponse({'error': 'Invalid data'}, status=400)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def payment_success(request):
    """Payment success page"""
    return render(request, 'payments/success.html')


@login_required
def payment_cancel(request):
    """Payment cancellation page"""
    messages.info(request, 'Payment was cancelled.')
    return render(request, 'payments/cancel.html')


@login_required
def payment_history(request):
    """View user's payment history"""
    purchases = Purchase.objects.filter(client=request.user).order_by('-created_at')
    
    context = {
        'purchases': purchases,
    }
    return render(request, 'payments/history.html', context)