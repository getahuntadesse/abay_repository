from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters
from django.db import models
from django.db.models import Sum, Q
from datetime import timedelta
from .forms import LoginForm, ClientRegistrationForm, AuthorRegistrationForm
from .models import CustomUser, AuthorProfile, ClientProfile
from books.models import Book
from payments.models import Purchase
from reviews.models import QualityReview


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def role_based_redirect(user):
    """Return the appropriate dashboard URL based on user role"""
    role_redirects = {
        'admin': 'accounts:admin_dashboard',
        'author': 'accounts:author_dashboard',
        'checker': 'accounts:checker_dashboard',
        'maker': 'accounts:maker_dashboard',
        'client': 'accounts:client_dashboard',
    }
    return role_redirects.get(user.role, 'accounts:client_dashboard')


# =====================================================
# AUTHENTICATION VIEWS
# =====================================================

@sensitive_post_parameters()
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    """User login view - redirects based on role"""
    if request.user.is_authenticated:
        return redirect(role_based_redirect(request.user))
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember = form.cleaned_data.get('remember', False)
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                if not remember:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)
                
                messages.success(request, f'Welcome back, {user.full_name}!')
                
                return redirect(role_based_redirect(user))
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


@csrf_protect
@ensure_csrf_cookie
def register_view(request):
    """Client/Reader registration view"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to Abrehot Library, {user.full_name}!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientRegistrationForm()
    
    return render(request, 'accounts/register_client.html', {'form': form})


@csrf_protect
@ensure_csrf_cookie
def register_author(request):
    """Author registration view with Fayda ID verification"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = AuthorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome Author! {user.full_name}, your profile has been created.')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
            print("Form errors:", form.errors)
    else:
        form = AuthorRegistrationForm()
    
    return render(request, 'accounts/register_author.html', {'form': form})


@login_required
def dashboard_redirect(request):
    """Redirect users to their respective dashboards based on role"""
    return redirect(role_based_redirect(request.user))


# =====================================================
# DASHBOARD VIEWS
# =====================================================

@login_required
def admin_dashboard(request):
    """Admin dashboard view with all statistics"""
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Date ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # ==================== USER STATISTICS ====================
    total_users = CustomUser.objects.count()
    total_authors = CustomUser.objects.filter(role='author').count()
    total_readers = CustomUser.objects.filter(role='client').count()
    total_checkers = CustomUser.objects.filter(role='checker').count()
    total_makers = CustomUser.objects.filter(role='maker').count()
    
    # ==================== BOOK STATISTICS ====================
    total_books = Book.objects.count()
    published_books = Book.objects.filter(status='published').count()
    pending_review = Book.objects.filter(status='pending_review').count()
    in_review = Book.objects.filter(status='in_review').count()
    needs_revision = Book.objects.filter(status='needs_revision').count()
    total_downloads = Book.objects.aggregate(total=Sum('downloads_count'))['total'] or 0
    
    # ==================== PAYMENT STATISTICS ====================
    total_sales = Purchase.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    total_transactions = Purchase.objects.count()
    completed_transactions = Purchase.objects.filter(status='completed').count()
    
    today_sales = Purchase.objects.filter(
        status='completed',
        completed_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    week_sales = Purchase.objects.filter(
        status='completed',
        completed_at__date__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    month_sales = Purchase.objects.filter(
        status='completed',
        completed_at__date__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    monthly_sales = month_sales
    
    # Sales by payment method
    telebirr_sales = Purchase.objects.filter(
        status='completed',
        transaction_id__icontains='TELEBIRR'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    cbe_sales = Purchase.objects.filter(
        status='completed',
        transaction_id__icontains='CBE'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # ==================== RECENT ACTIVITY ====================
    recent_activity = []
    
    # Recent purchases
    recent_purchases = Purchase.objects.filter(status='completed').order_by('-completed_at')[:5]
    for purchase in recent_purchases:
        recent_activity.append({
            'type': 'purchase',
            'icon': 'fa-shopping-cart',
            'title': f'Purchase: {purchase.book.title if purchase.book else "Book"} by {purchase.client.full_name}',
            'time': purchase.completed_at or purchase.created_at,
        })
    
    # Recent user registrations
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]
    for user in recent_users:
        recent_activity.append({
            'type': 'user',
            'icon': 'fa-user-plus',
            'title': f'New {user.role}: {user.full_name or user.username} registered',
            'time': user.date_joined,
        })
    
    # Recent book publications
    recent_books = Book.objects.filter(status='published').order_by('-published_at')[:5]
    for book in recent_books:
        recent_activity.append({
            'type': 'book',
            'icon': 'fa-book',
            'title': f'Book Published: "{book.title}" by {book.author.full_name}',
            'time': book.published_at or book.created_at,
        })
    
    # Sort by time (most recent first)
    recent_activity.sort(key=lambda x: x['time'], reverse=True)
    recent_activity = recent_activity[:10]
    
    context = {
        'user': request.user,
        
        # User Stats
        'total_users': total_users,
        'total_authors': total_authors,
        'total_readers': total_readers,
        'total_checkers': total_checkers,
        'total_makers': total_makers,
        
        # Book Stats
        'total_books': total_books,
        'published_books': published_books,
        'pending_review': pending_review,
        'in_review': in_review,
        'needs_revision': needs_revision,
        'total_downloads': total_downloads,
        
        # Payment Stats
        'total_sales': total_sales,
        'total_transactions': total_transactions,
        'completed_transactions': completed_transactions,
        'today_sales': today_sales,
        'week_sales': week_sales,
        'month_sales': month_sales,
        'monthly_sales': monthly_sales,
        'telebirr_sales': telebirr_sales,
        'cbe_sales': cbe_sales,
        
        # Activity Log
        'recent_activity': recent_activity,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def author_dashboard(request):
    """Author dashboard view with quality scores"""
    if request.user.role != 'author':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Get author's books
    books = Book.objects.filter(author=request.user)
    
    # Annotate each book with its quality review score from checker reviews
    for book in books:
        quality_review = QualityReview.objects.filter(
            book=book,
            review_type='checker'
        ).first()
        if quality_review and quality_review.overall_score:
            book.quality_review_score = quality_review.overall_score
        else:
            book.quality_review_score = None
    
    # Calculate statistics
    total_books = books.count()
    published_books = books.filter(status='published').count()
    pending_review = books.filter(status='pending_review').count()
    in_review = books.filter(status='in_review').count()
    needs_revision = books.filter(status='needs_revision').count()
    total_downloads = books.aggregate(total=Sum('downloads_count'))['total'] or 0
    
    context = {
        'user': request.user,
        'total_books': total_books,
        'published_books': published_books,
        'pending_review': pending_review,
        'in_review': in_review,
        'needs_revision': needs_revision,
        'recent_books': books.order_by('-created_at')[:15],
        'total_downloads': total_downloads,
        'total_earned': 0,
        'pending_earnings': 0,
    }
    return render(request, 'dashboard/author_dashboard.html', context)


@login_required
def checker_dashboard(request):
    """Checker dashboard view - Review and validate book submissions"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Get books pending checker review
    pending_books = Book.objects.filter(status='pending_review').order_by('created_at')
    
    # Get already reviewed books by this checker
    reviewed_books = QualityReview.objects.filter(
        reviewer=request.user, 
        review_type='checker'
    ).select_related('book', 'book__author').order_by('-created_at')[:20]
    
    # Calculate statistics
    total_pending = pending_books.count()
    total_reviewed = reviewed_books.count()
    avg_score = reviewed_books.aggregate(avg=models.Avg('overall_score'))['avg'] or 0
    
    # Reviewed this month
    current_month = timezone.now().month
    current_year = timezone.now().year
    reviewed_this_month = QualityReview.objects.filter(
        reviewer=request.user,
        review_type='checker',
        created_at__year=current_year,
        created_at__month=current_month
    ).count()
    
    context = {
        'user': request.user,
        'pending_books': pending_books,
        'reviewed_books': reviewed_books,
        'total_pending': total_pending,
        'total_reviewed': total_reviewed,
        'avg_score': avg_score,
        'reviewed_this_month': reviewed_this_month,
    }
    return render(request, 'dashboard/checker_dashboard.html', context)


@login_required
def maker_dashboard(request):
    """Maker dashboard view"""
    if request.user.role != 'maker':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    # Get books pending maker approval
    pending_books = Book.objects.filter(status='checker_approved').order_by('checker_reviewed_at')
    
    # Get recently published books
    published_books = Book.objects.filter(
        status='published',
        published_at__month=timezone.now().month
    ).order_by('-published_at')[:10]
    
    # Calculate statistics
    pending_count = pending_books.count()
    approved_count = Book.objects.filter(
        status='published',
        published_at__month=timezone.now().month
    ).count()
    published_count = approved_count
    total_published = Book.objects.filter(status='published').count()
    
    context = {
        'user': request.user,
        'pending_books': pending_books,
        'published_books': published_books,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'published_count': published_count,
        'total_published': total_published,
    }
    return render(request, 'dashboard/maker_dashboard.html', context)


@login_required
def client_dashboard(request):
    """Client dashboard view"""
    if request.user.role != 'client':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:dashboard')
    
    purchases = Purchase.objects.filter(client=request.user, status='completed')
    
    context = {
        'user': request.user,
        'purchases_count': purchases.count(),
        'recent_purchases': purchases.order_by('-created_at')[:10],
        'wishlist_count': 0,
        'total_spent': purchases.aggregate(total=Sum('amount'))['total'] or 0,
    }
    return render(request, 'dashboard/client_dashboard.html', context)


@login_required
def process_checker_review(request):
    """Process the checker's review submission"""
    if request.user.role != 'checker':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        content_quality = request.POST.get('content_quality')
        editorial_quality = request.POST.get('editorial_quality')
        technical_quality = request.POST.get('technical_quality')
        comments = request.POST.get('comments')
        recommendation = request.POST.get('recommendation')
        
        # Validate inputs
        if not all([book_id, content_quality, editorial_quality, technical_quality, recommendation]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('accounts:checker_dashboard')
        
        try:
            book = Book.objects.get(id=book_id)
            
            # Calculate overall score
            scores = [
                float(content_quality),
                float(editorial_quality),
                float(technical_quality),
            ]
            overall_score = sum(scores) / len(scores)
            
            # Update book status based on recommendation
            if recommendation == 'approved':
                book.status = 'checker_approved'
            elif recommendation == 'needs_revision':
                book.status = 'needs_revision'
            else:
                book.status = 'rejected'
            
            book.checker_reviewed_at = timezone.now()
            book.checker_score = round(overall_score, 1)
            book.save()
            
            # Create or update quality review
            quality_review, created = QualityReview.objects.update_or_create(
                book=book,
                reviewer=request.user,
                review_type='checker',
                defaults={
                    'content_quality': float(content_quality),
                    'editorial_quality': float(editorial_quality),
                    'technical_quality': float(technical_quality),
                    'overall_score': round(overall_score, 1),
                    'comments': comments,
                    'recommendation': recommendation,
                    'updated_at': timezone.now(),
                }
            )
            
            if created:
                quality_review.created_at = timezone.now()
                quality_review.save()
            
            messages.success(request, f'Review for "{book.title}" submitted successfully!')
            
        except Book.DoesNotExist:
            messages.error(request, 'Book not found.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('accounts:checker_dashboard')


# =====================================================
# PROFILE VIEWS
# =====================================================

@login_required
def profile_view(request):
    """User profile view with statistics"""
    context = {
        'user': request.user,
    }
    
    # Add author statistics if user is author
    if request.user.role == 'author':
        books = Book.objects.filter(author=request.user)
        context['author_stats'] = {
            'total_books': books.count(),
            'total_downloads': books.aggregate(total=Sum('downloads_count'))['total'] or 0,
            'total_earned': 0,
        }
    else:
        context['author_stats'] = {}
    
    # Add client statistics if user is client
    if request.user.role == 'client':
        purchases = Purchase.objects.filter(client=request.user, status='completed')
        context['client_stats'] = {
            'purchases_count': purchases.count(),
            'total_spent': purchases.aggregate(total=Sum('amount'))['total'] or 0,
        }
    else:
        context['client_stats'] = {}
    
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    """Edit user profile"""
    if request.method == 'POST':
        user = request.user
        user.full_name = request.POST.get('full_name', user.full_name)
        user.phone = request.POST.get('phone', user.phone)
        user.address = request.POST.get('address', user.address)
        user.region = request.POST.get('region', user.region)
        user.zone = request.POST.get('zone', user.zone)
        user.woreda = request.POST.get('woreda', user.woreda)
        user.bio = request.POST.get('bio', user.bio)
        
        # Handle gender update
        gender = request.POST.get('gender')
        if gender in ['M', 'F', 'O']:
            user.gender = gender
        
        # Handle date of birth
        date_of_birth = request.POST.get('date_of_birth')
        if date_of_birth:
            from datetime import datetime
            try:
                user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except:
                pass
        
        if request.FILES.get('profile_image'):
            user.profile_image = request.FILES['profile_image']
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile_edit.html', {'user': request.user})