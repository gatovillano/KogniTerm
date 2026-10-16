"""
Servicio extendido de pagos para KogniTerm.

Añade capacidades de producción sobre PaymentService:
- Cálculo de precios con descuentos e impuestos
- Gestión de cupones
- Facturación
- Reembolsos
- Registro de pagos
- Salud de proveedores de pago
- Enforzamiento de límites de cuota
"""

import os
import logging
import uuid
import datetime
from typing import List, Optional, Dict, Any

from kogniterm.server.payments.models import (
    PlanInfo, PlanTier, BillingCycle, SubscriptionDetails,
    SubscriptionStatus, CreateCheckoutSessionRequest, PaymentProvider,
)
from kogniterm.server.payments.service import PaymentService, AVAILABLE_PLANS
from kogniterm.server.payments.models_extended import (
    RefundStatus, RefundReason, CreateRefundRequest, RefundResponse,
    CouponType, CouponStatus, CouponInfo, ApplyCouponRequest, ApplyCouponResponse,
    InvoiceStatus, InvoiceItem, InvoiceInfo, CreateInvoiceRequest,
    PaymentRecordStatus, PaymentRecord, TaxInfo, PricingCalculation,
    PaymentProviderHealth, ProviderHealthCheck,
)

logger = logging.getLogger("kogniterm.server.payments.service_extended")


class PaymentServiceExtended(PaymentService):
    """Extensión del servicio de pagos con capacidades de producción."""

    def __init__(self):
        super().__init__()
        self._refunds_db: Dict[str, RefundResponse] = {}
        self._coupons_db: Dict[str, CouponInfo] = {}
        self._invoice_db: Dict[str, InvoiceInfo] = {}
        self._payment_records_db: Dict[str, PaymentRecord] = {}
        self._tax_rates_db: Dict[str, TaxInfo] = {}
        self._coupon_usage: Dict[str, Dict[str, int]] = {}  # user_id -> {coupon_code: count}

        # Cupones predefinidos de demo
        now = datetime.datetime.now(datetime.timezone.utc)
        one_year = now + datetime.timedelta(days=365)

        default_coupons = [
            CouponInfo(
                id="coupon_welcome20",
                code="WELCOME20",
                type=CouponType.PERCENTAGE,
                value=20.0,
                status=CouponStatus.ACTIVE,
                valid_from=now.isoformat(),
                valid_until=one_year.isoformat(),
                max_uses=None,
                max_uses_per_user=1,
                applies_to=["plan_pro_monthly", "plan_pro_yearly"],
                description="20% de descuento en tu primer plan Pro",
            ),
            CouponInfo(
                id="coupon_save10",
                code="SAVE10",
                type=CouponType.PERCENTAGE,
                value=10.0,
                status=CouponStatus.ACTIVE,
                valid_from=now.isoformat(),
                valid_until=one_year.isoformat(),
                max_uses=None,
                max_uses_per_user=None,
                applies_to=None,
                description="10% de descuento en cualquier plan",
            ),
            CouponInfo(
                id="coupon_fixed5",
                code="FIXED5",
                type=CouponType.FIXED_AMOUNT,
                value=5.0,
                currency="usd",
                status=CouponStatus.ACTIVE,
                valid_from=now.isoformat(),
                valid_until=one_year.isoformat(),
                max_uses=None,
                max_uses_per_user=1,
                applies_to=["plan_pro_monthly"],
                description="$5 USD de descuento en Pro Monthly",
            ),
        ]
        for c in default_coupons:
            self._coupons_db[c.code] = c

        # Tasas de impuesto por país (ejemplos)
        self._tax_rates_db = {
            "US": TaxInfo(country="US", tax_rate=0.0, tax_name="No tax", is_tax_inclusive=False),
            "AR": TaxInfo(country="AR", tax_rate=0.21, tax_name="IVA", is_tax_inclusive=False),
            "MX": TaxInfo(country="MX", tax_rate=0.16, tax_name="IVA", is_tax_inclusive=False),
            "ES": TaxInfo(country="ES", tax_rate=0.21, tax_name="IVA", is_tax_inclusive=False),
            "BR": TaxInfo(country="BR", tax_rate=0.17, tax_name="ICMS", is_tax_inclusive=False),
        }

    # ── Cálculo de precios ──────────────────────────────────────────────

    def calculate_price(
        self,
        plan_id: str,
        coupon_code: Optional[str] = None,
        user_id: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> PricingCalculation:
        """Calcula el precio final de un plan aplicando descuentos e impuestos."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {plan_id}")

        base_price = plan.price
        discount_amount = 0.0
        coupon_applied: Optional[CouponInfo] = None

        # Aplicar cupón si se proporciona
        if coupon_code:
            coupon = self._coupons_db.get(coupon_code)
            if not coupon or coupon.status != CouponStatus.ACTIVE:
                raise ValueError(f"Cupón inválido o inactivo: {coupon_code}")

            now = datetime.datetime.now(datetime.timezone.utc)
            valid_from = datetime.datetime.fromisoformat(coupon.valid_from)
            if now < valid_from:
                raise ValueError("El cupón aún no es válido")

            if coupon.valid_until:
                valid_until = datetime.datetime.fromisoformat(coupon.valid_until)
                if now > valid_until:
                    raise ValueError("El cupón ha expirado")

            if coupon.applies_to and plan.id not in coupon.applies_to:
                raise ValueError("El cupón no aplica a este plan")

            # Verificar usos por usuario
            if user_id and coupon.max_uses_per_user:
                user_uses = self._coupon_usage.get(user_id, {}).get(coupon_code, 0)
                if user_uses >= coupon.max_uses_per_user:
                    raise ValueError("Has alcanzado el límite de usos de este cupón")

            # Calcular descuento
            if coupon.type == CouponType.PERCENTAGE:
                discount_amount = round(base_price * (coupon.value / 100.0), 2)
            else:
                discount_amount = min(coupon.value, base_price)

            coupon_applied = coupon

        subtotal = max(0.0, round(base_price - discount_amount, 2))

        # Impuestos
        tax_info: Optional[TaxInfo] = None
        tax_amount = 0.0
        if country_code and country_code in self._tax_rates_db:
            tax_info = self._tax_rates_db[country_code]
            tax_amount = round(subtotal * tax_info.tax_rate, 2)

        total = round(subtotal + tax_amount, 2)

        return PricingCalculation(
            plan_id=plan.id,
            plan_name=plan.name,
            base_price=base_price,
            currency=plan.currency,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            coupon_applied=coupon_applied,
            tax_info=tax_info,
            billing_cycle=plan.billing_cycle.value,
        )

    # ── Cupones ─────────────────────────────────────────────────────────

    def list_coupons(self) -> List[CouponInfo]:
        """Lista todos los cupones disponibles."""
        return list(self._coupons_db.values())

    def get_coupon(self, coupon_code: str) -> Optional[CouponInfo]:
        """Obtiene un cupón por su código."""
        return self._coupons_db.get(coupon_code)

    def create_coupon(self, coupon: CouponInfo) -> CouponInfo:
        """Crea un nuevo cupón."""
        self._coupons_db[coupon.code] = coupon
        return coupon

    def apply_coupon(self, req: ApplyCouponRequest) -> ApplyCouponResponse:
        """Aplica un cupón a un plan y retorna el cálculo de precio."""
        pricing = self.calculate_price(
            plan_id=req.plan_id,
            coupon_code=req.coupon_code,
            user_id=req.user_id,
        )
        return ApplyCouponResponse(
            coupon=pricing.coupon_applied,
            original_price=pricing.base_price,
            discount_amount=pricing.discount_amount,
            final_price=pricing.total,
            currency=pricing.currency,
        )

    def record_coupon_usage(self, user_id: str, coupon_code: str) -> None:
        """Registra el uso de un cupón por un usuario."""
        self._coupon_usage.setdefault(user_id, {})
        self._coupon_usage.setdefault(coupon_code, {})
        self._coupon_usage[user_id][coupon_code] = (
            self._coupon_usage[user_id].get(coupon_code, 0) + 1
        )

    # ── Facturación ─────────────────────────────────────────────────────

    def create_invoice(self, req: CreateInvoiceRequest) -> InvoiceInfo:
        """Crea una factura para un plan (con posible cupón e impuestos)."""
        plan = self.get_plan(req.plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {req.plan_id}")

        pricing = self.calculate_price(
            plan_id=req.plan_id,
            coupon_code=req.coupon_code,
            user_id=req.user_id,
        )

        invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
        invoice_number = f"KT-{datetime.datetime.now().strftime('%Y%m%d')}-{invoice_id[-6:].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc)

        items = [
            InvoiceItem(
                description=f"{plan.name} ({plan.billing_cycle.value})",
                quantity=1,
                unit_amount=pricing.base_price,
                amount=pricing.base_price,
                currency=pricing.currency,
            )
        ]
        if pricing.discount_amount > 0:
            items.append(
                InvoiceItem(
                    description=f"Descuento cupón ({pricing.coupon_applied.code if pricing.coupon_applied else 'N/A'})",
                    quantity=1,
                    unit_amount=-pricing.discount_amount,
                    amount=-pricing.discount_amount,
                    currency=pricing.currency,
                )
            )
        if pricing.tax_amount > 0:
            items.append(
                InvoiceItem(
                    description=f"Impuestos ({pricing.tax_info.tax_name if pricing.tax_info else 'N/A'})",
                    quantity=1,
                    unit_amount=pricing.tax_amount,
                    amount=pricing.tax_amount,
                    currency=pricing.currency,
                )
            )

        invoice = InvoiceInfo(
            id=invoice_id,
            invoice_number=invoice_number,
            user_id=req.user_id,
            plan_id=req.plan_id,
            status=InvoiceStatus.OPEN,
            subtotal=pricing.base_price - pricing.discount_amount,
            tax_amount=pricing.tax_amount,
            total=pricing.total,
            currency=pricing.currency,
            items=items,
            issued_at=now.isoformat(),
            due_at=(now + datetime.timedelta(days=30)).isoformat(),
            metadata={
                "coupon_code": req.coupon_code,
                "tax_rate": pricing.tax_info.tax_rate if pricing.tax_info else 0.0,
            },
        )
        self._invoice_db[invoice_id] = invoice
        return invoice

    def get_invoice(self, invoice_id: str) -> Optional[InvoiceInfo]:
        """Obtiene una factura por su ID."""
        return self._invoice_db.get(invoice_id)

    def list_invoices(self, user_id: str) -> List[InvoiceInfo]:
        """Lista facturas de un usuario."""
        return [inv for inv in self._invoice_db.values() if inv.user_id == user_id]

    def mark_invoice_paid(self, invoice_id: str, payment_id: str) -> Optional[InvoiceInfo]:
        """Marca una factura como pagada."""
        invoice = self._invoice_db.get(invoice_id)
        if not invoice:
            return None
        invoice.status = InvoiceStatus.PAID
        invoice.payment_id = payment_id
        invoice.paid_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._invoice_db[invoice_id] = invoice
        return invoice

    # ── Reembolsos ──────────────────────────────────────────────────────

    def create_refund(self, req: CreateRefundRequest) -> RefundResponse:
        """Crea una solicitud de reembolso."""
        payment = self._payment_records_db.get(req.payment_id)
        if not payment:
            raise ValueError(f"Pago no encontrado: {req.payment_id}")

        if payment.status != PaymentRecordStatus.SUCCEEDED:
            raise ValueError("Solo se pueden reembolsar pagos exitosos")

        refund_amount = req.amount if req.amount is not None else payment.amount
        if refund_amount > payment.amount:
            raise ValueError("El monto de reembolso excede el monto del pago")

        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        refund = RefundResponse(
            refund_id=refund_id,
            status=RefundStatus.COMPLETED,  # En modo mock, se completa inmediatamente
            amount=refund_amount,
            currency=payment.currency,
            reason=req.reason,
            created_at=now.isoformat(),
            payment_id=req.payment_id,
            user_id=req.user_id or payment.user_id,
        )
        self._refunds_db[refund_id] = refund
        return refund

    def get_refund(self, refund_id: str) -> Optional[RefundResponse]:
        """Obtiene un reembolso por su ID."""
        return self._refunds_db.get(refund_id)

    def list_refunds(self, user_id: str) -> List[RefundResponse]:
        """Lista reembolsos de un usuario."""
        return [r for r in self._refunds_db.values() if r.user_id == user_id]

    # ── Registro de pagos ───────────────────────────────────────────────

    def record_payment(
        self,
        user_id: str,
        plan_id: str,
        amount: float,
        currency: str = "usd",
        provider: str = "mock",
        provider_payment_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        coupon_code: Optional[str] = None,
        discount_amount: float = 0.0,
        tax_amount: float = 0.0,
        status: PaymentRecordStatus = PaymentRecordStatus.SUCCEEDED,
    ) -> PaymentRecord:
        """Registra un pago en el sistema."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"

        record = PaymentRecord(
            id=payment_id,
            user_id=user_id,
            plan_id=plan_id,
            amount=amount,
            currency=currency,
            status=status,
            provider=provider,
            provider_payment_id=provider_payment_id,
            invoice_id=invoice_id,
            coupon_code=coupon_code,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            created_at=now,
            updated_at=now,
        )
        self._payment_records_db[payment_id] = record
        return record

    def get_payment_record(self, payment_id: str) -> Optional[PaymentRecord]:
        """Obtiene un registro de pago por ID."""
        return self._payment_records_db.get(payment_id)

    def list_payment_records(self, user_id: str) -> List[PaymentRecord]:
        """Lista registros de pago de un usuario."""
        return [p for p in self._payment_records_db.values() if p.user_id == user_id]

    # ── Salud de proveedores ────────────────────────────────────────────

    def check_provider_health(self, provider: str) -> ProviderHealthCheck:
        """Verifica la salud de un proveedor de pago."""
        if provider == PaymentProvider.STRIPE.value:
            if self._stripe_available:
                return ProviderHealthCheck(
                    provider=provider,
                    status=PaymentProviderHealth.HEALTHY,
                    message="Stripe SDK configurado",
                )
            return ProviderHealthCheck(
                provider=provider,
                status=PaymentProviderHealth.UNAVAILABLE,
                message="Stripe no configurado",
            )
        if provider == PaymentProvider.MOCK.value:
            return ProviderHealthCheck(
                provider=provider,
                status=PaymentProviderHealth.HEALTHY,
                message="Modo simulado disponible",
            )
        return ProviderHealthCheck(
            provider=provider,
            status=PaymentProviderHealth.UNAVAILABLE,
            message="Proveedor desconocido",
        )

    def list_providers_health(self) -> List[ProviderHealthCheck]:
        """Lista la salud de todos los proveedores configurados."""
        return [
            self.check_provider_health(PaymentProvider.STRIPE.value),
            self.check_provider_health(PaymentProvider.MOCK.value),
        ]

    # ── Enforzamiento de cuotas ─────────────────────────────────────────

    def enforce_quota_limits(
        self, user_id: str, tokens_needed: int = 0, sessions_needed: int = 0
    ) -> Dict[str, Any]:
        """Verifica si un usuario puede realizar una acción según su cuota."""
        sub = self.get_user_subscription(user_id)
        plan = self.get_plan(sub.plan_id)

        usage = self._usage_db.get(user_id, {"tokens": 0})
        tokens_used = usage.get("tokens", 0)

        can_proceed = True
        reasons: List[str] = []

        if tokens_needed and (tokens_used + tokens_needed) > plan.token_limit_per_month:
            can_proceed = False
            reasons.append(
                f"Límite de tokens excedido: {tokens_used}/{plan.token_limit_per_month}"
            )

        active_sessions = len(usage.get("active_sessions", []))
        if sessions_needed and (active_sessions + sessions_needed) > plan.max_sessions:
            can_proceed = False
            reasons.append(
                f"Límite de sesiones excedido: {active_sessions}/{plan.max_sessions}"
            )

        if sub.status != SubscriptionStatus.ACTIVE:
            can_proceed = False
            reasons.append(f"Suscripción no activa: {sub.status.value}")

        return {
            "can_proceed": can_proceed,
            "reasons": reasons,
            "plan": plan.id,
            "status": sub.status.value,
            "tokens_used": tokens_used,
            "tokens_limit": plan.token_limit_per_month,
            "sessions_active": active_sessions,
            "sessions_limit": plan.max_sessions,
        }

    # ── Webhooks extendidos ─────────────────────────────────────────────

    def handle_mercadopago_webhook_extended(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa webhook de MercadoPago y registra el pago."""
        result = super().handle_mercadopago_webhook(payload)
        if result.get("status") == "success":
            user_id = result.get("user_id")
            plan_id = result.get("plan_id")
            plan = self.get_plan(plan_id)
            if user_id and plan:
                self.record_payment(
                    user_id=user_id,
                    plan_id=plan_id,
                    amount=plan.price,
                    currency=plan.currency,
                    provider="mercadopago",
                    provider_payment_id=payload.get("data", {}).get("id", "unknown"),
                )
        return result


payment_service_extended = PaymentServiceExtended()
