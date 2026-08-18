"""
PayPal Orders API v2 – production ready.
Create order → returns approve URL (checkOutUrl).
"""
import logging
import uuid
from typing import Dict, Any, Tuple, Optional
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger("payments.paypal")


class PayPalService:
    def __init__(self):
        cfg = getattr(settings, "PAYPAL_CONFIG", {})
        self.client_id = cfg.get("CLIENT_ID", "")
        self.client_secret = cfg.get("CLIENT_SECRET", "")
        self.mode = cfg.get("MODE", "sandbox")  # sandbox | live
        if self.mode == "live":
            self.base_url = "https://api-m.paypal.com"
        else:
            self.base_url = "https://api-m.sandbox.paypal.com"
        self.return_url = cfg.get("RETURN_URL", "")
        self.cancel_url = cfg.get("CANCEL_URL", "")
        self.currency = cfg.get("CURRENCY", "USD")  # or ETB if supported
        self.timeout = int(cfg.get("TIMEOUT", 30))
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    def _get_token(self) -> Optional[str]:
        import time
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        url = f"{self.base_url}/v1/oauth2/token"
        try:
            resp = requests.post(
                url,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
                timeout=self.timeout,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("access_token"):
                self._access_token = data["access_token"]
                self._token_expiry = time.time() + int(data.get("expires_in", 3600))
                return self._access_token
            logger.error("PayPal token failed: %s", data)
            return None
        except Exception as e:
            logger.exception("PayPal token error")
            return None

    def _headers(self) -> Dict[str, str]:
        token = self._get_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def create_order(
        self,
        amount: str,
        description: str = "Book purchase",
        custom_id: Optional[str] = None,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a PayPal order.
        Returns (success, {checkOutUrl, order_id, ...}).
        """
        if not self.client_id or not self.client_secret:
            return False, {"error": "PayPal credentials not configured"}

        currency = currency or self.currency
        custom_id = custom_id or f"PP-{uuid.uuid4().hex[:12].upper()}"

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": str(Decimal(amount).quantize(Decimal("0.01"))),
                    },
                    "description": description[:127],
                    "custom_id": custom_id,
                }
            ],
            "application_context": {
                "return_url": return_url or self.return_url,
                "cancel_url": cancel_url or self.cancel_url,
                "brand_name": getattr(settings, "APP_NAME", "Abay Repository"),
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
            },
        }

        url = f"{self.base_url}/v2/checkout/orders"
        try:
            resp = requests.post(
                url, json=payload, headers=self._headers(), timeout=self.timeout
            )
            data = resp.json() if resp.content else {}
            logger.info("PayPal create order: %s", data)

            if resp.status_code in (200, 201) and data.get("id"):
                approve_url = None
                for link in data.get("links", []):
                    if link.get("rel") == "approve":
                        approve_url = link.get("href")
                        break
                return True, {
                    "checkOutUrl": approve_url,
                    "order_id": data["id"],
                    "custom_id": custom_id,
                    "raw": data,
                }
            return False, {
                "error": data.get("message") or data.get("error_description") or "PayPal create failed",
                "raw": data,
            }
        except Exception as e:
            logger.exception("PayPal create order error")
            return False, {"error": str(e)}

    def capture_order(self, order_id: str) -> Tuple[bool, Dict[str, Any]]:
        url = f"{self.base_url}/v2/checkout/orders/{order_id}/capture"
        try:
            resp = requests.post(
                url, headers=self._headers(), timeout=self.timeout
            )
            data = resp.json() if resp.content else {}
            if resp.status_code in (200, 201) and data.get("status") == "COMPLETED":
                return True, data
            return False, {"error": "Capture failed", "raw": data}
        except Exception as e:
            logger.exception("PayPal capture error")
            return False, {"error": str(e)}

    def get_order(self, order_id: str) -> Tuple[bool, Dict[str, Any]]:
        url = f"{self.base_url}/v2/checkout/orders/{order_id}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                return True, data
            return False, {"error": "Get order failed", "raw": data}
        except Exception as e:
            return False, {"error": str(e)}

    def create_order_for_js_sdk(
        self,
        amount: str,
        description: str = "Book purchase",
        custom_id: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        PayPal Standard (JS SDK): create order and return order_id only.
        Frontend paypal.Buttons createOrder expects the order id string.
        """
        ok, data = self.create_order(
            amount=amount,
            description=description,
            custom_id=custom_id,
            currency=currency,
        )
        if not ok:
            return False, data
        return True, {
            "id": data.get("order_id"),
            "order_id": data.get("order_id"),
            "custom_id": data.get("custom_id"),
            "checkOutUrl": data.get("checkOutUrl"),
            "raw": data.get("raw"),
        }
