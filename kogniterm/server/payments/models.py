from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"
    NONE = "none"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    MOCK = "mock"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INACTIVE = "inactive"


@dataclass
class PlanInfo:
    id: str
    name: str
    tier: PlanTier
    price_cents: int = 0
    currency: str = "usd"
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    features: List[str] = field(default_factory=list)
    sessions_limit: int = 2
    messages_limit: int = 200
    workspaces_limit: int = 1
    stripe_price_id: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tier"] = self.tier.value if isinstance(self.tier, Enum) else self.tier
        data["billing_cycle"] = self.billing_cycle.value if isinstance(self.billing_cycle, Enum) else self.billing_cycle
        return data


@dataclass
class Subscription:
    user_id: str
    plan_id: str
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    provider: PaymentProvider = PaymentProvider.MOCK
    current_period_start: str = ""
    current_period_end: str = ""
    cancel_at_period_end: bool = False
    created_at: str = ""
    updated_at: str = ""
    external_customer_id: Optional[str] = None
    external_subscription_id: Optional[str] = None
    customer_email: Optional[str] = None

    def __post_init__(self) -> None:
        now = utc_now_iso()
        if not self.current_period_start:
            self.current_period_start = now
        if not self.current_period_end:
            self.current_period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if isinstance(self.status, str):
            try:
                self.status = SubscriptionStatus(self.status)
            except ValueError:
                self.status = SubscriptionStatus.ACTIVE
        if isinstance(self.provider, str):
            try:
                self.provider = PaymentProvider(self.provider)
            except ValueError:
                self.provider = PaymentProvider.MOCK

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, Enum) else self.status
        data["provider"] = self.provider.value if isinstance(self.provider, Enum) else self.provider
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        return cls(**data)


@dataclass
class UsageQuota:
    user_id: str
    tier: PlanTier
    sessions_limit: int
    sessions_active: int
    messages_limit: int
    messages_used: int
    workspaces_limit: int
    workspaces_used: int
    period_start: str
    period_end: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tier"] = self.tier.value if isinstance(self.tier, Enum) else self.tier
        return data


@dataclass
class CheckoutSessionRequest:
    plan_id: str
    success_url: str = "http://localhost:8765/billing/success"
    cancel_url: str = "http://localhost:8765/billing/cancel"
    customer_email: Optional[str] = None
    user_id: Optional[str] = None
    provider: PaymentProvider = PaymentProvider.MOCK

    @classmethod
    def from_any(cls, obj: Any) -> "CheckoutSessionRequest":
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            provider = obj.get("provider", PaymentProvider.MOCK)
            if isinstance(provider, str):
                try:
                    provider = PaymentProvider(provider)
                except ValueError:
                    provider = PaymentProvider.MOCK
            return cls(
                plan_id=obj.get("plan_id") or obj.get("planId") or "",
                success_url=obj.get("success_url") or obj.get("successUrl") or cls.success_url,
                cancel_url=obj.get("cancel_url") or obj.get("cancelUrl") or cls.cancel_url,
                customer_email=obj.get("customer_email") or obj.get("customerEmail"),
                user_id=obj.get("user_id") or obj.get("userId"),
                provider=provider,
            )
        provider = getattr(obj, "provider", PaymentProvider.MOCK)
        if isinstance(provider, str):
            try:
                provider = PaymentProvider(provider)
            except ValueError:
                provider = PaymentProvider.MOCK
        return cls(
            plan_id=getattr(obj, "plan_id", "") or "",
            success_url=getattr(obj, "success_url", cls.success_url),
            cancel_url=getattr(obj, "cancel_url", cls.cancel_url),
            customer_email=getattr(obj, "customer_email", None),
            user_id=getattr(obj, "user_id", None),
            provider=provider,
        )


@dataclass
class CheckoutSessionResponse:
    session_id: str
    checkout_url: str
    provider: PaymentProvider
    status: str = "open"
    plan_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "checkout_url": self.checkout_url,
            "provider": self.provider.value if isinstance(self.provider, Enum) else self.provider,
            "status": self.status,
            "plan_id": self.plan_id,
        }


@dataclass
class CompleteCheckoutRequest:
    session_id: str
    user_id: Optional[str] = None
    plan_id: Optional[str] = None

    @classmethod
    def from_any(cls, obj: Any) -> "CompleteCheckoutRequest":
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            return cls(
                session_id=obj.get("session_id") or obj.get("sessionId") or "",
                user_id=obj.get("user_id") or obj.get("userId"),
                plan_id=obj.get("plan_id") or obj.get("planId"),
            )
        return cls(
            session_id=getattr(obj, "session_id", "") or "",
            user_id=getattr(obj, "user_id", None),
            plan_id=getattr(obj, "plan_id", None),
        )


@dataclass
class CompleteCheckoutResponse:
    status: str
    subscription: Subscription
    session_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "subscription": self.subscription.to_dict() if hasattr(self.subscription, "to_dict") else self.subscription,
            "session_id": self.session_id,
        }


@dataclass
class SwitchPlanRequest:
    plan_id: str
    provider: PaymentProvider = PaymentProvider.MOCK
    prorate: bool = True

    @classmethod
    def from_any(cls, obj: Any) -> "SwitchPlanRequest":
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            provider = obj.get("provider", PaymentProvider.MOCK)
            if isinstance(provider, str):
                try:
                    provider = PaymentProvider(provider)
                except ValueError:
                    provider = PaymentProvider.MOCK
            return cls(
                plan_id=obj.get("plan_id") or obj.get("planId") or "",
                provider=provider,
                prorate=obj.get("prorate", True),
            )
        provider = getattr(obj, "provider", PaymentProvider.MOCK)
        if isinstance(provider, str):
            try:
                provider = PaymentProvider(provider)
            except ValueError:
                provider = PaymentProvider.MOCK
        return cls(
            plan_id=getattr(obj, "plan_id", "") or "",
            provider=provider,
            prorate=getattr(obj, "prorate", True),
        )


@dataclass
class PaymentRecord:
    id: str
    user_id: str
    plan_id: str
    amount_cents: int
    currency: str
    provider: PaymentProvider
    status: str
    created_at: str
    description: str = ""
    session_id: Optional[str] = None
    invoice_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "provider": self.provider.value if isinstance(self.provider, Enum) else self.provider,
            "status": self.status,
            "created_at": self.created_at,
            "description": self.description,
            "session_id": self.session_id,
            "invoice_url": self.invoice_url,
        }
