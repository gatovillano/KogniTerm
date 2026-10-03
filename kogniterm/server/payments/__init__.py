"""
Sistema de pagos y suscripciones de KogniTerm.

Punto de entrada público del paquete. Mantiene la API que el resto del
proyecto ya importaba (``payment_service``, ``PaymentService``,
``SubscriptionTier``, ``PaymentProviderType``, ``PaymentStatus``) pero ahora
resuelve el servicio **de forma perezosa**, de modo que importar este paquete
no abre ni escribe el almacén de pagos.

Uso típico::

    from kogniterm.server.payments import get_payment_service

    service = get_payment_service()
    checkout = service.create_checkout("user-1", "pro_monthly")
"""

from __future__ import annotations

from typing import Any

from kogniterm.server.payments.credentials import CredentialStore
from kogniterm.server.payments.entitlements import (
    Entitlements,
    build_entitlements,
    effective_tier,
    require_credits,
    require_tier,
)
from kogniterm.server.payments.errors import (
    ConfigurationError,
    EntitlementDeniedError,
    InsufficientCreditsError,
    InvalidStateError,
    PaymentError,
    PlanNotFoundError,
    ProviderAPIError,
    SignatureVerificationError,
    StorageError,
    SubscriptionNotFoundError,
    TransactionNotFoundError,
)
from kogniterm.server.payments.models import (
    BillingInterval,
    CreditLedgerEntry,
    CreditPack,
    PaymentData,
    PaymentProviderType,
    PaymentSettings,
    PaymentStatus,
    PlanConfig,
    ProviderCredentials,
    RefundRecord,
    SubscriptionStatus,
    SubscriptionTier,
    TransactionRecord,
    UserSubscription,
    WebhookEvent,
)
from kogniterm.server.payments.service import (
    PaymentService,
    get_payment_service,
    reset_payment_service,
)
from kogniterm.server.payments.store import PaymentStore, resolve_data_file

__all__ = [
    # Servicio
    "PaymentService",
    "get_payment_service",
    "reset_payment_service",
    "PaymentStore",
    "CredentialStore",
    "resolve_data_file",
    # Modelos (compatibilidad con el módulo anterior)
    "SubscriptionTier",
    "PaymentProviderType",
    "PaymentStatus",
    "SubscriptionStatus",
    "BillingInterval",
    "PlanConfig",
    "CreditPack",
    "TransactionRecord",
    "UserSubscription",
    "RefundRecord",
    "CreditLedgerEntry",
    "WebhookEvent",
    "PaymentSettings",
    "PaymentData",
    "ProviderCredentials",
    # Entitlements
    "Entitlements",
    "build_entitlements",
    "effective_tier",
    "require_tier",
    "require_credits",
    # Errores
    "PaymentError",
    "ConfigurationError",
    "PlanNotFoundError",
    "TransactionNotFoundError",
    "SubscriptionNotFoundError",
    "InvalidStateError",
    "SignatureVerificationError",
    "InsufficientCreditsError",
    "EntitlementDeniedError",
    "ProviderAPIError",
    "StorageError",
    # Proxy perezoso
    "payment_service",
]


class _LazyPaymentService:
    """Proxy que construye el ``PaymentService`` en el primer uso real.

    Existe por compatibilidad con ``from ... import payment_service``: el
    atributo se materializa como instancia solo cuando se toca, así que importar
    el paquete no crea el archivo de pagos ni carga el catálogo.
    """

    __slots__ = ("_target",)

    def __init__(self) -> None:
        object.__setattr__(self, "_target", None)

    def _resolve(self) -> PaymentService:
        target = object.__getattribute__(self, "_target")
        if target is None:
            target = get_payment_service()
            object.__setattr__(self, "_target", target)
        return target

    def __getattr__(self, item: str) -> Any:
        return getattr(self._resolve(), item)

    def __setattr__(self, key: str, value: Any) -> None:
        setattr(self._resolve(), key, value)

    def __repr__(self) -> str:
        return f"<LazyPaymentService target={object.__getattribute__(self, '_target')!r}>"

    # Debe delegar en la clase para que isinstance() siga funcionando.
    def __class_getitem__(cls, item):  # pragma: no cover
        return cls


#: Instancia perezosa del servicio (compatible con el módulo anterior).
payment_service = _LazyPaymentService()
