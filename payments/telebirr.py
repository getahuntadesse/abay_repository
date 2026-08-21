"""
Production Telebirr (Ethio Telecom Fabric H5) gateway.
SHA256WithRSA signing per official SuperApp / Fabric docs.
"""
from __future__ import annotations

import base64
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
            "https://superapp.ethiomobilemoney.et:38443/apiaccess/payment/gateway",
        ).rstrip("/")
        self.fabric_app_id = getattr(settings, "TELEBIRR_FABRIC_APP_ID", "") or ""
        self.app_secret = getattr(settings, "TELEBIRR_APP_SECRET", "") or ""
        self.merchant_app_id = getattr(settings, "TELEBIRR_MERCHANT_APP_ID", "") or ""
        self.merchant_code = getattr(settings, "TELEBIRR_MERCHANT_CODE", "") or ""
        self.private_key_raw = getattr(settings, "TELEBIRR_PRIVATE_KEY", "") or ""
        self.web_base_url = getattr(
            settings,
            "TELEBIRR_WEB_BASE_URL",
            "https://superapp.ethiomobilemoney.et:38443/payment/web/pay?",
        )
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        self.notify_url = getattr(settings, "TELEBIRR_NOTIFY_URL", "") or (
            base + "/payments/webhook/telebirr/"
        )
        self.redirect_url = getattr(settings, "TELEBIRR_RETURN_URL", "") or (
            base + "/payments/return/"
        )
        self.timeout_express = getattr(settings, "TELEBIRR_TIMEOUT_EXPRESS", "120m")
        self.verify_ssl = bool(getattr(settings, "TELEBIRR_VERIFY_SSL", True))
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
        if not self.private_key_raw:
            return None
        raw = self.private_key_raw.strip().replace("\\n", "\n")
        try:
            if "BEGIN" in raw:
                return serialization.load_pem_private_key(raw.encode("utf-8"), password=None)
            # DER from base64 body
            key_bytes = base64.b64decode(raw)
            return serialization.load_der_private_key(key_bytes, password=None)
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
        signature = self._rsa_key.sign(
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
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
        endpoints = [
            f"{self.base_url}/payment/v1/token",
            f"{self.base_url}/payment/v1/auth/authToken",
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
        raise RuntimeError(f"Telebirr fabric token failed: {last_err}")

    def create_checkout(
        self,
        title: str,
        amount: float,
        merch_order_id: Optional[str] = None,
        notify_url: Optional[str] = None,
        redirect_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "error": "Telebirr is not fully configured (keys / RSA private key).",
            }
        merch_order_id = merch_order_id or f"ORD{uuid.uuid4().hex[:16].upper()}"
        try:
            token = self.apply_fabric_token()
        except Exception as e:
            logger.exception("Telebirr token error")
            return {"success": False, "error": str(e)}

        # Amount as string with 2 decimals
        total = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"

        biz = {
            "notify_url": notify_url or self.notify_url,
            "trade_type": "Checkout",
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
            "title": (title or "Abay Repository")[:128],
            "total_amount": total,
            "trans_currency": "ETB",
            "timeout_express": self.timeout_express,
            "payee_identifier": self.merchant_code,
            "payee_identifier_type": "04",
            "payee_type": "5000",
            "redirect_url": redirect_url or self.redirect_url,
        }
        req = {
            "timestamp": self._ts(),
            "method": "payment.preorder",
            "nonce_str": self._nonce(),
            "version": "1.0",
            "biz_content": biz,
            "sign_type": "SHA256WithRSA",
        }
        try:
            req["sign"] = self._sign(req)
        except Exception as e:
            return {"success": False, "error": f"Sign failed: {e}"}

        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabric_app_id,
            "Authorization": token,
        }
        endpoints = [
            f"{self.base_url}/payment/v1/merchant/preOrder",
            f"{self.base_url}/payment/v1/merchant/createOrder",
        ]
        last = None
        for url in endpoints:
            try:
                r = requests.post(
                    url, headers=headers, json=req, timeout=30, verify=self.verify_ssl
                )
                data = r.json() if r.content else {}
                code = str(data.get("code", ""))
                ok = code in ("0", "200") or data.get("result") in ("SUCCESS", "success")
                if ok:
                    prepay_id = (data.get("biz_content") or {}).get("prepay_id")
                    if not prepay_id:
                        last = data
                        continue
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
                last = data
            except Exception as e:
                last = str(e)
                logger.warning("Telebirr preorder %s failed: %s", url, e)
        return {"success": False, "error": f"Create order failed: {last}"}

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
        biz = {
            "appid": self.merchant_app_id,
            "merch_code": self.merchant_code,
            "merch_order_id": merch_order_id,
        }
        req = {
            "timestamp": self._ts(),
            "method": "payment.queryorder",
            "nonce_str": self._nonce(),
            "version": "1.0",
            "biz_content": biz,
            "sign_type": "SHA256WithRSA",
        }
        try:
            req["sign"] = self._sign(req)
        except Exception as e:
            return {"success": False, "error": str(e)}
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
            return {"success": r.status_code == 200, "raw": r.json() if r.content else {}}
        except Exception as e:
            return {"success": False, "error": str(e)}
