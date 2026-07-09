# books/views.py - Complete with all functions
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Book, Genre, Wishlist
from accounts.models import CustomUser
from payments.models import Purchase, Payment
import logging
import json
import uuid
import traceback
from decimal import Decimal

logger = logging.getLogger(__name__)
User = get_user_model()


class HomeView(TemplateView):
    """Home page view with featured books and statistics"""
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['featured_books'] = Book.objects.filter(
            status='published'
        ).select_related('author').order_by('-downloads_count', '-created_at')[:8]
        
        context['total_books'] = Book.objects.filter(status='published').count()
        context['total_downloads'] = Book.objects.filter(status='published').aggregate(
            total=Sum('downloads_count')
        )['total'] or 0
        context['total_authors'] = CustomUser.objects.filter(role='author', is_active=True).count()
        context['total_readers'] = CustomUser.objects.filter(role='client', is_active=True).count()
        
        return context


def browse_books(request):
    """Browse all published books with search and filter"""
    books = Book.objects.filter(status='published').select_related('author').order_by('-created_at')
    genres = Genre.objects.filter(is_active=True)
    
    query = request.GET.get('q', '')
    genre_param = request.GET.get('genre')
    price_filter = request.GET.get('price')
    sort_by = request.GET.get('sort', 'newest')
    
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__full_name__icontains=query) |
            Q(description__icontains=query)
        )
    
    genre_id = None
    if genre_param:
        try:
            if genre_param.isdigit():
                genre_id = int(genre_param)
                books = books.filter(genre_id=genre_id)
            else:
                genre = Genre.objects.filter(slug=genre_param, is_active=True).first()
                if genre:
                    genre_id = genre.id
                    books = books.filter(genre=genre)
        except (ValueError, TypeError):
            pass
    
    if price_filter == 'free':
        books = books.filter(is_free=True)
    elif price_filter == 'paid':
        books = books.filter(is_free=False)
    
    if sort_by == 'newest':
        books = books.order_by('-created_at')
    elif sort_by == 'popular':
        books = books.order_by('-downloads_count', '-views_count')
    elif sort_by == 'price_low':
        books = books.order_by('price')
    elif sort_by == 'price_high':
        books = books.order_by('-price')
    else:
        books = books.order_by('-created_at')
    
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'genres': genres,
        'query': query,
        'selected_genre': genre_id,
        'selected_price': price_filter,
        'sort': sort_by,
        'user': request.user,
    }
    return render(request, 'books/browse.html', context)


def search_books(request):
    """Search books API endpoint for autocomplete"""
    query = request.GET.get('q', '')
    books = []
    if query:
        books = Book.objects.filter(
            status='published',
            title__icontains=query
        ).select_related('author')[:10]
    
    return render(request, 'books/search_results.html', {'books': books, 'query': query})


def book_detail(request, book_id):
    """Display book details with purchase options"""
    try:
        book = get_object_or_404(Book, id=book_id)
    except Book.DoesNotExist:
        messages.error(request, 'Book not found.')
        return redirect('books:browse')
    
    if book.status != 'published':
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to view this book.')
            return redirect('accounts:login')
        elif request.user.role not in ['admin', 'maker', 'checker']:
            messages.error(request, 'This book is not yet published.')
            return redirect('books:browse')
    
    book.views_count += 1
    book.save()
    
    has_purchased = False
    in_wishlist = False
    
    if request.user.is_authenticated:
        try:
            has_purchased = Purchase.objects.filter(
                user=request.user, 
                book=book, 
                status='completed'
            ).exists()
        except Exception as e:
            logger.error(f"Error checking purchase: {e}")
            has_purchased = False
        
        try:
            in_wishlist = Wishlist.objects.filter(
                user=request.user, 
                book=book
            ).exists()
        except Exception as e:
            logger.error(f"Error checking wishlist: {e}")
            in_wishlist = False
    
    quality_score = None
    try:
        from reviews.models import QualityReview
        quality_review = QualityReview.objects.filter(
            book=book,
            review_type='checker'
        ).first()
        if quality_review and quality_review.overall_score:
            quality_score = quality_review.overall_score
    except:
        pass
    
    related_books = []
    if book.genre_id:
        try:
            genre = Genre.objects.get(id=book.genre_id)
            related_books = Book.objects.filter(
                genre=genre, 
                status='published'
            ).exclude(id=book.id).select_related('author')[:5]
        except Genre.DoesNotExist:
            related_books = Book.objects.filter(status='published').exclude(id=book.id).order_by('?')[:5]
        except:
            related_books = []
    else:
        related_books = Book.objects.filter(status='published').exclude(id=book.id).order_by('?')[:5]
    
    context = {
        'book': book,
        'has_purchased': has_purchased,
        'in_wishlist': in_wishlist,
        'quality_score': quality_score,
        'related_books': related_books,
        'user': request.user,
    }
    return render(request, 'books/detail.html', context)


# =============================================
# PURCHASE AND PAYMENT VIEWS
# =============================================

@csrf_exempt
@login_required
def purchase_book(request, book_id):
    """
    Handle book purchase - Creates purchase record and processes payment
    Supports both AJAX and regular form submissions
    """
    try:
        book = get_object_or_404(Book, id=book_id, status='published')
    except Book.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Book not found'}, status=404)
        messages.error(request, 'Book not found.')
        return redirect('books:browse')
    
    # Check if user already owns this book
    if Purchase.objects.filter(user=request.user, book=book, status='completed').exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'You already own this book'}, status=400)
        messages.warning(request, 'You already own this book.')
        return redirect('books:detail', book_id=book_id)
    
    # Get payment method from POST
    payment_method = request.POST.get('payment_method', 'telebirr')
    if request.headers.get('Content-Type') == 'application/json':
        try:
            data = json.loads(request.body)
            payment_method = data.get('payment_method', 'telebirr')
        except:
            pass
    
    try:
        # Create purchase record
        purchase = Purchase.objects.create(
            book=book,
            user=request.user,
            amount=book.price,
            status='pending',
            payment_method=payment_method,
            transaction_id=f"PUR-{uuid.uuid4().hex[:12].upper()}"
        )
        
        # If book is free, complete immediately
        if book.price == 0 or book.is_free:
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.transaction_reference = 'FREE-DOWNLOAD'
            purchase.save()
            
            # Create payment record for author
            create_payment_record(purchase)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Book downloaded successfully!',
                    'free': True,
                    'download_url': reverse('books:download', kwargs={'book_id': book.id})
                })
            
            messages.success(request, f'You have successfully downloaded "{book.title}"!')
            return redirect('books:detail', book_id=book_id)
        
        # For paid books, process payment
        result = process_payment_gateway(purchase, payment_method)
        
        if result.get('success'):
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.transaction_reference = result.get('reference')
            purchase.save()
            
            # Create payment record for author
            create_payment_record(purchase)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Payment successful! Book downloaded.',
                    'transaction_id': purchase.transaction_id,
                    'download_url': reverse('books:download', kwargs={'book_id': book.id})
                })
            
            messages.success(request, f'Payment of {book.price} ETB completed successfully!')
            return redirect('books:detail', book_id=book_id)
        else:
            purchase.status = 'failed'
            purchase.save()
            
            error_msg = result.get('error', 'Payment failed. Please try again.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            
            messages.error(request, error_msg)
            return redirect('books:detail', book_id=book_id)
        
    except Exception as e:
        logger.error(f"Purchase error: {str(e)}")
        logger.error(traceback.format_exc())
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        messages.error(request, f'Failed to process purchase: {str(e)}')
        return redirect('books:detail', book_id=book_id)


def process_payment_gateway(purchase, method='telebirr'):
    """
    Process payment through the selected gateway
    For now, simulates payment processing
    """
    try:
        # In production, integrate with actual payment gateway
        reference = f"{method.upper()}-{uuid.uuid4().hex[:12].upper()}"
        
        if settings.DEBUG:
            return {
                'success': True,
                'reference': reference,
                'message': 'Payment processed successfully (simulated)'
            }
        
        return {
            'success': True,
            'reference': reference,
            'message': 'Payment processed successfully'
        }
        
    except Exception as e:
        logger.error(f"Payment gateway error: {str(e)}")
        return {'success': False, 'error': str(e)}


def create_payment_record(purchase):
    """Create payment record for the author after successful purchase"""
    try:
        book = purchase.book
        author = book.author
        gross_amount = purchase.amount
        
        royalty_rate = getattr(settings, 'ROYALTY_RATE', 70)
        abrehot_rate = 100 - royalty_rate
        
        author_royalty = gross_amount * (Decimal(royalty_rate) / Decimal(100))
        abrehot_share = gross_amount * (Decimal(abrehot_rate) / Decimal(100))
        
        tax_rate = get_tax_rate(book)
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
            status='calculated',
            created_at=timezone.now()
        )
        
        logger.info(f"Payment record created for author {author.username}: {final_amount} ETB")
        return payment
        
    except Exception as e:
        logger.error(f"Error creating payment record: {str(e)}")
        return None


def get_tax_rate(book):
    """Determine tax rate based on book genre (5% culture, 10% other)"""
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


@csrf_exempt
@login_required
def process_payment(request, purchase_id):
    """Process payment for a specific purchase"""
    try:
        purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)
    except Purchase.DoesNotExist:
        messages.error(request, 'Purchase not found.')
        return redirect('books:browse')
    
    if purchase.status == 'completed':
        messages.warning(request, 'This purchase has already been completed.')
        return redirect('books:detail', book_id=purchase.book.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'telebirr')
        
        result = process_payment_gateway(purchase, payment_method)
        
        if result.get('success'):
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.transaction_reference = result.get('reference')
            purchase.payment_method = payment_method
            purchase.save()
            
            create_payment_record(purchase)
            
            messages.success(request, f'Payment of {purchase.amount} ETB completed successfully!')
            return redirect('books:detail', book_id=purchase.book.id)
        else:
            purchase.status = 'failed'
            purchase.save()
            messages.error(request, result.get('error', 'Payment failed. Please try again.'))
            return redirect('books:payment', purchase_id=purchase.id)
    
    context = {
        'purchase': purchase,
        'book': purchase.book,
        'amount': purchase.amount,
    }
    return render(request, 'books/payment.html', context)


@login_required
def payment_success(request, purchase_id):
    """Display payment success page"""
    try:
        purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)
    except Purchase.DoesNotExist:
        messages.error(request, 'Purchase not found.')
        return redirect('books:browse')
    
    if purchase.status != 'completed':
        return redirect('books:payment', purchase_id=purchase_id)
    
    context = {
        'purchase': purchase,
        'book': purchase.book,
    }
    return render(request, 'books/payment_success.html', context)


# =============================================
# BOOK DOWNLOAD AND READING
# =============================================

@login_required
def download_book(request, book_id):
    """Download a book (after purchase or if free)"""
    book = get_object_or_404(Book, id=book_id, status='published')
    
    has_access = False
    if book.is_free or book.price == 0:
        has_access = True
    elif request.user.is_authenticated:
        has_access = Purchase.objects.filter(
            user=request.user,
            book=book,
            status='completed'
        ).exists()
    
    if not has_access:
        messages.error(request, 'You do not have permission to download this book.')
        return redirect('books:detail', book_id=book_id)
    
    book.downloads_count += 1
    book.save()
    
    if book.file:
        return redirect(book.file.url)
    else:
        messages.error(request, 'File not available for download.')
        return redirect('books:detail', book_id=book_id)


@login_required
def read_free_book(request, book_id):
    """Read a free book"""
    try:
        book = get_object_or_404(Book, id=book_id, is_free=True, status='published')
        book.downloads_count += 1
        book.views_count += 1
        book.save()
        context = {'book': book, 'user': request.user}
        return render(request, 'books/reader.html', context)
    except Book.DoesNotExist:
        messages.error(request, 'Book not found or not available for free reading.')
        return redirect('books:browse')
    except Exception as e:
        logger.error(f"Error in read_free_book: {str(e)}")
        messages.error(request, 'An error occurred while loading the book.')
        return redirect('books:detail', book_id=book_id)


# =============================================
# WISHLIST FUNCTIONS
# =============================================

@csrf_exempt
@login_required
def add_to_wishlist(request, book_id):
    """Add a book to user's wishlist"""
    book = get_object_or_404(Book, id=book_id, status='published')
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, book=book)
    if created:
        messages.success(request, f'"{book.title}" added to your wishlist.')
    else:
        messages.info(request, f'"{book.title}" is already in your wishlist.')
    return redirect('books:detail', book_id=book_id)


@csrf_exempt
@login_required
def remove_from_wishlist(request, book_id):
    """Remove a book from user's wishlist"""
    book = get_object_or_404(Book, id=book_id)
    Wishlist.objects.filter(user=request.user, book=book).delete()
    messages.success(request, f'"{book.title}" removed from your wishlist.')
    return redirect('books:detail', book_id=book_id)


@login_required
def my_wishlist(request):
    """Display user's wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('book', 'book__author')
    context = {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_items.count(),
    }
    return render(request, 'books/wishlist.html', context)


# =============================================
# AUTHOR FUNCTIONS
# =============================================

@csrf_exempt
@login_required
def upload_book(request):
    """Upload a new book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Only authors can upload books.')
        return redirect('home')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        genre_id = request.POST.get('genre')
        language = request.POST.get('language')
        price = request.POST.get('price', 0)
        is_free = request.POST.get('is_free') == 'on'
        isbn = request.POST.get('isbn', '').strip()
        subtitle = request.POST.get('subtitle', '')
        edition = request.POST.get('edition', '1')
        page_count = request.POST.get('page_count', 0)
        publication_year = request.POST.get('publication_year', 2024)
        keywords = request.POST.get('keywords', '')
        
        if not all([title, description, genre_id, language]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('books:upload')
        
        book = Book.objects.create(
            title=title,
            subtitle=subtitle,
            description=description,
            genre_id=genre_id,
            language=language,
            edition=edition,
            page_count=int(page_count) if page_count else 0,
            publication_year=int(publication_year) if publication_year else 2024,
            price=float(price) if not is_free else 0,
            is_free=is_free,
            isbn=isbn if isbn else None,
            keywords=keywords,
            author=request.user,
            status='pending_review',
            submitted_for_review_at=timezone.now()
        )
        
        if request.FILES.get('file'):
            book.file = request.FILES['file']
        if request.FILES.get('cover_image'):
            book.cover_image = request.FILES['cover_image']
        if request.FILES.get('sample_file'):
            book.sample_file = request.FILES['sample_file']
        
        book.save()
        messages.success(request, f'Book "{title}" has been uploaded and submitted for review.')
        return redirect('books:my_books')
    
    genres = Genre.objects.filter(is_active=True)
    return render(request, 'books/upload.html', {'genres': genres})


@login_required
def my_books(request):
    """Display author's books"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    books = Book.objects.filter(author=request.user).select_related('genre').order_by('-created_at')
    
    total_books = books.count()
    published_books = books.filter(status='published').count()
    pending_review = books.filter(status='pending_review').count()
    in_review = books.filter(status='in_review').count()
    needs_revision = books.filter(status='needs_revision').count()
    rejected = books.filter(status='rejected').count()
    total_downloads = books.aggregate(total=Sum('downloads_count'))['total'] or 0
    
    context = {
        'books': books,
        'total_books': total_books,
        'published_books': published_books,
        'pending_review': pending_review,
        'in_review': in_review,
        'needs_revision': needs_revision,
        'rejected': rejected,
        'total_downloads': total_downloads,
    }
    return render(request, 'books/my_books.html', context)


# =============================================
# EDIT BOOK - FIXED (Previously missing)
# =============================================

@csrf_exempt
@login_required
def edit_book(request, book_id):
    """Edit a book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status == 'published':
        messages.error(request, 'Published books cannot be edited.')
        return redirect('books:my_books')
    
    if request.method == 'POST':
        book.title = request.POST.get('title')
        book.subtitle = request.POST.get('subtitle', '')
        book.description = request.POST.get('description')
        book.genre_id = request.POST.get('genre')
        book.language = request.POST.get('language')
        book.edition = request.POST.get('edition', '1')
        book.page_count = request.POST.get('page_count', 0)
        book.publication_year = request.POST.get('publication_year', 2024)
        book.price = request.POST.get('price', 0)
        book.is_free = request.POST.get('is_free') == 'on'
        book.keywords = request.POST.get('keywords', '')
        
        isbn = request.POST.get('isbn', '').strip()
        book.isbn = isbn if isbn else None
        
        if request.FILES.get('file'):
            book.file = request.FILES['file']
        if request.FILES.get('cover_image'):
            book.cover_image = request.FILES['cover_image']
        if request.FILES.get('sample_file'):
            book.sample_file = request.FILES['sample_file']
        
        book.save()
        messages.success(request, 'Book updated successfully.')
        return redirect('books:my_books')
    
    genres = Genre.objects.filter(is_active=True)
    return render(request, 'books/edit.html', {'book': book, 'genres': genres})


# =============================================
# DELETE BOOK - FIXED (Previously missing)
# =============================================

@csrf_exempt
@login_required
def delete_book(request, book_id):
    """Delete a book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status == 'published':
        messages.error(request, 'Published books cannot be deleted.')
        return redirect('books:my_books')
    
    if request.method == 'POST':
        book_title = book.title
        book.delete()
        messages.success(request, f'Book "{book_title}" has been deleted.')
        return redirect('books:my_books')
    
    return render(request, 'books/confirm_delete.html', {'book': book})


# =============================================
# MAKER FUNCTIONS
# =============================================

@login_required
def pending_approval(request):
    """Books pending maker approval (Maker only)"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    books = Book.objects.filter(status='checker_approved').select_related('author', 'genre').order_by('checker_reviewed_at')
    context = {'books': books, 'pending_count': books.count()}
    return render(request, 'books/pending_approval.html', context)


@csrf_exempt
@login_required
def publish_book(request, book_id):
    """Publish a book (Maker only)"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    book = get_object_or_404(Book, id=book_id, status='checker_approved')
    if request.method == 'POST':
        book.status = 'published'
        book.published_at = timezone.now()
        book.maker_approved_at = timezone.now()
        book.save()
        messages.success(request, f'Book "{book.title}" has been published successfully!')
        return redirect('books:pending_approval')
    return render(request, 'books/confirm_publish.html', {'book': book})


@login_required
def my_publications(request):
    """Books published by the maker"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    books = Book.objects.filter(status='published').select_related('author', 'genre').order_by('-published_at')
    context = {'books': books, 'total_publications': books.count()}
    return render(request, 'books/my_publications.html', context)


# =============================================
# PUBLIC FUNCTIONS
# =============================================

def published_books(request):
    """List all published books (public view)"""
    books = Book.objects.filter(status='published').select_related('author', 'genre').order_by('-published_at')
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'books/published_books.html', {'books': page_obj})


def genre_books(request, genre_slug):
    """Display books by genre slug"""
    try:
        genre = get_object_or_404(Genre, slug=genre_slug, is_active=True)
    except Genre.DoesNotExist:
        messages.error(request, 'Genre not found.')
        return redirect('books:browse')
    books = Book.objects.filter(genre=genre, status='published').select_related('author').order_by('-created_at')
    context = {'genre': genre, 'books': books, 'total_books': books.count()}
    return render(request, 'books/genre_books.html', context)


def author_books(request, author_id):
    """Display books by a specific author"""
    try:
        author = get_object_or_404(CustomUser, id=author_id, role='author')
    except CustomUser.DoesNotExist:
        messages.error(request, 'Author not found.')
        return redirect('books:browse')
    books = Book.objects.filter(author=author, status='published').select_related('genre').order_by('-created_at')
    context = {
        'author': author,
        'books': books,
        'total_books': books.count(),
        'total_downloads': books.aggregate(total=Sum('downloads_count'))['total'] or 0,
    }
    return render(request, 'books/author_books.html', context)


# =============================================
# ERROR HANDLERS
# =============================================

def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)


def error_403(request, exception):
    return render(request, '403.html', status=403)