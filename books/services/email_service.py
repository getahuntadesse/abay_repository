"""
Central email helper for Abay Repository.
Works with SMTP (production) or console backend (DEBUG).
Handles SSL certificate errors common on Windows development machines.
"""
from __future__ import annotations

import logging
import ssl
from typing import Optional, Sequence, Union

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail

logger = logging.getLogger(__name__)


def get_from_email() -> str:
    """Prefer DEFAULT_FROM_EMAIL; fall back to SMTP user (required for Gmail)."""
    default = (getattr(settings, "DEFAULT_FROM_EMAIL", None) or "").strip()
    host_user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
    if default and "@" in default:
        if host_user and "gmail.com" in (getattr(settings, "EMAIL_HOST", "") or "").lower():
            if default.lower() != host_user.lower() and "gmail.com" not in default.lower():
                return host_user
        return default
    if host_user:
        return host_user
    return "noreply@abay.local"


def is_email_configured() -> bool:
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if "console" in backend or "locmem" in backend or "dummy" in backend:
        return True
    host = (getattr(settings, "EMAIL_HOST", None) or "").strip()
    user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
    password = (getattr(settings, "EMAIL_HOST_PASSWORD", None) or "").strip()
    return bool(host and user and password)


def _smtp_connection(fail_silently=False):
    """
    Build SMTP connection. On SSLError (common in local/Windows), fall back
    to console backend so development keeps working.
    """
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if "console" in backend or "locmem" in backend or "dummy" in backend:
        return get_connection(fail_silently=fail_silently)

    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True))
    use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
    # Never enable both (Django raises / SSL breaks)
    if use_ssl and use_tls:
        use_tls = False

    try:
        return get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=getattr(settings, "EMAIL_HOST", "smtp.gmail.com"),
            port=int(getattr(settings, "EMAIL_PORT", 587) or 587),
            username=getattr(settings, "EMAIL_HOST_USER", "") or None,
            password=getattr(settings, "EMAIL_HOST_PASSWORD", "") or None,
            use_tls=use_tls,
            use_ssl=use_ssl,
            fail_silently=fail_silently,
            timeout=20,
        )
    except Exception as e:
        logger.warning("SMTP connection setup failed: %s", e)
        if getattr(settings, "DEBUG", False):
            return get_connection(
                backend="django.core.mail.backends.console.EmailBackend",
                fail_silently=True,
            )
        raise


def send_app_email(
    subject: str,
    message: str,
    recipient_list: Union[str, Sequence[str]],
    *,
    html_message: Optional[str] = None,
    fail_silently: bool = False,
    book=None,
    event_type: Optional[str] = None,
) -> bool:
    """Send plain (and optional HTML) email. Returns True on success."""
    if isinstance(recipient_list, str):
        recipients = [recipient_list]
    else:
        recipients = [r for r in recipient_list if r]

    recipients = [r.strip() for r in recipients if r and str(r).strip() and "@" in str(r)]
    if not recipients:
        logger.warning("send_app_email: no valid recipients for subject=%s", subject)
        return False

    from_email = get_from_email()
    subject = (subject or "").strip() or "Abay Repository"
    message = message or ""

    success = False
    error_message = ""

    def _send(connection):
        if html_message:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipients,
                connection=connection,
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
        else:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipients,
                fail_silently=False,
                connection=connection,
            )

    try:
        conn = _smtp_connection(fail_silently=False)
        _send(conn)
        success = True
        logger.info("Email sent to %s | subject=%s", recipients, subject)
    except (ssl.SSLError, OSError) as e:
        error_message = str(e)
        logger.warning("Email SSL/network error: %s", e)
        # Development fallback: print to console so reset still "works" for testing
        if getattr(settings, "DEBUG", False):
            try:
                console = get_connection(
                    backend="django.core.mail.backends.console.EmailBackend",
                    fail_silently=True,
                )
                _send(console)
                success = True
                logger.info(
                    "Email printed to console (SSL failed in development). "
                    "Fix EMAIL_* / certs for real SMTP."
                )
            except Exception as e2:
                logger.exception("Console fallback also failed: %s", e2)
                success = False
        elif not fail_silently:
            success = False
    except Exception as e:
        error_message = str(e)
        logger.exception("Email failed to %s | subject=%s | error=%s", recipients, subject, e)
        if getattr(settings, "DEBUG", False):
            try:
                console = get_connection(
                    backend="django.core.mail.backends.console.EmailBackend",
                    fail_silently=True,
                )
                _send(console)
                success = True
                logger.info("Email printed to console after SMTP error in DEBUG.")
            except Exception:
                success = False
        else:
            success = False

    if book is not None and event_type:
        try:
            from books.models import BookEmailEvent
            for r in recipients:
                BookEmailEvent.objects.create(
                    book=book,
                    recipient=r,
                    event_type=event_type if event_type in dict(BookEmailEvent.EVENT_TYPES) else "decision_made",
                    subject=subject[:255],
                    body=message,
                    is_successful=success,
                    error_message=(error_message or "")[:2000],
                )
        except Exception as e:
            logger.warning("BookEmailEvent log failed: %s", e)

    return success


def email_user(user, subject: str, message: str, **kwargs) -> bool:
    email = getattr(user, "email", None)
    if not email:
        logger.warning("User %s has no email address", getattr(user, "username", user))
        return False
    name = (
        getattr(user, "get_full_name", lambda: "")()
        or getattr(user, "full_name", None)
        or getattr(user, "username", "")
    )
    body = f"Hello {name},\n\n{message}\n\nBest regards,\nAbay Repository Team\n"
    html = kwargs.pop("html_message", None)
    if not html:
        html = (
            f"<p>Hello {name},</p><p>{message.replace(chr(10), '<br>')}</p>"
            f"<p>Best regards,<br>Abay Repository Team</p>"
        )
    return send_app_email(subject, body, email, html_message=html, **kwargs)
