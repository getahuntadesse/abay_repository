# books/views.py - Complete with complete decision support
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.paginator import Paginator
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import IntegrityError, transaction
from django.core.files.storage import default_storage
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import json
import uuid
import traceback
import hashlib
import hmac
import mimetypes
import os
import random
import string

logger = logging.getLogger(__name__)
from payments.telebirr import TelebirrService
from payments.chapa import ChapaService
from payments.paypal_service import PayPalService
User = get_user_model()

# Import models
from .models import (
    Book, Genre, Wishlist, BookReview, BookActivityLog,
    BookVersion, ReviewAssignment, CheckerReview, RevisionRequest,
    AuthorResponse, EditorialDecision, PublicationRecord,
    BookNotification, BookEmailEvent
)


# =============================================
# WORKFLOW SERVICE (Built-in)
# =============================================

class WorkflowService:
    """Service to handle book workflow operations"""
    
    @staticmethod
    def submit_manuscript(book, user):
        """Submit a manuscript for review"""
        from .models import BookActivityLog
        
        if book.status != Book.STATUS_DRAFT:
            raise ValueError("Only draft books can be submitted")
        
        book.status = Book.STATUS_SUBMITTED
        if not book.submitted_at:
            book.submitted_at = timezone.now()
        book.save()
        
        BookActivityLog.objects.create(
            book=book,
            user=user,
            action='author_submitted',
            old_status=Book.STATUS_DRAFT,
            new_status=Book.STATUS_SUBMITTED,
            notes=f'Book "{book.title}" submitted for review by {user.get_full_name() or user.username}'
        )
        
        logger.info(f"Book {book.id} ({book.title}) submitted by {user.username}")
        return book
    
    @staticmethod
    def initial_review(book, maker, decision, notes):
        """Maker performs initial review of submitted book"""
        from .models import BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can perform initial review")
        
        if book.status not in [Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW]:
            raise ValueError(f"Book must be SUBMITTED or INITIAL_REVIEW. Current: {book.status}")
        
        old_status = book.status
        
        # Map decision to status - SUPPORTING 'complete' AS A VALID DECISION
        status_mapping = {
            'accept': Book.STATUS_AWAITING_CHECKER,
            'complete': Book.STATUS_AWAITING_CHECKER,  # 'complete' maps to AWAITING_CHECKER
            'needs_revision': Book.STATUS_REVISION_REQUIRED,
            'reject': Book.STATUS_REJECTED,
        }
        
        # Map decision to message
        message_mapping = {
            'accept': "Initial review passed. Moving to checker assignment.",
            'complete': "Initial review completed. Forwarding to checker assignment.",
            'needs_revision': f"Initial review: revision needed. Notes: {notes}",
            'reject': f"Initial review rejected. Reason: {notes}",
        }
        
        if decision not in status_mapping:
            raise ValueError(f"Invalid decision: {decision}")
        
        new_status = status_mapping[decision]
        message = message_mapping.get(decision, f"Initial review decision: {decision}")
        
        # Update book
        book.status = new_status
        if decision in ['needs_revision', 'reject']:
            book.revision_notes = notes
        book.maker_notes = notes
        book.save()
        
        # Log activity
        BookActivityLog.objects.create(
            book=book,
            user=maker,
            action='maker_initial_review',
            old_status=old_status,
            new_status=book.status,
            notes=message
        )
        
        logger.info(f"Initial review for book {book.id} completed. Decision: {decision}")
        
        # Create notifications based on decision
        try:
            if decision in ['accept', 'complete']:
                BookNotification.objects.create(
                    book=book,
                    user=book.author,
                    notification_type='book_accepted_initial',
                    title=f'Book Passed Initial Review: {book.title}',
                    message=f'Your book "{book.title}" has passed initial review and has been sent to a quality checker.',
                    link=f'/books/detail/{book.id}/',
                    is_read=False,
                    created_at=timezone.now()
                )
            elif decision == 'reject':
                BookNotification.objects.create(
                    book=book,
                    user=book.author,
                    notification_type='book_rejected',
                    title=f'Book Rejected: {book.title}',
                    message=f'Your book "{book.title}" has been rejected. Reason: {notes}',
                    link=f'/books/detail/{book.id}/',
                    is_read=False,
                    created_at=timezone.now()
                )
            else:
                BookNotification.objects.create(
                    book=book,
                    user=book.author,
                    notification_type='revision_needed',
                    title=f'Revision Needed: {book.title}',
                    message=f'Your book "{book.title}" needs revision. Notes: {notes}',
                    link=f'/books/author/revision/{book.id}/',
                    is_read=False,
                    created_at=timezone.now()
                )
        except Exception as e:
            logger.warning(f"Failed to create notification: {e}")
        
        return book
    
    @staticmethod
    def assign_checker(book, maker, checker, due_date, instructions=None):
        """Assign a checker to a book"""
        from .models import ReviewAssignment, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can assign checkers")
        
        if checker.role != 'checker':
            raise ValueError("User must be a checker")
        
        if book.status != Book.STATUS_AWAITING_CHECKER:
            raise ValueError(f"Book must be AWAITING_CHECKER. Current: {book.status}")
        
        current_version = book.versions.filter(is_current=True).first()
        if not current_version:
            raise ValueError("No current version found for this book")
        
        assignment = ReviewAssignment.objects.create(
            book=book,
            book_version=current_version,
            checker=checker,
            maker=maker,
            due_date=due_date,
            instructions=instructions or '',
            assignment_type='initial',
            assigned_at=timezone.now()
        )
        
        book.checker_assigned = checker
        book.status = Book.STATUS_UNDER_REVIEW
        book.save()
        
        BookActivityLog.objects.create(
            book=book,
            user=maker,
            action='maker_assigned_checker',
            old_status=Book.STATUS_AWAITING_CHECKER,
            new_status=Book.STATUS_UNDER_REVIEW,
            notes=f"Assigned to {checker.get_full_name() or checker.username}"
        )
        
        logger.info(f"Checker {checker.username} assigned to book {book.id}")
        
        # Notify checker
        try:
            BookNotification.objects.create(
                book=book,
                user=checker,
                notification_type='checker_assigned',
                title=f'New Review Assignment: {book.title}',
                message=f'You have been assigned to review "{book.title}". Due date: {due_date}',
                link=f'/books/checker/view/{assignment.id}/',
                is_read=False,
                created_at=timezone.now()
            )
        except Exception as e:
            logger.warning(f"Failed to create notification: {e}")
        
        return assignment
    
    @staticmethod
    def checker_accept_assignment(assignment, checker):
        """Checker accepts a review assignment"""
        if assignment.checker != checker:
            raise ValueError("Assignment does not belong to this checker")
        
        if assignment.status != assignment.STATUS_ASSIGNED:
            raise ValueError(f"Assignment must be ASSIGNED. Current: {assignment.status}")
        
        assignment.accept(checker)
        logger.info(f"Checker {checker.username} accepted assignment {assignment.id}")
        return assignment
    
    @staticmethod
    def checker_submit_review(assignment, checker, review_data):
        """Checker submits a review for a book"""
        from .models import CheckerReview, BookActivityLog
        
        if assignment.checker != checker:
            raise ValueError("Assignment does not belong to this checker")
        
        if assignment.status not in [assignment.STATUS_ACCEPTED, assignment.STATUS_IN_PROGRESS]:
            raise ValueError(f"Assignment must be ACCEPTED or IN_PROGRESS. Current: {assignment.status}")
        
        # Validate required fields
        required = ['recommendation', 'overall_comment']
        for field in required:
            if not review_data.get(field):
                raise ValueError(f"{field} is required")
        
        review = CheckerReview.objects.create(
            assignment=assignment,
            book=assignment.book,
            book_version=assignment.book_version,
            checker=checker,
            recommendation=review_data.get('recommendation'),
            overall_comment=review_data.get('overall_comment'),
            content_quality=review_data.get('content_quality'),
            originality=review_data.get('originality'),
            completeness=review_data.get('completeness'),
            structure=review_data.get('structure'),
            language_quality=review_data.get('language_quality'),
            technical_quality=review_data.get('technical_quality'),
            overall_score=review_data.get('overall_score'),
            author_visible_comments=review_data.get('author_visible_comments', ''),
            internal_comments=review_data.get('internal_comments', ''),
            required_corrections=review_data.get('required_corrections', ''),
            annotated_file=review_data.get('annotated_file'),
        )
        
        review.submit()
        
        assignment.status = assignment.STATUS_COMPLETED
        assignment.completed_at = timezone.now()
        assignment.save()
        
        BookActivityLog.objects.create(
            book=assignment.book,
            user=checker,
            action='checker_submitted_review',
            notes=f"Review submitted. Score: {review.overall_score}/10"
        )
        
        logger.info(f"Review submitted for book {assignment.book.id} by checker {checker.username}")
        return review
    
    @staticmethod
    def maker_make_decision(book, maker, decision, comment):
        """Maker makes final decision based on checker reviews"""
        from .models import EditorialDecision, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can make final decisions")
        
        if book.status != Book.STATUS_REVIEW_COMPLETED:
            raise ValueError(f"Book must be REVIEW_COMPLETED. Current: {book.status}")
        
        editorial = EditorialDecision.objects.create(
            book=book,
            maker=maker,
            decision=decision,
            comment=comment
        )
        
        if decision == 'accept':
            book.status = Book.STATUS_ACCEPTED
            editorial.approved_at = timezone.now()
        elif decision == 'reject':
            book.status = Book.STATUS_REJECTED
        elif decision == 'needs_revision':
            book.status = Book.STATUS_REVISION_REQUIRED
            book.revision_notes = comment
        else:
            raise ValueError(f"Invalid decision: {decision}")
        
        book.save()
        editorial.save()
        
        BookActivityLog.objects.create(
            book=book,
            user=maker,
            action='maker_final_decision',
            new_status=book.status,
            notes=f"Decision: {decision}. Comment: {comment}"
        )
        
        logger.info(f"Final decision for book {book.id}: {decision}")
        
        # Notify author
        if decision == 'accept':
            try:
                BookNotification.objects.create(
                    book=book,
                    user=book.author,
                    notification_type='book_accepted',
                    title=f'Book Accepted: {book.title}',
                    message=f'Congratulations! Your book "{book.title}" has been accepted for publication.',
                    link=f'/books/detail/{book.id}/',
                    is_read=False,
                    created_at=timezone.now()
                )
            except Exception as e:
                logger.warning(f"Failed to create notification: {e}")
        
        return editorial
    
    @staticmethod
    def publish_manuscript(book, maker, data):
        """Publish a manuscript"""
        from .models import PublicationRecord, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can publish books")
        
        if book.status not in [Book.STATUS_ACCEPTED, Book.STATUS_PENDING_PUBLICATION, Book.STATUS_REVIEW_COMPLETED]:
            raise ValueError(f"Book must be ACCEPTED, PENDING_PUBLICATION, or REVIEW_COMPLETED. Current: {book.status}")
        
        book.status = Book.STATUS_PUBLISHED
        book.published_at = timezone.now()
        book.save()
        
        publication = PublicationRecord.objects.create(
            book=book,
            published_by=maker,
            publication_date=timezone.now(),
            version=book.current_version or 1,
            notes=data.get('notes', '')
        )
        
        BookActivityLog.objects.create(
            book=book,
            user=maker,
            action='maker_published',
            new_status=Book.STATUS_PUBLISHED,
            notes=f'Book published by {maker.get_full_name() or maker.username}'
        )
        
        logger.info(f"Book {book.id} published by {maker.username}")
        
        # Notify author
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='book_published',
                title=f'Book Published: {book.title}',
                message=f'Great news! Your book "{book.title}" has been published and is now available in the repository.',
                link=f'/books/detail/{book.id}/',
                is_read=False,
                created_at=timezone.now()
            )
        except Exception as e:
            logger.warning(f"Failed to create notification: {e}")
        
        return publication
    
    @staticmethod
    def author_submit_revision(book, author, file, revision_notes):
        """Author submits a revision"""
        from .models import BookVersion, BookActivityLog
        
        if author != book.author:
            raise ValueError("Only the book author can submit revisions")
        
        if book.status != Book.STATUS_REVISION_REQUIRED:
            raise ValueError(f"Book must be REVISION_REQUIRED. Current: {book.status}")
        
        current_version = book.versions.filter(is_current=True).first()
        new_version_number = (current_version.version_number + 1) if current_version else 1
        
        new_version = BookVersion.objects.create(
            book=book,
            version_number=new_version_number,
            file=file,
            cover_image=book.cover_image,
            sample_file=book.sample_file,
            uploaded_by=author,
            revision_notes=revision_notes,
            parent_version=current_version.version_number if current_version else None,
            is_current=True,
            file_size=file.size if file else 0,
            file_hash='',
            changes_summary=revision_notes or 'Revision submitted',
            is_major_revision=True
        )
        
        if current_version:
            current_version.is_current = False
            current_version.save()
        
        book.file = file
        book.current_version = new_version_number
        book.revision_count = (book.revision_count or 0) + 1
        book.status = Book.STATUS_RESUBMITTED
        book.revision_notes = revision_notes
        book.save()
        
        BookActivityLog.objects.create(
            book=book,
            user=author,
            action='author_submitted_revision',
            old_status=Book.STATUS_REVISION_REQUIRED,
            new_status=Book.STATUS_RESUBMITTED,
            notes=f"Revision v{new_version_number} submitted"
        )
        
        logger.info(f"Revision v{new_version_number} submitted for book {book.id}")
        return new_version


# =============================================
# NOTIFICATION SERVICE (Built-in)
# =============================================

class NotificationService:
    """Service to handle notifications"""
    
    @staticmethod
    def notify_makers_new_submission(book):
        """Notify all makers about a new submission"""
        makers = User.objects.filter(role='maker', is_active=True)
        
        for maker in makers:
            try:
                BookNotification.objects.create(
                    book=book,
                    user=maker,
                    notification_type='new_submission',
                    title=f'New Book Submission: {book.title}',
                    message=f'{book.author.get_full_name() or book.author.username} has submitted "{book.title}" for review.',
                    link=f'/books/maker/initial-review/{book.id}/',
                    is_read=False,
                    created_at=timezone.now()
                )
            except Exception as e:
                logger.error(f"Failed to create notification for maker {maker.username}: {e}")
        
        logger.info(f"Notifications sent to {makers.count()} makers about new submission {book.id}")
    
    @staticmethod
    def notify_checker_assigned(assignment):
        """Notify checker about assignment"""
        try:
            BookNotification.objects.create(
                book=assignment.book,
                user=assignment.checker,
                notification_type='checker_assigned',
                title=f'New Review Assignment: {assignment.book.title}',
                message=f'You have been assigned to review "{assignment.book.title}". Due date: {assignment.due_date}',
                link=f'/books/checker/view/{assignment.id}/',
                is_read=False,
                created_at=timezone.now()
            )
            logger.info(f"Notification sent to checker {assignment.checker.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for checker: {e}")


# =============================================
# TELEBIRR PAYMENT CLASS
# =============================================

class TelebirrPayment:
    """Telebirr payment integration class with simulation support"""
    
    def __init__(self, request=None):
        self.app_id = getattr(settings, 'TELEBIRR_FABRIC_APP_ID', 'SIM-APP-2024-001')
        self.app_key = getattr(settings, 'TELEBIRR_APP_SECRET', 'SIM-KEY-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=32)))
        self.short_code = getattr(settings, 'TELEBIRR_MERCHANT_CODE', '101011')
        self.merchant_app_id = getattr(settings, 'TELEBIRR_MERCHANT_APP_ID', '930231098009602')
        self.api_url = getattr(settings, 'TELEBIRR_BASE_URL', 'https://superapp.ethiomobilemoney.et:38443/apiaccess/payment/gateway')
        self.callback_url = getattr(settings, 'TELEBIRR_CALLBACK_URL', '')
        self.return_url = getattr(settings, 'TELEBIRR_RETURN_URL', '')
        self.request = request
        self.verify_ssl = getattr(settings, 'TELEBIRR_VERIFY_SSL', True)
        self.use_simulated = getattr(settings, 'USE_SIMULATED_PAYMENT', False)
        self.telebirr_enabled = getattr(settings, 'TELEBIRR_ENABLED', True)
        self.simulate_success_rate = 0.95
        self.simulate_delay = 2
    
    def get_base_url(self):
        base_url = getattr(settings, 'BASE_URL', None)
        if base_url:
            return base_url.rstrip('/')
        if self.request:
            scheme = 'https' if self.request.is_secure() else 'http'
            host = self.request.get_host()
            return f"{scheme}://{host}"
        return 'http://localhost:3000'
    
    def generate_signature(self, data):
        sorted_data = {k: data[k] for k in sorted(data.keys())}
        data_string = '&'.join([f"{k}={v}" for k, v in sorted_data.items()])
        signature = hmac.new(
            self.app_key.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def generate_transaction_id(self):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"TEL-{timestamp}-{random_part}"
    
    def generate_payment_url(self, transaction_id, amount):
        base_url = self.get_base_url()
        return f"{base_url}/books/telebirr/pay/{transaction_id}/?amount={amount}&status=pending"
    
    def process_payment_simulation(self, transaction_id, amount, phone_number):
        import time
        time.sleep(self.simulate_delay)
        
        is_success = random.random() < self.simulate_success_rate
        payment_ref = f"PAY-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        
        if is_success:
            return {
                'status': 'success',
                'code': '00',
                'message': 'Payment processed successfully',
                'transactionId': transaction_id,
                'reference': payment_ref,
                'amount': str(amount),
                'phoneNumber': phone_number,
                'paymentUrl': self.generate_payment_url(transaction_id, amount),
                'processingTime': f"{self.simulate_delay}.{random.randint(10, 99)}s",
                'timestamp': datetime.now().isoformat()
            }
        else:
            error_codes = ['01', '02', '03', '04', '05']
            error_messages = [
                'Insufficient balance',
                'Invalid phone number',
                'Transaction timeout',
                'Network error',
                'Payment declined by bank'
            ]
            idx = random.randint(0, 4)
            return {
                'status': 'failed',
                'code': error_codes[idx],
                'message': error_messages[idx],
                'transactionId': transaction_id,
                'amount': str(amount),
                'phoneNumber': phone_number,
                'timestamp': datetime.now().isoformat()
            }
    
    def initiate_payment(self, purchase, phone_number=None):
        """Production Telebirr checkout (simulation only if USE_SIMULATED_PAYMENT=True)."""
        try:
            amount = float(purchase.amount)
            if amount <= 0:
                return {
                    'success': True,
                    'reference': f"FREE-{uuid.uuid4().hex[:8].upper()}",
                    'message': 'Free book - no payment needed',
                    'is_free': True,
                    'payment_mode': 'free',
                    'is_simulated': False,
                }

            # ---- PRODUCTION path ----
            if not self.use_simulated:
                tb = TelebirrService()
                merch_order_id = getattr(purchase, 'transaction_id', None) or self.generate_transaction_id()
                result = tb.create_checkout(
                    title=f"Book: {purchase.book.title}",
                    amount=amount,
                    merch_order_id=merch_order_id,
                )
                if result.get('success'):
                    return {
                        'success': True,
                        'reference': result.get('merch_order_id') or merch_order_id,
                        'payment_url': result.get('checkout_url'),
                        'transaction_id': result.get('merch_order_id') or merch_order_id,
                        'message': 'Redirecting to Telebirr',
                        'is_real_payment': True,
                        'is_simulated': False,
                    }
                return {
                    'success': False,
                    'error': result.get('error', 'Telebirr checkout failed'),
                    'is_simulated': False,
                }

            # ---- Simulation path (dev only) ----
            transaction_id = self.generate_transaction_id()
            result = self.process_payment_simulation(
                transaction_id, amount, phone_number or '0912345678'
            )
            if result.get('status') == 'success' and result.get('code') == '00':
                return {
                    'success': True,
                    'reference': transaction_id,
                    'payment_url': self.generate_payment_url(transaction_id, amount),
                    'transaction_id': transaction_id,
                    'message': 'Payment initiated (SIMULATED — set USE_SIMULATED_PAYMENT=False for live)',
                    'is_real_payment': False,
                    'is_simulated': True,
                }
            return {
                'success': False,
                'error': result.get('message', 'Simulated payment failed'),
                'is_simulated': True,
            }
        except Exception as e:
            logger.error(f"Telebirr payment error: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e), 'is_simulated': False}
    
    def verify_payment(self, transaction_id):
        try:
            import time
            time.sleep(1)
            
            verification_data = {
                'appId': self.app_id,
                'transactionId': transaction_id,
                'timestamp': datetime.now().strftime('%Y%m%d%H%M%S')
            }
            verification_data['signature'] = self.generate_signature(verification_data)
            
            payment_ref = f"PAY-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
            
            return {
                'success': True,
                'status': 'completed',
                'reference': payment_ref,
                'transaction_id': transaction_id,
                'amount': '100.00',
                'payment_method': 'telebirr',
                'verification_time': datetime.now().isoformat(),
                'is_debug': True,
                'is_simulated': True,
                'message': 'Payment verified successfully (simulated)'
            }
                
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'is_simulated': True
            }


# =============================================
# PAYMENT METHODS HELPERS
# =============================================

def get_available_payment_methods():
    """Methods shown on the book purchase interface. Telebirr only."""
    return [
        {
            'id': 'telebirr',
            'name': 'Telebirr',
            'icon': 'fas fa-mobile-alt',
            'description': 'Pay with Telebirr (Ethio telecom mobile money)',
            'color': 'success',
            'badge': 'Available',
            'show_badge': True,
        },
    ]


def get_tax_rate(book):
    """Determine tax rate based on book genre"""
    culture_genres = [
        'culture', 'cultural', 'history', 'heritage', 'tradition',
        'ethiopian', 'amharic', 'oromo', 'tigrinya', 'somali',
        'african', 'folklore', 'mythology', 'traditional',
        'language', 'literature', 'poetry', 'religious',
        'spiritual', 'custom', 'ritual', 'celebration'
    ]
    
    if book and book.genre:
        genre_name = book.genre.name.lower() if book.genre.name else ''
        if any(g in genre_name for g in culture_genres):
            return 5
    return 10


def create_payment_record(purchase):
    """Create payment record for a completed purchase (FinanceSettings rates)."""
    try:
        from payments.views import create_author_payment as _cap
        return _cap(purchase)
        from payments.models import Payment  # noqa
        
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


# =============================================
# HOME VIEW
# =============================================

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['featured_books'] = Book.objects.filter(
            status=Book.STATUS_PUBLISHED
        ).select_related('author', 'genre').order_by('-downloads_count', '-created_at')[:8]
        context['total_books'] = Book.objects.filter(status=Book.STATUS_PUBLISHED).count()
        context['total_downloads'] = Book.objects.filter(status=Book.STATUS_PUBLISHED).aggregate(
            total=Sum('downloads_count')
        )['total'] or 0
        context['total_authors'] = User.objects.filter(role='author', is_active=True).count()
        context['total_readers'] = User.objects.filter(role='client', is_active=True).count()
        return context


# =============================================
# TELEBIRR SIMULATION VIEWS
# =============================================

@login_required
def telebirr_pay_simulate(request, transaction_id):
    from payments.models import Purchase
    
    amount = request.GET.get('amount', '0.00')
    status = request.GET.get('status', 'pending')
    
    purchase = Purchase.objects.filter(
        Q(transaction_reference=transaction_id) | 
        Q(purchase_reference=transaction_id) |
        Q(transaction_id=transaction_id)
    ).first()
    
    context = {
        'transaction_id': transaction_id,
        'amount': amount,
        'status': status,
        'purchase': purchase,
        'merchant_name': 'Abay Repository',
        'merchant_logo': '/static/images/logo.png',
    }
    return render(request, 'books/telebirr_payment_simulate.html', context)


@login_required
def telebirr_pay_process(request, transaction_id):
    from payments.models import Purchase
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('books:detail', book_id=1)
    
    action = request.POST.get('action', 'confirm')
    
    purchase = Purchase.objects.filter(
        Q(transaction_reference=transaction_id) | 
        Q(purchase_reference=transaction_id) |
        Q(transaction_id=transaction_id)
    ).first()
    
    if not purchase:
        messages.error(request, 'Purchase not found.')
        return redirect('books:browse')
    
    if action == 'confirm':
        try:
            with transaction.atomic():
                purchase.status = 'completed'
                purchase.completed_at = timezone.now()
                purchase.transaction_reference = transaction_id
                purchase.purchase_reference = transaction_id
                purchase.save()
                
                purchase.book.purchase_count += 1
                purchase.book.save()
                
                create_payment_record(purchase)
                
                messages.success(request, f'Payment successful! "{purchase.book.title}" added to your library.')
                return redirect('books:my_books_user')
                
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            messages.error(request, 'An error occurred processing your payment. Please try again.')
            return redirect('books:detail', book_id=purchase.book.id)
    
    elif action == 'cancel':
        purchase.status = 'failed'
        purchase.save()
        messages.error(request, 'Payment was cancelled.')
        return redirect('books:detail', book_id=purchase.book.id)
    
    return redirect('books:detail', book_id=purchase.book.id)


@csrf_exempt
def telebirr_callback(request):
    from payments.models import Purchase
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.POST
            logger.info(f"Telebirr callback received: {data}")
            
            transaction_id = data.get('transactionId') or data.get('transaction_id')
            status = data.get('status')
            reference = data.get('reference')
            payment_status = data.get('paymentStatus') or data.get('payment_status')
            
            if not status and payment_status:
                status = payment_status
            
            if not transaction_id:
                logger.warning("No transaction ID in callback")
                return JsonResponse({'status': 'error', 'message': 'Missing transaction ID'}, status=400)
            
            with transaction.atomic():
                purchase = Purchase.objects.filter(
                    Q(transaction_reference=transaction_id) | 
                    Q(purchase_reference=transaction_id) |
                    Q(transaction_id=transaction_id)
                ).first()
                
                if not purchase:
                    logger.warning(f"Purchase not found for transaction: {transaction_id}")
                    return JsonResponse({'status': 'error', 'message': 'Purchase not found'}, status=404)
                
                if status and (status.lower() == 'success' or status.lower() == 'completed'):
                    purchase.status = 'completed'
                    purchase.completed_at = timezone.now()
                    if reference:
                        purchase.transaction_reference = reference
                        purchase.purchase_reference = reference
                    purchase.save()
                    
                    purchase.book.purchase_count += 1
                    purchase.book.save()
                    
                    create_payment_record(purchase)
                    
                    logger.info(f"Payment completed for purchase {purchase.id}")
                    return JsonResponse({'status': 'success', 'message': 'Payment confirmed'})
                
                elif status and (status.lower() == 'failed' or status.lower() == 'cancelled'):
                    purchase.status = 'failed'
                    purchase.save()
                    logger.warning(f"Payment failed for purchase {purchase.id}")
                    return JsonResponse({'status': 'success', 'message': 'Payment failed'})
                
                else:
                    logger.info(f"Unknown payment status: {status} for purchase {purchase.id}")
                    return JsonResponse({'status': 'success', 'message': 'Status pending'})
                
        except Exception as e:
            logger.error(f"Callback processing error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required
def telebirr_return(request):
    from payments.models import Purchase
    
    transaction_id = request.GET.get('transactionId') or request.GET.get('transaction_id')
    status = request.GET.get('status')
    reference = request.GET.get('reference')
    
    if not transaction_id:
        messages.error(request, 'Invalid payment response')
        return redirect('books:browse')
    
    try:
        with transaction.atomic():
            purchase = Purchase.objects.filter(
                Q(transaction_reference=transaction_id) | 
                Q(purchase_reference=transaction_id) |
                Q(transaction_id=transaction_id)
            ).first()
            
            if not purchase:
                messages.error(request, 'Purchase not found')
                return redirect('books:browse')
            
            if purchase.status == 'completed':
                messages.success(request, f'Payment successful! "{purchase.book.title}" added to your library.')
                return redirect('books:my_books_user')
            
            purchase.status = 'completed'
            purchase.completed_at = timezone.now()
            if reference:
                purchase.transaction_reference = reference
                purchase.purchase_reference = reference
            purchase.save()
            
            purchase.book.purchase_count += 1
            purchase.book.save()
            
            create_payment_record(purchase)
            
            messages.success(request, f'Payment successful! "{purchase.book.title}" added to your library.')
            return redirect('books:my_books_user')
                    
    except Exception as e:
        logger.error(f"Return processing error: {str(e)}")
        messages.error(request, 'An error occurred processing your payment. Please contact support.')
        return redirect('books:browse')


@login_required
def telebirr_simulate(request, transaction_id):
    from payments.models import Purchase
    
    if not settings.DEBUG:
        messages.error(request, 'This endpoint is only available in debug mode')
        return redirect('books:browse')
    
    try:
        with transaction.atomic():
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
            
            purchase.book.purchase_count += 1
            purchase.book.save()
            
            create_payment_record(purchase)
            
            messages.success(request, f'Payment simulated successfully! "{purchase.book.title}" added to your library.')
            return redirect('books:my_books_user')
            
    except Exception as e:
        logger.error(f"Simulation error: {str(e)}")
        messages.error(request, 'An error occurred during simulation. Please try again.')
        return redirect('books:browse')


# =============================================
# BROWSE AND SEARCH VIEWS
# =============================================

def browse_books(request):
    books = Book.objects.filter(status=Book.STATUS_PUBLISHED).select_related('author', 'genre').order_by('-created_at')
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
    query = request.GET.get('q', '')
    books = []
    if query:
        books = Book.objects.filter(
            status=Book.STATUS_PUBLISHED,
            title__icontains=query
        ).select_related('author')[:10]
    return render(request, 'books/search_results.html', {'books': books, 'query': query})


# =============================================
# BOOK DETAIL VIEW
# =============================================

def book_detail(request, book_id):
    try:
        book = get_object_or_404(Book, id=book_id)
    except Book.DoesNotExist:
        messages.error(request, 'Book not found.')
        return redirect('books:browse')
    
    if book.status != Book.STATUS_PUBLISHED:
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
            from payments.models import Purchase
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
                client=request.user,
                book=book
            ).exists()
        except Exception as e:
            logger.error(f"Error checking wishlist: {e}")
            in_wishlist = False
    
    quality_score = book.checker_score
    
    related_books = []
    if book.genre_id:
        try:
            genre = Genre.objects.get(id=book.genre_id)
            related_books = Book.objects.filter(
                genre=genre, 
                status=Book.STATUS_PUBLISHED
            ).exclude(id=book.id).select_related('author')[:5]
        except:
            related_books = []
    else:
        related_books = Book.objects.filter(status=Book.STATUS_PUBLISHED).exclude(id=book.id).order_by('?')[:5]
    
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
# PURCHASE FLOW
# =============================================

@csrf_exempt
@login_required
def purchase_book(request, book_id):
    from payments.models import Purchase
    
    try:
        book = get_object_or_404(Book, id=book_id, status=Book.STATUS_PUBLISHED)
    except Book.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Book not found'}, status=404)
        messages.error(request, 'Book not found.')
        return redirect('books:browse')
    
    if Purchase.objects.filter(user=request.user, book=book, status='completed').exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'You already own this book'}, status=400)
        messages.warning(request, 'You already own this book.')
        return redirect('books:detail', book_id=book_id)
    
    if book.price == 0 or book.is_free:
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(
                    book=book,
                    user=request.user,
                    amount=Decimal('0.00'),
                    status='completed',
                    payment_method='free',
                    transaction_reference='FREE-DOWNLOAD',
                    purchase_reference='FREE-DOWNLOAD',
                    completed_at=timezone.now(),
                )
                
                book.purchase_count += 1
                book.save()
                
                create_payment_record(purchase)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Book downloaded successfully!',
                        'free': True,
                        'transaction_id': purchase.transaction_id,
                        'download_url': reverse('books:download', kwargs={'book_id': book.id})
                    })
                
                messages.success(request, f'You have successfully downloaded "{book.title}"!')
                return redirect('books:detail', book_id=book_id)
        except Exception as e:
            logger.error(f"Free book purchase error: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')
            return redirect('books:detail', book_id=book_id)
    
    if request.method == 'GET':
        payment_methods = get_available_payment_methods()
        context = {
            'book': book,
            'payment_methods': payment_methods,
            'amount': book.price,
            'user': request.user,
            'debug': settings.DEBUG,
            'use_simulated': getattr(settings, 'USE_SIMULATED_PAYMENT', False),
            'telebirr_enabled': getattr(settings, 'TELEBIRR_ENABLED', False),
        }
        return render(request, 'books/payment_methods.html', context)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        phone_number = request.POST.get('phone_number', request.user.phone or '')
        
        if not payment_method:
            messages.error(request, 'Please select a payment method.')
            return redirect('books:purchase_book', book_id=book_id)
        
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(
                    book=book,
                    user=request.user,
                    amount=book.price,
                    status='pending',
                    payment_method=payment_method,
                    transaction_reference=None,
                    purchase_reference=None,
                )
                
                email = request.POST.get('email') or getattr(request.user, 'email', '') or ''
                checkout_url = None
                reference = None

                if payment_method == 'telebirr':
                    tb = TelebirrService()
                    if not tb.is_configured():
                        purchase.status = 'failed'
                        purchase.save(update_fields=['status'])
                        # Log which keys are missing so support can fix .env quickly
                        missing = []
                        if not getattr(settings, 'TELEBIRR_FABRIC_APP_ID', ''):
                            missing.append('TELEBIRR_FABRIC_APP_ID')
                        if not getattr(settings, 'TELEBIRR_APP_SECRET', ''):
                            missing.append('TELEBIRR_APP_SECRET')
                        if not getattr(settings, 'TELEBIRR_MERCHANT_APP_ID', ''):
                            missing.append('TELEBIRR_MERCHANT_APP_ID')
                        if not getattr(settings, 'TELEBIRR_MERCHANT_CODE', ''):
                            missing.append('TELEBIRR_MERCHANT_CODE')
                        if not getattr(settings, 'TELEBIRR_PRIVATE_KEY', ''):
                            missing.append('TELEBIRR_PRIVATE_KEY')
                        logger.error("Telebirr not configured. Missing: %s", missing or "private key failed to load")
                        err = 'Telebirr is not configured. Set TELEBIRR_* keys in .env.'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'error': err}, status=503)
                        messages.error(request, err)
                        return redirect('books:purchase_book', book_id=book_id)
                    phone = (phone_number or '').strip()
                    if not phone or len(phone) < 9:
                        purchase.status = 'failed'
                        purchase.save(update_fields=['status'])
                        err = 'A valid Telebirr phone number is required.'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'error': err}, status=400)
                        messages.error(request, err)
                        return redirect('books:purchase_book', book_id=book_id)
                    result = tb.create_checkout(
                        title=book.title[:128],
                        amount=float(book.price),
                        merch_order_id=(purchase.transaction_id or f"PUR{purchase.id}").replace("-", "").replace("_", ""),
                    )
                    if not result.get('success'):
                        purchase.status = 'failed'
                        purchase.save(update_fields=['status'])
                        err = result.get('error', 'Telebirr checkout failed.')
                        logger.error("Telebirr create_checkout failed: %s", err)
                        err_s = err if isinstance(err, str) else str(err)
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'error': err_s}, status=502)
                        messages.error(request, err_s)
                        return redirect('books:purchase_book', book_id=book_id)
                    checkout_url = result.get('checkout_url') or result.get('checkOutUrl')
                    reference = result.get('merch_order_id') or result.get('prepay_id')
                    prepay_id = result.get('prepay_id') or ''

                else:
                    purchase.status = 'failed'
                    purchase.save(update_fields=['status'])
                    messages.error(request, 'Only Telebirr is supported. Please select Telebirr.')
                    return redirect('books:purchase_book', book_id=book_id)

                if checkout_url:
                    # Store both ids so return/webhook can find the purchase
                    purchase.transaction_reference = reference
                    purchase.purchase_reference = prepay_id or reference
                    purchase.save(update_fields=['transaction_reference', 'purchase_reference', 'updated_at'])
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'redirect_url': checkout_url,
                            'payment_url': checkout_url,
                            'checkout_url': checkout_url,
                            'transaction_id': purchase.transaction_id,
                            'reference': reference,
                        })
                    return redirect(checkout_url)

                purchase.status = 'failed'
                purchase.save(update_fields=['status'])
                err_msg = 'Payment URL not available. Please try again.'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': err_msg}, status=502)
                messages.error(request, err_msg)
                return redirect('books:purchase_book', book_id=book_id)
                    
        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            err = 'Database error. Please try again.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': err}, status=500)
            messages.error(request, err)
            return redirect('books:detail', book_id=book_id)
        except Exception as e:
            logger.error(f"Purchase error: {str(e)}")
            logger.error(traceback.format_exc())
            err = f'Failed to process purchase: {str(e)[:200]}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': err}, status=500)
            messages.error(request, err)
            return redirect('books:detail', book_id=book_id)
    
    return redirect('books:detail', book_id=book_id)


@csrf_exempt
@login_required
def process_payment(request, purchase_id):
    from payments.models import Purchase
    
    try:
        purchase = get_object_or_404(Purchase, id=purchase_id, user=request.user)
    except Purchase.DoesNotExist:
        messages.error(request, 'Purchase not found.')
        return redirect('books:browse')
    
    if purchase.status == 'completed':
        messages.warning(request, 'This purchase has already been completed.')
        return redirect('books:my_books_user')
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'telebirr')
        phone_number = request.POST.get('phone_number', request.user.phone or '')
        
        try:
            with transaction.atomic():
                if payment_method == 'telebirr':
                    telebirr = TelebirrPayment(request=request)
                    result = telebirr.initiate_payment(purchase, phone_number)
                elif payment_method == 'chapa':
                    ch = ChapaService()
                    email = request.POST.get('email') or request.user.email or ''
                    full = (getattr(request.user, 'full_name', None) or request.user.username or 'Customer').split(' ', 1)
                    result = ch.initialize(
                        amount=float(purchase.amount),
                        email=email or 'customer@abay.local',
                        first_name=full[0],
                        last_name=full[1] if len(full) > 1 else '',
                        phone=phone_number or '',
                        tx_ref=purchase.transaction_id,
                        title=f"Book: {purchase.book.title}"[:16],
                    )
                    if result.get('success'):
                        result = {
                            'success': True,
                            'reference': result.get('tx_ref'),
                            'payment_url': result.get('checkout_url'),
                            'is_simulated': False,
                        }
                elif payment_method == 'paypal':
                    pp = PayPalService()
                    amount = float(purchase.amount)
                    rate = float(getattr(settings, 'ETB_TO_USD_RATE', 0) or 0)
                    if getattr(settings, 'PAYPAL_CURRENCY', 'USD') == 'USD' and rate > 0:
                        amount = round(amount * rate, 2)
                    result = pp.create_order(
                        amount=amount,
                        description=f"Abay: {purchase.book.title}"[:127],
                        custom_id=purchase.transaction_id,
                    )
                    if result.get('success'):
                        result = {
                            'success': True,
                            'reference': result.get('order_id'),
                            'payment_url': result.get('checkout_url'),
                            'is_simulated': False,
                        }
                else:
                    result = {'success': False, 'error': 'Unsupported payment method'}
                
                if result.get('success'):
                    is_simulated = result.get('is_debug', False) or result.get('is_simulated', False)
                    
                    if is_simulated:
                        purchase.status = 'completed'
                        purchase.completed_at = timezone.now()
                        reference = result.get('reference')
                        purchase.transaction_reference = reference
                        purchase.purchase_reference = reference
                        purchase.payment_method = payment_method
                        purchase.save()
                        
                        purchase.book.purchase_count += 1
                        purchase.book.save()
                        
                        create_payment_record(purchase)
                        
                        messages.success(request, f'Payment of {purchase.amount} ETB completed successfully!')
                        return redirect('books:my_books_user')
                    else:
                        payment_url = result.get('payment_url')
                        if payment_url:
                            return redirect(payment_url)
                        else:
                            messages.error(request, 'Payment URL not available.')
                            return redirect('books:detail', book_id=purchase.book.id)
                else:
                    purchase.status = 'failed'
                    purchase.save()
                    messages.error(request, result.get('error', 'Payment failed. Please try again.'))
                    return redirect('books:payment', purchase_id=purchase.id)
                    
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            messages.error(request, f'Error processing payment: {str(e)[:100]}')
            return redirect('books:payment', purchase_id=purchase.id)
    
    context = {
        'purchase': purchase,
        'book': purchase.book,
        'amount': purchase.amount,
        'phone_number': request.user.phone or '',
        'payment_methods': get_available_payment_methods(),
    }
    return render(request, 'books/payment.html', context)


@login_required
def payment_success(request, purchase_id):
    from payments.models import Purchase
    
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
# USER'S BOOKS (MY LIBRARY)
# =============================================

@login_required
def my_books_user(request):
    from payments.models import Purchase
    
    purchases = Purchase.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('book', 'book__author', 'book__genre').order_by('-completed_at')
    
    books = [purchase.book for purchase in purchases if purchase.book.status == Book.STATUS_PUBLISHED]
    
    total_downloads = sum(book.downloads_count for book in books)
    
    total_read_time = 0
    for book in books:
        if book.page_count and book.page_count > 0:
            total_read_time += book.page_count * 2
    
    context = {
        'books': books,
        'total_books': len(books),
        'purchases': purchases,
        'total_downloads': total_downloads,
        'total_read_time': total_read_time,
        'user': request.user,
    }
    return render(request, 'books/my_books_user.html', context)


# =============================================
# BOOK DOWNLOAD
# =============================================

def _user_can_read_book(user, book):
    """Free books: anyone logged in. Paid: completed purchase required."""
    if book.is_free or book.price == 0:
        return True
    if not user.is_authenticated:
        return False
    if getattr(user, 'role', None) in ('admin', 'maker', 'checker'):
        return True
    if getattr(book, 'author_id', None) and book.author_id == user.id:
        return True
    try:
        from payments.models import Purchase
        return Purchase.objects.filter(
            user=user, book=book, status='completed'
        ).exists()
    except Exception:
        return False


@login_required
def download_book(request, book_id):
    """Downloads disabled — redirect to in-browser reader."""
    messages.info(request, 'Books are available for online reading only (download disabled).')
    return redirect('books:read', book_id=book_id)


@login_required
def read_free_book(request, book_id):
    """Legacy URL — same as unified reader."""
    return redirect('books:read', book_id=book_id)


@login_required
def read_book(request, book_id):
    """
    In-browser reader for free or purchased books.
    PDF is not offered as a file download; it is viewed on this page only.
    """
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_PUBLISHED)

    if not _user_can_read_book(request.user, book):
        messages.error(
            request,
            'You need to purchase this book before you can read it online.',
        )
        return redirect('books:detail', book_id=book_id)

    if not book.file:
        messages.error(request, 'This book has no readable file yet.')
        return redirect('books:detail', book_id=book_id)

    try:
        book.views_count = (book.views_count or 0) + 1
        book.save(update_fields=['views_count'])
    except Exception:
        pass

    is_pdf = str(book.file.name).lower().endswith('.pdf')
    context = {
        'book': book,
        'is_pdf': is_pdf,
        'stream_url': f'/books/{book.id}/stream/',
        'is_free': book.is_free or book.price == 0,
    }
    return render(request, 'books/reader.html', context)



@login_required
def stream_book_pdf(request, book_id):
    """
    Stream book PDF for the reader (inline only — no attachment download).
    """
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_PUBLISHED)

    if not _user_can_read_book(request.user, book):
        raise Http404('Not allowed')

    if not book.file:
        raise Http404('File missing')

    try:
        if not default_storage.exists(book.file.name):
            raise Http404('File not found on storage')
    except Exception:
        pass

    try:
        file_path = book.file.path
    except Exception:
        try:
            f = default_storage.open(book.file.name, 'rb')
            response = FileResponse(f, content_type='application/pdf')
            response['Content-Disposition'] = 'inline'
            response['X-Content-Type-Options'] = 'nosniff'
            response['Cache-Control'] = 'private, max-age=3600'
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        except Exception as e:
            logger.error('stream_book_pdf open error: %s', e)
            raise Http404('Unable to open file')

    if not os.path.exists(file_path):
        raise Http404('File not found')

    content_type = 'application/pdf'
    if not str(file_path).lower().endswith('.pdf'):
        guessed, _ = mimetypes.guess_type(file_path)
        content_type = guessed or 'application/octet-stream'

    try:
        f = open(file_path, 'rb')
        response = FileResponse(f, content_type=content_type)
        response['Content-Disposition'] = 'inline'
        response['X-Content-Type-Options'] = 'nosniff'
        # private + short cache helps offline SW/IDB without public CDN caching
        response['Cache-Control'] = 'private, max-age=3600'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        logger.info('Book streamed for reading: %s by %s', book.title, request.user.username)
        return response
    except Exception as e:
        logger.error('stream_book_pdf error: %s', e)
        raise Http404('Unable to stream file')


@login_required
def offline_library(request):
    """Shell page for managing offline-cached books (data lives in browser IndexedDB)."""
    return render(request, 'books/offline_library.html')


def reader_service_worker(request):
    """Service worker with Service-Worker-Allowed: / for PDF stream caching."""
    from django.http import HttpResponse
    candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'js', 'reader-sw.js'),
        os.path.join(settings.BASE_DIR, 'staticfiles', 'js', 'reader-sw.js'),
    ]
    body = None
    for path in candidates:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as fh:
                body = fh.read()
            break
    if body is None:
        body = '/* reader-sw.js missing */\n'
    resp = HttpResponse(body, content_type='application/javascript; charset=utf-8')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache'
    return resp


def add_to_wishlist(request, book_id):
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_PUBLISHED)
    wishlist_item, created = Wishlist.objects.get_or_create(
        client=request.user,
        book=book
    )
    if created:
        messages.success(request, f'"{book.title}" added to your wishlist.')
    else:
        messages.info(request, f'"{book.title}" is already in your wishlist.')
    return redirect('books:detail', book_id=book_id)


@csrf_exempt
@login_required
def remove_from_wishlist(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    Wishlist.objects.filter(
        client=request.user,
        book=book
    ).delete()
    messages.success(request, f'"{book.title}" removed from your wishlist.')
    return redirect('books:detail', book_id=book_id)


@login_required
def my_wishlist(request):
    wishlist_items = Wishlist.objects.filter(
        client=request.user
    ).select_related('book', 'book__author')
    
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
    """Author uploads a new book - can save as draft or submit directly"""
    if request.user.role != 'author':
        messages.error(request, 'Only authors can upload books.')
        return redirect('home')
    
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        genre_id = request.POST.get('genre')
        language = (request.POST.get('language') or '').strip()
        price_raw = request.POST.get('price', '0')
        is_free = request.POST.get('is_free') in ('on', 'true', '1', 'yes')
        isbn = (request.POST.get('isbn') or '').strip()
        subtitle = (request.POST.get('subtitle') or '').strip()
        edition = (request.POST.get('edition') or '1').strip() or '1'
        page_count = request.POST.get('page_count', 0)
        publication_year = request.POST.get('publication_year', timezone.now().year)
        keywords = (request.POST.get('keywords') or '').strip()
        submit_action = request.POST.get('submit_action', 'draft')

        errors = []
        if not title or len(title) < 2:
            errors.append('Title is required (at least 2 characters).')
        if not description or len(description) < 20:
            errors.append('Description is required (at least 20 characters).')
        if not genre_id:
            errors.append('Please select a genre.')
        if not language:
            errors.append('Please select a language.')

        # Price rules: free => 0; paid => must be positive (> 0)
        try:
            price_val = Decimal(str(price_raw or '0').replace(',', ''))
        except Exception:
            price_val = None
            errors.append('Price must be a valid number.')

        if is_free:
            # Free books only via checkbox — price stored as 0
            price_val = Decimal('0.00')
        elif price_val is not None:
            if price_val <= 0:
                errors.append('Price cannot be zero. Enter a positive price, or mark the book as free.')
            elif price_val < Decimal('0.01'):
                errors.append('Price must be at least 0.01 ETB.')
            else:
                is_free = False

        # Secure upload validation (magic bytes + whitelist) — SAR 6.1 / 6.2
        from books.utils.secure_upload import (
            validate_book_file, validate_cover_image, validate_sample_file,
        )
        upload = request.FILES.get('book_file') or request.FILES.get('file')
        ok, err = validate_book_file(upload)
        if not ok:
            errors.append(err)

        cover = request.FILES.get('cover_image')
        ok, err = validate_cover_image(cover)
        if not ok:
            errors.append(err)

        sample = request.FILES.get('sample_file')
        ok, err = validate_sample_file(sample)
        if not ok:
            errors.append(err)

        try:
            page_count_i = int(page_count) if page_count not in (None, '') else 0
            if page_count_i < 0:
                errors.append('Page count cannot be negative.')
        except (TypeError, ValueError):
            page_count_i = 0
            errors.append('Page count must be a whole number.')

        try:
            year_i = int(publication_year) if publication_year not in (None, '') else timezone.now().year
            if year_i < 1900 or year_i > timezone.now().year + 1:
                errors.append('Publication year looks invalid.')
        except (TypeError, ValueError):
            year_i = timezone.now().year
            errors.append('Publication year must be a number.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return redirect('books:upload')

        try:
            # Determine initial status based on submit action
            if submit_action == 'submit':
                initial_status = Book.STATUS_SUBMITTED
                submitted_at = timezone.now()
                success_message = f'Book "{title}" has been uploaded and submitted for review! A maker will review it shortly.'
            else:
                initial_status = Book.STATUS_DRAFT
                submitted_at = None
                success_message = f'Book "{title}" saved as draft. You can submit it for review later from your dashboard.'

            book = Book.objects.create(
                title=title,
                subtitle=subtitle,
                description=description,
                genre_id=genre_id,
                language=language,
                edition=edition,
                page_count=page_count_i,
                publication_year=year_i,
                price=price_val,
                is_free=is_free,
                isbn=isbn if isbn else None,
                keywords=keywords,
                author=request.user,
                status=initial_status,
                submitted_at=submitted_at,
                revision_attempts=0,
                current_version=0,
                revision_count=0,
            )

            # Save files (PDF only for manuscript)
            book.file = upload
            if cover:
                book.cover_image = cover
            if sample:
                book.sample_file = sample

            book.save()
            
            # Create initial version
            BookVersion.objects.create(
                book=book,
                version_number=1,
                file=book.file,
                cover_image=book.cover_image,
                sample_file=book.sample_file,
                uploaded_by=request.user,
                is_current=True,
                revision_notes='Initial upload',
                file_size=book.file.size if book.file else 0,
                file_hash='',
                changes_summary='Initial upload',
                is_major_revision=True
            )
            
            book.current_version = 1
            book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=request.user,
                action='author_uploaded',
                old_status=Book.STATUS_DRAFT,
                new_status=book.status,
                notes=f'Book "{title}" uploaded by author with action: {submit_action}'
            )
            
            if submit_action == 'submit':
                # If submitted, notify makers
                try:
                    NotificationService.notify_makers_new_submission(book)
                except Exception as e:
                    logger.warning(f"Failed to send notifications: {e}")
                
                messages.success(request, success_message)
                return redirect('books:my_books_author')
            else:
                messages.success(request, success_message)
                return redirect('books:my_books_author')
            
        except Exception as e:
            logger.error(f"Error creating book: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, f'Error creating book: {str(e)}')
            return redirect('books:upload')
    
    genres = Genre.objects.filter(is_active=True)
    return render(request, 'books/upload.html', {'genres': genres})


@login_required
def submit_book(request, book_id):
    """Author submits draft for review"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status != Book.STATUS_DRAFT:
        messages.error(request, 'Only draft books can be submitted.')
        return redirect('books:my_books_author')
    
    if not book.file:
        messages.error(request, 'Please upload a file before submitting.')
        return redirect('books:edit_book', book_id=book_id)
    
    if not book.title or not book.description:
        messages.error(request, 'Please fill in all required fields.')
        return redirect('books:edit_book', book_id=book_id)
    
    try:
        if not book.submitted_at:
            book.submitted_at = timezone.now()
            book.save()
        
        WorkflowService.submit_manuscript(book, request.user)
        
        try:
            NotificationService.notify_makers_new_submission(book)
        except Exception as e:
            logger.warning(f"Failed to send notifications: {e}")
        
        messages.success(request, f'Book "{book.title}" submitted for review! A maker will review it shortly.')
        return redirect('books:my_books_author')
        
    except Exception as e:
        logger.error(f"Error submitting book: {str(e)}")
        logger.error(traceback.format_exc())
        messages.error(request, f'Error submitting book: {str(e)}')
        return redirect('books:my_books_author')


@login_required
def my_books_author(request):
    """Display author's uploaded books with workflow status"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    books = Book.objects.filter(author=request.user).select_related('genre').order_by('-created_at')
    
    total_books = books.count()
    published_books = books.filter(status=Book.STATUS_PUBLISHED).count()
    draft_books = books.filter(status=Book.STATUS_DRAFT).count()
    submitted_books = books.filter(status=Book.STATUS_SUBMITTED).count()
    initial_review = books.filter(status=Book.STATUS_INITIAL_REVIEW).count()
    awaiting_checker = books.filter(status=Book.STATUS_AWAITING_CHECKER).count()
    under_review = books.filter(status=Book.STATUS_UNDER_REVIEW).count()
    review_completed = books.filter(status=Book.STATUS_REVIEW_COMPLETED).count()
    revision_required = books.filter(status=Book.STATUS_REVISION_REQUIRED).count()
    accepted = books.filter(status=Book.STATUS_ACCEPTED).count()
    rejected = books.filter(status=Book.STATUS_REJECTED).count()
    total_downloads = books.aggregate(total=Sum('downloads_count'))['total'] or 0
    
    context = {
        'books': books,
        'total_books': total_books,
        'published_books': published_books,
        'draft_books': draft_books,
        'submitted_books': submitted_books,
        'initial_review': initial_review,
        'awaiting_checker': awaiting_checker,
        'under_review': under_review,
        'review_completed': review_completed,
        'revision_required': revision_required,
        'accepted': accepted,
        'rejected': rejected,
        'total_downloads': total_downloads,
    }
    return render(request, 'books/my_books_author.html', context)


@csrf_exempt
@login_required
def edit_book(request, book_id):
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status in [Book.STATUS_PUBLISHED, Book.STATUS_ACCEPTED, Book.STATUS_PENDING_PUBLICATION]:
        messages.error(request, 'Published or accepted books cannot be edited.')
        return redirect('books:my_books_author')
    
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
        
        # SAR 6.1/6.2 secure validation on edit
        from books.utils.secure_upload import (
            validate_book_file, validate_cover_image, validate_sample_file,
        )
        if request.FILES.get('file'):
            ok, err = validate_book_file(request.FILES.get('file'))
            if not ok:
                messages.error(request, err)
                return redirect(request.path)
        if request.FILES.get('cover_image'):
            ok, err = validate_cover_image(request.FILES.get('cover_image'))
            if not ok:
                messages.error(request, err)
                return redirect(request.path)
        if request.FILES.get('sample_file'):
            ok, err = validate_sample_file(request.FILES.get('sample_file'))
            if not ok:
                messages.error(request, err)
                return redirect(request.path)
        if request.FILES.get('file'):
            if book.status != Book.STATUS_DRAFT:
                current_version = book.versions.filter(is_current=True).first()
                new_version_number = (current_version.version_number + 1) if current_version else 1
                
                BookVersion.objects.create(
                    book=book,
                    version_number=new_version_number,
                    file=request.FILES['file'],
                    cover_image=book.cover_image,
                    sample_file=book.sample_file,
                    uploaded_by=request.user,
                    revision_notes=request.POST.get('revision_notes', ''),
                    parent_version=current_version.version_number if current_version else None,
                    is_current=True,
                    file_size=request.FILES['file'].size,
                    file_hash='',
                    changes_summary=request.POST.get('revision_notes', 'File update'),
                    is_major_revision=True
                )
                
                if current_version:
                    current_version.is_current = False
                    current_version.save()
                
                book.current_version = new_version_number
                book.file = request.FILES['file']
            else:
                book.file = request.FILES['file']
        
        if request.FILES.get('cover_image'):
            book.cover_image = request.FILES['cover_image']
        if request.FILES.get('sample_file'):
            book.sample_file = request.FILES['sample_file']
        
        book.save()
        messages.success(request, 'Book updated successfully.')
        return redirect('books:my_books_author')
    
    genres = Genre.objects.filter(is_active=True)
    return render(request, 'books/edit.html', {'book': book, 'genres': genres})


@csrf_exempt
@login_required
def delete_book(request, book_id):
    if request.user.role != 'author':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status not in [Book.STATUS_DRAFT, Book.STATUS_CANCELLED]:
        messages.error(request, 'Only draft or cancelled books can be deleted.')
        return redirect('books:my_books_author')
    
    if request.method == 'POST':
        book_title = book.title
        book.delete()
        messages.success(request, f'Book "{book_title}" has been deleted.')
        return redirect('books:my_books_author')
    
    return render(request, 'books/confirm_delete.html', {'book': book})


@login_required
def author_revision_submit(request, book_id):
    """Author submits revised book after receiving feedback"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied. Only authors can revise books.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, author=request.user)
    
    if book.status not in [Book.STATUS_REVISION_REQUIRED, Book.STATUS_AUTHOR_REVISION]:
        messages.error(request, 'This book does not need revision at this time.')
        return redirect('books:my_books_author')
    
    if request.method == 'POST':
        revision_notes = request.POST.get('revision_notes', '')
        file = request.FILES.get('file')
        from books.utils.secure_upload import validate_book_file
        if file:
            ok, err = validate_book_file(file)
            if not ok:
                messages.error(request, err)
                return redirect(request.path)
        
        if not file:
            messages.error(request, 'Please upload the revised file.')
            return redirect('books:author_revision_submit', book_id=book_id)
        
        try:
            new_version = WorkflowService.author_submit_revision(book, request.user, file, revision_notes)
            messages.success(request, f'Revision v{new_version.version_number} submitted successfully!')
            return redirect('books:my_books_author')
        except Exception as e:
            logger.error(f"Error submitting revision: {str(e)}")
            messages.error(request, f'Error submitting revision: {str(e)}')
            return redirect('books:author_revision_submit', book_id=book_id)
    
    context = {
        'book': book,
        'user': request.user,
    }
    return render(request, 'books/author_revision_form.html', context)


# =============================================
# AUTHOR DASHBOARD
# =============================================

@login_required
def author_dashboard(request):
    """Author dashboard to manage books"""
    if request.user.role != 'author':
        messages.error(request, 'Access denied. Only authors can access this dashboard.')
        return redirect('home')
    
    try:
        books = Book.objects.filter(author=request.user).select_related('genre').order_by('-created_at')
        
        total_books = books.count()
        published_books = books.filter(status=Book.STATUS_PUBLISHED).count()
        draft_books = books.filter(status=Book.STATUS_DRAFT).count()
        submitted_books = books.filter(status=Book.STATUS_SUBMITTED).count()
        in_review = books.filter(status__in=[Book.STATUS_INITIAL_REVIEW, Book.STATUS_AWAITING_CHECKER, Book.STATUS_UNDER_REVIEW, Book.STATUS_REVIEW_COMPLETED]).count()
        needs_revision = books.filter(status=Book.STATUS_REVISION_REQUIRED).count()
        accepted = books.filter(status=Book.STATUS_ACCEPTED).count()
        rejected = books.filter(status=Book.STATUS_REJECTED).count()
        total_downloads = books.aggregate(total=Sum('downloads_count'))['total'] or 0
        
        needs_revision_books = books.filter(status=Book.STATUS_REVISION_REQUIRED)[:10]
        recent_books = books.exclude(status=Book.STATUS_DRAFT)[:10]
        
        try:
            from payments.models import Payment
            total_earned = Payment.objects.filter(
                author=request.user,
                status='paid'
            ).aggregate(total=Sum('final_amount'))['total'] or 0
            
            pending_earnings = Payment.objects.filter(
                author=request.user,
                status='calculated'
            ).aggregate(total=Sum('final_amount'))['total'] or 0
        except:
            total_earned = 0
            pending_earnings = 0
        
        context = {
            'recent_books': recent_books,
            'needs_revision_books': needs_revision_books,
            'total_books': total_books,
            'published_books': published_books,
            'draft_books': draft_books,
            'submitted_books': submitted_books,
            'in_review': in_review,
            'needs_revision': needs_revision,
            'accepted': accepted,
            'rejected': rejected,
            'total_downloads': total_downloads,
            'total_earned': total_earned,
            'pending_earnings': pending_earnings,
            'user': request.user,
        }
        
        return render(request, 'dashboard/author_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in author_dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        messages.error(request, 'An error occurred loading the dashboard.')
        return redirect('home')


# =============================================
# MAKER DASHBOARD
# =============================================

@login_required
def maker_dashboard(request):
    """Maker dashboard with workflow metrics"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    # Get all books with their workflow status
    submitted_books = Book.objects.filter(status=Book.STATUS_SUBMITTED).count()
    pending_initial = Book.objects.filter(status=Book.STATUS_INITIAL_REVIEW).count()
    awaiting_checker = Book.objects.filter(status=Book.STATUS_AWAITING_CHECKER).count()
    under_review = Book.objects.filter(status=Book.STATUS_UNDER_REVIEW).count()
    review_completed = Book.objects.filter(status=Book.STATUS_REVIEW_COMPLETED).count()
    revision_required = Book.objects.filter(status=Book.STATUS_REVISION_REQUIRED).count()
    resubmitted = Book.objects.filter(status=Book.STATUS_RESUBMITTED).count()
    accepted = Book.objects.filter(status=Book.STATUS_ACCEPTED).count()
    rejected = Book.objects.filter(status=Book.STATUS_REJECTED).count()
    pending_publication = Book.objects.filter(status=Book.STATUS_PENDING_PUBLICATION).count()
    published = Book.objects.filter(status=Book.STATUS_PUBLISHED).count()
    
    # Overdue reviews
    overdue_reviews = ReviewAssignment.objects.filter(
        due_date__lt=timezone.now(),
        status__in=[ReviewAssignment.STATUS_ASSIGNED, ReviewAssignment.STATUS_ACCEPTED]
    ).count()
    
    # NEW SUBMISSIONS - Get all books that have been submitted and need initial review
    new_submissions = Book.objects.filter(
        status__in=[Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW]
    ).select_related('author', 'genre').order_by('-submitted_at', '-created_at')
    
    new_submissions_count = new_submissions.count()
    
    # Log for debugging
    logger.info(f"Maker dashboard: {new_submissions_count} new submissions found")
    for book in new_submissions:
        logger.info(f"  - {book.id}: {book.title} - {book.status} - submitted_at: {book.submitted_at}")
    
    # Pending books for approval (checker approved)
    pending_books = Book.objects.filter(
        status=Book.STATUS_REVIEW_COMPLETED
    ).select_related('author', 'genre').order_by('-checker_reviewed_at', '-updated_at')
    
    pending_count = pending_books.count()
    
    # Books pending checker assignment
    pending_review_books = Book.objects.filter(
        status=Book.STATUS_AWAITING_CHECKER
    ).select_related('author', 'genre').order_by('-submitted_at', '-created_at')
    
    # Books under review
    under_review_books = Book.objects.filter(
        status=Book.STATUS_UNDER_REVIEW
    ).select_related('author', 'genre', 'checker_assigned').order_by('-updated_at')
    
    # Recently published
    published_books = Book.objects.filter(
        status=Book.STATUS_PUBLISHED
    ).select_related('author', 'genre').order_by('-published_at')[:10]
    
    # Books that need revision (sent back by maker)
    maker_revision_books = Book.objects.filter(
        status=Book.STATUS_REVISION_REQUIRED
    ).select_related('author', 'genre').order_by('-updated_at')
    
    # Books with conflicting reviews
    conflicting_reviews = []
    for book in Book.objects.filter(status=Book.STATUS_REVIEW_COMPLETED):
        reviews = book.checker_reviews.filter(is_submitted=True)
        if reviews.count() > 1:
            recommendations = list(reviews.values_list('recommendation', flat=True).distinct())
            if len(recommendations) > 1:
                conflicting_reviews.append(book)
    
    context = {
        'user': request.user,
        'submitted_books': submitted_books,
        'pending_initial': pending_initial,
        'new_submissions': new_submissions,
        'new_submissions_count': new_submissions_count,
        'awaiting_checker': awaiting_checker,
        'pending_review_books': pending_review_books,
        'under_review': under_review,
        'under_review_books': under_review_books,
        'review_completed': review_completed,
        'revision_required': revision_required,
        'resubmitted': resubmitted,
        'accepted': accepted,
        'rejected': rejected,
        'pending_publication': pending_publication,
        'published': published,
        'total_published': published,
        'pending_books': pending_books,
        'pending_count': pending_count,
        'published_books': published_books,
        'maker_revision_books': maker_revision_books,
        'overdue_reviews': overdue_reviews,
        'conflicting_reviews': conflicting_reviews,
        'approved_count': published,
        'published_count': published,
    }
    
    return render(request, 'dashboard/maker_dashboard.html', context)


# =============================================
# MAKER INITIAL REVIEW - UPDATED WITH COMPLETE SUPPORT
# =============================================

@login_required
def maker_initial_review(request, book_id):
    """Maker performs initial review of submission"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    # Allow initial review for multiple statuses
    if book.status not in [Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW]:
        messages.error(request, f'This book is not pending initial review. Current status: {book.get_status_display()}')
        return redirect('books:maker_dashboard')
    
    if request.method == 'POST':
        decision = request.POST.get('decision')
        notes = request.POST.get('notes', '')
        
        if not decision:
            messages.error(request, 'Please select a decision.')
            return redirect('books:maker_initial_review', book_id=book_id)
        
        try:
            # Call the updated workflow service with complete support
            WorkflowService.initial_review(book, request.user, decision, notes)
            messages.success(request, f'Initial review completed. Decision: {decision}')
            return redirect('books:maker_dashboard')
        except Exception as e:
            logger.error(f"Error in initial review: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'book': book,
        'user': request.user,
    }
    return render(request, 'dashboard/maker_initial_review.html', context)


# =============================================
# MAKER ASSIGN CHECKER
# =============================================

@login_required
def maker_assign_checker(request, book_id):
    """Maker assigns a checker to a specific book"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_AWAITING_CHECKER)
    
    if request.method == 'POST':
        checker_id = request.POST.get('checker_id')
        due_date = request.POST.get('due_date')
        instructions = request.POST.get('instructions', '')
        
        if not checker_id:
            messages.error(request, 'Please select a checker.')
            return redirect('books:maker_assign_checker', book_id=book_id)
        
        if not due_date:
            messages.error(request, 'Please set a due date.')
            return redirect('books:maker_assign_checker', book_id=book_id)
        
        try:
            checker = User.objects.get(id=checker_id, role='checker', is_active=True)
            
            current_version = book.versions.filter(is_current=True).first()
            if not current_version:
                messages.error(request, 'No current version found for this book.')
                return redirect('books:maker_assign_checker', book_id=book_id)
            
            assignment = ReviewAssignment.objects.create(
                book=book,
                book_version=current_version,
                checker=checker,
                maker=request.user,
                due_date=due_date,
                instructions=instructions,
                assignment_type='initial',
                assigned_at=timezone.now()
            )
            
            book.checker_assigned = checker
            book.status = Book.STATUS_UNDER_REVIEW
            book.save()
            
            BookActivityLog.objects.create(
                book=book,
                user=request.user,
                action='maker_assigned_checker',
                old_status=Book.STATUS_AWAITING_CHECKER,
                new_status=Book.STATUS_UNDER_REVIEW,
                notes=f"Assigned to {checker.get_full_name() or checker.username}"
            )
            
            try:
                NotificationService.notify_checker_assigned(assignment)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            messages.success(request, f'Book assigned to {checker.get_full_name() or checker.username} for review.')
            return redirect('books:maker_dashboard')
            
        except User.DoesNotExist:
            messages.error(request, 'Selected checker not found.')
        except Exception as e:
            logger.error(f"Error assigning checker: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    checkers = User.objects.filter(
        role='checker',
        is_active=True
    ).annotate(
        active_assignments=Count('checker_assignments', filter=Q(
            checker_assignments__status__in=[
                ReviewAssignment.STATUS_ASSIGNED,
                ReviewAssignment.STATUS_ACCEPTED,
                ReviewAssignment.STATUS_IN_PROGRESS
            ]
        ))
    ).order_by('active_assignments')
    
    context = {
        'book': book,
        'checkers': checkers,
        'user': request.user,
    }
    return render(request, 'dashboard/maker_assign_checker.html', context)


# =============================================
# MAKER REVIEW DECISION
# =============================================

@login_required
def maker_review_decision(request, book_id):
    """Maker makes final decision based on checker reviews"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_REVIEW_COMPLETED)
    
    reviews = CheckerReview.objects.filter(
        book=book,
        is_submitted=True
    ).select_related('checker')
    
    if request.method == 'POST':
        decision = request.POST.get('decision')
        comment = request.POST.get('comment', '')
        
        if not decision:
            messages.error(request, 'Please select a decision.')
            return redirect('books:maker_review_decision', book_id=book_id)
        
        try:
            WorkflowService.maker_make_decision(book, request.user, decision, comment)
            messages.success(request, f'Decision: {decision}')
            
            if decision == 'accept':
                return redirect('books:maker_pending_publication')
            else:
                return redirect('books:maker_dashboard')
                
        except Exception as e:
            logger.error(f"Error making decision: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    recommendations = reviews.values_list('recommendation', flat=True)
    has_conflict = len(set(recommendations)) > 1
    
    context = {
        'book': book,
        'reviews': reviews,
        'has_conflict': has_conflict,
        'user': request.user,
    }
    return render(request, 'books/maker_review_decision.html', context)


# =============================================
# MAKER PENDING PUBLICATION
# =============================================

@login_required
def maker_pending_publication(request):
    """Maker views books pending publication"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    pending_books = Book.objects.filter(
        status=Book.STATUS_PENDING_PUBLICATION
    ).select_related('author', 'genre').order_by('-updated_at')
    
    context = {
        'pending_books': pending_books,
        'pending_count': pending_books.count(),
        'user': request.user,
    }
    return render(request, 'books/maker_pending_publication.html', context)


# =============================================
# MAKER PUBLISH BOOK
# =============================================

@login_required
def maker_publish_book(request, book_id):
    """Maker publishes a book"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    if book.status not in [Book.STATUS_ACCEPTED, Book.STATUS_PENDING_PUBLICATION, Book.STATUS_REVIEW_COMPLETED]:
        messages.error(request, 'This book cannot be published at this stage.')
        return redirect('books:maker_dashboard')
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        
        try:
            WorkflowService.publish_manuscript(book, request.user, {'notes': notes})
            messages.success(request, f'Book "{book.title}" published successfully!')
            return redirect('books:maker_dashboard')
        except Exception as e:
            logger.error(f"Error publishing book: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'book': book,
        'user': request.user,
    }
    return render(request, 'dashboard/maker_publish_book.html', context)


# =============================================
# MAKER REJECT BOOK
# =============================================

@login_required
def maker_reject_book(request, book_id):
    """Maker rejects a book or sends back for revision"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    if book.status not in [Book.STATUS_REVIEW_COMPLETED, Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW, Book.STATUS_UNDER_REVIEW]:
        messages.error(request, 'This book cannot be rejected at this stage.')
        return redirect('books:maker_dashboard')
    
    if request.method == 'POST':
        decision = request.POST.get('decision')
        notes = request.POST.get('notes', '')
        
        if not decision:
            messages.error(request, 'Please select a decision.')
            return redirect('books:maker_reject_book', book_id=book_id)
        
        try:
            if decision == 'reject':
                WorkflowService.maker_make_decision(book, request.user, 'reject', notes)
                messages.success(request, f'Book "{book.title}" has been rejected.')
            elif decision == 'needs_revision':
                WorkflowService.maker_make_decision(book, request.user, 'needs_revision', notes)
                messages.success(request, f'Book "{book.title}" sent for revision.')
            return redirect('books:maker_dashboard')
        except Exception as e:
            logger.error(f"Error in reject/revision: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'book': book,
        'user': request.user,
    }
    return render(request, 'dashboard/maker_reject_book.html', context)


# =============================================
# PENDING APPROVAL
# =============================================

@login_required
def pending_approval(request):
    """View for maker to see books pending approval"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    books = Book.objects.filter(
        status=Book.STATUS_REVIEW_COMPLETED
    ).select_related('author', 'genre').order_by('checker_reviewed_at')
    
    context = {
        'books': books,
        'pending_count': books.count(),
        'user': request.user,
    }
    return render(request, 'books/pending_approval.html', context)


@login_required
def publish_book_maker(request, book_id):
    """Maker publishes a book that has been approved by checker"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id, status=Book.STATUS_REVIEW_COMPLETED)
    
    if request.method == 'POST':
        try:
            WorkflowService.publish_manuscript(
                book,
                request.user,
                {
                    'publication_date': timezone.now().date(),
                    'notes': request.POST.get('notes', '')
                }
            )
            messages.success(request, f'Book "{book.title}" has been published successfully!')
            return redirect('books:pending_approval')
        except Exception as e:
            logger.error(f"Error publishing book: {str(e)}")
            messages.error(request, f'Error publishing book: {str(e)}')
    
    context = {
        'book': book,
        'user': request.user,
    }
    return render(request, 'books/confirm_publish.html', context)


@login_required
def my_publications(request):
    """View for maker to see their publications"""
    if request.user.role not in ['maker', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    books = Book.objects.filter(
        status=Book.STATUS_PUBLISHED
    ).select_related('author', 'genre').order_by('-published_at')
    
    context = {
        'books': books,
        'total_publications': books.count(),
        'user': request.user,
    }
    return render(request, 'books/my_publications.html', context)


# =============================================
# CHECKER DASHBOARD
# =============================================

@login_required
def checker_dashboard(request):
    """Checker dashboard with assignments"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')

    pending_books = Book.objects.filter(
        checker_assigned=request.user,
        status=Book.STATUS_UNDER_REVIEW
    ).select_related('author', 'genre').order_by('updated_at')
    
    reviewed_books = CheckerReview.objects.filter(
        checker=request.user,
        is_submitted=True
    ).select_related('book', 'book__author').order_by('-submitted_at')[:20]
    
    total_reviewed = CheckerReview.objects.filter(
        checker=request.user,
        is_submitted=True
    ).count()
    
    avg_score = CheckerReview.objects.filter(
        checker=request.user,
        is_submitted=True
    ).aggregate(avg=Avg('overall_score'))['avg'] or 0
    
    reviewed_this_month = CheckerReview.objects.filter(
        checker=request.user,
        is_submitted=True,
        submitted_at__month=timezone.now().month,
        submitted_at__year=timezone.now().year
    ).count()
    
    re_review_books = Book.objects.filter(
        checker_assigned=request.user,
        status=Book.STATUS_REVISION_REQUIRED
    ).select_related('author', 'genre').order_by('-updated_at')
    
    assignments = ReviewAssignment.objects.filter(
        checker=request.user
    ).select_related('book', 'book__author', 'book_version').order_by('-assigned_at')
    
    pending_assignments = assignments.filter(status=ReviewAssignment.STATUS_ASSIGNED)
    active_assignments = assignments.filter(
        status__in=[ReviewAssignment.STATUS_ACCEPTED, ReviewAssignment.STATUS_IN_PROGRESS]
    )
    completed_assignments = assignments.filter(status=ReviewAssignment.STATUS_COMPLETED)[:10]
    overdue_assignments = assignments.filter(
        due_date__lt=timezone.now(),
        status__in=[ReviewAssignment.STATUS_ASSIGNED, ReviewAssignment.STATUS_ACCEPTED]
    )
    overdue_count = overdue_assignments.count()

    context = {
        'user': request.user,
        'pending_books': pending_books,
        'reviewed_books': reviewed_books,
        'pending_assignments': pending_assignments,
        'active_assignments': active_assignments,
        'completed_assignments': completed_assignments,
        'overdue_assignments': overdue_assignments,
        'overdue_count': overdue_count,
        'total_pending': pending_assignments.count(),
        'total_active': active_assignments.count(),
        'total_reviewed': total_reviewed,
        'avg_score': avg_score,
        'reviewed_this_month': reviewed_this_month,
        're_review_books': re_review_books,
    }
    
    return render(request, 'dashboard/checker_dashboard.html', context)


@login_required
def checker_accept_assignment(request, assignment_id):
    """Checker accepts assignment"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    assignment = get_object_or_404(
        ReviewAssignment,
        id=assignment_id,
        checker=request.user,
        status=ReviewAssignment.STATUS_ASSIGNED
    )
    
    try:
        WorkflowService.checker_accept_assignment(assignment, request.user)
        messages.success(request, 'Assignment accepted')
    except Exception as e:
        logger.error(f"Error accepting assignment: {str(e)}")
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('books:checker_dashboard')


@login_required
def checker_decline_assignment(request, assignment_id):
    """Checker declines assignment"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    assignment = get_object_or_404(
        ReviewAssignment,
        id=assignment_id,
        checker=request.user,
        status=ReviewAssignment.STATUS_ASSIGNED
    )
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, 'Please provide a reason.')
            return redirect('books:checker_decline_assignment', assignment_id=assignment_id)
        
        try:
            assignment.decline(request.user, reason)
            messages.success(request, 'Assignment declined')
            return redirect('books:checker_dashboard')
        except Exception as e:
            logger.error(f"Error declining assignment: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'assignment': assignment,
        'user': request.user,
    }
    return render(request, 'books/checker_decline_assignment.html', context)


@login_required
def checker_conflict_assignment(request, assignment_id):
    """Checker declares conflict of interest"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    assignment = get_object_or_404(
        ReviewAssignment,
        id=assignment_id,
        checker=request.user,
        status=ReviewAssignment.STATUS_ASSIGNED
    )
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, 'Please provide a reason for the conflict.')
            return redirect('books:checker_conflict_assignment', assignment_id=assignment_id)
        
        try:
            assignment.declare_conflict(request.user, reason)
            messages.success(request, 'Conflict declared. Maker will be notified.')
            return redirect('books:checker_dashboard')
        except Exception as e:
            logger.error(f"Error declaring conflict: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'assignment': assignment,
        'user': request.user,
    }
    return render(request, 'books/checker_conflict_assignment.html', context)


@login_required
def checker_submit_review(request, assignment_id):
    """Checker submits review"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    assignment = get_object_or_404(
        ReviewAssignment,
        id=assignment_id,
        checker=request.user,
        status=ReviewAssignment.STATUS_ACCEPTED
    )
    
    existing_review = CheckerReview.objects.filter(assignment=assignment).first()
    if existing_review and existing_review.is_submitted:
        messages.error(request, 'Review already submitted.')
        return redirect('books:checker_dashboard')
    
    if request.method == 'POST':
        recommendation = request.POST.get('recommendation')
        overall_comment = request.POST.get('overall_comment')
        
        if not recommendation or not overall_comment:
            messages.error(request, 'Recommendation and overall comment are required.')
            return redirect('books:checker_submit_review', assignment_id=assignment_id)
        
        review_data = {
            'recommendation': recommendation,
            'overall_comment': overall_comment,
            'content_quality': request.POST.get('content_quality'),
            'originality': request.POST.get('originality'),
            'completeness': request.POST.get('completeness'),
            'structure': request.POST.get('structure'),
            'language_quality': request.POST.get('language_quality'),
            'technical_quality': request.POST.get('technical_quality'),
            'overall_score': request.POST.get('overall_score'),
            'author_visible_comments': request.POST.get('author_visible_comments'),
            'internal_comments': request.POST.get('internal_comments'),
            'required_corrections': request.POST.get('required_corrections'),
            'annotated_file': request.FILES.get('annotated_file') if request.FILES else None,
        }
        
        try:
            review = WorkflowService.checker_submit_review(
                assignment,
                request.user,
                review_data
            )
            messages.success(request, 'Review submitted successfully!')
            return redirect('books:checker_dashboard')
        except Exception as e:
            logger.error(f"Error submitting review: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'assignment': assignment,
        'book': assignment.book,
        'user': request.user,
        'scores': [
            ('content_quality', 'Content Quality'),
            ('originality', 'Originality'),
            ('completeness', 'Completeness'),
            ('structure', 'Structure & Flow'),
            ('language_quality', 'Language Quality'),
            ('technical_quality', 'Technical Quality'),
        ],
    }
    return render(request, 'books/checker_submit_review.html', context)


@login_required
def view_book_for_review(request, book_id):
    """View a book for review (Checker)"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    if book.checker_assigned == request.user and book.status == Book.STATUS_UNDER_REVIEW:
        context = {
            'book': book,
            'user': request.user,
        }
        return render(request, 'books/view_book_for_review.html', context)
    
    assignment = ReviewAssignment.objects.filter(
        book=book,
        checker=request.user,
        status__in=[ReviewAssignment.STATUS_ASSIGNED, ReviewAssignment.STATUS_ACCEPTED]
    ).first()
    
    if not assignment:
        messages.error(request, 'You are not assigned to review this book.')
        return redirect('books:checker_dashboard')
    
    context = {
        'book': book,
        'assignment': assignment,
        'user': request.user,
    }
    return render(request, 'books/view_book_for_review.html', context)


# =============================================
# ADMIN DASHBOARD
# =============================================

@login_required
def admin_dashboard(request):
    """Admin dashboard to manage the platform"""
    if request.user.role != 'admin' and not request.user.is_superuser:
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('home')
    
    try:
        total_users = User.objects.filter(is_active=True).count()
        total_authors = User.objects.filter(role='author', is_active=True).count()
        total_checkers = User.objects.filter(role='checker', is_active=True).count()
        total_makers = User.objects.filter(role='maker', is_active=True).count()
        total_clients = User.objects.filter(role='client', is_active=True).count()
        
        total_books = Book.objects.count()
        published_books = Book.objects.filter(status=Book.STATUS_PUBLISHED).count()
        pending_books = Book.objects.filter(status__in=[Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW, Book.STATUS_AWAITING_CHECKER]).count()
        in_review = Book.objects.filter(status__in=[Book.STATUS_UNDER_REVIEW]).count()
        total_downloads = Book.objects.aggregate(total=Sum('downloads_count'))['total'] or 0
        
        today = timezone.now().date()
        week_start = today - timedelta(days=7)
        month_start = today.replace(day=1)
        
        try:
            from payments.models import Purchase, Payment
            completed_purchases = Purchase.objects.filter(status='completed')
            
            def sum_amount(qs):
                result = qs.aggregate(total=Sum('amount'))['total']
                return result if result is not None else 0
            
            total_sales = sum_amount(completed_purchases)
            today_sales = sum_amount(completed_purchases.filter(created_at__date=today))
            week_sales = sum_amount(completed_purchases.filter(created_at__date__gte=week_start, created_at__date__lte=today))
            month_sales = sum_amount(completed_purchases.filter(created_at__date__gte=month_start, created_at__date__lte=today))
            
            telebirr_sales = sum_amount(completed_purchases.filter(payment_method__icontains='telebirr'))
            cbe_sales = sum_amount(completed_purchases.filter(Q(payment_method__icontains='cbe') | Q(payment_method__icontains='cbe_birr')))
            
            total_royalties = Payment.objects.aggregate(total=Sum('final_amount'))['total'] or 0
            pending_payouts = Payment.objects.filter(status__in=['calculated', 'pending']).aggregate(total=Sum('final_amount'))['total'] or 0
            completed_payouts = Payment.objects.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
        except:
            total_sales = 0
            today_sales = 0
            week_sales = 0
            month_sales = 0
            telebirr_sales = 0
            cbe_sales = 0
            total_royalties = 0
            pending_payouts = 0
            completed_payouts = 0
        
        recent_submissions = Book.objects.filter(
            status__in=[Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW]
        ).order_by('-submitted_at')[:10]
        
        context = {
            'total_users': total_users,
            'total_authors': total_authors,
            'total_checkers': total_checkers,
            'total_makers': total_makers,
            'total_clients': total_clients,
            'total_books': total_books,
            'published_books': published_books,
            'pending_books': pending_books,
            'in_review': in_review,
            'total_downloads': total_downloads,
            'total_sales': total_sales,
            'today_sales': today_sales,
            'week_sales': week_sales,
            'month_sales': month_sales,
            'telebirr_sales': telebirr_sales,
            'cbe_sales': cbe_sales,
            'total_royalties': total_royalties,
            'pending_payouts': pending_payouts,
            'completed_payouts': completed_payouts,
            'recent_submissions': recent_submissions,
            'user': request.user,
        }
        
        return render(request, 'dashboard/admin_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {str(e)}")
        messages.error(request, 'An error occurred loading the dashboard.')
        return redirect('home')


# =============================================
# PUBLIC FUNCTIONS
# =============================================

def published_books(request):
    books = Book.objects.filter(status=Book.STATUS_PUBLISHED).select_related('author', 'genre').order_by('-published_at')
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'books/published_books.html', {'books': page_obj})


def genre_books(request, genre_slug):
    try:
        genre = get_object_or_404(Genre, slug=genre_slug, is_active=True)
    except Genre.DoesNotExist:
        messages.error(request, 'Genre not found.')
        return redirect('books:browse')
    books = Book.objects.filter(genre=genre, status=Book.STATUS_PUBLISHED).select_related('author').order_by('-created_at')
    context = {'genre': genre, 'books': books, 'total_books': books.count()}
    return render(request, 'books/genre_books.html', context)


def author_books(request, author_id):
    try:
        author = get_object_or_404(User, id=author_id, role='author')
    except User.DoesNotExist:
        messages.error(request, 'Author not found.')
        return redirect('books:browse')
    books = Book.objects.filter(author=author, status=Book.STATUS_PUBLISHED).select_related('genre').order_by('-created_at')
    context = {
        'author': author,
        'books': books,
        'total_books': books.count(),
        'total_downloads': books.aggregate(total=Sum('downloads_count'))['total'] or 0,
    }
    return render(request, 'books/author_books.html', context)


# =============================================
# PROCESS CHECKER REVIEW (Legacy Support)
# =============================================

@login_required
def process_checker_review(request):
    """Process checker's review of a book (Legacy support)"""
    if request.user.role != 'checker':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('books:checker_dashboard')
    
    book_id = request.POST.get('book_id')
    if not book_id:
        messages.error(request, 'Book ID is required.')
        return redirect('books:checker_dashboard')
    
    book = get_object_or_404(Book, id=book_id)
    
    if request.user != book.checker_assigned:
        messages.error(request, 'You are not authorized to review this book.')
        return redirect('books:checker_dashboard')
    
    try:
        content_quality = float(request.POST.get('content_quality', 0))
        editorial_quality = float(request.POST.get('editorial_quality', 0))
        technical_quality = float(request.POST.get('technical_quality', 0))
        copyright_compliance = float(request.POST.get('copyright_compliance', 0))
        community_guidelines = float(request.POST.get('community_guidelines', 0))
    except ValueError:
        messages.error(request, 'Invalid score values. Please use numbers between 0 and 10.')
        return redirect('books:checker_dashboard')
    
    for score in [content_quality, editorial_quality, technical_quality, copyright_compliance, community_guidelines]:
        if score < 0 or score > 10:
            messages.error(request, 'All scores must be between 0 and 10.')
            return redirect('books:checker_dashboard')
    
    overall_score = (content_quality + editorial_quality + technical_quality) / 3
    
    recommendation = request.POST.get('recommendation')
    if recommendation not in ['approved', 'needs_revision', 'rejected']:
        messages.error(request, 'Invalid recommendation.')
        return redirect('books:checker_dashboard')
    
    comments = request.POST.get('comments', '').strip()
    if not comments:
        messages.warning(request, 'Please provide comments for the author.')
    
    try:
        with transaction.atomic():
            assignment = ReviewAssignment.objects.filter(
                book=book,
                checker=request.user,
                status=ReviewAssignment.STATUS_ACCEPTED
            ).first()
            
            if not assignment:
                assignment = ReviewAssignment.objects.filter(
                    book=book,
                    checker=request.user
                ).first()
            
            workflow_recommendation = {
                'approved': 'accept',
                'needs_revision': 'major_revision',
                'rejected': 'reject'
            }.get(recommendation, 'major_revision')
            
            if assignment:
                review = CheckerReview.objects.create(
                    assignment=assignment,
                    book=book,
                    book_version=assignment.book_version if assignment else book.versions.filter(is_current=True).first(),
                    checker=request.user,
                    recommendation=workflow_recommendation,
                    overall_comment=comments,
                    content_quality=int(content_quality / 2) if content_quality else None,
                    originality=int(content_quality / 2) if content_quality else None,
                    completeness=int(editorial_quality / 2) if editorial_quality else None,
                    structure=int(editorial_quality / 2) if editorial_quality else None,
                    language_quality=int(technical_quality / 2) if technical_quality else None,
                    technical_quality=int(technical_quality / 2) if technical_quality else None,
                    overall_score=int(overall_score / 2) if overall_score else None,
                    author_visible_comments=comments,
                    internal_comments=comments,
                    required_corrections=comments,
                )
            else:
                review = CheckerReview.objects.create(
                    book=book,
                    book_version=book.versions.filter(is_current=True).first(),
                    checker=request.user,
                    recommendation=workflow_recommendation,
                    overall_comment=comments,
                    content_quality=int(content_quality / 2) if content_quality else None,
                    originality=int(content_quality / 2) if content_quality else None,
                    completeness=int(editorial_quality / 2) if editorial_quality else None,
                    structure=int(editorial_quality / 2) if editorial_quality else None,
                    language_quality=int(technical_quality / 2) if technical_quality else None,
                    technical_quality=int(technical_quality / 2) if technical_quality else None,
                    overall_score=int(overall_score / 2) if overall_score else None,
                    author_visible_comments=comments,
                    internal_comments=comments,
                    required_corrections=comments,
                    is_submitted=True,
                    submitted_at=timezone.now(),
                )
            
            if assignment and not review.is_submitted:
                review.submit()
            
            if recommendation == 'approved':
                book.status = Book.STATUS_REVIEW_COMPLETED
            elif recommendation == 'needs_revision':
                book.status = Book.STATUS_REVISION_REQUIRED
                book.revision_notes = comments
            else:
                book.status = Book.STATUS_REJECTED
            
            book.checker_score = overall_score
            book.checker_reviewed_at = timezone.now()
            book.save()
            
            BookActivityLog.objects.create(
                book=book,
                user=request.user,
                action='checker_submitted_review',
                old_status=Book.STATUS_UNDER_REVIEW,
                new_status=book.status,
                notes=f'Score: {overall_score:.1f}/10'
            )
            
            messages.success(request, f'Review for "{book.title}" submitted successfully!')
        
    except Exception as e:
        logger.error(f"Error processing review: {str(e)}")
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('books:checker_dashboard')


# =============================================
# ERROR HANDLERS
# =============================================

def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)


def error_403(request, exception):
    return render(request, '403.html', status=403)