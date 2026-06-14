from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import connection
from books.models import Book


@login_required
def submit_checker_review(request):
    """Submit checker review for a book"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied. Only checkers can submit reviews.')
        return redirect('dashboard:redirect')
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        content_quality = request.POST.get('content_quality')
        editorial_quality = request.POST.get('editorial_quality')
        technical_quality = request.POST.get('technical_quality')
        comments = request.POST.get('comments', '')
        recommendation = request.POST.get('recommendation')
        
        # Validate inputs
        if not all([content_quality, editorial_quality, technical_quality, recommendation]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('dashboard:checker_dashboard')
        
        try:
            content_quality = float(content_quality)
            editorial_quality = float(editorial_quality)
            technical_quality = float(technical_quality)
        except ValueError:
            messages.error(request, 'Invalid score values. Please enter numbers between 0 and 10.')
            return redirect('dashboard:checker_dashboard')
        
        # Validate score ranges
        if not all(0 <= score <= 10 for score in [content_quality, editorial_quality, technical_quality]):
            messages.error(request, 'Scores must be between 0 and 10.')
            return redirect('dashboard:checker_dashboard')
        
        # Get the book
        book = get_object_or_404(Book, id=book_id)
        
        # Calculate overall score
        overall_score = (content_quality + editorial_quality + technical_quality) / 3
        
        cursor = connection.cursor()
        
        # Check if review exists
        cursor.execute("""
            SELECT id FROM quality_reviews 
            WHERE book_id = %s AND review_type = 'checker'
        """, [book_id])
        existing = cursor.fetchone()
        
        if existing:
            # Update existing review
            cursor.execute("""
                UPDATE quality_reviews 
                SET content_quality = %s, 
                    editorial_quality = %s, 
                    technical_quality = %s,
                    overall_score = %s,
                    comments = %s,
                    recommendation = %s,
                    updated_at = %s
                WHERE book_id = %s AND review_type = 'checker'
            """, [content_quality, editorial_quality, technical_quality, 
                   overall_score, comments, recommendation, timezone.now(), book_id])
        else:
            # Insert new review
            cursor.execute("""
                INSERT INTO quality_reviews 
                (book_id, reviewer_id, review_type, content_quality, editorial_quality, 
                 technical_quality, overall_score, comments, recommendation, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [book_id, request.user.id, 'checker', content_quality, editorial_quality, 
                  technical_quality, overall_score, comments, recommendation, timezone.now(), timezone.now()])
        
        # Update book status based on recommendation
        if recommendation == 'approved':
            book.status = 'in_review'
            messages.success(request, f'Book "{book.title}" approved (Score: {overall_score:.1f}/10). Sent to maker.')
        elif recommendation == 'needs_revision':
            book.status = 'needs_revision'
            book.revision_attempts += 1
            messages.warning(request, f'Revision requested for "{book.title}".')
        elif recommendation == 'rejected':
            book.status = 'rejected'
            messages.error(request, f'Book "{book.title}" has been rejected (Score: {overall_score:.1f}/10).')
        
        book.checker_reviewed_at = timezone.now()
        book.save()
        
        return redirect('dashboard:checker_dashboard')
    
    return redirect('dashboard:checker_dashboard')


@login_required
def submit_maker_review(request):
    """Submit maker final decision for a book"""
    if request.user.role != 'maker':
        messages.error(request, 'Access denied. Only makers can submit final decisions.')
        return redirect('dashboard:redirect')
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        decision = request.POST.get('decision')
        comments = request.POST.get('comments', '')
        
        if not decision:
            messages.error(request, 'Please select a decision.')
            return redirect('dashboard:maker_dashboard')
        
        # Get the book
        book = get_object_or_404(Book, id=book_id)
        
        cursor = connection.cursor()
        
        # Check if review exists
        cursor.execute("""
            SELECT id FROM quality_reviews 
            WHERE book_id = %s AND review_type = 'maker'
        """, [book_id])
        existing = cursor.fetchone()
        
        if existing:
            # Update existing review
            cursor.execute("""
                UPDATE quality_reviews 
                SET comments = %s, recommendation = %s, updated_at = %s
                WHERE book_id = %s AND review_type = 'maker'
            """, [comments, decision, timezone.now(), book_id])
        else:
            # Insert new review
            cursor.execute("""
                INSERT INTO quality_reviews 
                (book_id, reviewer_id, review_type, comments, recommendation, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [book_id, request.user.id, 'maker', comments, decision, timezone.now(), timezone.now()])
        
        # Update book status based on decision
        if decision == 'approved':
            book.status = 'published'
            book.published_at = timezone.now()
            messages.success(request, f'Book "{book.title}" has been approved and published!')
        elif decision == 'needs_revision':
            book.status = 'needs_revision'
            book.revision_attempts += 1
            messages.warning(request, f'Revision requested for "{book.title}".')
        elif decision == 'rejected':
            book.status = 'rejected'
            messages.error(request, f'Book "{book.title}" has been rejected.')
        
        book.maker_approved_at = timezone.now()
        book.save()
        
        return redirect('dashboard:maker_dashboard')
    
    return redirect('dashboard:maker_dashboard')


@login_required
def book_reviews(request, book_id):
    """View all reviews for a specific book"""
    book = get_object_or_404(Book, id=book_id)
    
    # Check permissions
    if request.user.role not in ['admin', 'checker', 'maker'] and book.author != request.user:
        messages.error(request, 'You do not have permission to view these reviews.')
        return redirect('books:detail', book_id=book_id)
    
    cursor = connection.cursor()
    
    # Get checker reviews
    cursor.execute("""
        SELECT qr.*, u.full_name as reviewer_name
        FROM quality_reviews qr
        JOIN users u ON qr.reviewer_id = u.id
        WHERE qr.book_id = %s AND qr.review_type = 'checker'
        ORDER BY qr.id DESC
    """, [book_id])
    columns = [col[0] for col in cursor.description]
    checker_reviews = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # Get maker reviews
    cursor.execute("""
        SELECT qr.*, u.full_name as reviewer_name
        FROM quality_reviews qr
        JOIN users u ON qr.reviewer_id = u.id
        WHERE qr.book_id = %s AND qr.review_type = 'maker'
        ORDER BY qr.id DESC
    """, [book_id])
    maker_reviews = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    context = {
        'book': book,
        'checker_reviews': checker_reviews,
        'maker_reviews': maker_reviews,
    }
    return render(request, 'reviews/book_reviews.html', context)