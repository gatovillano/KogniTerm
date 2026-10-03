"""
Proveedores de pago (Estrategia).

Cada proveedor implementa el contrato ``PaymentProvider``:

* ``create_checkout``  → devuelve una URL a la que enviar al usuario.
* ``verify_webhook``   → **valida la firma criptográficamente** y devuelve el
  evento normalizado. Si la firma no cuadra lanza ``SignatureVerificationError``
  y el evento jamás se procesa.
* ``parse_event``      → traduce el evento nativo a una acción canónica.
* ``refund``           → reembolso (best-effort con el proveedor).

El proveedor por defecto es ``MockProvider``: no performs red y permite
desarrollar y testear el flujo completo de compra sin credenciales.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from kogniterm.server.payments.errors import (
    ConfigurationError,
    ProviderAPIError,
    SignatureVerificationError,
)
from kogniterm.server.payments.models import (
    CreditPack,
    PaymentProviderType,
    PlanConfig,
    new_id,
)

logger = logging.getLogger("kogniterm.payments.providers")


# ── Eventos canónicos ────────────────────────────────────────────────────────

EVENT_CHECKOUT_COMPLETED = "checkout.completed"
EVENT_PAYMENT_SUCCEEDED = "payment.succeeded"
EVENT_PAYMENT_FAILED = "payment.failed"
EVENT_SUBSCRIPTION_RENEWED = "subscription.renewed"
EVENT_SUBSCRIPTION_CANCELED = "subscription.canceled"
EVENT_SUBSCRIPTION_EXPIRED = "subscription.expired"
EVENT_SUBSCRIPTION_UPDATED = "subscription.updated"
EVENT_PAYMENT_REFUNDED = "payment.refunded"
EVENT_DISPUTED = "payment.disputed"


class NormalizedEvent(BaseModel):
    """Evento de proveedor traducido al vocabulario de KogniTerm."""

    id: str
    type: str
    provider: PaymentProviderType
    user_id: Optional[str] = None
    plan_id: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    provider_customer_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    amount_cents: Optional[int] = None
    refunded_cents: int = 0
    currency: str = "USD"
    period_start: Optional[float] = None
    period_end: Optional[float] = None
    raw: Dict[str, Any] = Field(default_factory=dict, repr=False)
    signature_verified: bool = False
    payload_hash: str = ""


class CheckoutResult(BaseModel):
    """Lo que el proveedor devuelve al crear una sesión de pago."""

    transaction_id: str
    checkout_url: str
    provider: PaymentProviderType
    provider_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    expires_at: Optional[float] = None
    raw: Dict[str, Any] = Field(default_factory=dict, repr=False)


class RefundResult(BaseModel):
    refund_id: str
    transaction_id: str
    amount_cents: int
    provider: PaymentProviderType
    provider_refund_id: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict, repr=False)


# ── Contrato base ────────────────────────────────────────────────────────────


class PaymentProvider(ABC):
    """Interfaz común a todos los proveedores de pago."""

    provider_type: PaymentProviderType

    def __init__(self, credentials: Optional[Dict[str, str]] = None):
        self.credentials = credentials or {}

    # -- ciclo de vida --
    def is_ready(self) -> bool:
        return True

    @abstractmethod
    def create_checkout(
        self,
        *,
        user_id: str,
        item: Any,
        success_url: str,
        cancel_url: str,
        transaction_id: str,
        idempotency_key: str,
        client: Dict[str, Any],
    ) -> CheckoutResult:
        """Crea la sesión de cobro y devuelve la URL de redirección."""

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> Dict[str, Any]:
        """Verifica la firma y devuelve el cuerpo ya validado."""

    @abstractmethod
    def parse_event(self, body: Dict[str, Any]) -> List[NormalizedEvent]:
        """Traduce el cuerpo nativo a eventos canónicos."""

    def refund(
        self,
        *,
        provider_transaction_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
        client: Dict[str, Any],
    ) -> RefundResult:
        raise ProviderAPIError(
            f"El proveedor '{self.provider_type.value}' no implementa reembolsos."
        )

    # -- utilidades --
    @staticmethod
    def payload_hash(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()


# ── Mock (desarrollo / offline) ──────────────────────────────────────────────


class MockProvider(PaymentProvider):
    """Proveedor simulado.

    Genera un token firmado con HMAC usando un secreto efímero del proceso, de
    modo que la ruta del webhook *sí* ejercita la verificación de firma (y no
    una vía que aceptase cualquier payload sin comprobar nada).
    """

    provider_type = PaymentProviderType.MOCK

    SECRET_HEADER = "x-kogniterm-signature"
    TIMESTAMP_HEADER = "x-kogniterm-timestamp"

    def __init__(self, credentials: Optional[Dict[str, str]] = None):
        super().__init__(credentials)
        self._secret = (
            (credentials or {}).get("webhook_secret")
            or self._env("KOGNITERM_MOCK_WEBHOOK_SECRET")
            or secrets.token_hex(32)
        )

    @staticmethod
    def _env(name: str) -> Optional[str]:
        import os

        return os.getenv(name)

    def sign(self, payload: bytes, timestamp: int) -> str:
        signed = f"{timestamp}.".encode() + payload
        digest = hmac.new(self._secret.encode(), signed, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={digest}"

    def is_ready(self) -> bool:
        return True

    def create_checkout(
        self,
        *,
        user_id: str,
        item: Any,
        success_url: str,
        cancel_url: str,
        transaction_id: str,
        idempotency_key: str,
        client: Dict[str, Any],
    ) -> CheckoutResult:
        token = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "tx": transaction_id,
                    "uid": user_id,
                    "plan": getattr(item, "id", ""),
                    "kind": "credit_pack"
                    if isinstance(item, CreditPack)
                    else "subscription",
                    "exp": int(time.time()) + 1800,
                    "nonce": secrets.token_urlsafe(8),
                },
                separators=(",", ":"),
            ).encode()
        ).decode().rstrip("=")

        query = urlencode({"token": token})
        return CheckoutResult(
            transaction_id=transaction_id,
            checkout_url=f"{success_url.rstrip('/').rsplit('/', 1)[0]}/payments/mock-checkout?{query}"
            if "/payment" in success_url
            else f"http://localhost:5173/payments/mock-checkout?{query}",
            provider=self.provider_type,
            provider_transaction_id=f"mock_cs_{transaction_id}",
            idempotency_key=idempotency_key,
            expires_at=time.time() + 1800,
        )

    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> Dict[str, Any]:
        tolerance = 300
        if not signature:
            raise SignatureVerificationError(
                "Falta la firma del webhook. El proveedor MOCK exige "
                f"'{self.SECRET_HEADER}'."
            )
        parts = dict(
            kv.split("=", 1) for kv in signature.split(",") if "=" in kv
        )
        ts_raw, provided = parts.get("t"), parts.get("v1")
        if not ts_raw or not provided:
            raise SignatureVerificationError("Firma mal formada: se espera 't=<ts>,v1=<hex>'.")

        try:
            ts = int(ts_raw)
        except ValueError:
            raise SignatureVerificationError("Timestamp de firma inválido.")

        if abs(time.time() - ts) > tolerance:
            raise SignatureVerificationError(
                "Timestamp de webhook fuera de la ventana de tolerancia "
                f"({tolerance}s). ¿Intento de replay?"
            )

        expected = hmac.new(
            self._secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise SignatureVerificationError("Firma de webhook MOCK inválida.")

        return json.loads(payload.decode("utf-8"))

    def parse_event(self, body: Dict[str, Any]) -> List[NormalizedEvent]:
        action = body.get("action", "payment.approved")
        status = body.get("status", "approved")

        if status in ("rejected", "failed", "cancelled"):
            event_type = EVENT_PAYMENT_FAILED
        elif action == "refund":
            event_type = EVENT_PAYMENT_REFUNDED
        elif action == "subscription.renewed":
            event_type = EVENT_SUBSCRIPTION_RENEWED
        elif action == "subscription.canceled":
            event_type = EVENT_SUBSCRIPTION_CANCELED
        else:
            event_type = EVENT_PAYMENT_SUCCEEDED

        amount = body.get("amount_cents")
        return [
            NormalizedEvent(
                id=body.get("event_id") or new_id("evt"),
                type=event_type,
                provider=self.provider_type,
                user_id=body.get("user_id"),
                plan_id=body.get("plan_id"),
                provider_transaction_id=body.get("provider_transaction_id"),
                amount_cents=amount,
                refunded_cents=body.get("refunded_cents", 0),
                currency=body.get("currency", "USD"),
                signature_verified=True,
                payload_hash=PaymentProvider.payload_hash(
                    json.dumps(body, sort_keys=True).encode()
                ),
                raw=body,
            )
        ]

    def refund(
        self,
        *,
        provider_transaction_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
        client: Dict[str, Any],
    ) -> RefundResult:
        return RefundResult(
            refund_id=new_id("mref"),
            transaction_id=provider_transaction_id,
            amount_cents=amount_cents,
            provider=self.provider_type,
            raw={"simulated": True, "reason": reason},
        )


# ── Stripe ───────────────────────────────────────────────────────────────────


class StripeProvider(PaymentProvider):
    """Integración con Stripe Checkout + firma de webhooks.

    La firma se valida **siempre**: si hay secreto configurado es obligatoria;
    si no lo hay, el proveedor se declara no listo y el servicio lo rechaza
    antes de llegar aquí (nunca se degrada a "parsear sin verificar").
    """

    provider_type = PaymentProviderType.STRIPE
    API = "https://api.stripe.com/v1"

    def is_ready(self) -> bool:
        return bool(self.credentials.get("secret_key"))

    def _require_key(self) -> str:
        key = self.credentials.get("secret_key")
        if not key:
            raise ConfigurationError(
                "Falta la clave secreta de Stripe. Configúrala con "
                "`kogniterm-cli pay config --provider stripe --secret-key sk_...`."
            )
        return key

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        idempotency_key: Optional[str] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        import urllib.error
        import urllib.request

        data = None
        if params:
            data = urlencode(_flatten(params), doseq=True).encode()

        req = urllib.request.Request(f"{self.API}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._require_key()}")
        if idempotency_key:
            req.add_header("Idempotency-Key", idempotency_key)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ProviderAPIError(f"Stripe rechazó la petición ({exc.code}): {detail}")
        except urllib.error.URLError as exc:
            raise ProviderAPIError(f"No se pudo contactar con Stripe: {exc.reason}")

    # -- checkout --
    def create_checkout(
        self,
        *,
        user_id: str,
        item: Any,
        success_url: str,
        cancel_url: str,
        transaction_id: str,
        idempotency_key: str,
        client: Dict[str, Any],
    ) -> CheckoutResult:
        if isinstance(item, CreditPack):
            mode = "payment"
            price_data = {
                "currency": item.currency.lower(),
                "product_data": {
                    "name": item.name,
                    "metadata": {"pack_id": item.id},
                },
                "unit_amount": item.price_cents,
            }
        else:
            mode = "subscription" if item.is_recurring else "payment"
            price_data = {
                "currency": item.currency.lower(),
                "product_data": {"name": item.name, "metadata": {"plan_id": item.id}},
                "unit_amount": item.price_cents,
                "recurring": {"interval": "year" if item.interval.value == "year" else "month"},
            }

        params = {
            "mode": mode,
            "client_reference_id": user_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][price_data][currency]": price_data["currency"],
            "line_items[0][price_data][product_data][name]": price_data["product_data"]["name"],
            "line_items[0][price_data][product_data][metadata][plan_id]": (
                item.id if isinstance(item, PlanConfig) else ""
            ),
            "line_items[0][price_data][unit_amount]": price_data["unit_amount"],
            "line_items[0][quantity]": 1,
            "metadata[user_id]": user_id,
            "metadata[transaction_id]": transaction_id,
            "metadata[kind]": (
                "credit_pack" if isinstance(item, CreditPack) else "subscription"
            ),
        }
        if not isinstance(item, CreditPack) and item.is_recurring:
            params["subscription_data[metadata][plan_id]"] = item.id
            params["subscription_data[metadata][user_id]"] = user_id
            params["subscription_data[metadata][transaction_id]"] = transaction_id
            if item.trial_days:
                params["subscription_data[trial_period_days]"] = item.trial_days
        elif not isinstance(item, CreditPack):
            params["payment_intent_data[metadata][transaction_id]"] = transaction_id

        session = self._request(
            "POST", "/checkout/sessions", params, idempotency_key=idempotency_key
        )
        return CheckoutResult(
            transaction_id=transaction_id,
            checkout_url=session.get("url", ""),
            provider=self.provider_type,
            provider_transaction_id=session.get("id"),
            idempotency_key=idempotency_key,
            raw=session,
        )

    # -- webhooks --
    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> Dict[str, Any]:
        secret = self.credentials.get("webhook_secret")
        if not secret:
            raise ConfigurationError(
                "Falta STRIPE_WEBHOOK_SECRET: sin él no se puede verificar la "
                "firma y el sistema rechaza procesar el evento (por seguridad)."
            )
        if not signature:
            raise SignatureVerificationError("Falta la cabecera 'stripe-signature'.")

        header_parts = dict(
            kv.split("=", 1) for kv in signature.split(",") if "=" in kv
        )
        ts_raw = header_parts.get("t")
        provided = header_parts.get("v1")
        if not ts_raw or not provided:
            raise SignatureVerificationError("Cabecera 'stripe-signature' mal formada.")

        tolerance = int(self.credentials.get("tolerance", 300))
        try:
            ts = int(ts_raw)
        except ValueError:
            raise SignatureVerificationError("Timestamp de firma inválido.")
        if abs(time.time() - ts) > tolerance:
            raise SignatureVerificationError(
                f"Evento fuera de la ventana de tolerancia ({tolerance}s)."
            )

        signed = f"{ts_raw}.".encode() + payload
        expected = hmac.new(
            secret.encode(), signed, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise SignatureVerificationError("Firma de webhook de Stripe inválida.")

        return json.loads(payload.decode("utf-8"))

    def parse_event(self, body: Dict[str, Any]) -> List[NormalizedEvent]:
        event_type = body.get("type", "")
        obj = body.get("data", {}).get("object", {}) or {}
        meta = obj.get("metadata", {}) or {}
        base = {
            "id": body.get("id") or new_id("evt"),
            "provider": self.provider_type,
            "user_id": meta.get("user_id") or obj.get("client_reference_id"),
            "plan_id": meta.get("plan_id") or meta.get("pack_id"),
            "currency": (obj.get("currency") or "usd").upper(),
            "signature_verified": True,
            "payload_hash": PaymentProvider.payload_hash(
                json.dumps(body, sort_keys=True).encode()
            ),
            "raw": obj,
        }

        def ev(**kw: Any) -> NormalizedEvent:
            return NormalizedEvent(**{**base, **kw})

        if event_type == "checkout.session.completed":
            if obj.get("payment_status") not in ("paid", "no_payment_required", None):
                return [
                    ev(
                        type=EVENT_PAYMENT_FAILED,
                        provider_transaction_id=obj.get("id"),
                        amount_cents=obj.get("amount_total"),
                    )
                ]
            return [
                ev(
                    type=EVENT_PAYMENT_SUCCEEDED,
                    provider_transaction_id=obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("subscription"),
                    amount_cents=obj.get("amount_total"),
                )
            ]

        if event_type == "invoice.paid":
            lines = (obj.get("lines", {}) or {}).get("data", []) or []
            plan_id = meta.get("plan_id")
            for line in lines:
                meta_line = (line.get("metadata") or {})
                plan_id = plan_id or meta_line.get("plan_id")

            return [
                ev(
                    type=EVENT_SUBSCRIPTION_RENEWED,
                    provider_transaction_id=obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("subscription") or obj.get("id"),
                    amount_cents=obj.get("amount_paid"),
                    period_start=_iso(obj.get("period_start")),
                    period_end=_iso(obj.get("period_end")),
                )
            ]

        if event_type == "invoice.payment_failed":
            return [
                ev(
                    type=EVENT_SUBSCRIPTION_EXPIRED,
                    provider_transaction_id=obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("subscription"),
                    amount_cents=obj.get("amount_due"),
                )
            ]

        if event_type in (
            "customer.subscription.updated",
            "customer.subscription.created",
        ):
            action = EVENT_SUBSCRIPTION_UPDATED
            status = obj.get("status")
            if status == "canceled":
                action = EVENT_SUBSCRIPTION_CANCELED
            elif status in ("past_due", "unpaid", "incomplete_expired"):
                action = EVENT_SUBSCRIPTION_EXPIRED
            return [
                ev(
                    type=action,
                    provider_transaction_id=obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("id"),
                    period_start=_iso((obj.get("current_period_start") and obj)),
                    period_end=_iso(obj.get("current_period_end")),
                )
            ]

        if event_type == "customer.subscription.deleted":
            return [
                ev(
                    type=EVENT_SUBSCRIPTION_CANCELED,
                    provider_transaction_id=obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    provider_subscription_id=obj.get("id"),
                )
            ]

        if event_type == "charge.refunded":
            return [
                ev(
                    type=EVENT_PAYMENT_REFUNDED,
                    provider_transaction_id=obj.get("payment_intent")
                    or obj.get("id"),
                    provider_customer_id=obj.get("customer"),
                    amount_cents=obj.get("amount"),
                    refunded_cents=obj.get("amount_refunded", 0),
                )
            ]

        if event_type == "charge.dispute.created":
            return [
                ev(
                    type=EVENT_DISPUTED,
                    provider_transaction_id=obj.get("payment_intent"),
                    provider_customer_id=obj.get("customer"),
                    amount_cents=obj.get("amount"),
                )
            ]

        return [ev(type="unhandled", provider_transaction_id=obj.get("id"))]

    def refund(
        self,
        *,
        provider_transaction_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
        client: Dict[str, Any],
    ) -> RefundResult:
        params: Dict[str, Any] = {"payment_intent": provider_transaction_id}
        if amount_cents:
            params["amount"] = amount_cents
        if reason:
            params["reason"] = reason

        result = self._request("POST", "/refunds", params)
        return RefundResult(
            refund_id=new_id("sref"),
            transaction_id=provider_transaction_id,
            amount_cents=result.get("amount", amount_cents),
            provider=self.provider_type,
            provider_refund_id=result.get("id"),
            raw=result,
        )


# ── MercadoPago ──────────────────────────────────────────────────────────────


class MercadoPagoProvider(PaymentProvider):
    """Integración con MercadoPago (Preferencias + validación por consulta).

    A diferencia de Stripe, MercadoPago no firma el cuerpo del webhook con
    HMAC: manda un ``secret-key`` en la query y su firma llega en el campo
    ``x-signature``. La verificación exige:
      1. La query con ``id`` + ``secret-key`` que produce el ``data.id``.
      2. ``ts`` + el cuerpo firmados con HMAC-SHA256.
    Tras validar, el estado real del pago se **confirma consultando la API**
    (el webhook por sí solo nunca activa una suscripción).
    """

    provider_type = PaymentProviderType.MERCADOPAGO
    API = "https://api.mercadopago.com"

    def is_ready(self) -> bool:
        return bool(self.credentials.get("secret_key"))

    def _require_key(self) -> str:
        key = self.credentials.get("secret_key")
        if not key:
            raise ConfigurationError(
                "Falta el access token de MercadoPago. Configúralo con "
                "`kogniterm-cli pay config --provider mercadopago --secret-key ...`."
            )
        return key

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        import urllib.error
        import urllib.request

        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"{self.API}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._require_key()}")
        if payload is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ProviderAPIError(
                f"MercadoPago rechazó la petición ({exc.code}): {detail}"
            )
        except urllib.error.URLError as exc:
            raise ProviderAPIError(f"No se pudo contactar con MercadoPago: {exc.reason}")

    def create_checkout(
        self,
        *,
        user_id: str,
        item: Any,
        success_url: str,
        cancel_url: str,
        transaction_id: str,
        idempotency_key: str,
        client: Dict[str, Any],
    ) -> CheckoutResult:
        base = client.get("success_url_base") or "http://localhost:5173"
        payload = {
            "items": [
                {
                    "title": item.name,
                    "quantity": 1,
                    "unit_price": item.price_cents / 100.0,
                    "currency_id": item.currency.upper(),
                    "description": getattr(item, "description", "") or item.name,
                }
            ],
            "back_urls": {
                "success": success_url,
                "failure": cancel_url,
                "pending": cancel_url,
            },
            "auto_return": "approved",
            "external_reference": transaction_id,
            "notification_url": f"{base}/api/payments/webhook/mercadopago",
            "metadata": {"user_id": user_id, "kind": "credit_pack" if isinstance(item, CreditPack) else "subscription"},
        }
        pref = self._request("POST", "/checkout/preferences", payload=payload)
        return CheckoutResult(
            transaction_id=transaction_id,
            checkout_url=pref.get("init_point") or pref.get("sandbox_init_point", ""),
            provider=self.provider_type,
            provider_transaction_id=pref.get("id"),
            idempotency_key=idempotency_key,
            raw=pref,
        )

    def verify_webhook(self, payload: bytes, signature: Optional[str]) -> Dict[str, Any]:
        secret = self.credentials.get("webhook_secret")
        if not secret:
            raise ConfigurationError(
                "Falta MERCADOPAGO_WEBHOOK_SECRET: sin él no se puede validar "
                "x-signature y el evento se rechaza por seguridad."
            )
        if not signature:
            raise SignatureVerificationError("Falta la cabecera 'x-signature'.")

        parts = dict(kv.split("=", 1) for kv in signature.split(",") if "=" in kv)
        ts_raw, provided = parts.get("ts"), parts.get("v1")
        if not ts_raw or not provided:
            raise SignatureVerificationError("Cabecera 'x-signature' mal formada.")

        tolerance = int(self.credentials.get("tolerance", 300))
        try:
            ts = int(ts_raw)
        except ValueError:
            raise SignatureVerificationError("Timestamp de firma inválido.")
        if abs(time.time() - ts) > tolerance:
            raise SignatureVerificationError(
                f"Evento fuera de la ventana de tolerancia ({tolerance}s)."
            )

        expected = hmac.new(
            secret.encode(), f"{ts_raw}{payload}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise SignatureVerificationError("Firma de webhook de MercadoPago inválida.")

        return json.loads(payload.decode("utf-8"))

    def parse_event(self, body: Dict[str, Any]) -> List[NormalizedEvent]:
        action = (body.get("action") or "").lower()
        payment_id = str(body.get("data", {}).get("id") or "")

        if not payment_id:
            return []

        # Confirmación real contra la API: el cuerpo del webhook no es fuente
        # de verdad, así que consultamos el estado del pago.
        payment = self._request("GET", f"/v1/payments/{payment_id}")
        status = payment.get("status")
        approved = status == "approved"
        refunded = (payment.get("status_details") or {}).get("refunded")

        external_ref = payment.get("external_reference") or ""
        amount_cents = int(round(float(payment.get("transaction_amount", 0)) * 100))
        currency = (payment.get("currency_id") or "USD").upper()
        metadata = payment.get("metadata") or {}

        if action.startswith("refund") or refunded:
            event_type = EVENT_PAYMENT_REFUNDED
            refunded_cents = int(round(float(refunded or 0) * 100))
        elif action.startswith("chargeback") or status == "chargeback":
            event_type = EVENT_DISPUTED
            refunded_cents = 0
        elif approved:
            event_type = EVENT_PAYMENT_SUCCEEDED
            refunded_cents = 0
        elif status in ("rejected", "cancelled", "charged_back"):
            event_type = EVENT_PAYMENT_FAILED
            refunded_cents = 0
        else:
            # pending / in_process / authorized → todavía no se cobra nada.
            return [
                NormalizedEvent(
                    id=payment_id,
                    type="payment.pending",
                    provider=self.provider_type,
                    provider_transaction_id=payment_id,
                    amount_cents=amount_cents,
                    currency=currency,
                    signature_verified=True,
                    raw=payment,
                )
            ]

        user_id = metadata.get("user_id")
        if external_ref and not user_id:
            user_id = external_ref

        return [
            NormalizedEvent(
                id=payment_id,
                type=event_type,
                provider=self.provider_type,
                user_id=user_id,
                plan_id=metadata.get("plan_id") or metadata.get("pack_id"),
                provider_transaction_id=payment_id,
                provider_customer_id=str(payment.get("payer", {}).get("id") or "") or None,
                amount_cents=amount_cents,
                refunded_cents=refunded_cents,
                currency=currency,
                signature_verified=True,
                payload_hash=PaymentProvider.payload_hash(
                    json.dumps(body, sort_keys=True).encode()
                ),
                raw=payment,
            )
        ]

    def refund(
        self,
        *,
        provider_transaction_id: str,
        amount_cents: int,
        reason: Optional[str] = None,
        client: Dict[str, Any],
    ) -> RefundResult:
        result = self._request(
            "POST", f"/v1/payments/{provider_transaction_id}/refunds",
            payload={"amount": amount_cents / 100.0},
        )
        return RefundResult(
            refund_id=new_id("mpref"),
            transaction_id=provider_transaction_id,
            amount_cents=result.get("amount", amount_cents / 100),
            provider=self.provider_type,
            provider_refund_id=str(result.get("id")) if result.get("id") else None,
            raw=result,
        )


# ── Fábrica ──────────────────────────────────────────────────────────────────

PROVIDER_CLASSES = {
    PaymentProviderType.MOCK: MockProvider,
    PaymentProviderType.STRIPE: StripeProvider,
    PaymentProviderType.MERCADOPAGO: MercadoPagoProvider,
}


def build_provider(
    provider: PaymentProviderType, credentials: Optional[Dict[str, str]] = None
) -> PaymentProvider:
    cls = PROVIDER_CLASSES.get(provider)
    if cls is None:
        raise ConfigurationError(f"Proveedor de pago desconocido: '{provider}'")
    return cls(credentials)


def available_providers() -> List[str]:
    return [p.value for p in PaymentProviderType]


# ── Utilidades ───────────────────────────────────────────────────────────────


def _flatten(params: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Aplana un dict anidado al formato ``a[b][c]=v`` que espera Stripe."""
    out: Dict[str, Any] = {}
    for key, value in params.items():
        full = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, full))
        else:
            out[full] = "" if value is None else value
    return out


def _iso(value: Any) -> Optional[float]:
    """Convierte timestamps de Stripe (epoch o ISO-8601) a epoch float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None
