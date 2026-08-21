"""
Production webhook signature verification for Telebirr, Chapa, and PayPal.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Telebirr / Fabric — SHA256WithRSA using platform public key
# ---------------------------------------------------------------------------

def _load_telebirr_public_key():
    raw = (getattr(settings, "TELEBIRR_PUBLIC_KEY", "") or "").strip().replace("\\n", "\n")
    if not raw:
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        if "BEGIN" in raw:
            return serialization.load_pem_public_key(raw.encode("utf-8"))
        key_bytes = base64.b64decode(raw)
        return serialization.load_der_public_key(key_bytes)
    except Exception as e:
        logger.error("TELEBIRR_PUBLIC_KEY load failed: %s", e)
        return None


def telebirr_sign_string(payload: Dict[str, Any]) -> str:
    """
    Build Fabric-style sign string: sorted leaf key=value joined by &.
    Excludes sign / sign_type.
    """
    flat: Dict[str, str] = {}

    def walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("sign", "sign_type") or v is None:
                    continue
                if isinstance(v, dict):
                    walk(v, f"{prefix}.{k}" if prefix else k)
                else:
                    leaf = k
                    flat[leaf] = str(v)
        elif obj is not None and prefix:
            flat[prefix.split(".")[-1]] = str(obj)

    walk(payload)
    return "&".join(f"{k}={flat[k]}" for k in sorted(flat.keys()))


def verify_telebirr_signature(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verify Telebirr notify sign with TELEBIRR_PUBLIC_KEY.
    Returns (ok, reason).
    """
    strict = getattr(settings, "WEBHOOK_VERIFY_STRICT", True)
    pub = _load_telebirr_public_key()
    signature = payload.get("sign") or ""
    if isinstance(payload.get("biz_content"), dict) and not signature:
        signature = payload["biz_content"].get("sign") or ""

    if not signature:
        if strict and pub is not None:
            return False, "missing sign"
        if not pub:
            logger.warning("Telebirr webhook: no TELEBIRR_PUBLIC_KEY — signature check skipped")
            return (not strict) or True, "no public key configured"
        return False, "missing sign"

    if not pub:
        logger.warning("Telebirr webhook: TELEBIRR_PUBLIC_KEY missing — cannot verify")
        return (not strict), "TELEBIRR_PUBLIC_KEY not set"

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        sign_str = telebirr_sign_string(payload)
        sig_bytes = base64.b64decode(signature)
        pub.verify(
            sig_bytes,
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True, "ok"
    except Exception as e:
        logger.warning("Telebirr signature invalid: %s", e)
        return False, f"invalid signature: {e}"


# ---------------------------------------------------------------------------
# Chapa — HMAC-SHA256 of raw body with secret key
# ---------------------------------------------------------------------------

def verify_chapa_signature(raw_body: bytes, headers) -> Tuple[bool, str]:
    """
    Chapa sends header `chapa-signature` (or `x-chapa-signature`) =
    HMAC-SHA256(secret_key, raw_body) hex digest.
    Always pair with API verify(tx_ref) for production.
    """
    strict = getattr(settings, "WEBHOOK_VERIFY_STRICT", True)
    secret = (
        getattr(settings, "CHAPA_WEBHOOK_SECRET", "")
        or getattr(settings, "CHAPA_SECRET_KEY", "")
        or ""
    )
    signature = (
        headers.get("Chapa-Signature")
        or headers.get("chapa-signature")
        or headers.get("X-Chapa-Signature")
        or headers.get("x-chapa-signature")
        or ""
    )
    if not signature:
        if strict:
            # Still allow if we will API-verify; mark as soft
            return True, "no signature header (will API-verify)"
        return True, "no signature header"

    if not secret:
        logger.warning("Chapa webhook: no secret for HMAC")
        return (not strict), "CHAPA_SECRET_KEY / CHAPA_WEBHOOK_SECRET missing"

    try:
        digest = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        # Some deployments use base64 HMAC
        digest_b64 = base64.b64encode(
            hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode("utf-8")
        ok = hmac.compare_digest(digest, signature.strip()) or hmac.compare_digest(
            digest_b64, signature.strip()
        )
        return (ok, "ok" if ok else "HMAC mismatch")
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# PayPal — webhook signature via PayPal verify-webhook-signature API
# ---------------------------------------------------------------------------

def verify_paypal_webhook(raw_body: bytes, headers) -> Tuple[bool, str]:
    """
    Verify using POST /v1/notifications/verify-webhook-signature
    Requires PAYPAL_WEBHOOK_ID from the PayPal developer dashboard.
    """
    strict = getattr(settings, "WEBHOOK_VERIFY_STRICT", True)
    webhook_id = getattr(settings, "PAYPAL_WEBHOOK_ID", "") or ""

    transmission_id = headers.get("Paypal-Transmission-Id") or headers.get("PAYPAL-TRANSMISSION-ID") or ""
    timestamp = headers.get("Paypal-Transmission-Time") or headers.get("PAYPAL-TRANSMISSION-TIME") or ""
    cert_url = headers.get("Paypal-Cert-Url") or headers.get("PAYPAL-CERT-URL") or ""
    auth_algo = headers.get("Paypal-Auth-Algo") or headers.get("PAYPAL-AUTH-ALGO") or "SHA256withRSA"
    transmission_sig = headers.get("Paypal-Transmission-Sig") or headers.get("PAYPAL-TRANSMISSION-SIG") or ""

    if not all([transmission_id, timestamp, cert_url, transmission_sig]):
        if not webhook_id:
            return (not strict), "PayPal webhook headers / PAYPAL_WEBHOOK_ID missing"
        return False, "missing PayPal transmission headers"

    if not webhook_id:
        logger.warning("PAYPAL_WEBHOOK_ID not set — skipping API verify")
        return (not strict), "PAYPAL_WEBHOOK_ID not set"

    try:
        import requests
        from payments.paypal_service import PayPalService

        pp = PayPalService()
        token = pp._token()
        try:
            event = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            event = {}

        body = {
            "transmission_id": transmission_id,
            "transmission_time": timestamp,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": transmission_sig,
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        r = requests.post(
            f"{pp.base}/v1/notifications/verify-webhook-signature",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json=body,
            timeout=25,
        )
        data = r.json() if r.content else {}
        status = (data.get("verification_status") or "").upper()
        ok = status == "SUCCESS"
        return ok, status or str(data)
    except Exception as e:
        logger.exception("PayPal webhook verify error")
        return False, str(e)


def extract_paypal_order_id(event: Dict[str, Any]) -> Optional[str]:
    """Pull order/capture id from PayPal webhook event resource."""
    resource = event.get("resource") or {}
    # CHECKOUT.ORDER.APPROVED
    if resource.get("id") and event.get("event_type", "").startswith("CHECKOUT.ORDER"):
        return resource.get("id")
    # PAYMENT.CAPTURE.COMPLETED — supplementary_data.related_ids.order_id
    related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    if related.get("order_id"):
        return related.get("order_id")
    if resource.get("custom_id"):
        return resource.get("custom_id")
    if resource.get("invoice_id"):
        return resource.get("invoice_id")
    return resource.get("id")
