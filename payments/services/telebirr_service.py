"""
Production Telebirr SuperApp / Merchant Gateway service.
Implements createOrder (returns checkOutUrl), queryOrder, notify verification, refund.
Matches Ethio telecom Fabric + Mobile Money API (SHA256WithRSA).
"""
import json
import time
import uuid
import base64
import logging
from typing import Dict, Any, Optional, Tuple

import requests
from django.conf import settings
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger("payments.telebirr")


class TelebirrService:
    """
    Telebirr payment gateway – production ready.
    Flow:
      1. applyFabricToken (or use pre-configured token)
      2. createOrder → returns checkOutUrl
      3. Frontend opens checkOutUrl
      4. Async notify callback + optional queryOrder
      5. refund when needed
    """

    def __init__(self):
        cfg = getattr(settings, "TELEBIRR_CONFIG", {})
        self.base_url = cfg.get(
            "BASE_URL",
            "https://developerportal.ethiotelebirr.et:38443/apiaccess/payment/gateway",
        )
        # Production override
        if not settings.DEBUG and cfg.get("PRODUCTION_BASE_URL"):
            self.base_url = cfg["PRODUCTION_BASE_URL"]

        self.fabric_app_id = cfg.get("FABRIC_APP_ID", "")          # X-APP-Key
        self.app_secret = cfg.get("APP_SECRET", "")
        self.merchant_app_id = cfg.get("MERCHANT_APP_ID", "")      # appid inside biz_content
        self.merchant_code = cfg.get("MERCHANT_CODE", "")          # merch_code
        self.private_key_pem = cfg.get("PRIVATE_KEY", "")
        self.public_key_pem = cfg.get("PUBLIC_KEY", "")            # for verify notify
        self.notify_url = cfg.get("NOTIFY_URL", "")
        self.return_url = cfg.get("RETURN_URL", "")
        self.timeout = int(cfg.get("TIMEOUT", 30))

        self._fabric_token: Optional[str] = None
        self._token_expiry: float = 0
        self._private_key = None

        if self.private_key_pem:
            try:
                key_data = self.private_key_pem
                if "BEGIN" not in key_data:
                    key_data = (
                        "-----BEGIN PRIVATE KEY-----\n"
                        + key_data
                        + "\n-----END PRIVATE KEY-----"
                    )
                self._private_key = serialization.load_pem_private_key(
                    key_data.encode(), password=None, backend=default_backend()
                )
            except Exception as e:
                logger.error("Failed to load Telebirr private key: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _nonce(self) -> str:
        return uuid.uuid4().hex[:32]

    def _timestamp(self) -> str:
        # UTC seconds as string (docs: unit is second, <=13 chars)
        return str(int(time.time()))

    def _rsa_sign(self, content: str) -> str:
        if not self._private_key:
            raise RuntimeError("Telebirr private key not configured")
        signature = self._private_key.sign(
            content.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _build_sign_content(self, params: Dict[str, Any]) -> str:
        """
        Alphabetical key=value joined by & (exclude sign and sign_type).
        Nested objects (biz_content) are JSON-serialized without spaces.
        """
        items = []
        for k in sorted(params.keys()):
            if k in ("sign", "sign_type"):
                continue
            v = params[k]
            if isinstance(v, (dict, list)):
                v = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
            items.append(f"{k}={v}")
        return "&".join(items)

    def _sign_request(self, body: Dict[str, Any]) -> Dict[str, Any]:
        content = self._build_sign_content(body)
        body["sign"] = self._rsa_sign(content)
        body["sign_type"] = "SHA256WithRSA"
        return body

    def _headers(self, token: Optional[str] = None) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabric_app_id,
        }
        if token:
            h["Authorization"] = token if token.startswith("Bearer") else f"Bearer {token}"
        return h

    # ------------------------------------------------------------------
    # Fabric token
    # ------------------------------------------------------------------

    def apply_fabric_token(self) -> Tuple[bool, Any]:
        """Obtain Fabric App Token (required for subsequent calls)."""
        url = f"{self.base_url}/payment/v1/token"
        # Some portals use /fabric/token/apply – support both via config
        token_path = getattr(settings, "TELEBIRR_CONFIG", {}).get(
            "TOKEN_PATH", "/payment/v1/token"
        )
        url = f"{self.base_url.rstrip('/')}{token_path}"

        payload = {
            "appSecret": self.app_secret,
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "X-APP-Key": self.fabric_app_id},
                timeout=self.timeout,
                verify=True,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get("token"):
                self._fabric_token = data["token"]
                # default 1h if not provided
                self._token_expiry = time.time() + int(data.get("expiresIn", 3600))
                return True, data
            # Alternative response shapes
            if data.get("code") in ("0", "0000") and data.get("data", {}).get("token"):
                self._fabric_token = data["data"]["token"]
                self._token_expiry = time.time() + int(data["data"].get("expiresIn", 3600))
                return True, data
            logger.error("Fabric token failed: %s %s", resp.status_code, data)
            return False, data
        except Exception as e:
            logger.exception("Fabric token error")
            return False, {"error": str(e)}

    def get_token(self) -> Optional[str]:
        if not self._fabric_token or time.time() > self._token_expiry - 60:
            ok, _ = self.apply_fabric_token()
            if not ok:
                return None
        return self._fabric_token

    # ------------------------------------------------------------------
    # Create Order → checkOutUrl
    # ------------------------------------------------------------------

    def create_order(
        self,
        title: str,
        amount: str,
        merch_order_id: str,
        notify_url: Optional[str] = None,
        return_url: Optional[str] = None,
        timeout_express: str = "30m",
        business_type: str = "BuyGoods",
        trade_type: str = "Checkout",
        payee_identifier: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a payment order.
        Returns (success, {checkOutUrl, merch_order_id, ...} or error).
        Frontend must open the returned checkOutUrl.
        """
        token = self.get_token()
        if not token:
            return False, {"error": "Unable to obtain Fabric token"}

        biz = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
            "title": title[:128],
            "total_amount": str(amount),
            "trans_currency": "ETB",
            "timeout_express": timeout_express,
            "business_type": business_type,
            "trade_type": trade_type,
            "notify_url": notify_url or self.notify_url,
            "redirect_url": return_url or self.return_url,
        }
        if payee_identifier:
            biz["payee_identifier"] = payee_identifier

        body = {
            "timestamp": self._timestamp(),
            "nonce_str": self._nonce(),
            "method": "payment.preorder",
            "version": "1.0",
            "biz_content": biz,
        }
        body = self._sign_request(body)

        url = f"{self.base_url.rstrip('/')}/payment/v1/merchant/preOrder"
        try:
            resp = requests.post(
                url,
                json=body,
                headers=self._headers(token),
                timeout=self.timeout,
                verify=True,
            )
            data = resp.json() if resp.content else {}
            logger.info("Telebirr createOrder response: %s", data)

            if data.get("result") == "SUCCESS" or data.get("code") in ("0", "0000"):
                biz_resp = data.get("biz_content") or data.get("data") or {}
                checkout = (
                    biz_resp.get("toPayUrl")
                    or biz_resp.get("checkOutUrl")
                    or biz_resp.get("checkout_url")
                    or biz_resp.get("paymentUrl")
                )
                if not checkout:
                    # Some environments return rawRequest that must be used differently
                    checkout = biz_resp.get("rawRequest")
                return True, {
                    "checkOutUrl": checkout,
                    "merch_order_id": merch_order_id,
                    "prepay_id": biz_resp.get("prepay_id"),
                    "raw": data,
                }
            return False, {
                "error": data.get("msg") or data.get("message") or "createOrder failed",
                "raw": data,
            }
        except Exception as e:
            logger.exception("createOrder error")
            return False, {"error": str(e)}

    # ------------------------------------------------------------------
    # Query Order
    # ------------------------------------------------------------------

    def query_order(self, merch_order_id: str) -> Tuple[bool, Dict[str, Any]]:
        token = self.get_token()
        if not token:
            return False, {"error": "Unable to obtain Fabric token"}

        biz = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
        }
        body = {
            "timestamp": self._timestamp(),
            "nonce_str": self._nonce(),
            "method": "payment.queryorder",
            "version": "1.0",
            "biz_content": biz,
        }
        body = self._sign_request(body)

        url = f"{self.base_url.rstrip('/')}/payment/v1/merchant/queryOrder"
        try:
            resp = requests.post(
                url, json=body, headers=self._headers(token), timeout=self.timeout, verify=True
            )
            data = resp.json() if resp.content else {}
            if data.get("result") == "SUCCESS" or data.get("code") in ("0", "0000"):
                return True, data.get("biz_content") or data
            return False, {"error": data.get("msg"), "raw": data}
        except Exception as e:
            logger.exception("queryOrder error")
            return False, {"error": str(e)}

    # ------------------------------------------------------------------
    # Notify verification
    # ------------------------------------------------------------------

    def verify_notify(self, payload: Dict[str, Any]) -> bool:
        """
        Verify SHA256WithRSA signature of async notification.
        Returns True if signature is valid.
        """
        if not self.public_key_pem:
            logger.warning("No public key – skipping notify signature verification")
            return True  # fail-open only if key missing; production should have key

        sign = payload.get("sign")
        if not sign:
            return False
        content = self._build_sign_content(payload)
        try:
            key_data = self.public_key_pem
            if "BEGIN" not in key_data:
                key_data = (
                    "-----BEGIN PUBLIC KEY-----\n"
                    + key_data
                    + "\n-----END PUBLIC KEY-----"
                )
            pub = serialization.load_pem_public_key(
                key_data.encode(), backend=default_backend()
            )
            pub.verify(
                base64.b64decode(sign),
                content.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.error("Notify signature verification failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Refund
    # ------------------------------------------------------------------

    def refund(
        self,
        merch_order_id: str,
        refund_request_no: str,
        actual_amount: str,
        refund_reason: str = "Customer request",
    ) -> Tuple[bool, Dict[str, Any]]:
        token = self.get_token()
        if not token:
            return False, {"error": "Unable to obtain Fabric token"}

        biz = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
            "refund_request_no": refund_request_no,
            "refund_reason": refund_reason,
            "actual_amount": str(actual_amount),
            "trans_currency": "ETB",
        }
        body = {
            "timestamp": self._timestamp(),
            "nonce_str": self._nonce(),
            "method": "payment.refund",
            "version": "1.0",
            "biz_content": biz,
        }
        body = self._sign_request(body)

        url = f"{self.base_url.rstrip('/')}/payment/v1/merchant/refund"
        try:
            resp = requests.post(
                url, json=body, headers=self._headers(token), timeout=self.timeout, verify=True
            )
            data = resp.json() if resp.content else {}
            if data.get("result") == "SUCCESS" or data.get("code") in ("0", "0000"):
                return True, data.get("biz_content") or data
            return False, {"error": data.get("msg"), "raw": data}
        except Exception as e:
            logger.exception("refund error")
            return False, {"error": str(e)}
