"""
Catálogo por defecto de planes y paquetes de créditos.

Los valores pueden sobrescribirse desde `~/.kogniterm/payments_data.json`
(campo `settings.plans`) o mediante las variables de entorno:

    KOGNITERM_PAYMENT_PROVIDER   proveedor activo (mock|stripe|mercadopago)
    KOGNITERM_PAYMENTS_FILE      ruta del almacén
    KOGNITERM_FREE_CREDITS       créditos otorgados al plan gratuito
    KOGNITERM_PUBLIC_BASE_URL    base URL para redirecciones de checkout
"""

from __future__ import annotations

import os
from typing import List

from kogniterm.server.payments.models import (
    BillingInterval,
    CreditPack,
    PlanConfig,
    SubscriptionTier,
)

#: Límites por tier. El plan puede endurecerlos, nunca relajarlos.
TIER_LIMITS = {
    SubscriptionTier.FREE: {
        "agents_per_session": 2,
        "parallel_subagents": 1,
        "skills_enabled": 15,
        "workspace_index_mb": 256,
        "max_heartbeats": 0,
        "custom_llm_providers": 0,
    },
    SubscriptionTier.PRO: {
        "agents_per_session": 8,
        "parallel_subagents": 3,
        "skills_enabled": 60,
        "workspace_index_mb": 4096,
        "max_heartbeats": 10,
        "custom_llm_providers": 5,
    },
    SubscriptionTier.ENTERPRISE: {
        "agents_per_session": 32,
        "parallel_subagents": 8,
        "skills_enabled": 999,
        "workspace_index_mb": 65536,
        "max_heartbeats": 100,
        "custom_llm_providers": 50,
    },
}


def _default_plans() -> List[PlanConfig]:
    free_credits = int(os.getenv("KOGNITERM_FREE_CREDITS", "100"))
    return [
        PlanConfig(
            id="free_plan",
            name="Free",
            tier=SubscriptionTier.FREE,
            price_cents=0,
            interval=BillingInterval.MONTH,
            credits_included=free_credits,
            description="Prueba KogniTerm sin límite de tiempo.",
            features=[
                "Acceso a la CLI y al servidor local",
                f"{free_credits:,} créditos de IA al mes".replace(",", "."),
                "Indexación semántica del workspace",
                "Soporte por comunidad",
            ],
            sort_order=0,
        ),
        PlanConfig(
            id="pro_monthly",
            name="Pro Mensual",
            tier=SubscriptionTier.PRO,
            price_cents=1999,
            interval=BillingInterval.MONTH,
            credits_included=5000,
            trial_days=7,
            popular=True,
            description="Para uso diario y equipos pequeños.",
            features=[
                "Todo lo del plan Free",
                "5.000 créditos mensuales",
                "Agentes dinámicos ilimitados (hasta 8 por sesión)",
                "3 subagentes en paralelo",
                "Modelos avanzados y proveedores propios",
                "Heartbeats programados",
            ],
            sort_order=1,
        ),
        PlanConfig(
            id="pro_annual",
            name="Pro Anual",
            tier=SubscriptionTier.PRO,
            price_cents=19900,
            interval=BillingInterval.YEAR,
            credits_included=5000,
            trial_days=14,
            description="Dos meses gratis frente al plan mensual.",
            features=[
                "Todo lo de Pro Mensual",
                "5.000 créditos cada mes durante 12 meses",
                "Ahorro del 17% anual",
                "14 días de prueba",
            ],
            sort_order=2,
        ),
        PlanConfig(
            id="enterprise_annual",
            name="Enterprise",
            tier=SubscriptionTier.ENTERPRISE,
            price_cents=79900,
            interval=BillingInterval.YEAR,
            credits_included=20000,
            description="Autonomía total con SLA y soporte dedicado.",
            features=[
                "Todo lo de Pro",
                "Agentes ilimitados y 8 subagentes en paralelo",
                "Heartbeats y webhooksSin límite",
                "SLA 24/7 con canal directo",
                "Despliegue autoalojado",
            ],
            sort_order=3,
        ),
    ]


def _default_credit_packs() -> List[CreditPack]:
    return [
        CreditPack(
            id="credits_5k",
            name="Paquete 5.000 créditos",
            credits=5000,
            price_cents=990,
            description="Créditos adicionales de pago único.",
            sort_order=0,
        ),
        CreditPack(
            id="credits_25k",
            name="Paquete 25.000 créditos",
            credits=25000,
            bonus_credits=2500,
            price_cents=3990,
            description="10% de créditos de regalo.",
            sort_order=1,
        ),
    ]


def default_settings_kwargs() -> dict:
    """Argumentos para construir ``PaymentSettings`` con el catálogo por defecto."""
    return {
        "plans": _default_plans(),
        "credit_packs": _default_credit_packs(),
        "public_base_url": os.getenv(
            "KOGNITERM_PUBLIC_BASE_URL", "http://localhost:5173"
        ),
        "active_provider": _env_provider(),
    }


def _env_provider():
    from kogniterm.server.payments.models import PaymentProviderType

    raw = os.getenv("KOGNITERM_PAYMENT_PROVIDER", "mock").strip().lower()
    try:
        return PaymentProviderType(raw)
    except ValueError:
        return PaymentProviderType.MOCK
