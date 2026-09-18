# books/services/notification_service.py
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def _author_name(user):
    try:
        return user.get_full_name() or user.username
    except Exception:
        return getattr(user, "username", "Author")


class NotificationService:
    """In-app BookNotification + real email notifications."""

    @staticmethod
    def _in_app(book, user, notification_type, title, message, link):
        from ..models import BookNotification
        try:
            BookNotification.objects.create(
                book=book,
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link,
                is_read=False,
            )
        except Exception as e:
            logger.error("In-app notification failed: %s", e)

    @staticmethod
    def _email(user, subject, message, book=None, event_type=None):
        try:
            from books.services.email_service import email_user
            ok = email_user(
                user,
                subject,
                message,
                book=book,
                event_type=event_type,
                fail_silently=True,
            )
            if not ok:
                logger.warning("Email not sent to %s (%s)", getattr(user, "username", user), subject)
            return ok
        except Exception as e:
            logger.exception("Email send error: %s", e)
            return False

    @staticmethod
    def notify_makers_new_submission(book):
        makers = User.objects.filter(role="maker", is_active=True)
        title = f"New Book Submission: {book.title}"
        message = f'{_author_name(book.author)} has submitted "{book.title}" for review.'
        link = f"/books/maker/initial-review/{book.id}/"
        for maker in makers:
            NotificationService._in_app(book, maker, "new_submission", title, message, link)
            NotificationService._email(
                maker,
                f"[Abay] {title}",
                message + f"\n\nOpen: {link}",
                book=book,
                event_type="submission_confirmation",
            )
        logger.info("Notified %s makers about submission %s", makers.count(), book.id)

    @staticmethod
    def notify_checker_assigned(assignment):
        book = assignment.book
        title = f"New Review Assignment: {book.title}"
        due = getattr(assignment, "due_date", None)
        message = f'You have been assigned to review "{book.title}".' + (
            f" Due date: {due}." if due else ""
        )
        link = f"/books/checker/view/{assignment.id}/"
        NotificationService._in_app(book, assignment.checker, "checker_assigned", title, message, link)
        NotificationService._email(
            assignment.checker,
            f"[Abay] {title}",
            message + f"\n\nOpen: {link}",
            book=book,
            event_type="review_assignment",
        )

    @staticmethod
    def notify_maker_review_completed(book):
        makers = User.objects.filter(role="maker", is_active=True)
        title = f"Review Completed: {book.title}"
        message = f'Review has been completed for "{book.title}".'
        link = f"/books/maker/decision/{book.id}/"
        for maker in makers:
            NotificationService._in_app(book, maker, "review_completed", title, message, link)
            NotificationService._email(
                maker,
                f"[Abay] {title}",
                message + f"\n\nOpen: {link}",
                book=book,
                event_type="review_completed",
            )

    @staticmethod
    def notify_author_book_accepted(book):
        title = f"Book Accepted: {book.title}"
        message = f'Congratulations! Your book "{book.title}" has been accepted.'
        link = f"/books/my-books/"
        NotificationService._in_app(book, book.author, "book_accepted", title, message, link)
        NotificationService._email(
            book.author,
            f"[Abay] {title}",
            message,
            book=book,
            event_type="decision_made",
        )

    @staticmethod
    def notify_author_book_rejected(book, reason):
        title = f"Book Not Accepted: {book.title}"
        message = f'Your book "{book.title}" was not accepted.' + (
            f"\nReason: {reason}" if reason else ""
        )
        link = f"/books/my-books/"
        NotificationService._in_app(book, book.author, "book_rejected", title, message, link)
        NotificationService._email(
            book.author,
            f"[Abay] {title}",
            message,
            book=book,
            event_type="decision_made",
        )

    @staticmethod
    def notify_author_revision_needed(book, notes):
        title = f"Revision Requested: {book.title}"
        message = f'Revisions are needed for "{book.title}".' + (
            f"\nNotes: {notes}" if notes else ""
        )
        link = f"/books/my-books/"
        NotificationService._in_app(book, book.author, "revision_needed", title, message, link)
        NotificationService._email(
            book.author,
            f"[Abay] {title}",
            message,
            book=book,
            event_type="revision_requested",
        )

    @staticmethod
    def notify_author_book_published(book):
        title = f"Book Published: {book.title}"
        message = f'Your book "{book.title}" is now published and available to readers.'
        link = f"/books/detail/{book.id}/"
        NotificationService._in_app(book, book.author, "book_published", title, message, link)
        NotificationService._email(
            book.author,
            f"[Abay] {title}",
            message,
            book=book,
            event_type="publication_notification",
        )

    @staticmethod
    def notify_author_book_accepted_initial(book):
        title = f"Initial Review Passed: {book.title}"
        message = f'Your book "{book.title}" passed the initial review and is moving to the next stage.'
        link = f"/books/my-books/"
        NotificationService._in_app(book, book.author, "book_accepted_initial", title, message, link)
        NotificationService._email(
            book.author,
            f"[Abay] {title}",
            message,
            book=book,
            event_type="decision_made",
        )

    @staticmethod
    def notify_maker_revision_submitted(book):
        makers = User.objects.filter(role="maker", is_active=True)
        title = f"Revision Submitted: {book.title}"
        message = f'{_author_name(book.author)} submitted a revision for "{book.title}".'
        link = f"/books/maker/decision/{book.id}/"
        for maker in makers:
            NotificationService._in_app(book, maker, "revision_submitted", title, message, link)
            NotificationService._email(
                maker,
                f"[Abay] {title}",
                message + f"\n\nOpen: {link}",
                book=book,
                event_type="submission_confirmation",
            )
