"""
Jerarquía de errores del sistema de pagos de KogniTerm.

Permite a la capa HTTP mapear excepciones a códigos de estado específicos
sin acoplar la lógica de negocio a FastAPI.
"""

from __future__ import annotations


class PaymentError(Exception):
    """Error base del dominio de pagos."""

    http_status: int = 400
    code: str = "payment_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        payload = {"error": self.code, "detail": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class ConfigurationError(PaymentError):
    """Falta o es inválida la configuración de un proveedor (API keys, etc.)."""

    http_status = 503
    code = "payment_not_configured"


class PlanNotFoundError(PaymentError):
    http_status = 404
    code = "plan_not_found"


class TransactionNotFoundError(PaymentError):
    http_status = 404
    code = "transaction_not_found"


class SubscriptionNotFoundError(PaymentError):
    http_status = 404
    code = "subscription_not_found"


class InvalidStateError(PaymentError):
    """La operación no es válida para el estado actual del objeto."""

    http_status = 409
    code = "invalid_state"


class SignatureVerificationError(PaymentError):
    """Firma de webhook ausente o inválida. NUNCA se procesa el evento."""

    http_status = 400
    code = "invalid_signature"


class InsufficientCreditsError(PaymentError):
    http_status = 402
    code = "insufficient_credits"


class EntitlementDeniedError(PaymentError):
    """El usuario no tiene el plan requerido para usar la funcionalidad."""

    http_status = 403
    code = "entitlement_denied"


class ProviderAPIError(PaymentError):
    """El proveedor externo rechazó la operación."""

    http_status = 502
    code = "provider_error"


class StorageError(PaymentError):
    http_status = 500
    code = "storage_error"
