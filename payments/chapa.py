"""
Production Chapa payment integration (hosted checkout + webhook verify).
Docs: https://developer.chapa.co
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ChapaService:
    def __init__(self) -> None:
        self.secret_key = getattr(settings, "CHAPA_SECRET_KEY", "") or ""
        self.public_key = getattr(settings, "CHAPA_PUBLIC_KEY", "") or ""
        self.base_url = getattr(settings, "CHAPA_BASE_URL", "https://api.chapa.co/v1").rstrip("/")
        self.currency = getattr(settings, "CHAPA_CURRENCY", "ETB")
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        self.callback_url = getattr(settings, "CHAPA_CALLBACK_URL", "") or (
            base + "/payments/webhook/chapa/"
        )
        self.return_url = getattr(settings, "CHAPA_RETURN_URL", "") or (
            base + "/payments/return/"
        )

    def is_configured(self) -> bool:
        return bool(self.secret_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def initialize(
        self,
        amount: float,
        email: str,
        first_name: str,
        last_name: str = "",
        tx_ref: Optional[str] = None,
        phone: str = "",
        title: str = "Abay Repository",
        description: str = "Book purchase",
        callback_url: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "CHAPA_SECRET_KEY is not configured"}

        tx_ref = tx_ref or f"CHAPA-{uuid.uuid4().hex[:16].upper()}"
        payload = {
            "amount": str(Decimal(str(amount)).quantize(Decimal("0.01"))),
            "currency": self.currency,
            "email": email or "customer@abay.local",
            "first_name": (first_name or "Customer")[:50],
            "last_name": (last_name or "User")[:50],
            "tx_ref": tx_ref,
            "callback_url": callback_url or self.callback_url,
            "return_url": return_url or self.return_url,
            "customization": {
                "title": (title or "Abay")[:16],
                "description": (description or "Purchase")[:50],
            },
        }
        if phone:
            payload["phone_number"] = phone

        try:
            r = requests.post(
                f"{self.base_url}/transaction/initialize",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            data = r.json() if r.content else {}
            if r.status_code in (200, 201) and str(data.get("status", "")).lower() == "success":
                checkout = (data.get("data") or {}).get("checkout_url")
                logger.info("Chapa init OK tx_ref=%s", tx_ref)
                return {
                    "success": True,
                    "tx_ref": tx_ref,
                    "checkout_url": checkout,
                    "raw": data,
                }
            msg = data.get("message") or data.get("msg") or data
            logger.warning("Chapa init failed: %s", msg)
            return {"success": False, "error": str(msg), "raw": data}
        except Exception as e:
            logger.exception("Chapa initialize error")
            return {"success": False, "error": str(e)}

    def verify(self, tx_ref: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "Chapa not configured"}
        try:
            r = requests.get(
                f"{self.base_url}/transaction/verify/{tx_ref}",
                headers=self._headers(),
                timeout=25,
            )
            data = r.json() if r.content else {}
            status = ((data.get("data") or {}).get("status") or data.get("status") or "").lower()
            ok = r.status_code == 200 and status in ("success", "successful")
            return {"success": ok, "status": status, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        """
        Chapa may send chapa-signature header (HMAC SHA256 of body with secret).
        If no signature header is present, returns True (rely on server-side verify()).
        """
        if not signature or not self.secret_key:
            return True
        try:
            digest = hmac.new(
                self.secret_key.encode("utf-8"),
                payload_body,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(digest, signature.strip())
        except Exception:
            return False
