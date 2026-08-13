# books/services/notification_service.py
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class NotificationService:
    """Service to handle notifications"""
    
    @staticmethod
    def notify_makers_new_submission(book):
        """Notify all makers about a new submission"""
        from ..models import BookNotification
        
        makers = User.objects.filter(role='maker', is_active=True)
        
        for maker in makers:
            try:
                BookNotification.objects.create(
                    book=book,
                    user=maker,
                    notification_type='new_submission',
                    title=f'New Book Submission: {book.title}',
                    message=f'{book.author.get_full_name()} has submitted "{book.title}" for review.',
                    link=f'/books/maker/initial-review/{book.id}/',
                    is_read=False
                )
            except Exception as e:
                logger.error(f"Failed to create notification for maker {maker.username}: {e}")
        
        logger.info(f"Notifications sent to {makers.count()} makers about new submission {book.id}")
    
    @staticmethod
    def notify_checker_assigned(assignment):
        """Notify checker about assignment"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=assignment.book,
                user=assignment.checker,
                notification_type='checker_assigned',
                title=f'New Review Assignment: {assignment.book.title}',
                message=f'You have been assigned to review "{assignment.book.title}". Due date: {assignment.due_date}',
                link=f'/books/checker/view/{assignment.id}/',
                is_read=False
            )
            logger.info(f"Notification sent to checker {assignment.checker.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for checker: {e}")
    
    @staticmethod
    def notify_maker_review_completed(book):
        """Notify makers that a review is completed"""
        from ..models import BookNotification
        
        makers = User.objects.filter(role='maker', is_active=True)
        
        for maker in makers:
            try:
                BookNotification.objects.create(
                    book=book,
                    user=maker,
                    notification_type='review_completed',
                    title=f'Review Completed: {book.title}',
                    message=f'Checker review for "{book.title}" is complete. Please make a decision.',
                    link=f'/books/maker/decision/{book.id}/',
                    is_read=False
                )
            except Exception as e:
                logger.error(f"Failed to create notification for maker {maker.username}: {e}")
    
    @staticmethod
    def notify_author_book_accepted(book):
        """Notify author that book was accepted"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='book_accepted',
                title=f'Book Accepted: {book.title}',
                message=f'Congratulations! Your book "{book.title}" has been accepted for publication.',
                link=f'/books/detail/{book.id}/',
                is_read=False
            )
            logger.info(f"Accepted notification sent to author {book.author.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for author: {e}")
    
    @staticmethod
    def notify_author_book_rejected(book, reason):
        """Notify author that book was rejected"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='book_rejected',
                title=f'Book Rejected: {book.title}',
                message=f'Your book "{book.title}" has been rejected. Reason: {reason}',
                link=f'/books/detail/{book.id}/',
                is_read=False
            )
            logger.info(f"Rejected notification sent to author {book.author.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for author: {e}")
    
    @staticmethod
    def notify_author_revision_needed(book, notes):
        """Notify author that revision is needed"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='revision_needed',
                title=f'Revision Needed: {book.title}',
                message=f'Your book "{book.title}" needs revision. Notes: {notes}',
                link=f'/books/author/revision/{book.id}/',
                is_read=False
            )
            logger.info(f"Revision notification sent to author {book.author.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for author: {e}")
    
    @staticmethod
    def notify_author_book_published(book):
        """Notify author that book was published"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='book_published',
                title=f'Book Published: {book.title}',
                message=f'Great news! Your book "{book.title}" has been published and is now available in the repository.',
                link=f'/books/detail/{book.id}/',
                is_read=False
            )
            logger.info(f"Published notification sent to author {book.author.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for author: {e}")
    
    @staticmethod
    def notify_author_book_accepted_initial(book):
        """Notify author that book passed initial review"""
        from ..models import BookNotification
        
        try:
            BookNotification.objects.create(
                book=book,
                user=book.author,
                notification_type='book_accepted_initial',
                title=f'Book Passed Initial Review: {book.title}',
                message=f'Your book "{book.title}" has passed initial review and has been sent to a quality checker.',
                link=f'/books/detail/{book.id}/',
                is_read=False
            )
            logger.info(f"Initial acceptance notification sent to author {book.author.username}")
        except Exception as e:
            logger.error(f"Failed to create notification for author: {e}")
    
    @staticmethod
    def notify_maker_revision_submitted(book):
        """Notify makers that author submitted revision"""
        from ..models import BookNotification
        
        makers = User.objects.filter(role='maker', is_active=True)
        
        for maker in makers:
            try:
                BookNotification.objects.create(
                    book=book,
                    user=maker,
                    notification_type='revision_submitted',
                    title=f'Revision Submitted: {book.title}',
                    message=f'{book.author.get_full_name()} has submitted a revision for "{book.title}".',
                    link=f'/books/maker/decision/{book.id}/',
                    is_read=False
                )
            except Exception as e:
                logger.error(f"Failed to create notification for maker {maker.username}: {e}")