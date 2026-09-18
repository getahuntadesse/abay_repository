"""
Email-based Two-Factor Authentication for Abay Repository.

Production-safe OTP storage:
  - Primary: Django session (shared via DB/file sessions across Gunicorn workers)
  - Fallback: cache (use DatabaseCache or Redis in production — NOT LocMemCache)

LocMemCache is per-process; with multiple workers the code was stored on one
worker and verified on another → "invalid or expired".
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import string
import time
from typing import List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
# 15 minutes — email can be delayed in production
OTP_TTL_SECONDS = int(getattr(settings, "OTP_EMAIL_TOKEN_VALIDITY", 900) or 900)
BACKUP_CODE_COUNT = 8
SESSION_USER_KEY = "pre_2fa_user_id"
SESSION_REMEMBER_KEY = "pre_2fa_remember"
SESSION_OTP_HASH = "abay_2fa_otp_hash"
SESSION_OTP_EXP = "abay_2fa_otp_exp"


def _otp_cache_key(user_id: int) -> str:
    return f"abay_2fa_otp:{user_id}"


def _hash_code(code: str) -> str:
    # Normalize: strip spaces/dashes, keep digits for OTP comparison
    normalized = "".join(c for c in (code or "").strip() if c.isdigit())
    if not normalized:
        normalized = (code or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_otp_input(code: str) -> str:
    """User may paste '123 456' or '123-456'."""
    return "".join(c for c in (code or "").strip() if c.isdigit())


def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> List[str]:
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def store_otp(user_id: int, otp: str, request=None) -> None:
    """
    Store OTP hash in session (preferred) and cache (backup).
    Always pass request in login/2FA flow so session is used.
    """
    digest = _hash_code(otp)
    exp = time.time() + OTP_TTL_SECONDS

    if request is not None:
        request.session[SESSION_OTP_HASH] = digest
        request.session[SESSION_OTP_EXP] = exp
        request.session.modified = True
        try:
            request.session.save()
        except Exception as e:
            logger.warning("Session save for OTP failed: %s", e)

    try:
        cache.set(_otp_cache_key(user_id), {"hash": digest, "exp": exp}, timeout=OTP_TTL_SECONDS)
    except Exception as e:
        logger.warning("Cache store OTP failed: %s", e)

    logger.info("2FA OTP stored user_id=%s ttl=%ss session=%s", user_id, OTP_TTL_SECONDS, bool(request))


def verify_otp(user_id: int, otp: str, request=None) -> bool:
    """Verify OTP from session first, then cache. One-time use."""
    candidate = _hash_code(normalize_otp_input(otp) or otp)
    now = time.time()

    # 1) Session (works across workers when SESSION_ENGINE is DB/cached_db)
    if request is not None:
        stored = request.session.get(SESSION_OTP_HASH)
        exp = request.session.get(SESSION_OTP_EXP) or 0
        if stored and exp and now <= float(exp):
            if secrets.compare_digest(str(stored), candidate):
                request.session.pop(SESSION_OTP_HASH, None)
                request.session.pop(SESSION_OTP_EXP, None)
                request.session.modified = True
                try:
                    cache.delete(_otp_cache_key(user_id))
                except Exception:
                    pass
                logger.info("2FA OTP verified via session user_id=%s", user_id)
                return True
        elif stored and exp and now > float(exp):
            logger.info("2FA OTP session expired user_id=%s", user_id)
            request.session.pop(SESSION_OTP_HASH, None)
            request.session.pop(SESSION_OTP_EXP, None)

    # 2) Cache fallback
    try:
        data = cache.get(_otp_cache_key(user_id))
    except Exception:
        data = None

    if isinstance(data, dict):
        stored = data.get("hash")
        exp = float(data.get("exp") or 0)
        if stored and now <= exp and secrets.compare_digest(str(stored), candidate):
            try:
                cache.delete(_otp_cache_key(user_id))
            except Exception:
                pass
            if request is not None:
                request.session.pop(SESSION_OTP_HASH, None)
                request.session.pop(SESSION_OTP_EXP, None)
            logger.info("2FA OTP verified via cache user_id=%s", user_id)
            return True
    elif isinstance(data, str):
        # legacy: plain hash in cache
        if secrets.compare_digest(data, candidate):
            try:
                cache.delete(_otp_cache_key(user_id))
            except Exception:
                pass
            logger.info("2FA OTP verified via legacy cache user_id=%s", user_id)
            return True

    logger.warning("2FA OTP mismatch or missing user_id=%s", user_id)
    return False


def send_otp_email(user, otp: str) -> Tuple[bool, str]:
    """Send 6-digit OTP to user.email. Returns (ok, message)."""
    if not user.email:
        return False, "No email address on your account. Add one in Profile before enabling 2FA."

    subject = getattr(settings, "OTP_EMAIL_SUBJECT", "Your Abay Repository Verification Code")
    minutes = max(1, OTP_TTL_SECONDS // 60)
    name = getattr(user, "full_name", None) or user.username
    body = (
        f"Hello {name}," + chr(10) + chr(10)
        + "Your Abay Repository verification code is:" + chr(10) + chr(10)
        + f"    {otp}" + chr(10) + chr(10)
        + f"This code expires in {minutes} minute(s)." + chr(10)
        + "If you did not try to sign in, ignore this email and secure your account."
        + chr(10) + chr(10)
        + "— Abay Repository Security"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;line-height:1.5;color:#222;">
  <div style="max-width:480px;margin:0 auto;padding:24px;border:1px solid #eee;border-radius:12px;">
    <h2 style="color:#B8860B;margin-top:0;">Abay Repository</h2>
    <p>Hello {name},</p>
    <p>Your verification code is:</p>
    <p style="font-size:28px;letter-spacing:6px;font-weight:bold;text-align:center;
              background:#f8f5eb;padding:16px;border-radius:8px;">{otp}</p>
    <p style="font-size:13px;color:#666;">Expires in {minutes} minute(s). Do not share this code.</p>
    <p style="font-size:13px;color:#666;">If you did not try to sign in, ignore this email.</p>
    <p>— Abay Repository Security</p>
  </div>
</body></html>"""
    try:
        try:
            from books.services.email_service import send_app_email
            ok = send_app_email(subject, body, user.email, html_message=html, fail_silently=False)
        except Exception:
            from django.core.mail import send_mail
            send_mail(
                subject,
                body,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                [user.email],
                fail_silently=False,
            )
            ok = True
        if ok:
            logger.info("2FA OTP emailed to user_id=%s email=%s", user.id, user.email)
            return True, f"A verification code was sent to {user.email}."
        return False, "Could not send the verification email. Check email settings or try again."
    except Exception as e:
        logger.exception("Failed to send 2FA OTP: %s", e)
        return False, f"Could not send email: {e}"


def start_2fa_challenge(request, user, remember: bool = False) -> Tuple[bool, str]:
    """After password OK, start 2FA (do not fully log in yet)."""
    otp = generate_otp()
    store_otp(user.id, otp, request=request)
    ok, msg = send_otp_email(user, otp)
    if not ok:
        return False, msg
    request.session[SESSION_USER_KEY] = user.id
    request.session[SESSION_REMEMBER_KEY] = bool(remember)
    request.session.modified = True
    try:
        request.session.save()
    except Exception:
        pass
    return True, msg


def consume_backup_code(user, code: str) -> bool:
    codes = user.get_backup_codes_list()
    normalized = (code or "").strip().upper().replace(" ", "")
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
    user.set_backup_codes([])
    user.save(
        update_fields=[
            "two_factor_enabled",
            "two_factor_verified",
            "two_factor_secret",
            "two_factor_backup_codes",
        ]
    )
