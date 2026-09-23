# accounts/views.py — BRUTE-FORCE PROTECTION FIX
# Drop-in replacement for the login attempt helpers + login_view rate-limit logic.
# Uses IP + username keys and a shared cache (Redis or FileBasedCache).

from django.core.cache import cache
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
import logging

logger = logging.getLogger(__name__)

LOGIN_MAX_ATTEMPTS = int(getattr(settings, "LOGIN_MAX_ATTEMPTS", 5))
LOGIN_LOCKOUT_SECONDS = int(getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _attempt_key(ip: str, username: str = "") -> str:
    # Track both IP-wide and per-username to stop distributed + targeted attacks
    uname = (username or "").strip().lower()[:150]
    return f"login_attempts:{ip}:{uname}"


def _block_key(ip: str) -> str:
    return f"login_blocked:{ip}"


def is_ip_blocked(ip: str) -> bool:
    return bool(cache.get(_block_key(ip)))


def get_login_attempts(ip: str, username: str = "") -> int:
    return int(cache.get(_attempt_key(ip, username), 0))


def increment_login_attempts(ip: str, username: str = "") -> int:
    key = _attempt_key(ip, username)
    attempts = int(cache.get(key, 0)) + 1
    cache.set(key, attempts, LOGIN_LOCKOUT_SECONDS)

    # Also increment pure-IP counter for broader protection
    ip_key = _attempt_key(ip, "")
    ip_attempts = int(cache.get(ip_key, 0)) + 1
    cache.set(ip_key, ip_attempts, LOGIN_LOCKOUT_SECONDS)

    if attempts >= LOGIN_MAX_ATTEMPTS or ip_attempts >= LOGIN_MAX_ATTEMPTS * 3:
        cache.set(_block_key(ip), True, LOGIN_LOCKOUT_SECONDS)
        logger.warning(
            "IP %s blocked after %s failed attempts (user=%s)",
            ip, attempts, username,
        )
    return attempts


def reset_login_attempts(ip: str, username: str = "") -> None:
    cache.delete(_attempt_key(ip, username))
    cache.delete(_attempt_key(ip, ""))
    cache.delete(_block_key(ip))


# ---------------------------------------------------------------------------
# Inside login_view — use this logic in the POST branch:
# ---------------------------------------------------------------------------
#
# client_ip = get_client_ip(request)
#
# if is_ip_blocked(client_ip):
#     messages.error(request, "Too many failed login attempts. Please try again later.")
#     return render(request, "accounts/login.html", {"form": LoginForm()})
#
# if request.method == "POST":
#     form = LoginForm(request.POST)
#     if form.is_valid():
#         username = form.cleaned_data.get("username", "").strip()
#         password = form.cleaned_data.get("password")
#
#         attempts = get_login_attempts(client_ip, username)
#         if attempts >= LOGIN_MAX_ATTEMPTS:
#             messages.error(
#                 request,
#                 f"Too many failed attempts. Account temporarily locked. "
#                 f"Try again in {LOGIN_LOCKOUT_SECONDS // 60} minutes.",
#             )
#             return render(request, "accounts/login.html", {"form": form})
#
#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             reset_login_attempts(client_ip, username)
#             login(request, user)
#             # ... existing success / 2FA redirect logic ...
#         else:
#             n = increment_login_attempts(client_ip, username)
#             remaining = max(0, LOGIN_MAX_ATTEMPTS - n)
#             if remaining > 0:
#                 messages.error(
#                     request,
#                     f"Invalid username or password. {remaining} attempt(s) remaining.",
#                 )
#             else:
#                 messages.error(
#                     request,
#                     "Too many failed attempts. Please try again later.",
#                 )
#     ...
# ---------------------------------------------------------------------------
