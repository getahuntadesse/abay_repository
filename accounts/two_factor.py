"""
Email-based Two-Factor Authentication helpers for Abay Repository.
Uses CustomUser.two_factor_* fields + session-stored OTP hashes.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import string
from typing import List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_SECONDS = getattr(settings, "OTP_EMAIL_TOKEN_VALIDITY", 300)
BACKUP_CODE_COUNT = 8
SESSION_USER_KEY = "pre_2fa_user_id"
SESSION_REMEMBER_KEY = "pre_2fa_remember"


def _otp_cache_key(user_id: int) -> str:
    return f"abay_2fa_otp:{user_id}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> List[str]:
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()  # 8 hex chars
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def store_otp(user_id: int, otp: str) -> None:
    cache.set(_otp_cache_key(user_id), _hash_code(otp), timeout=OTP_TTL_SECONDS)


def verify_otp(user_id: int, otp: str) -> bool:
    stored = cache.get(_otp_cache_key(user_id))
    if not stored:
        return False
    if secrets.compare_digest(stored, _hash_code(otp)):
        cache.delete(_otp_cache_key(user_id))
        return True
    return False


def send_otp_email(user, otp: str) -> Tuple[bool, str]:
    """Send 6-digit OTP to user.email. Returns (ok, message)."""
    if not user.email:
        return False, "No email address on your account. Add one in Profile before enabling 2FA."

    subject = getattr(settings, "OTP_EMAIL_SUBJECT", "Your Abay Repository Verification Code")
    from_email = getattr(
        settings,
        "OTP_EMAIL_SENDER",
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@abay.abrehot.org.et"),
    )
    minutes = max(1, OTP_TTL_SECONDS // 60)
    body = (
        f"Hello {user.full_name or user.username},\n\n"
        f"Your verification code is: {otp}\n\n"
        f"This code expires in {minutes} minute(s).\n"
        f"If you did not request this, ignore this email.\n\n"
        f"— Abay Repository"
    )
    try:
        send_mail(subject, body, from_email, [user.email], fail_silently=False)
        logger.info("2FA OTP sent to user_id=%s email=%s", user.id, user.email)
        return True, f"A verification code was sent to {user.email}."
    except Exception as e:
        logger.exception("Failed to send 2FA OTP: %s", e)
        return False, f"Could not send email: {e}"


def start_2fa_challenge(request, user, remember: bool = False) -> Tuple[bool, str]:
    """After password OK, start 2FA challenge (do not fully log in yet)."""
    otp = generate_otp()
    store_otp(user.id, otp)
    ok, msg = send_otp_email(user, otp)
    if not ok:
        return False, msg
    request.session[SESSION_USER_KEY] = user.id
    request.session[SESSION_REMEMBER_KEY] = bool(remember)
    request.session.modified = True
    return True, msg


def consume_backup_code(user, code: str) -> bool:
    codes = user.get_backup_codes_list()
    normalized = code.strip().upper().replace(" ", "")
    matched = None
    for c in codes:
        if c.replace(" ", "").upper() == normalized:
            matched = c
            break
    if not matched:
        return False
    codes = [c for c in codes if c != matched]
    user.set_backup_codes(codes)
    return True


def enable_2fa_for_user(user) -> List[str]:
    codes = generate_backup_codes()
    user.two_factor_enabled = True
    user.two_factor_verified = True
    user.two_factor_secret = secrets.token_hex(16)
    user.set_backup_codes(codes)
    user.save(
        update_fields=[
            "two_factor_enabled",
            "two_factor_verified",
            "two_factor_secret",
            "two_factor_backup_codes",
        ]
    )
    return codes


def disable_2fa_for_user(user) -> None:
    user.two_factor_enabled = False
    user.two_factor_verified = False
    user.two_factor_secret = ""
    user.two_factor_backup_codes = ""
    user.save(
        update_fields=[
            "two_factor_enabled",
            "two_factor_verified",
            "two_factor_secret",
            "two_factor_backup_codes",
        ]
    )
