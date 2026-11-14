"""Business logic for payments, subscriptions and usage quotas."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .models import (
    AVAILABLE_PLANS,
    BillingCycle,
    CheckoutCompleteRequest,
    CheckoutCompleteResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentHistoryItem,
    PaymentMethod,
    PaymentProvider,
    PlanInfo,
    PlanTier,
    Subscription,
    SubscriptionStatus,
    SwitchPlanRequest,
    UsageQuota,
    WebhookEvent,
    _now_iso,
)


class PaymentService:
    """In-memory/mock-first payment service with Stripe-ready structure."""

    def __init__(self) -> None:
        self._subscriptions_db: Dict[str, Subscription] = {}
        self._usage_db: Dict[str, Dict[str, Any]] = {}
        self._checkout_sessions: Dict[str, Dict[str, Any]] = {}
        self._payment_methods: Dict[str, List[PaymentMethod]] = {}
        self._history: Dict[str, List[PaymentHistoryItem]] = {}
        self._events: List[WebhookEvent] = []

    # ── Plans ──────────────────────────────────────────────────────────────

    def list_plans(self) -> List[PlanInfo]:
        return [p for p in AVAILABLE_PLANS.values() if p.is_active]

    def get_plan(self, plan_id: str) -> PlanInfo:
        plan = AVAILABLE_PLANS.get(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' no encontrado")
        return plan

    # ── Subscriptions ──────────────────────────────────────────────────────

    def _create_free_subscription(self, user_id: str) -> Subscription:
        now = _now_iso()
        sub = Subscription(
            id=f"sub_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            plan_id="plan_free",
            tier=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
            provider=PaymentProvider.MOCK,
            current_period_start=now,
            current_period_end=None,
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )
        self._subscriptions_db[user_id] = sub
        return sub

    def get_user_subscription(self, user_id: str) -> Subscription:
        sub = self._subscriptions_db.get(user_id)
        if sub:
            return sub
        return self._create_free_subscription(user_id)

    def _apply_plan(self, user_id: str, plan_id: str, provider: PaymentProvider) -> Subscription:
        plan = self.get_plan(plan_id)
        now = datetime.now(timezone.utc)
        period_end: Optional[str] = None
        if plan.billing_cycle == BillingCycle.MONTHLY:
            period_end = (now + timedelta(days=30)).replace(microsecond=0).isoformat()
        elif plan.billing_cycle == BillingCycle.YEARLY:
            period_end = (now + timedelta(days=365)).replace(microsecond=0).isoformat()

        existing = self._subscriptions_db.get(user_id)
        sub_id = existing.id if existing else f"sub_{uuid.uuid4().hex[:12]}"
        created_at = existing.created_at if existing else _now_iso()
        sub = Subscription(
            id=sub_id,
            user_id=user_id,
            plan_id=plan.id,
            tier=plan.tier,
            status=SubscriptionStatus.ACTIVE,
            provider=provider,
            current_period_start=_now_iso(),
            current_period_end=period_end,
            cancel_at_period_end=False,
            canceled_at=None,
            created_at=created_at,
            updated_at=_now_iso(),
        )
        self._subscriptions_db[user_id] = sub
        self._record_payment(user_id, plan, provider, status="succeeded", description=f"Suscripción a {plan.name}")
        return sub

    # ── Checkout ───────────────────────────────────────────────────────────

    def _to_checkout_request(self, req: Any) -> CheckoutSessionRequest:
        if isinstance(req, CheckoutSessionRequest):
            return req
        # Accept simple objects/namespaces used by tests
        data = {
            "plan_id": getattr(req, "plan_id"),
            "success_url": getattr(req, "success_url", "http://localhost:3000/billing/success"),
            "cancel_url": getattr(req, "cancel_url", "http://localhost:3000/billing/cancel"),
            "customer_email": getattr(req, "customer_email", None),
            "user_id": getattr(req, "user_id", None),
            "provider": getattr(req, "provider", PaymentProvider.MOCK),
            "metadata": getattr(req, "metadata", {}) or {},
        }
        return CheckoutSessionRequest(**data)

    def create_checkout_session(self, user_id: str, req: Any) -> CheckoutSessionResponse:
        req_obj = self._to_checkout_request(req)
        uid = req_obj.user_id or user_id
        plan = self.get_plan(req_obj.plan_id)
        session_id = f"cs_{uuid.uuid4().hex[:16]}"
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0).isoformat()

        provider = req_obj.provider
        status = "open"
        if provider == PaymentProvider.STRIPE and os.environ.get("STRIPE_SECRET_KEY"):
            checkout_url = f"https://checkout.stripe.com/pay/{session_id}"
        else:
            provider = PaymentProvider.MOCK
            status = "completed"
            # Mock flow: auto-activate for local/dev and tests
            self._apply_plan(uid, plan.id, PaymentProvider.MOCK)
            checkout_url = f"{req_obj.success_url}?session_id={session_id}&provider=mock"

        self._checkout_sessions[session_id] = {
            "session_id": session_id,
            "user_id": uid,
            "plan_id": plan.id,
            "provider": provider.value if isinstance(provider, PaymentProvider) else str(provider),
            "status": status,
            "created_at": _now_iso(),
            "expires_at": expires_at,
            "customer_email": req_obj.customer_email,
        }

        return CheckoutSessionResponse(
            session_id=session_id,
            checkout_url=checkout_url,
            provider=provider if isinstance(provider, PaymentProvider) else PaymentProvider(provider),
            plan_id=plan.id,
            status=status,
            expires_at=expires_at,
        )

    def _to_complete_request(self, req: Any) -> CheckoutCompleteRequest:
        if isinstance(req, CheckoutCompleteRequest):
            return req
        return CheckoutCompleteRequest(
            session_id=getattr(req, "session_id"),
            user_id=getattr(req, "user_id", None),
            plan_id=getattr(req, "plan_id", None),
        )

    def complete_checkout_session(self, user_id: str, req: Any) -> CheckoutCompleteResponse:
        req_obj = self._to_complete_request(req)
        uid = req_obj.user_id or user_id
        session = self._checkout_sessions.get(req_obj.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sesión de checkout no encontrada")

        plan_id = req_obj.plan_id or session.get("plan_id")
        if not plan_id:
            raise HTTPException(status_code=400, detail="No se pudo determinar el plan del checkout")

        provider = PaymentProvider(session.get("provider", PaymentProvider.MOCK.value))
        sub = self._apply_plan(uid, plan_id, provider)
        session["status"] = "completed"
        session["completed_at"] = _now_iso()

        return CheckoutCompleteResponse(
            status="success",
            session_id=req_obj.session_id,
            subscription=sub,
            message="Checkout completado y suscripción activada",
        )

    # ── Plan changes / cancellation ────────────────────────────────────────

    def _to_switch_request(self, req: Any) -> SwitchPlanRequest:
        if isinstance(req, SwitchPlanRequest):
            return req
        return SwitchPlanRequest(
            plan_id=getattr(req, "plan_id"),
            provider=getattr(req, "provider", PaymentProvider.MOCK),
            prorate=getattr(req, "prorate", True),
        )

    def switch_plan(self, user_id: str, req: Any) -> Subscription:
        req_obj = self._to_switch_request(req)
        return self._apply_plan(user_id, req_obj.plan_id, req_obj.provider)

    def cancel_subscription(self, user_id: str, at_period_end: bool = False) -> Subscription:
        current = self.get_user_subscription(user_id)
        if current.plan_id == "plan_free":
            # Keep active free plan semantics simple, but allow CANCELED marker when explicitly requested in history flows
            if current.status == SubscriptionStatus.ACTIVE and at_period_end:
                current.cancel_at_period_end = True
                current.updated_at = _now_iso()
                self._subscriptions_db[user_id] = current
            return current

        if at_period_end and current.current_period_end:
            current.cancel_at_period_end = True
            current.updated_at = _now_iso()
            self._subscriptions_db[user_id] = current
            self._record_payment(user_id, self.get_plan(current.plan_id), current.provider, status="cancel_scheduled", description="Cancelación programada al fin del periodo")
            return current

        # Immediate downgrade to free
        now = _now_iso()
        free = self._create_free_subscription(user_id)
        free.status = SubscriptionStatus.CANCELED
        free.canceled_at = now
        free.updated_at = now
        self._subscriptions_db[user_id] = free
        self._record_payment(user_id, self.get_plan(current.plan_id), current.provider, status="canceled", description="Suscripción cancelada y degradada a Free")
        return free

    # ── Usage & quotas ─────────────────────────────────────────────────────

    def get_usage_quota(self, user_id: str, active_sessions_count: int = 0) -> UsageQuota:
        sub = self.get_user_subscription(user_id)
        plan = self.get_plan(sub.plan_id)
        usage = self._usage_db.setdefault(user_id, {"requests_used_today": 0, "tokens_used_this_month": 0})
        return UsageQuota(
            user_id=user_id,
            plan_id=plan.id,
            tier=plan.tier,
            sessions_limit=plan.sessions_limit,
            sessions_active=active_sessions_count,
            requests_limit_per_day=plan.requests_per_day,
            requests_used_today=int(usage.get("requests_used_today", 0)),
            tokens_limit_per_month=plan.tokens_per_month,
            tokens_used_this_month=int(usage.get("tokens_used_this_month", 0)),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
        )

    # ── Payment methods & history ──────────────────────────────────────────

    def list_payment_methods(self, user_id: str) -> List[PaymentMethod]:
        return self._payment_methods.get(user_id, [])

    def add_mock_payment_method(self, user_id: str, brand: str = "visa", last4: str = "4242") -> PaymentMethod:
        now = _now_iso()
        methods = self._payment_methods.setdefault(user_id, [])
        method = PaymentMethod(
            id=f"pm_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            provider=PaymentProvider.MOCK,
            type="card",
            brand=brand,
            last4=last4,
            exp_month=12,
            exp_year=datetime.now(timezone.utc).year + 3,
            is_default=len(methods) == 0,
            created_at=now,
        )
        methods.append(method)
        return method

    def list_payment_history(self, user_id: str, limit: int = 50) -> List[PaymentHistoryItem]:
        items = self._history.get(user_id, [])
        return list(reversed(items))[: max(1, min(limit, 200))]

    def _record_payment(self, user_id: str, plan: PlanInfo, provider: PaymentProvider, status: str, description: str) -> PaymentHistoryItem:
        item = PaymentHistoryItem(
            id=f"pay_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            amount_cents=plan.price_cents if status == "succeeded" else 0,
            currency=plan.currency,
            status=status,
            description=description,
            provider=provider,
            plan_id=plan.id,
            created_at=_now_iso(),
        )
        self._history.setdefault(user_id, []).append(item)
        return item

    # ── Webhooks ───────────────────────────────────────────────────────────

    def verify_stripe_signature(self, payload: bytes, signature_header: Optional[str]) -> bool:
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        if not secret:
            return True
        if not signature_header:
            return False
        try:
            parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
            timestamp = parts.get("t")
            v1 = parts.get("v1")
            if not timestamp or not v1:
                return False
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
            expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, v1)
        except Exception:
            return False

    def handle_webhook(self, payload: Dict[str, Any], provider: PaymentProvider = PaymentProvider.MOCK) -> WebhookEvent:
        event_type = str(payload.get("type") or "payment.event")
        event = WebhookEvent(
            id=str(payload.get("id") or f"evt_{uuid.uuid4().hex[:12]}"),
            type=event_type,
            provider=provider,
            created_at=_now_iso(),
            data=payload,
        )
        self._events.append(event)

        data_obj = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
        user_id = data_obj.get("metadata", {}).get("user_id") or payload.get("user_id")
        plan_id = data_obj.get("metadata", {}).get("plan_id") or payload.get("plan_id")

        if provider == PaymentProvider.STRIPE:
            if event_type in ("checkout.session.completed", "invoice.paid") and user_id and plan_id:
                self._apply_plan(str(user_id), str(plan_id), PaymentProvider.STRIPE)
            elif event_type in ("customer.subscription.deleted", "invoice.payment_failed") and user_id:
                self.cancel_subscription(str(user_id), at_period_end=False)
        else:
            if event_type == "checkout.completed" and user_id and plan_id:
                self._apply_plan(str(user_id), str(plan_id), PaymentProvider.MOCK)
            elif event_type == "subscription.canceled" and user_id:
                self.cancel_subscription(str(user_id), at_period_end=False)

        return event

    def reset_user(self, user_id: str) -> None:
        self._subscriptions_db.pop(user_id, None)
        self._usage_db.pop(user_id, None)
        self._payment_methods.pop(user_id, None)
        self._history.pop(user_id, None)


payment_service = PaymentService()
AVAILABLE_PLANS = AVAILABLE_PLANS
