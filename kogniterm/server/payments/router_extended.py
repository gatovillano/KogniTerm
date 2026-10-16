"""
Router extendido de FastAPI para endpoints adicionales del sistema de pagos.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, status

from kogniterm.server.payments.models import (
    PaymentProvider,
)
from kogniterm.server.payments.models_extended import (
    CreateRefundRequest, RefundResponse,
    CouponInfo, ApplyCouponRequest, ApplyCouponResponse,
    CreateInvoiceRequest, InvoiceInfo,
    PricingCalculation, TaxInfo,
    PaymentRecord, ProviderHealthCheck,
)
from kogniterm.server.payments.service_extended import payment_service_extended

router = APIRouter(tags=["Pagos y Suscripciones (Extendido)"])


def _extract_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID") or request.headers.get("X-Session-ID")
    if not user_id:
        user_id = f"user_{request.client.host if request.client else 'anonymous'}"
    return user_id


# ── Precios y cupones ───────────────────────────────────────────────────

@router.post("/pricing/calculate", response_model=PricingCalculation, summary="Calcular precio con descuentos e impuestos")
async def calculate_pricing(request: Request, plan_id: str, coupon_code: Optional[str] = None, country_code: Optional[str] = None):
    """Calcula el precio final de un plan aplicando cupón e impuestos por país."""
    user_id = _extract_user_id(request)
    try:
        return payment_service_extended.calculate_price(
            plan_id=plan_id,
            coupon_code=coupon_code,
            user_id=user_id,
            country_code=country_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/coupons", response_model=List[CouponInfo], summary="Listar cupones disponibles")
async def list_coupons():
    return payment_service_extended.list_coupons()


@router.post("/coupons/apply", response_model=ApplyCouponResponse, summary="Aplicar cupón a un plan")
async def apply_coupon(req: ApplyCouponRequest, request: Request):
    user_id = req.user_id or _extract_user_id(request)
    req.user_id = user_id
    try:
        return payment_service_extended.apply_coupon(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Facturación ─────────────────────────────────────────────────────────

@router.post("/invoices", response_model=InvoiceInfo, summary="Crear factura")
async def create_invoice(req: CreateInvoiceRequest, request: Request):
    user_id = req.user_id or _extract_user_id(request)
    req.user_id = user_id
    try:
        return payment_service_extended.create_invoice(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices/{invoice_id}", response_model=InvoiceInfo, summary="Obtener factura")
async def get_invoice(invoice_id: str):
    invoice = payment_service_extended.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


@router.get("/invoices", response_model=List[InvoiceInfo], summary="Listar facturas del usuario")
async def list_invoices(request: Request):
    user_id = _extract_user_id(request)
    return payment_service_extended.list_invoices(user_id)


@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceInfo, summary="Marcar factura como pagada")
async def pay_invoice(invoice_id: str, request: Request, payment_id: Optional[str] = None):
    user_id = _extract_user_id(request)
    invoice = payment_service_extended.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if invoice.user_id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado para esta factura")
    updated = payment_service_extended.mark_invoice_paid(invoice_id, payment_id or f"pay_{invoice_id}")
    if not updated:
        raise HTTPException(status_code=500, detail="Error al marcar factura pagada")
    return updated


# ── Reembolsos ──────────────────────────────────────────────────────────

@router.post("/refunds", response_model=RefundResponse, summary="Solicitar reembolso")
async def create_refund(req: CreateRefundRequest, request: Request):
    user_id = req.user_id or _extract_user_id(request)
    req.user_id = user_id
    try:
        return payment_service_extended.create_refund(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/refunds/{refund_id}", response_model=RefundResponse, summary="Obtener reembolso")
async def get_refund(refund_id: str):
    refund = payment_service_extended.get_refund(refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Reembolso no encontrado")
    return refund


@router.get("/refunds", response_model=List[RefundResponse], summary="Listar reembolsos del usuario")
async def list_refunds(request: Request):
    user_id = _extract_user_id(request)
    return payment_service_extended.list_refunds(user_id)


# ── Registros de pago ───────────────────────────────────────────────────

@router.get("/records", response_model=List[PaymentRecord], summary="Listar registros de pago")
async def list_payment_records(request: Request):
    user_id = _extract_user_id(request)
    return payment_service_extended.list_payment_records(user_id)


@router.get("/records/{payment_id}", response_model=PaymentRecord, summary="Obtener registro de pago")
async def get_payment_record(payment_id: str):
    record = payment_service_extended.get_payment_record(payment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Registro de pago no encontrado")
    return record


# ── Salud de proveedores ────────────────────────────────────────────────

@router.get("/providers/health", response_model=List[ProviderHealthCheck], summary="Estado de proveedores de pago")
async def providers_health():
    return payment_service_extended.list_providers_health()


# ── Enforzamiento de cuotas ─────────────────────────────────────────────

@router.get("/quota/enforce", summary="Verificar límites de cuota antes de una acción")
async def enforce_quota(
    request: Request,
    tokens_needed: int = 0,
    sessions_needed: int = 0,
):
    user_id = _extract_user_id(request)
    return payment_service_extended.enforce_quota_limits(
        user_id=user_id,
        tokens_needed=tokens_needed,
        sessions_needed=sessions_needed,
    )
