"""
Modelos de dominio del sistema de pagos de KogniTerm.

Todos los modelos son Pydantic v2 y serializables a JSON plano, de modo que
el almacén de datos y la API REST comparten exactamente el mismo contrato.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 2


def now() -> float:
    """Timestamp Unix actual (segundos, con fractional)."""
    return time.time()


def new_id(prefix: str) -> str:
    """Genera un identificador opaco y único con prefijo legible."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


# ── Enumeraciones ────────────────────────────────────────────────────────────


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

    @property
    def rank(self) -> int:
        """Orden jerárquico: FREE(0) < PRO(1) < ENTERPRISE(2)."""
        return {"free": 0, "pro": 1, "enterprise": 2}[self.value]

    @classmethod
    def at_least(cls, tier: "SubscriptionTier", minimum: "SubscriptionTier") -> bool:
        return tier.rank >= minimum.rank


class PaymentProviderType(str, Enum):
    MOCK = "mock"
    STRIPE = "stripe"
    MERCADOPAGO = "mercadopago"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    DISPUTED = "disputed"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class BillingInterval(str, Enum):
    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"
    LIFETIME = "lifetime"


# ── Planes y catálogo ────────────────────────────────────────────────────────


class PlanConfig(BaseModel):
    """Definición de un plan comercializable."""

    id: str
    name: str
    tier: SubscriptionTier
    price_cents: int = Field(ge=0, description="Precio en centavos de la unidad mínima")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    interval: BillingInterval = BillingInterval.MONTH
    credits_included: int = Field(default=0, ge=0)
    description: str = ""
    features: List[str] = Field(default_factory=list)
    # ID del precio/producto remoto en el proveedor (Stripe price_xxx, etc.)
    provider_price_id: Optional[str] = None
    trial_days: int = Field(default=0, ge=0)
    active: bool = True
    popular: bool = False
    sort_order: int = 0
    # Límites operativos por plan (se combinan con los del tier en entitlements.py)
    limits: Dict[str, int] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @property
    def is_recurring(self) -> bool:
        return self.interval in (BillingInterval.MONTH, BillingInterval.YEAR)

    def price_display(self) -> str:
        symbol = {"USD": "$", "EUR": "€", "ARS": "$", "MXN": "$", "BRL": "R$"}.get(
            self.currency, ""
        )
        return f"{symbol}{self.price_cents / 100:,.2f} {self.currency}"


class CreditPack(BaseModel):
    """Paquete de créditos de pago único (sin suscripción)."""

    id: str
    name: str
    credits: int = Field(ge=0)
    price_cents: int = Field(ge=0)
    currency: str = "USD"
    bonus_credits: int = Field(default=0, ge=0)
    active: bool = True
    sort_order: int = 0
    description: str = ""

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()

    @property
    def total_credits(self) -> int:
        return self.credits + self.bonus_credits


# ── Transacciones y suscripciones ────────────────────────────────────────────


class TransactionRecord(BaseModel):
    """Registro inmutable (con saldos) de un intento de cobro."""

    id: str = Field(default_factory=lambda: new_id("tx"))
    user_id: str
    kind: str = Field(default="subscription", description="subscription|credit_pack")
    plan_id: str
    provider: PaymentProviderType
    provider_transaction_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    amount_cents: int
    refunded_cents: int = 0
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    failure_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    period_start: Optional[float] = None
    period_end: Optional[float] = None
    created_at: float = Field(default_factory=now)
    updated_at: float = Field(default_factory=now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def net_cents(self) -> int:
        return max(0, self.amount_cents - self.refunded_cents)

    @property
    def is_settled(self) -> bool:
        return self.status in (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED)


class UserSubscription(BaseModel):
    """Estado de suscripción de un usuario."""

    user_id: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    plan_id: str = "free_plan"
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    credits_remaining: int = Field(default=0, ge=0)
    credits_granted_total: int = 0
    credits_consumed_total: int = 0
    provider: PaymentProviderType = PaymentProviderType.MOCK
    provider_customer_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    mercadopago_payer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    cancel_at_period_end: bool = False
    active: bool = True
    period_start: Optional[float] = None
    expires_at: Optional[float] = None
    created_at: float = Field(default_factory=now)
    updated_at: float = Field(default_factory=now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= now()

    def days_remaining(self) -> Optional[int]:
        if not self.expires_at:
            return None
        return max(0, int((self.expires_at - now()) // 86400))


class RefundRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ref"))
    transaction_id: str
    user_id: str
    amount_cents: int
    currency: str = "USD"
    reason: str = "requested_by_customer"
    provider_refund_id: Optional[str] = None
    credits_revoked: int = 0
    created_at: float = Field(default_factory=now)


class CreditLedgerEntry(BaseModel):
    """Asiento contable de créditos: cada consumo/otorgación queda auditado."""

    id: str = Field(default_factory=lambda: new_id("cl"))
    user_id: str
    delta: int
    balance_after: int
    reason: str
    transaction_id: Optional[str] = None
    created_at: float = Field(default_factory=now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Eventos y auditoría ──────────────────────────────────────────────────────


class WebhookEvent(BaseModel):
    """Evento de proveedor ya recibido, para garantizar idempotencia."""

    id: str
    provider: PaymentProviderType
    type: str
    payload_hash: str
    received_at: float = Field(default_factory=now)
    processed: bool = False
    result: Optional[str] = None
    error: Optional[str] = None


class AuditEntry(BaseModel):
    """Entrada de bitácora encadenada por hash (detección de manipulación)."""

    seq: int
    ts: float = Field(default_factory=now)
    actor: str = "system"
    action: str
    target: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = "0" * 16
    hash: str = ""


# ── Configuración persistida ─────────────────────────────────────────────────


class ProviderCredentials(BaseModel):
    """Credenciales por proveedor. NUNCA se serializan junto a los datos."""

    provider: PaymentProviderType
    enabled: bool = False
    secret_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    extra: Dict[str, str] = Field(default_factory=dict)

    def is_ready(self) -> bool:
        return bool(self.enabled and self.secret_key)

    def public_view(self) -> dict:
        """Vista segura para la API: nunca expone el secreto."""
        return {
            "provider": self.provider.value,
            "enabled": self.enabled,
            "configured": bool(self.secret_key),
            "webhook_configured": bool(self.webhook_secret),
        }


class PaymentSettings(BaseModel):
    """Configuración global del sistema de pagos (sin secretos)."""

    schema_version: int = SCHEMA_VERSION
    active_provider: PaymentProviderType = PaymentProviderType.MOCK
    default_currency: str = "USD"
    public_base_url: str = "http://localhost:5173"
    success_path: str = "/payment/success"
    cancel_path: str = "/payment/cancel"
    # Ventana de tolerancia (segundos) para validar la firma de los webhooks
    webhook_tolerance_seconds: int = 300
    # Marcas de agua/anti-abuso
    max_checkout_per_hour: int = 10
    free_credits: int = 100
    auto_downgrade: bool = True
    plans: List[PlanConfig] = Field(default_factory=list)
    credit_packs: List[CreditPack] = Field(default_factory=list)


class PaymentData(BaseModel):
    """Documento raíz persistido en disco."""

    schema_version: int = SCHEMA_VERSION
    settings: PaymentSettings = Field(default_factory=PaymentSettings)
    subscriptions: Dict[str, UserSubscription] = Field(default_factory=dict)
    transactions: List[TransactionRecord] = Field(default_factory=list)
    refunds: List[RefundRecord] = Field(default_factory=list)
    credit_ledger: List[CreditLedgerEntry] = Field(default_factory=list)
    processed_events: Dict[str, WebhookEvent] = Field(default_factory=dict)
    audit_log: List[AuditEntry] = Field(default_factory=list)
