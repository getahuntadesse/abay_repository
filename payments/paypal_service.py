"""
Production PayPal Orders v2 (create → approve URL → capture).
Sandbox or Live via PAYPAL_MODE.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PayPalService:
    def __init__(self) -> None:
        self.client_id = getattr(settings, "PAYPAL_CLIENT_ID", "") or ""
        self.client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "") or ""
        mode = (getattr(settings, "PAYPAL_MODE", "sandbox") or "sandbox").lower()
        self.mode = mode
        self.base = (
            "https://api-m.paypal.com"
            if mode == "live"
            else "https://api-m.sandbox.paypal.com"
        )
        self.currency = getattr(settings, "PAYPAL_CURRENCY", "USD")
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        self.return_url = getattr(settings, "PAYPAL_RETURN_URL", "") or (
            base + "/payments/paypal/return/"
        )
        self.cancel_url = getattr(settings, "PAYPAL_CANCEL_URL", "") or (
            base + "/payments/return/?cancelled=1"
        )
        self._token: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _token(self) -> str:
        if self._token:
            return self._token
        if not self.is_configured():
            raise RuntimeError("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET missing")
        r = requests.post(
            f"{self.base}/v1/oauth2/token",
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def create_order(
        self,
        amount: float,
        description: str = "Abay Repository purchase",
        custom_id: Optional[str] = None,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "PayPal is not configured"}
        try:
            token = self._token()
            value = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"
            body: Dict[str, Any] = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": self.currency,
                            "value": value,
                        },
                        "description": (description or "Purchase")[:127],
                    }
                ],
                "application_context": {
                    "return_url": return_url or self.return_url,
                    "cancel_url": cancel_url or self.cancel_url,
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                },
            }
            if custom_id:
                body["purchase_units"][0]["custom_id"] = str(custom_id)[:127]
                body["purchase_units"][0]["invoice_id"] = str(custom_id)[:127]

            r = requests.post(
                f"{self.base}/v2/checkout/orders",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                json=body,
                timeout=30,
            )
            data = r.json() if r.content else {}
            if r.status_code not in (200, 201):
                logger.warning("PayPal create order failed: %s", data)
                return {
                    "success": False,
                    "error": data.get("message") or data.get("details") or data,
                    "raw": data,
                }
            approve = None
            for link in data.get("links") or []:
                if link.get("rel") == "approve":
                    approve = link.get("href")
                    break
            logger.info("PayPal order created id=%s", data.get("id"))
            return {
                "success": True,
                "order_id": data.get("id"),
                "checkout_url": approve,
                "status": data.get("status"),
                "raw": data,
            }
        except Exception as e:
            logger.exception("PayPal create order error")
            return {"success": False, "error": str(e)}

    def capture(self, order_id: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "PayPal is not configured"}
        try:
            # Clear cached token on auth issues by always fetching
            self._token = None
            token = self._token()
            r = requests.post(
                f"{self.base}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=30,
            )
            data = r.json() if r.content else {}
            ok = r.status_code in (200, 201) and str(data.get("status", "")).upper() in (
                "COMPLETED",
                "APPROVED",
            )
            if not ok and r.status_code in (200, 201) and data.get("status") == "COMPLETED":
                ok = True
            # Also success if capture already completed
            if r.status_code in (200, 201) and data.get("status") == "COMPLETED":
                ok = True
            return {"success": ok or r.status_code in (200, 201), "raw": data, "status": data.get("status")}
        except Exception as e:
            logger.exception("PayPal capture error")
            return {"success": False, "error": str(e)}

    def get_order(self, order_id: str) -> Dict[str, Any]:
        try:
            token = self._token()
            r = requests.get(
                f"{self.base}/v2/checkout/orders/{order_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=25,
            )
            data = r.json() if r.content else {}
            return {"success": r.status_code == 200, "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}
