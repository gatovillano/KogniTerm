"""
Modelos de datos Pydantic para el sistema de pagos y suscripciones de KogniTerm.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    MOCK = "mock"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"


class PlanInfo(BaseModel):
    id: str = Field(..., description="ID del plan (ej: plan_free, plan_pro_monthly)")
    name: str = Field(..., description="Nombre del plan")
    tier: PlanTier = Field(..., description="Tier de la suscripción")
    price: float = Field(..., description="Precio en USD")
    currency: str = Field(default="usd", description="Moneda")
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY, description="Ciclo de facturación")
    description: str = Field(..., description="Descripción de características")
    features: List[str] = Field(default_factory=list, description="Lista de características del plan")
    token_limit_per_month: int = Field(..., description="Límite mensual de tokens")
    max_sessions: int = Field(..., description="Máximo número de sesiones concurrentes")
    custom_models_allowed: bool = Field(default=False, description="Permite configuración de modelos personalizados")


class SubscriptionDetails(BaseModel):
    user_id: str = Field(..., description="ID del usuario o cliente")
    plan_id: str = Field(..., description="ID del plan suscrito")
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    current_period_start: str = Field(..., description="Fecha inicio periodo ISO 8601")
    current_period_end: str = Field(..., description="Fecha fin periodo ISO 8601")
    cancel_at_period_end: bool = Field(default=False)
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateCheckoutSessionRequest(BaseModel):
    plan_id: str = Field(..., description="ID del plan a contratar")
    success_url: str = Field(..., description="URL de redirección tras éxito")
    cancel_url: str = Field(..., description="URL de redirección tras cancelación")
    customer_email: Optional[str] = Field(default=None, description="Email del cliente")
    user_id: Optional[str] = Field(default=None, description="ID explícito de usuario u organización")
    provider: Optional[PaymentProvider] = Field(default=None, description="Proveedor preferido (stripe o mock)")


class CreateCheckoutSessionResponse(BaseModel):
    checkout_url: str = Field(..., description="URL para completar el pago o checkout")
    session_id: str = Field(..., description="ID de la sesión de checkout")
    provider: PaymentProvider = Field(default=PaymentProvider.MOCK)


class CompleteCheckoutRequest(BaseModel):
    session_id: str = Field(..., description="ID de la sesión de checkout a completar")
    user_id: Optional[str] = Field(default=None, description="ID del usuario")
    plan_id: Optional[str] = Field(default=None, description="ID del plan")


class CompleteCheckoutResponse(BaseModel):
    status: str = Field(default="success")
    message: str = Field(..., description="Mensaje de confirmación")
    subscription: SubscriptionDetails = Field(..., description="Detalles de la suscripción actualizada")


class SwitchPlanRequest(BaseModel):
    plan_id: str = Field(..., description="Nuevo plan objetivo")
    provider: Optional[PaymentProvider] = Field(default=None, description="Proveedor preferido para el cambio")
    prorate: bool = Field(default=True, description="Si se debe prorratear el cambio inmediatamente")


class PaymentMethodDetails(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool = False


class PaymentHistoryItem(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    date: str
    receipt_url: Optional[str] = None
    description: str


class UsageQuotaInfo(BaseModel):
    tier: PlanTier
    tokens_used_this_month: int
    tokens_limit: int
    percentage_used: float
    sessions_active: int
    sessions_limit: int
