"""
Production Telebirr (Ethio Telecom Fabric H5) gateway.
SHA256WithRSA signing per official SuperApp / Fabric docs.
"""
from __future__ import annotations

import base64
import re
import json
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


class TelebirrService:
    """Fabric Payment Gateway — create H5 checkout URL for the buyer."""

    def __init__(self) -> None:
        self.base_url = getattr(
            settings,
            "TELEBIRR_BASE_URL",
            "https://developerportal.ethiotelebirr.et:38443/apiaccess/payment/gateway",
        ).rstrip("/")
        self.fabric_app_id = (getattr(settings, "TELEBIRR_FABRIC_APP_ID", "") or "").strip()
        self.app_secret = (getattr(settings, "TELEBIRR_APP_SECRET", "") or "").strip()
        self.merchant_app_id = (getattr(settings, "TELEBIRR_MERCHANT_APP_ID", "") or "").strip()
        self.merchant_code = (getattr(settings, "TELEBIRR_MERCHANT_CODE", "") or "").strip()
        self.private_key_raw = (getattr(settings, "TELEBIRR_PRIVATE_KEY", "") or "").strip()
        self.web_base_url = getattr(
            settings,
            "TELEBIRR_WEB_BASE_URL",
            "https://developerportal.ethiotelebirr.et:38443/payment/web/paygate?",
        )
        # Known sandbox Fabric credentials are REJECTED by production SuperApp.
        # Auto-correct base URL if still pointing at superapp with these keys.
        _SANDBOX_FABRIC_IDS = {
            "c4182ef8-9249-458a-985e-06d191f4d505",
            "8d0c438b-783b-47f5-a546-fe5700dbdeb2",
        }
        if (
            self.fabric_app_id in _SANDBOX_FABRIC_IDS
            and "superapp.ethiomobilemoney.et" in self.base_url
        ):
            logger.warning(
                "TELEBIRR_BASE_URL points to production SuperApp but Fabric App ID is sandbox. "
                "Switching to developerportal.ethiotelebirr.et"
            )
            self.base_url = "https://developerportal.ethiotelebirr.et:38443/apiaccess/payment/gateway"
            if "superapp" in (self.web_base_url or ""):
                self.web_base_url = "https://developerportal.ethiotelebirr.et:38443/payment/web/paygate?"
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        self.notify_url = getattr(settings, "TELEBIRR_NOTIFY_URL", "") or (
            base + "/payments/webhook/telebirr/"
        )
        self.redirect_url = getattr(settings, "TELEBIRR_RETURN_URL", "") or (
            base + "/payments/return/"
        )
        self.timeout_express = getattr(settings, "TELEBIRR_TIMEOUT_EXPRESS", "120m")
        self.verify_ssl = bool(getattr(settings, "TELEBIRR_VERIFY_SSL", False))
        self._rsa_key = self._load_private_key()
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    def is_configured(self) -> bool:
        return bool(
            self.fabric_app_id
            and self.app_secret
            and self.merchant_app_id
            and self.merchant_code
            and self._rsa_key is not None
        )

    def _load_private_key(self):
        """Load RSA private key from PEM or base64 (PKCS#8 DER) string."""
        if not self.private_key_raw:
            logger.warning("TELEBIRR_PRIVATE_KEY is empty")
            return None
        raw = self.private_key_raw.strip().replace("\\n", "\n").replace(" ", "")
        # Restore newlines if user pasted PEM with spaces stripped incorrectly
        if "BEGIN" in self.private_key_raw:
            raw = self.private_key_raw.strip().replace("\\n", "\n")
        try:
            if "BEGIN" in raw:
                return serialization.load_pem_private_key(raw.encode("utf-8"), password=None)
            # Try base64-decoded DER (PKCS#8 or PKCS#1)
            key_bytes = base64.b64decode(raw)
            try:
                return serialization.load_der_private_key(key_bytes, password=None)
            except Exception:
                # Wrap as PEM PKCS#8 and retry
                pem = (
                    "-----BEGIN PRIVATE KEY-----\n"
                    + "\n".join(raw[i:i+64] for i in range(0, len(raw), 64))
                    + "\n-----END PRIVATE KEY-----"
                )
                return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        except Exception as e:
            logger.error("Telebirr private key load failed: %s", e)
            return None

    @staticmethod
    def _ts() -> str:
        return str(int(time.time()))

    @staticmethod
    def _nonce() -> str:
        return uuid.uuid4().hex

    def _sign(self, params: Dict[str, Any]) -> str:
        if not self._rsa_key:
            raise RuntimeError("Telebirr RSA private key not configured")

        def flatten(obj: Any, prefix: str = "") -> Dict[str, str]:
            out: Dict[str, str] = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if v is None or k in ("sign", "sign_type"):
                        continue
                    key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, dict):
                        out.update(flatten(v, key))
                    else:
                        out[key if prefix else k] = str(v)
            return out

        flat = flatten(params)
        # Fabric: join key=value sorted; for biz_content nested fields use leaf keys only
        # Official demo uses top-level + biz_content fields as sibling keys
        pieces = []
        for k in sorted(flat.keys()):
            leaf = k.split(".")[-1] if "." in k else k
            pieces.append(f"{leaf}={flat[k]}")
        # Prefer unique leaf keys (last wins if clash)
        leaf_map = {}
        for k in sorted(flat.keys()):
            leaf = k.split(".")[-1] if "." in k else k
            leaf_map[leaf] = flat[k]
        sign_str = "&".join(f"{k}={leaf_map[k]}" for k in sorted(leaf_map.keys()))
        # Official Telebirr Fabric demo uses SHA256withRSAandMGF1 (RSA-PSS)
        signature = self._rsa_key.sign(
            sign_str.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def apply_fabric_token(self) -> str:
        if self._token and time.time() < self._token_exp - 30:
            return self._token
        if not self.fabric_app_id or not self.app_secret:
            raise RuntimeError("TELEBIRR_FABRIC_APP_ID / TELEBIRR_APP_SECRET missing")

        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabric_app_id,
        }
        body = {"appSecret": self.app_secret}
        # Official endpoint only (auth/authToken returns 49401024988)
        endpoints = [
            f"{self.base_url}/payment/v1/token",
        ]
        last_err = None
        for url in endpoints:
            try:
                r = requests.post(
                    url, headers=headers, json=body, timeout=25, verify=self.verify_ssl
                )
                data = r.json() if r.content else {}
                token = (
                    data.get("token")
                    or data.get("access_token")
                    or (data.get("biz_content") or {}).get("token")
                )
                if token:
                    self._token = token
                    self._token_exp = time.time() + 3500
                    return token
                last_err = data
            except Exception as e:
                last_err = str(e)
                logger.warning("Telebirr token %s failed: %s", url, e)
        msg = f"Telebirr fabric token failed: {last_err}"
        if isinstance(last_err, dict) and str(last_err.get("errorCode", "")).startswith("4940"):
            msg += (
                " | HINT: Your Fabric App ID/Secret belong to the DEVELOPER PORTAL (sandbox). "
                "Set TELEBIRR_BASE_URL=https://developerportal.ethiotelebirr.et:38443/apiaccess/payment/gateway "
                "and TELEBIRR_WEB_BASE_URL=https://developerportal.ethiotelebirr.et:38443/payment/web/paygate? "
                "in .env then restart. Production SuperApp rejects these keys."
            )
        raise RuntimeError(msg)

    def create_checkout(
        self,
        title: str,
        amount: float,
        merch_order_id: Optional[str] = None,
        notify_url: Optional[str] = None,
        redirect_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create H5 pre-order matching official C2B_WebCheckoutDemo."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "Telebirr is not fully configured (keys / RSA private key).",
            }
        # Telebirr requires merch_order_id matching ^[A-Za-z0-9]+$ (no hyphens/underscores)
        raw_id = merch_order_id or f"ORD{uuid.uuid4().hex[:16].upper()}"
        merch_order_id = re.sub(r"[^A-Za-z0-9]", "", str(raw_id)) or f"ORD{uuid.uuid4().hex[:16].upper()}"
        if len(merch_order_id) > 64:
            merch_order_id = merch_order_id[:64]
        try:
            token = self.apply_fabric_token()
        except Exception as e:
            logger.exception("Telebirr token error")
            return {"success": False, "error": str(e)}

        total = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"

        # Build return URL with merch_order_id so we can complete purchase when user returns
        # (notify webhook often cannot reach localhost)
        ret = redirect_url or self.redirect_url or ""
        if ret and "merch_order_id=" not in ret:
            sep = "&" if "?" in ret else "?"
            ret = f"{ret}{sep}merch_order_id={merch_order_id}"

        biz = {
            "notify_url": notify_url or self.notify_url or "https://www.google.com",
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
            "trade_type": "Checkout",
            "title": (title or "Abay Repository")[:128],
            "total_amount": total,
            "trans_currency": "ETB",
            "timeout_express": self.timeout_express or "120m",
            "redirect_url": ret,
        }
        req = {
            "timestamp": self._ts(),
            "nonce_str": self._nonce(),
            "method": "payment.preorder",
            "version": "1.0",
            "biz_content": biz,
        }
        try:
            # Sign BEFORE attaching sign_type (matches official demo)
            req["sign"] = self._sign(req)
        except Exception as e:
            return {"success": False, "error": f"Sign failed: {e}"}
        req["sign_type"] = "SHA256WithRSA"

        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabric_app_id,
            "Authorization": token,
        }
        # Only valid published API path (preorder / createOrder return 49401026001)
        url = f"{self.base_url}/payment/v1/merchant/preOrder"
        try:
            r = requests.post(
                url, headers=headers, json=req, timeout=30, verify=self.verify_ssl
            )
            data = r.json() if r.content else {}
            logger.info("Telebirr preOrder response: %s", data)
            code = str(data.get("code", ""))
            ok = code in ("0", "200") or data.get("result") in ("SUCCESS", "success")
            if ok:
                prepay_id = (data.get("biz_content") or {}).get("prepay_id")
                if not prepay_id:
                    return {"success": False, "error": f"No prepay_id in response: {data}"}
                checkout_url = self._build_checkout_url(prepay_id)
                logger.info(
                    "Telebirr preorder OK merch_order_id=%s prepay_id=%s",
                    merch_order_id,
                    prepay_id,
                )
                return {
                    "success": True,
                    "merch_order_id": merch_order_id,
                    "prepay_id": prepay_id,
                    "checkout_url": checkout_url,
                    "raw": data,
                }
            return {
                "success": False,
                "error": data.get("msg")
                or data.get("errorMsg")
                or data.get("exceptionInfo")
                or f"Create order failed: {data}",
                "raw": data,
            }
        except Exception as e:
            logger.exception("Telebirr preOrder error")
            return {"success": False, "error": str(e)}

    def _build_checkout_url(self, prepay_id: str) -> str:
        maps = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "nonce_str": self._nonce(),
            "prepay_id": prepay_id,
            "timestamp": self._ts(),
            "sign_type": "SHA256WithRSA",
        }
        maps["sign"] = self._sign(maps)
        query = "&".join(f"{k}={v}" for k, v in maps.items())
        base = self.web_base_url
        if not base.endswith("?") and "?" not in base:
            base = base + "?"
        return f"{base}{query}&version=1.0&trade_type=Checkout"

    def query_order(self, merch_order_id: str) -> Dict[str, Any]:
        try:
            token = self.apply_fabric_token()
        except Exception as e:
            return {"success": False, "error": str(e)}
        merch_order_id = "".join(c for c in str(merch_order_id) if c.isalnum())
        biz = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
        }
        req = {
            "timestamp": self._ts(),
            "nonce_str": self._nonce(),
            "method": "payment.queryorder",
            "version": "1.0",
            "biz_content": biz,
        }
        try:
            req["sign"] = self._sign(req)
        except Exception as e:
            return {"success": False, "error": str(e)}
        req["sign_type"] = "SHA256WithRSA"
        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabric_app_id,
            "Authorization": token,
        }
        url = f"{self.base_url}/payment/v1/merchant/queryOrder"
        try:
            r = requests.post(
                url, headers=headers, json=req, timeout=25, verify=self.verify_ssl
            )
            data = r.json() if r.content else {}
            biz_out = data.get("biz_content") if isinstance(data.get("biz_content"), dict) else {}
            trade_status = str(biz_out.get("trade_status") or data.get("trade_status") or "").upper()
            paid = trade_status in (
                "PAY_SUCCESS", "SUCCESS", "COMPLETED", "PAID", "FINISH"
            ) or str(data.get("code")) in ("0", "200") and trade_status in (
                "PAY_SUCCESS", "SUCCESS", "COMPLETED", "PAID", "FINISH", ""
            )
            # Prefer explicit PAY_SUCCESS
            if trade_status in ("PAY_SUCCESS", "SUCCESS", "COMPLETED", "PAID", "FINISH"):
                paid = True
            return {
                "success": True,
                "paid": bool(trade_status in ("PAY_SUCCESS", "SUCCESS", "COMPLETED", "PAID", "FINISH")),
                "trade_status": trade_status,
                "payment_order_id": biz_out.get("payment_order_id") or data.get("payment_order_id"),
                "merch_order_id": merch_order_id,
                "raw": data,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
