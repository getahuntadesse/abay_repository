"""
Production Chapa payment gateway integration.

Uses the official `chapa` Python SDK:
  https://github.com/Chapa-Et/chapa-python

  pip install chapa

Flow:
  1. initialize() -> checkout_url (checkOutUrl for frontend)
  2. Customer pays on Chapa hosted page
  3. Webhook / callback -> verify() -> mark Purchase completed
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger("payments.chapa")


class ChapaService:
    """Production-ready Chapa client (official SDK + webhook HMAC verify)."""

    def __init__(self):
        cfg = getattr(settings, "CHAPA_CONFIG", {}) or {}
        self.secret_key = (cfg.get("SECRET_KEY") or "").strip()
        self.public_key = (cfg.get("PUBLIC_KEY") or "").strip()
        self.callback_url = (cfg.get("CALLBACK_URL") or "").strip()
        self.return_url = (cfg.get("RETURN_URL") or "").strip()
        self.webhook_secret = (cfg.get("WEBHOOK_SECRET") or self.secret_key or "").strip()
        self.currency = (cfg.get("CURRENCY") or "ETB").strip()

        if not self.secret_key:
            logger.error("CHAPA_SECRET_KEY is not configured")

        self._client = None
        if self.secret_key:
            try:
                from chapa import Chapa

                self._client = Chapa(self.secret_key)
            except ImportError:
                logger.error(
                    "chapa package not installed. Run: pip install chapa"
                )
            except Exception as e:
                logger.exception("Failed to init Chapa SDK: %s", e)

    def initialize(
        self,
        amount: str,
        email: str,
        first_name: str,
        last_name: str = "",
        phone: str = "",
        tx_ref: Optional[str] = None,
        title: str = "Book Purchase",
        description: str = "",
        callback_url: Optional[str] = None,
        return_url: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a Chapa hosted checkout session.

        Returns:
            (True, {"checkOutUrl": "...", "tx_ref": "...", "raw": {...}})
            or (False, {"error": "..."})
        """
        if not self.secret_key:
            return False, {"error": "Chapa secret key not configured"}
        if not self._client:
            return False, {"error": "Chapa SDK not available (pip install chapa)"}

        tx_ref = tx_ref or f"ABY-{uuid.uuid4().hex[:16].upper()}"
        currency = currency or self.currency
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                return False, {"error": "Amount must be greater than zero"}
        except (TypeError, ValueError):
            return False, {"error": "Invalid amount"}

        email = (email or "").strip() or "customer@abay.local"
        first_name = (first_name or "Customer").strip()[:50]
        last_name = (last_name or "").strip()[:50]
        phone = (phone or "").strip()

        kwargs: Dict[str, Any] = {
            "email": email,
            "amount": amount_val,
            "first_name": first_name,
            "last_name": last_name or first_name,
            "tx_ref": tx_ref,
            "currency": currency,
            "callback_url": callback_url or self.callback_url,
            "return_url": return_url or self.return_url,
        }
        if phone:
            kwargs["phone_number"] = phone
        if title or description:
            kwargs["customization"] = {
                "title": (title or "Abay Book")[:16],
                "description": (description or title or "Book purchase")[:50],
            }

        try:
            response = self._client.initialize(**kwargs)
            logger.info("Chapa initialize tx_ref=%s response=%s", tx_ref, response)

            if isinstance(response, dict):
                status = (response.get("status") or "").lower()
                data = response.get("data") or {}
                checkout = (
                    data.get("checkout_url")
                    or data.get("checkoutUrl")
                    or response.get("checkout_url")
                )
                if status == "success" and checkout:
                    return True, {
                        "checkOutUrl": checkout,
                        "tx_ref": tx_ref,
                        "raw": response,
                    }
                msg = response.get("message") or "Chapa initialize failed"
                return False, {"error": msg, "raw": response}

            status = getattr(response, "status", None) or ""
            data = getattr(response, "data", None) or {}
            if isinstance(data, dict):
                checkout = data.get("checkout_url")
            else:
                checkout = getattr(data, "checkout_url", None)
            if str(status).lower() == "success" and checkout:
                return True, {
                    "checkOutUrl": checkout,
                    "tx_ref": tx_ref,
                    "raw": response if isinstance(response, dict) else str(response),
                }
            return False, {"error": "Unexpected Chapa response", "raw": str(response)}

        except Exception as e:
            logger.exception("Chapa initialize error")
            return False, {"error": str(e)}

    def verify(self, tx_ref: str) -> Tuple[bool, Dict[str, Any]]:
        """Verify a transaction with Chapa after callback/webhook."""
        if not self._client:
            return False, {"error": "Chapa SDK not available"}
        if not tx_ref:
            return False, {"error": "tx_ref required"}

        try:
            response = self._client.verify(tx_ref)
            logger.info("Chapa verify tx_ref=%s response=%s", tx_ref, response)

            if isinstance(response, dict):
                api_status = (response.get("status") or "").lower()
                data = response.get("data") or {}
                txn_status = (data.get("status") or "").lower()
                if api_status == "success":
                    return True, {
                        "status": txn_status or api_status,
                        "amount": data.get("amount"),
                        "currency": data.get("currency"),
                        "reference": data.get("reference"),
                        "tx_ref": data.get("tx_ref") or tx_ref,
                        "raw": response,
                    }
                return False, {
                    "error": response.get("message") or "Verification failed",
                    "raw": response,
                }

            api_status = str(getattr(response, "status", "")).lower()
            data = getattr(response, "data", None) or {}
            if isinstance(data, dict):
                txn_status = (data.get("status") or "").lower()
                amount = data.get("amount")
            else:
                txn_status = str(getattr(data, "status", "")).lower()
                amount = getattr(data, "amount", None)
            if api_status == "success":
                return True, {
                    "status": txn_status or api_status,
                    "amount": amount,
                    "tx_ref": tx_ref,
                    "raw": str(response),
                }
            return False, {"error": "Verification failed", "raw": str(response)}

        except Exception as e:
            logger.exception("Chapa verify error")
            return False, {"error": str(e)}

    def verify_webhook(
        self,
        body: bytes | str,
        chapa_signature: Optional[str] = None,
        x_chapa_signature: Optional[str] = None,
    ) -> bool:
        """
        Verify webhook originated from Chapa (official protocol).

        Per https://developer.chapa.co/integrations/webhooks :

        - ``Chapa-Signature``  : HMAC-SHA256 of the **secret key** signed with
          the secret key (hash of the key itself).
        - ``x-chapa-signature`` : HMAC-SHA256 of the **event payload** signed
          with the secret key.

        Either header valid is enough to accept the request. If both are
        missing, reject. Always compare with ``hmac.compare_digest``.
        """
        secret = (self.webhook_secret or self.secret_key or "").strip()
        if not secret:
            logger.error("No CHAPA_WEBHOOK_SECRET / CHAPA_SECRET_KEY for webhook verification")
            return False

        chapa_signature = (chapa_signature or "").strip()
        x_chapa_signature = (x_chapa_signature or "").strip()
        if not chapa_signature and not x_chapa_signature:
            logger.warning("Chapa webhook missing both signature headers")
            return False

        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = body or b""

        secret_bytes = secret.encode("utf-8")

        def _hmac_hex(message: bytes) -> str:
            return hmac.new(secret_bytes, message, hashlib.sha256).hexdigest()

        # 1) Official SDK helper (if installed)
        try:
            from chapa import verify_webhook as sdk_verify

            for sig in (chapa_signature, x_chapa_signature):
                if not sig:
                    continue
                try:
                    if sdk_verify(
                        secret_key=secret,
                        body=body_bytes,
                        chapa_signature=sig,
                    ):
                        return True
                except TypeError:
                    # older SDK may expect str body
                    if sdk_verify(
                        secret_key=secret,
                        body=body_bytes.decode("utf-8", errors="replace"),
                        chapa_signature=sig,
                    ):
                        return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning("chapa SDK verify_webhook error, falling back to local HMAC: %s", e)

        valid = False

        # 2) Chapa-Signature = HMAC(secret, secret)
        if chapa_signature:
            expected_key_sig = _hmac_hex(secret_bytes)
            if hmac.compare_digest(chapa_signature, expected_key_sig):
                valid = True
            else:
                # Some integrations hash the payload under this header name too
                if hmac.compare_digest(chapa_signature, _hmac_hex(body_bytes)):
                    valid = True

        # 3) x-chapa-signature = HMAC(secret, payload)
        if x_chapa_signature and not valid:
            payload_candidates = {_hmac_hex(body_bytes)}
            # JSON compact / spaced variants (Node JSON.stringify differences)
            try:
                import json

                parsed = json.loads(body_bytes.decode("utf-8"))
                compact = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                )
                spaced = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
                payload_candidates.add(_hmac_hex(compact))
                payload_candidates.add(_hmac_hex(spaced))
            except Exception:
                pass
            for exp in payload_candidates:
                if hmac.compare_digest(x_chapa_signature, exp):
                    valid = True
                    break

        if not valid:
            logger.warning(
                "Chapa webhook signature mismatch (Chapa-Signature present=%s, x-chapa-signature present=%s)",
                bool(chapa_signature),
                bool(x_chapa_signature),
            )
        return valid

    def extract_tx_ref_from_webhook(self, body: bytes | str) -> Optional[str]:
        """Parse tx_ref / trx_ref from Chapa webhook JSON body."""
        try:
            import json

            if isinstance(body, bytes):
                payload = json.loads(body.decode("utf-8") or "{}")
            else:
                payload = json.loads(body or "{}")
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        return (
            payload.get("tx_ref")
            or payload.get("trx_ref")
            or data.get("tx_ref")
            or data.get("trx_ref")
            or payload.get("reference")
            or data.get("reference")
        )
