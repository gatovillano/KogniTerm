from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from .models import CheckoutSessionRequest, PaymentProvider


class BaseProvider:
    name = PaymentProvider.MOCK

    def create_checkout_session(self, user_id: str, req: CheckoutSessionRequest, plan: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> bool:
        return True

    def parse_webhook_event(self, payload: bytes) -> Dict[str, Any]:
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return {}


class MockProvider(BaseProvider):
    name = PaymentProvider.MOCK

    def create_checkout_session(self, user_id: str, req: CheckoutSessionRequest, plan: Dict[str, Any]) -> Dict[str, Any]:
        session_id = f"cs_mock_{uuid.uuid4().hex[:16]}"
        base = req.success_url or "http://localhost:8765/billing/success"
        sep = "&" if "?" in base else "?"
        checkout_url = f"{base}{sep}session_id={session_id}&plan_id={req.plan_id}&mock=true"
        return {
            "session_id": session_id,
            "checkout_url": checkout_url,
            "provider": self.name.value,
            "status": "open",
            "plan_id": req.plan_id,
        }


class StripeProvider(BaseProvider):
    name = PaymentProvider.STRIPE

    def __init__(self):
        self.secret_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
        self.webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        self._stripe = None
        try:
            import stripe  # type: ignore
            self._stripe = stripe
            if self.secret_key:
                stripe.api_key = self.secret_key
        except Exception:
            self._stripe = None

    @property
    def is_configured(self) -> bool:
        return bool(self.secret_key and self._stripe)

    def create_checkout_session(self, user_id: str, req: CheckoutSessionRequest, plan: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured:
            result = MockProvider().create_checkout_session(user_id, req, plan)
            result["fallback"] = "stripe_not_configured"
            result["provider"] = self.name.value
            return result

        stripe = self._stripe
        assert stripe is not None
        price_id = plan.get("stripe_price_id") or os.environ.get(f"STRIPE_PRICE_{str(plan.get('id', '')).upper()}")
        amount = int(plan.get("price_cents", 0) or 0)
        mode = "subscription" if amount > 0 and str(plan.get("billing_cycle", "")).lower() != "none" else "payment"
        if price_id:
            line_item: Dict[str, Any] = {"price": price_id, "quantity": 1}
        else:
            line_item = {
                "price_data": {
                    "currency": plan.get("currency", "usd"),
                    "product_data": {
                        "name": plan.get("name", plan.get("id", "KogniTerm Plan")),
                        "description": plan.get("description") or "KogniTerm subscription",
                    },
                    "unit_amount": amount,
                },
                "quantity": 1,
            }
            if mode == "subscription":
                billing_cycle = str(plan.get("billing_cycle", "monthly")).lower()
                interval = "year" if "year" in billing_cycle else "month"
                line_item["price_data"]["recurring"] = {"interval": interval}

        success_url = req.success_url or "http://localhost:8765/billing/success"
        if "{CHECKOUT_SESSION_ID}" not in success_url:
            success_url = success_url + ("&session_id={CHECKOUT_SESSION_ID}" if "?" in success_url else "?session_id={CHECKOUT_SESSION_ID}")

        session = stripe.checkout.Session.create(
            mode=mode,
            line_items=[line_item],
            success_url=success_url,
            cancel_url=req.cancel_url or "http://localhost:8765/billing/cancel",
            client_reference_id=user_id,
            customer_email=req.customer_email,
            metadata={"user_id": user_id, "plan_id": req.plan_id},
        )
        return {
            "session_id": session.get("id"),
            "checkout_url": session.get("url"),
            "provider": self.name.value,
            "status": session.get("status", "open"),
            "plan_id": req.plan_id,
        }

    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> bool:
        if not self.webhook_secret:
            return True
        if not signature:
            return False
        if self._stripe and hasattr(self._stripe, "Webhook"):
            try:
                self._stripe.Webhook.construct_event(payload=payload, sig_header=signature, secret=self.webhook_secret)
                return True
            except Exception:
                return False
        try:
            parts = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
            ts = parts.get("t")
            v1 = parts.get("v1")
            if not ts or not v1:
                return False
            signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
            expected = hmac.new(self.webhook_secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, v1):
                return False
            if abs(int(time.time()) - int(ts)) > 300:
                return False
            return True
        except Exception:
            return False
