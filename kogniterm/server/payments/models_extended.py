"""
Modelos extendidos de datos Pydantic para el sistema de pagos y suscripciones de KogniTerm.

Incluye: reembolsos, cupones, facturas, impuestos y registros de pagos.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RefundStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class RefundReason(str, Enum):
    CUSTOMER_REQUEST = "customer_request"
    DUPLICATE_CHARGE = "duplicate_charge"
    FRAUD = "fraud"
    PRODUCT_UNSATISFACTORY = "product_unsatisfactory"
    SUBSCRIPTION_CANCELED = "subscription_canceled"


class CreateRefundRequest(BaseModel):
    payment_id: str = Field(..., description="ID del pago a reembolsar")
    amount: Optional[float] = Field(default=None, description="Monto a reembolsar (si es None, reembolso total)")
    reason: RefundReason = Field(default=RefundReason.CUSTOMER_REQUEST, description="Motivo del reembolso")
    user_id: Optional[str] = Field(default=None, description="ID del usuario solicitante")


class RefundResponse(BaseModel):
    refund_id: str = Field(..., description="ID único del reembolso")
    status: RefundStatus = Field(default=RefundStatus.PENDING)
    amount: float = Field(..., description="Monto reembolsado")
    currency: str = Field(default="usd")
    reason: RefundReason
    created_at: str
    payment_id: str
    user_id: Optional[str] = None


class CouponType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


class CouponStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    USED = "used"
    REVOKED = "revoked"


class CouponInfo(BaseModel):
    id: str = Field(..., description="ID del cupón")
    code: str = Field(..., description="Código del cupón (ej: SAVE20)")
    type: CouponType = Field(..., description="Tipo de descuento")
    value: float = Field(..., description="Valor del descuento (porcentaje o monto fijo)")
    currency: str = Field(default="usd", description="Moneda para descuento fijo")
    status: CouponStatus = Field(default=CouponStatus.ACTIVE)
    valid_from: str = Field(..., description="Fecha de inicio de validez ISO 8601")
    valid_until: Optional[str] = Field(default=None, description="Fecha de expiración ISO 8601")
    max_uses: Optional[int] = Field(default=None, description="Número máximo de usos totales")
    max_uses_per_user: Optional[int] = Field(default=1, description="Usos máximos por usuario")
    applies_to: Optional[List[str]] = Field(default=None, description="IDs de planes aplicables (None = todos)")
    description: str = Field(default="", description="Descripción del cupón")


class ApplyCouponRequest(BaseModel):
    coupon_code: str = Field(..., description="Código del cupón a aplicar")
    plan_id: str = Field(..., description="ID del plan al cual aplicar el cupón")
    user_id: Optional[str] = Field(default=None, description="ID del usuario")


class ApplyCouponResponse(BaseModel):
    coupon: CouponInfo
    original_price: float
    discount_amount: float
    final_price: float
    currency: str


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"


class InvoiceItem(BaseModel):
    description: str = Field(..., description="Descripción del item")
    quantity: int = Field(default=1, ge=1)
    unit_amount: float = Field(..., description="Monto unitario")
    amount: float = Field(..., description="Monto total del item")
    currency: str = Field(default="usd")


class InvoiceInfo(BaseModel):
    id: str = Field(..., description="ID de la factura")
    invoice_number: str = Field(..., description="Número de factura")
    user_id: str = Field(..., description="ID del usuario")
    plan_id: str = Field(..., description="ID del plan")
    status: InvoiceStatus = Field(default=InvoiceStatus.OPEN)
    subtotal: float = Field(..., description="Subtotal antes de impuestos")
    tax_amount: float = Field(default=0.0, description="Monto de impuestos")
    total: float = Field(..., description="Total a pagar")
    currency: str = Field(default="usd")
    items: List[InvoiceItem] = Field(default_factory=list)
    issued_at: str
    due_at: Optional[str] = None
    paid_at: Optional[str] = None
    payment_id: Optional[str] = None
    receipt_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateInvoiceRequest(BaseModel):
    user_id: str = Field(..., description="ID del usuario")
    plan_id: str = Field(..., description="ID del plan")
    coupon_code: Optional[str] = Field(default=None, description="Código de cupón opcional")
    tax_rate: Optional[float] = Field(default=0.0, description="Tasa de impuesto (ej: 0.21 para 21%)")


class PaymentRecordStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class PaymentRecord(BaseModel):
    id: str = Field(..., description="ID único del registro de pago")
    user_id: str = Field(..., description="ID del usuario")
    plan_id: str = Field(..., description="ID del plan")
    amount: float = Field(..., description="Monto cobrado")
    currency: str = Field(default="usd")
    status: PaymentRecordStatus = Field(default=PaymentRecordStatus.PENDING)
    provider: str = Field(default="mock", description="Proveedor de pago utilizado")
    provider_payment_id: Optional[str] = Field(default=None, description="ID del proveedor externo")
    invoice_id: Optional[str] = None
    coupon_code: Optional[str] = None
    discount_amount: float = Field(default=0.0)
    tax_amount: float = Field(default=0.0)
    created_at: str
    updated_at: str
    receipt_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaxInfo(BaseModel):
    country: str = Field(..., description="Código ISO del país")
    tax_rate: float = Field(..., description="Tasa de impuesto aplicable")
    tax_name: str = Field(..., description="Nombre del impuesto (ej: IVA, GST, Sales Tax)")
    is_tax_inclusive: bool = Field(default=False, description="Si el precio ya incluye impuestos")


class PricingCalculation(BaseModel):
    plan_id: str
    plan_name: str
    base_price: float
    currency: str
    discount_amount: float = 0.0
    tax_amount: float = 0.0
    total: float
    coupon_applied: Optional[CouponInfo] = None
    tax_info: Optional[TaxInfo] = None
    billing_cycle: str


class PaymentProviderHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class ProviderHealthCheck(BaseModel):
    provider: str
    status: PaymentProviderHealth
    latency_ms: Optional[int] = None
    message: Optional[str] = None
