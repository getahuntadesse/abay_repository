from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.views.generic import TemplateView
from .models import Book, Genre, Wishlist
from accounts.models import CustomUser
from payments.models import Purchase


# =====================================================
# HOME VIEW - For the homepage
# =====================================================

class HomeView(TemplateView):
    """Home page view with featured books and statistics"""
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get featured/popular books (published, ordered by downloads)
        context['featured_books'] = Book.objects.filter(
            status='published'
        ).select_related('author', 'genre').order_by('-downloads_count', '-created_at')[:8]
        
        # Statistics for homepage
        context['total_books'] = Book.objects.filter(status='published').count()
        context['total_downloads'] = Book.objects.filter(status='published').aggregate(
            total=Sum('downloads_count')
        )['total'] or 0
        context['total_authors'] = CustomUser.objects.filter(role='author', is_active=True).count()
        context['total_readers'] = CustomUser.objects.filter(role='client', is_active=True).count()
        
        return context


# =====================================================
# BOOK VIEWS
# =====================================================

def browse_books(request):
    """Browse all published books with search and filter"""
    books = Book.objects.filter(status='published').select_related('author', 'genre').order_by('-created_at')
    genres = Genre.objects.filter(is_active=True)
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__full_name__icontains=query) |
            Q(description__icontains=query) |
            Q(keywords__icontains=query)
        )
    
    # Filter by genre
    genre_id = request.GET.get('genre')
    if genre_id:
        books = books.filter(genre_id=genre_id)
    
    # Filter by price (free or paid)
    price_filter = request.GET.get('price')
    if price_filter == 'free':
        books = books.filter(is_free=True)
    elif price_filter == 'paid':
        books = books.filter(is_free=False)
    
    # Sort options
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['title', '-title', 'price', '-price', 'downloads_count', '-downloads_count', 'created_at', '-created_at']
    if sort_by in valid_sorts:
        books = books.order_by(sort_by)
    else:
        books = books.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'genres': genres,
        'query': query,
        'selected_genre': genre_id,
        'selected_price': price_filter,
        'selected_sort': sort_by,
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
    """Display book details"""
    book = get_object_or_404(Book, id=book_id)
    
    # Increment view count
    book.views_count += 1
    book.save()
    
    # Check if user has purchased this book
    has_purchased = False
    in_wishlist = False
    
    if request.user.is_authenticated:
        has_purchased = Purchase.objects.filter(
            client=request.user, 
            book=book, 
            status='completed'
        ).exists()
        in_wishlist = Wishlist.objects.filter(
            client=request.user, 
            book=book
        ).exists()
    
    # Get related books (same genre)
    related_books = Book.objects.filter(
        genre=book.genre, 
        status='published'
    ).exclude(id=book.id).select_related('author')[:5]
    
    context = {
        'book': book,
        'has_purchased': has_purchased,
        'in_wishlist': in_wishlist,
        'related_books': related_books,
    }
    return render(request, 'books/detail.html', context)


@login_required
def upload_book(request):
    """Upload a new book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Only authors can upload books.')
        return redirect('home')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        subtitle = request.POST.get('subtitle', '')
        description = request.POST.get('description')
        genre_id = request.POST.get('genre')
        language = request.POST.get('language')
        edition = request.POST.get('edition', '1')
        page_count = request.POST.get('page_count', 0)
        publication_year = request.POST.get('publication_year', timezone.now().year)
        price = request.POST.get('price', 0)
        is_free = request.POST.get('is_free') == 'on'
        keywords = request.POST.get('keywords', '')
        isbn = request.POST.get('isbn', '')
        
        # Validate required fields
        if not all([title, description, genre_id, language]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('books:upload')
        
        # Create book
        book = Book.objects.create(
            title=title,
            subtitle=subtitle,
            description=description,
            genre_id=genre_id,
            language=language,
            edition=edition,
            page_count=page_count or 0,
            publication_year=publication_year or timezone.now().year,
            price=float(price) if not is_free else 0,
            is_free=is_free,
            keywords=keywords,
            isbn=isbn,
            author=request.user,
            status='pending_review',
            submitted_for_review_at=timezone.now()
        )
        
        # Handle file uploads
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
    
    # Statistics
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


@login_required
def edit_book(request, book_id):
    """Edit a book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    # Only allow editing if book is not published
    if book.status == 'published':
        messages.error(request, 'Published books cannot be edited. Please contact support.')
        return redirect('books:my_books')
    
    if request.method == 'POST':
        book.title = request.POST.get('title')
        book.subtitle = request.POST.get('subtitle', '')
        book.description = request.POST.get('description')
        book.genre_id = request.POST.get('genre')
        book.language = request.POST.get('language')
        book.edition = request.POST.get('edition', '1')
        book.page_count = request.POST.get('page_count', 0)
        book.publication_year = request.POST.get('publication_year', timezone.now().year)
        book.price = request.POST.get('price', 0)
        book.is_free = request.POST.get('is_free') == 'on'
        book.keywords = request.POST.get('keywords', '')
        book.isbn = request.POST.get('isbn', '')
        
        # Handle file uploads
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


@login_required
def delete_book(request, book_id):
    """Delete a book (Author only)"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    # Only allow deletion if book is not published
    if book.status == 'published':
        messages.error(request, 'Published books cannot be deleted. Please contact support.')
        return redirect('books:my_books')
    
    if request.method == 'POST':
        book_title = book.title
        book.delete()
        messages.success(request, f'Book "{book_title}" has been deleted.')
        return redirect('books:my_books')
    
    return render(request, 'books/confirm_delete.html', {'book': book})


@login_required
def pending_approval(request):
    """Books pending maker approval (Maker only)"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    books = Book.objects.filter(status='checker_approved').select_related('author', 'genre').order_by('checker_reviewed_at')
    
    context = {
        'books': books,
        'pending_count': books.count(),
    }
    return render(request, 'books/pending_approval.html', context)


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
        book.maker_approved_by = request.user
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
    
    books = Book.objects.filter(
        status='published',
        maker_approved_by=request.user
    ).select_related('author', 'genre').order_by('-published_at')
    
    return render(request, 'books/my_publications.html', {'books': books})


def published_books(request):
    """List all published books (public view)"""
    books = Book.objects.filter(status='published').select_related('author', 'genre').order_by('-published_at')
    
    # Pagination
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'books/published_books.html', {'books': page_obj})


@login_required
def add_to_wishlist(request, book_id):
    """Add a book to user's wishlist"""
    book = get_object_or_404(Book, id=book_id, status='published')
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        client=request.user,
        book=book
    )
    
    if created:
        messages.success(request, f'"{book.title}" added to your wishlist.')
    else:
        messages.info(request, f'"{book.title}" is already in your wishlist.')
    
    return redirect('books:detail', book_id=book_id)


@login_required
def remove_from_wishlist(request, book_id):
    """Remove a book from user's wishlist"""
    book = get_object_or_404(Book, id=book_id)
    
    Wishlist.objects.filter(client=request.user, book=book).delete()
    messages.success(request, f'"{book.title}" removed from your wishlist.')
    
    return redirect('books:detail', book_id=book_id)


@login_required
def my_wishlist(request):
    """Display user's wishlist"""
    wishlist_items = Wishlist.objects.filter(client=request.user).select_related('book', 'book__author')
    
    context = {
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_items.count(),
    }
    return render(request, 'books/wishlist.html', context)


@login_required
def download_book(request, book_id):
    """Download a book (after purchase or if free)"""
    book = get_object_or_404(Book, id=book_id, status='published')
    
    # Check if user has access
    has_access = False
    
    if book.is_free:
        has_access = True
    elif request.user.is_authenticated:
        has_access = Purchase.objects.filter(
            client=request.user,
            book=book,
            status='completed'
        ).exists()
    
    if not has_access:
        messages.error(request, 'You do not have permission to download this book.')
        return redirect('books:detail', book_id=book_id)
    
    # Increment download count
    book.downloads_count += 1
    book.save()
    
    # Create download record
    try:
        from .models import Download
        Download.objects.create(
            user=request.user,
            book=book,
            downloaded_at=timezone.now()
        )
    except ImportError:
        pass
    
    if book.file:
        return redirect(book.file.url)
    else:
        messages.error(request, 'File not available for download.')
        return redirect('books:detail', book_id=book_id)


def genre_books(request, genre_slug):
    """Display books by genre slug"""
    genre = get_object_or_404(Genre, slug=genre_slug, is_active=True)
    books = Book.objects.filter(genre=genre, status='published').select_related('author').order_by('-created_at')
    
    context = {
        'genre': genre,
        'books': books,
        'total_books': books.count(),
    }
    return render(request, 'books/genre_books.html', context)


def author_books(request, author_id):
    """Display books by a specific author"""
    author = get_object_or_404(CustomUser, id=author_id, role='author')
    books = Book.objects.filter(author=author, status='published').select_related('genre').order_by('-created_at')
    
    context = {
        'author': author,
        'books': books,
        'total_books': books.count(),
        'total_downloads': books.aggregate(total=Sum('downloads_count'))['total'] or 0,
    }
    return render(request, 'books/author_books.html', context)