"""
Secure file upload validation — blocks Stored XSS via SVG and other dangerous types.

Already present in the repo; ensure this (or equivalent) is used on every
cover / book / sample upload path and that ALLOWED_UPLOAD_EXTENSIONS in
settings does NOT include .svg.
"""
from __future__ import annotations

import imghdr
import logging
import os
import re
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BOOK_EXTENSIONS = {".pdf", ".epub"}
BOOK_MAGIC = {
    ".pdf": (b"%PDF",),
    ".epub": (b"PK\x03\x04",),
}

COVER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
COVER_MAGIC = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}

# Explicit blocklist — never allow these even if someone adds them to whitelist
BLOCKED_EXTENSIONS = {
    ".svg", ".svgz", ".html", ".htm", ".xhtml", ".xml", ".xsl", ".xslt",
    ".php", ".phtml", ".php3", ".php4", ".php5", ".php7", ".phar",
    ".asp", ".aspx", ".jsp", ".jspx", ".js", ".mjs", ".ts",
    ".exe", ".dll", ".so", ".bat", ".cmd", ".com", ".msi",
    ".sh", ".bash", ".ps1", ".vbs", ".wsf", ".cgi",
    ".pl", ".py", ".rb", ".jar", ".war", ".class",
    ".htaccess", ".htpasswd", ".shtml", ".cfg", ".ini",
    ".wasm", ".swf", ".xap",
}

MALICIOUS_CONTENT = (
    b"<?php", b"<?=", b"<script", b"javascript:", b"vbscript:",
    b"eval(", b"base64_decode", b"system(", b"exec(", b"shell_exec",
    b"passthru(", b"popen(", b"<iframe", b"onload=", b"onerror=",
)


def extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def _read_head(uploaded_file, n: int = 32) -> bytes:
    pos = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        data = uploaded_file.read(n)
    finally:
        try:
            uploaded_file.seek(pos)
        except Exception:
            pass
    return data or b""


def _contains_malware_signature(uploaded_file) -> bool:
    head = _read_head(uploaded_file, 8192).lower()
    return any(sig in head for sig in MALICIOUS_CONTENT)


def sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename or "file")
    name = re.sub(r"[^\w.\-]", "_", name)
    if len(name) > 180:
        root, ext = os.path.splitext(name)
        name = root[:170] + ext
    return name or f"upload_{uuid.uuid4().hex[:8]}"


def validate_book_file(uploaded_file) -> Tuple[bool, str]:
    if not uploaded_file:
        return True, ""
    name = getattr(uploaded_file, "name", "") or ""
    ext = extension(name)
    if ext in BLOCKED_EXTENSIONS:
        return False, f"File type {ext} is not allowed."
    if ext not in BOOK_EXTENSIONS:
        return False, f"Only {', '.join(sorted(BOOK_EXTENSIONS))} files are allowed."
    head = _read_head(uploaded_file, 8)
    magic_ok = any(head.startswith(m) for m in BOOK_MAGIC.get(ext, ()))
    if not magic_ok:
        return False, "File content does not match its extension (signature check failed)."
    if _contains_malware_signature(uploaded_file):
        return False, "File contains blocked content."
    return True, ""


def validate_cover_image(uploaded_file) -> Tuple[bool, str]:
    if not uploaded_file:
        return True, ""
    name = getattr(uploaded_file, "name", "") or ""
    ext = extension(name)
    if ext in BLOCKED_EXTENSIONS or ext == ".svg" or ext == ".svgz":
        return False, "SVG and other scriptable image types are not allowed for covers."
    if ext not in COVER_EXTENSIONS:
        return False, f"Only {', '.join(sorted(COVER_EXTENSIONS))} covers are allowed."
    head = _read_head(uploaded_file, 8)
    magic_ok = any(head.startswith(m) for m in COVER_MAGIC.get(ext, ()))
    if not magic_ok:
        return False, "Cover file content is not a valid image (signature check failed)."
    try:
        uploaded_file.seek(0)
        kind = imghdr.what(uploaded_file)
        uploaded_file.seek(0)
        if kind not in ("jpeg", "png"):
            return False, "Cover file content is not a JPEG or PNG image."
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return False, "Unable to verify cover image format."
    if _contains_malware_signature(uploaded_file):
        return False, "Cover file contains blocked content."
    return True, ""


def validate_sample_file(uploaded_file) -> Tuple[bool, str]:
    if not uploaded_file:
        return True, ""
    return validate_book_file(uploaded_file)
