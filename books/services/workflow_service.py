# books/services/workflow_service.py
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class WorkflowService:
    """Service to handle book workflow operations"""
    
    @staticmethod
    def submit_manuscript(book, user):
        """
        Submit a manuscript for review.
        Changes status from DRAFT to SUBMITTED.
        """
        from ..models import BookActivityLog, Book
        
        if book.status != Book.STATUS_DRAFT:
            raise ValueError("Only draft books can be submitted")
        
        # Validate required fields
        if not book.title or not book.description:
            raise ValueError("Title and description are required")
        
        if not book.file:
            raise ValueError("Book file is required")
        
        with transaction.atomic():
            # Set submitted_at if not already set
            if not book.submitted_at:
                book.submitted_at = timezone.now()
            
            # Update status
            old_status = book.status
            book.status = Book.STATUS_SUBMITTED
            book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=user,
                action='author_submitted',
                old_status=old_status,
                new_status=Book.STATUS_SUBMITTED,
                notes=f'Book "{book.title}" submitted for review by {user.get_full_name()}'
            )
            
            logger.info(f"Book {book.id} ({book.title}) submitted by {user.username}")
            
            # Create notification for makers
            try:
                from .notification_service import NotificationService
                NotificationService.notify_makers_new_submission(book)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return book
    
    @staticmethod
    def initial_review(book, maker, decision, notes):
        """
        Maker performs initial review of submitted book.
        """
        from ..models import BookActivityLog, Book
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can perform initial review")
        
        if book.status not in [Book.STATUS_SUBMITTED, Book.STATUS_INITIAL_REVIEW]:
            raise ValueError(f"Book must be in SUBMITTED or INITIAL_REVIEW status. Current: {book.status}")
        
        with transaction.atomic():
            old_status = book.status
            
            if decision == 'accept':
                # Move to awaiting checker
                book.status = Book.STATUS_AWAITING_CHECKER
                book.maker_notes = notes
                message = f"Initial review passed. Moving to checker assignment."
            elif decision == 'reject':
                # Reject the book
                book.status = Book.STATUS_REJECTED
                book.maker_notes = notes
                message = f"Initial review rejected. Reason: {notes}"
            elif decision == 'needs_revision':
                # Send back for revision
                book.status = Book.STATUS_REVISION_REQUIRED
                book.revision_notes = notes
                book.maker_notes = notes
                message = f"Initial review: revision needed. Notes: {notes}"
            else:
                raise ValueError(f"Invalid decision: {decision}")
            
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
            
            # Notify author
            try:
                from .notification_service import NotificationService
                if decision == 'accept':
                    NotificationService.notify_author_book_accepted_initial(book)
                elif decision == 'reject':
                    NotificationService.notify_author_book_rejected(book, notes)
                else:
                    NotificationService.notify_author_revision_needed(book, notes)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return book
    
    @staticmethod
    def assign_checker(book, maker, checker, due_date, instructions=None):
        """
        Assign a checker to a book.
        """
        from ..models import ReviewAssignment, BookActivityLog, Book
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can assign checkers")
        
        if checker.role != 'checker':
            raise ValueError("User must be a checker")
        
        if book.status != Book.STATUS_AWAITING_CHECKER:
            raise ValueError(f"Book must be AWAITING_CHECKER. Current: {book.status}")
        
        # Get current version
        current_version = book.versions.filter(is_current=True).first()
        if not current_version:
            raise ValueError("No current version found for this book")
        
        with transaction.atomic():
            old_status = book.status
            
            # Create assignment
            assignment = ReviewAssignment.objects.create(
                book=book,
                book_version=current_version,
                checker=checker,
                maker=maker,
                due_date=due_date,
                instructions=instructions or '',
                assignment_type='initial'
            )
            
            # Update book
            book.checker_assigned = checker
            book.status = Book.STATUS_UNDER_REVIEW
            book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=maker,
                action='maker_assigned_checker',
                old_status=old_status,
                new_status=Book.STATUS_UNDER_REVIEW,
                notes=f"Assigned to {checker.get_full_name() or checker.username}"
            )
            
            logger.info(f"Checker {checker.username} assigned to book {book.id}")
            
            # Notify checker
            try:
                from .notification_service import NotificationService
                NotificationService.notify_checker_assigned(assignment)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return assignment
    
    @staticmethod
    def checker_accept_assignment(assignment, checker):
        """
        Checker accepts a review assignment.
        """
        from ..models import BookActivityLog, Book
        
        if assignment.checker != checker:
            raise ValueError("Assignment does not belong to this checker")
        
        if assignment.status != assignment.STATUS_ASSIGNED:
            raise ValueError(f"Assignment must be ASSIGNED. Current: {assignment.status}")
        
        with transaction.atomic():
            assignment.accept(checker)
            
            # Log activity
            BookActivityLog.objects.create(
                book=assignment.book,
                user=checker,
                action='checker_accepted',
                notes=f"Checker {checker.get_full_name()} accepted assignment"
            )
            
            logger.info(f"Checker {checker.username} accepted assignment {assignment.id}")
            
            return assignment
    
    @staticmethod
    def checker_submit_review(assignment, checker, review_data):
        """
        Checker submits a review for a book.
        """
        from ..models import CheckerReview, BookActivityLog
        
        if assignment.checker != checker:
            raise ValueError("Assignment does not belong to this checker")
        
        if assignment.status not in [assignment.STATUS_ACCEPTED, assignment.STATUS_IN_PROGRESS]:
            raise ValueError(f"Assignment must be ACCEPTED or IN_PROGRESS. Current: {assignment.status}")
        
        # Validate required fields
        required = ['recommendation', 'overall_comment']
        for field in required:
            if not review_data.get(field):
                raise ValueError(f"{field} is required")
        
        with transaction.atomic():
            # Create review
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
            
            # Submit the review
            review.submit()
            
            # Update assignment
            assignment.status = assignment.STATUS_COMPLETED
            assignment.completed_at = timezone.now()
            assignment.save()
            
            # Update book based on recommendation
            old_status = assignment.book.status
            recommendation = review_data.get('recommendation')
            
            if recommendation == 'accept':
                assignment.book.status = Book.STATUS_REVIEW_COMPLETED
            elif recommendation == 'major_revision' or recommendation == 'minor_revision':
                assignment.book.status = Book.STATUS_REVISION_REQUIRED
                assignment.book.revision_notes = review.required_corrections or review.overall_comment
            elif recommendation == 'reject':
                assignment.book.status = Book.STATUS_REJECTED
            else:
                # Default to revision required
                assignment.book.status = Book.STATUS_REVISION_REQUIRED
                assignment.book.revision_notes = review.overall_comment
            
            assignment.book.checker_score = review.overall_score
            assignment.book.checker_reviewed_at = timezone.now()
            assignment.book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=assignment.book,
                user=checker,
                action='checker_submitted_review',
                old_status=old_status,
                new_status=assignment.book.status,
                notes=f"Review submitted. Score: {review.overall_score}/10. Recommendation: {recommendation}"
            )
            
            logger.info(f"Review submitted for book {assignment.book.id} by checker {checker.username}")
            
            # Notify maker
            try:
                from .notification_service import NotificationService
                NotificationService.notify_maker_review_completed(assignment.book)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return review
    
    @staticmethod
    def maker_make_decision(book, maker, decision, comment):
        """
        Maker makes final decision based on checker reviews.
        """
        from ..models import EditorialDecision, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can make final decisions")
        
        if book.status != Book.STATUS_REVIEW_COMPLETED:
            raise ValueError(f"Book must be REVIEW_COMPLETED. Current: {book.status}")
        
        with transaction.atomic():
            old_status = book.status
            
            # Create editorial decision
            editorial = EditorialDecision.objects.create(
                book=book,
                maker=maker,
                decision=decision,
                comment=comment
            )
            
            # Update book status
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
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=maker,
                action='maker_final_decision',
                old_status=old_status,
                new_status=book.status,
                notes=f"Decision: {decision}. Comment: {comment}"
            )
            
            logger.info(f"Final decision for book {book.id}: {decision}")
            
            # Notify author
            try:
                from .notification_service import NotificationService
                if decision == 'accept':
                    NotificationService.notify_author_book_accepted(book)
                elif decision == 'reject':
                    NotificationService.notify_author_book_rejected(book, comment)
                else:
                    NotificationService.notify_author_revision_needed(book, comment)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return editorial
    
    @staticmethod
    def publish_manuscript(book, maker, data):
        """
        Publish a manuscript.
        """
        from ..models import PublicationRecord, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can publish books")
        
        if book.status not in [Book.STATUS_ACCEPTED, Book.STATUS_PENDING_PUBLICATION]:
            raise ValueError(f"Book must be ACCEPTED or PENDING_PUBLICATION. Current: {book.status}")
        
        with transaction.atomic():
            old_status = book.status
            
            # Update book
            book.status = Book.STATUS_PUBLISHED
            book.published_at = timezone.now()
            if data.get('publication_date'):
                book.publication_date = data.get('publication_date')
            book.save()
            
            # Create publication record
            publication = PublicationRecord.objects.create(
                book=book,
                published_by=maker,
                publication_date=timezone.now(),
                version=book.current_version or 1,
                notes=data.get('notes', '')
            )
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=maker,
                action='maker_published',
                old_status=old_status,
                new_status=Book.STATUS_PUBLISHED,
                notes=f"Book published by {maker.get_full_name() or maker.username}"
            )
            
            logger.info(f"Book {book.id} published by {maker.username}")
            
            # Notify author
            try:
                from .notification_service import NotificationService
                NotificationService.notify_author_book_published(book)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return publication
    
    @staticmethod
    def author_submit_revision(book, author, file, revision_notes):
        """
        Author submits a revision.
        """
        from ..models import BookVersion, BookActivityLog
        
        if author != book.author:
            raise ValueError("Only the book author can submit revisions")
        
        if book.status != Book.STATUS_REVISION_REQUIRED:
            raise ValueError(f"Book must be REVISION_REQUIRED. Current: {book.status}")
        
        with transaction.atomic():
            # Create new version
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
                is_current=True
            )
            
            # Update old version
            if current_version:
                current_version.is_current = False
                current_version.save()
            
            # Update book
            book.file = file
            book.current_version = new_version_number
            book.revision_count = (book.revision_count or 0) + 1
            book.status = Book.STATUS_RESUBMITTED
            book.revision_notes = revision_notes
            book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=author,
                action='author_submitted_revision',
                old_status=Book.STATUS_REVISION_REQUIRED,
                new_status=Book.STATUS_RESUBMITTED,
                notes=f"Revision v{new_version_number} submitted"
            )
            
            logger.info(f"Revision v{new_version_number} submitted for book {book.id}")
            
            # Notify maker
            try:
                from .notification_service import NotificationService
                NotificationService.notify_maker_revision_submitted(book)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return new_version
    
    @staticmethod
    def maker_request_revision(book, maker, revision_data):
        """
        Maker requests revision from author.
        """
        from ..models import RevisionRequest, BookActivityLog
        
        if maker.role not in ['maker', 'admin']:
            raise ValueError("Only makers can request revisions")
        
        with transaction.atomic():
            # Create revision request
            revision_request = RevisionRequest.objects.create(
                book=book,
                requested_by=maker,
                required_changes=revision_data.get('required_changes', ''),
                reviewer_comments=revision_data.get('reviewer_comments', ''),
                maker_instructions=revision_data.get('maker_instructions', ''),
                revision_deadline=revision_data.get('revision_deadline'),
                re_review_required=revision_data.get('re_review_required', False)
            )
            
            # Update book
            old_status = book.status
            book.status = Book.STATUS_REVISION_REQUIRED
            book.revision_notes = revision_data.get('required_changes', '')
            book.save()
            
            # Log activity
            BookActivityLog.objects.create(
                book=book,
                user=maker,
                action='maker_requested_revision',
                old_status=old_status,
                new_status=Book.STATUS_REVISION_REQUIRED,
                notes=f"Revision requested. Changes: {revision_data.get('required_changes', '')[:100]}"
            )
            
            logger.info(f"Revision requested for book {book.id} by {maker.username}")
            
            # Notify author
            try:
                from .notification_service import NotificationService
                NotificationService.notify_author_revision_needed(book, revision_data.get('required_changes', ''))
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
            
            return revision_request


class WorkflowValidator:
    """Validate workflow states and transitions"""
    
    @staticmethod
    def validate_transition(book, new_status):
        """Validate if a status transition is allowed"""
        valid_transitions = {
            Book.STATUS_DRAFT: [Book.STATUS_SUBMITTED, Book.STATUS_CANCELLED],
            Book.STATUS_SUBMITTED: [Book.STATUS_INITIAL_REVIEW, Book.STATUS_REJECTED],
            Book.STATUS_INITIAL_REVIEW: [Book.STATUS_AWAITING_CHECKER, Book.STATUS_REJECTED, Book.STATUS_REVISION_REQUIRED],
            Book.STATUS_AWAITING_CHECKER: [Book.STATUS_UNDER_REVIEW],
            Book.STATUS_UNDER_REVIEW: [Book.STATUS_REVIEW_COMPLETED, Book.STATUS_REVISION_REQUIRED],
            Book.STATUS_REVIEW_COMPLETED: [Book.STATUS_ACCEPTED, Book.STATUS_REJECTED, Book.STATUS_REVISION_REQUIRED],
            Book.STATUS_REVISION_REQUIRED: [Book.STATUS_RESUBMITTED, Book.STATUS_REJECTED],
            Book.STATUS_RESUBMITTED: [Book.STATUS_UNDER_REVIEW, Book.STATUS_REJECTED],
            Book.STATUS_ACCEPTED: [Book.STATUS_PENDING_PUBLICATION, Book.STATUS_PUBLISHED],
            Book.STATUS_PENDING_PUBLICATION: [Book.STATUS_PUBLISHED],
        }
        
        allowed = valid_transitions.get(book.status, [])
        if new_status not in allowed:
            return False, f"Invalid transition from {book.get_status_display()} to {new_status}"
        
        return True, "Valid transition"