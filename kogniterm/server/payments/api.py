"""
Router REST del sistema de pagos.

Se monta desde ``kogniterm/server/app.py`` con ``include_router``. Va en su
propio archivo (y no dentro de ``app.py``, que ya supera las 3.000 líneas)
para que el dominio de pagos siga siendo navegable por separado.

Todos los handlers delegan en ``PaymentService`` y convierten los errores de
dominio en respuestas HTTP con el código que define cada excepción.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from kogniterm.server.payments import get_payment_service
from kogniterm.server.payments.errors import PaymentError
from kogniterm.server.payments.models import PaymentProviderType

logger = logging.getLogger("kogniterm.payments.api")

router = APIRouter(tags=["Payments"])


# ── Modelos de entrada ───────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Identificador del comprador")
    plan_id: str = Field(..., min_length=1, description="plan_id o pack_id")
    provider: Optional[str] = Field(
        default=None, description="mock|stripe|mercadopago (opcional: usa el activo)"
    )
    idempotency_key: Optional[str] = Field(
        default=None, description="Evita duplicar cobros si el cliente reintenta"
    )


class MockCompleteRequest(BaseModel):
    transaction_id: str
    user_id: Optional[str] = None


class RefundRequest(BaseModel):
    transaction_id: str
    amount_cents: Optional[int] = Field(default=None, ge=1)
    reason: Optional[str] = None
    provider: Optional[str] = None


class CreditGrantRequest(BaseModel):
    user_id: str
    amount: int = Field(..., ge=1)
    reason: str = "manual_grant"


class CreditConsumeRequest(BaseModel):
    user_id: str
    amount: int = Field(..., ge=1)
    reason: str = "usage"


class CredentialRequest(BaseModel):
    provider: PaymentProviderType
    secret_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    enabled: Optional[bool] = None


# ── Utilidades ───────────────────────────────────────────────────────────────


def _handle(fn, *args, **kwargs):
    """Ejecuta ``fn`` traduciendo ``PaymentError`` a HTTP."""
    try:
        return fn(*args, **kwargs)
    except PaymentError as exc:
        logger.info(
            "Error de pagos (%s) en %s: %s", exc.code, getattr(fn, "__name__", "?"), exc.message
        )
        raise HTTPException(status_code=exc.http_status, detail=exc.to_dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "detail": str(exc)})


def _service():
    return get_payment_service()


# ── Catálogo ─────────────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans(include_inactive: bool = Query(default=False)):
    """Planes disponibles, ordenados como deben mostrarse en el pricing."""
    svc = _service()
    return {
        "plans": [p.model_dump(mode="json") for p in svc.get_plans(include_inactive)],
        "credit_packs": [c.model_dump(mode="json") for c in svc.get_credit_packs(include_inactive)],
        "active_provider": svc.settings.active_provider.value,
        "currency": svc.settings.default_currency,
    }


@router.get("/providers")
async def list_providers():
    """Estado de cada proveedor (nunca incluye los secretos)."""
    return _service().provider_status()


# ── Suscripción y entitlements ───────────────────────────────────────────────


@router.get("/subscription/{user_id}")
async def get_subscription(user_id: str = Path(..., min_length=1)):
    """Suscripción + créditos + límites efectivos del usuario."""
    return _service().summary(user_id)


@router.get("/entitlements/{user_id}")
async def get_entitlements(user_id: str = Path(..., min_length=1)):
    """Solo los entitlements (ligero, para checks en caliente)."""
    return _handle(_service().get_entitlements, user_id).to_dict()


@router.get("/transactions/{user_id}")
async def list_transactions(user_id: str, limit: int = Query(default=50, ge=1, le=200)):
    svc = _service()
    txs = svc.store.transactions_for_user(user_id, limit=limit)
    return {"transactions": [tx.model_dump(mode="json") for tx in txs]}


@router.get("/credits/{user_id}/ledger")
async def credit_ledger(user_id: str, limit: int = Query(default=50, ge=1, le=200)):
    """Libro de movimientos de créditos (auditoría de consumo)."""
    svc = _service()
    entries = svc.store.ledger_for_user(user_id, limit=limit)
    return {"entries": [e.model_dump(mode="json") for e in entries]}


# ── Checkout ─────────────────────────────────────────────────────────────────


@router.post("/checkout")
async def create_checkout(payload: CheckoutRequest):
    """Crea la sesión de cobro y devuelve la URL a la que redirigir."""
    return _handle(
        _service().create_checkout,
        payload.user_id,
        payload.plan_id,
        payload.provider,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/mock-checkout/complete")
async def complete_mock_checkout(payload: MockCompleteRequest):
    """Flujo de desarrollo: marca una transacción pendiente como pagada.

    Solo funciona con el proveedor MOCK y sigue requiriendo que el evento
    pase por la verificación de firma.
    """
    svc = _service()
    if svc.settings.active_provider is not PaymentProviderType.MOCK:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "mock_disabled",
                "detail": (
                    "El proveedor activo no es 'mock'. Esta ruta existe solo para "
                    "desarrollo; en producción el pago lo confirma el webhook."
                ),
            },
        )
    return _handle(svc.process_webhook, "mock", _mock_event(payload), _mock_signature(payload))


def _mock_event(payload: MockCompleteRequest) -> bytes:
    import json

    svc = _service()
    tx = svc.store.find_transaction(tx_id=payload.transaction_id)
    if tx is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "transaction_not_found", "detail": payload.transaction_id},
        )
    return json.dumps(
        {
            "event_id": f"evt_mock_{tx.id}",
            "action": "payment.approved",
            "status": "approved",
            "user_id": tx.user_id,
            "plan_id": tx.plan_id,
            "provider_transaction_id": tx.provider_transaction_id or f"mock_pay_{tx.id}",
            "amount_cents": tx.amount_cents,
            "currency": tx.currency,
        }
    ).encode()


def _mock_signature(payload: MockCompleteRequest) -> str:
    """Firma el evento con el secreto MOCK compartido."""
    import hmac
    import hashlib
    import time

    svc = _service()
    secret = svc.credentials.resolve(PaymentProviderType.MOCK).get("webhook_secret")
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "payment_not_configured",
                "detail": (
                    "Define KOGNITERM_MOCK_WEBHOOK_SECRET para usar el flujo simulado."
                ),
            },
        )
    payload_bytes = _mock_event(payload)
    ts = int(time.time())
    digest = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload_bytes, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={digest}"


@router.get("/transactions/{transaction_id:path}/status")
async def transaction_status(transaction_id: str):
    """Consulta el estado de una transacción concreta."""
    svc = _service()
    tx = svc.store.find_transaction(tx_id=transaction_id)
    if tx is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "transaction_not_found", "detail": transaction_id},
        )
    return {"transaction": tx.model_dump(mode="json")}


# ── Reembolsos y créditos ────────────────────────────────────────────────────


@router.post("/refund")
async def create_refund(payload: RefundRequest):
    """Emite un reembolso (total o parcial) y revoca créditos proporcionalmente."""
    return _handle(
        _service().refund,
        payload.transaction_id,
        payload.amount_cents,
        payload.reason,
        payload.provider,
    )


@router.post("/credits/grant")
async def grant_credits(payload: CreditGrantRequest):
    """Otorga créditos manualmente (soporte, promociones, cortesías)."""
    return _handle(
        _service().grant_credits, payload.user_id, payload.amount, payload.reason
    )


@router.post("/credits/consume")
async def consume_credits(payload: CreditConsumeRequest):
    """Descuenta créditos del saldo del usuario."""
    return _handle(
        _service().consume_credits, payload.user_id, payload.amount, payload.reason
    )


# ── Webhooks ─────────────────────────────────────────────────────────────────


@router.post("/webhook/{provider}")
async def payment_webhook(provider: str, request: Request):
    """Recepción de webhooks.

    La firma se verifica **antes** de tocar el estado. Si el evento no es
    verificable se responde 400 y no se procesa nada.
    """
    body = await request.body()
    signature = (
        request.headers.get("stripe-signature")
        or request.headers.get("x-signature")
        or request.headers.get("x-kogniterm-signature")
    )
    svc = _service()
    try:
        result = svc.process_webhook(provider.lower(), body, signature)
    except PaymentError as exc:
        logger.warning(
            "Webhook rechazado (%s) de %s: %s", exc.code, provider, exc.message
        )
        raise HTTPException(status_code=exc.http_status, detail=exc.to_dict())
    except Exception as exc:  # pragma: no cover - red de seguridad
        logger.exception("Fallo inesperado procesando webhook de %s", provider)
        raise HTTPException(
            status_code=500, detail={"error": "internal_error", "detail": str(exc)}
        )
    return result


# ── Administración ───────────────────────────────────────────────────────────


@router.post("/credentials")
async def set_credentials(payload: CredentialRequest):
    """Guarda las credenciales de un proveedor en el almacén de secretos (0600)."""
    svc = _service()
    _handle(
        svc.credentials.set,
        payload.provider,
        secret_key=payload.secret_key,
        webhook_secret=payload.webhook_secret,
        enabled=payload.enabled,
    )
    return {"status": "ok", "providers": svc.credentials.public_view()}


@router.post("/reconcile")
async def reconcile():
    """Degrada a FREE las suscripciones vencidas. Idempotente."""
    return _handle(_service().reconcile_expirations)


@router.get("/audit/verify")
async def verify_audit():
    """Verifica la cadena de hashes de la bitácora de pagos."""
    svc = _service()
    return {"audit": svc.store.verify_audit_chain()}
