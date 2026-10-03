"""
Entitlements: traducción de "plan contratado" a "capacidades permitidas".

Un único punto de decisión para todo el sistema. Evita que cada módulo
reimplemente comparaciones de tiers y, sobre todo, impide que un usuario
con un plan caducado conserve acceso por accidente.

Reglas:

* Los límites base salen del tier (ver ``catalog.TIER_LIMITS``).
* Un plan puede **endurecer** límites, nunca relajarlos por debajo del tier.
* Un plan expirado cae a los límites del plan gratuito, salvo que el tier
  siga siendo válido por un pago one_time ya liquidado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from kogniterm.server.payments.catalog import TIER_LIMITS
from kogniterm.server.payments.errors import EntitlementDeniedError
from kogniterm.server.payments.models import (
    PlanConfig,
    SubscriptionStatus,
    SubscriptionTier,
    UserSubscription,
)


@dataclass(frozen=True)
class Entitlements:
    """Capacidades efectivas de un usuario en un instante concreto."""

    user_id: str
    tier: SubscriptionTier
    plan_id: str
    status: SubscriptionStatus
    credits_remaining: int
    limits: Dict[str, int] = field(default_factory=dict)
    days_remaining: Optional[int] = None
    cancel_at_period_end: bool = False

    def allows(self, feature: str) -> bool:
        return self.limits.get(feature, 0) > 0

    def limit(self, feature: str) -> int:
        return self.limits.get(feature, 0)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "tier": self.tier.value,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "credits_remaining": self.credits_remaining,
            "days_remaining": self.days_remaining,
            "cancel_at_period_end": self.cancel_at_period_end,
            "limits": dict(self.limits),
        }


def effective_tier(sub: Optional[UserSubscription]) -> SubscriptionTier:
    """Tier efectivo: si venció o fue cancelado, degrada a FREE."""
    if sub is None:
        return SubscriptionTier.FREE
    if sub.status == SubscriptionStatus.CANCELED:
        return SubscriptionTier.FREE
    if sub.is_expired:
        return SubscriptionTier.FREE
    if not sub.active:
        return SubscriptionTier.FREE
    return sub.tier


def build_entitlements(
    sub: Optional[UserSubscription], plan: Optional[PlanConfig] = None
) -> Entitlements:
    tier = effective_tier(sub)
    limits = dict(TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE]))

    if plan and tier != SubscriptionTier.FREE:
        for key, value in (plan.limits or {}).items():
            # El plan solo puede endurecer: max(base, valor_del_plan).
            limits[key] = max(limits.get(key, 0), int(value))

    return Entitlements(
        user_id=sub.user_id if sub else "",
        tier=tier,
        plan_id=(sub.plan_id if sub else "free_plan"),
        status=sub.status if sub else SubscriptionStatus.ACTIVE,
        credits_remaining=sub.credits_remaining if sub else 0,
        limits=limits,
        days_remaining=sub.days_remaining() if sub else None,
        cancel_at_period_end=bool(sub.cancel_at_period_end) if sub else False,
    )


def require_tier(
    sub: Optional[UserSubscription], minimum: SubscriptionTier, feature: str = "la función"
) -> None:
    """Lanza ``EntitlementDeniedError`` si el usuario no alcanza el tier pedido."""
    if not SubscriptionTier.at_least(effective_tier(sub), minimum):
        raise EntitlementDeniedError(
            f"{feature} requiere el plan {minimum.value.upper()} o superior.",
            details={
                "required_tier": minimum.value,
                "current_tier": effective_tier(sub).value,
                "feature": feature,
            },
        )


def require_credits(sub: Optional[UserSubscription], amount: int) -> None:
    """Lanza ``InsufficientCreditsError`` si el saldo no cubre ``amount``."""
    balance = sub.credits_remaining if sub else 0
    if balance < amount:
        from kogniterm.server.payments.errors import InsufficientCreditsError

        raise InsufficientCreditsError(
            f"Saldo insuficiente: se requieren {amount} créditos y hay {balance}.",
            details={"required": amount, "available": balance},
        )


def snapshot_is_valid(sub: Optional[UserSubscription]) -> bool:
    """El plan de pago único (lifetime/one_time) sobrevive a la expiración."""
    if sub is None or not sub.active:
        return False
    if sub.is_expired and sub.tier == SubscriptionTier.FREE:
        return False
    return sub.status in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
    )
