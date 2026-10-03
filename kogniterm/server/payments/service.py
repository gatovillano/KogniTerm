"""
``PaymentService``: orquestador del sistema de pagos.

Responsabilidades:

* Catálogo (planes, paquetes, límites).
* Ciclo de vida de suscripciones: alta, renovación, cancelación, expiración,
  reembolso y downgrade automático.
* Libro de créditos con saldo auditable (cada movimiento deja asiento).
* Intake de webhooks: **verificar firma → deduplicar → aplicar**.
* Reembolsos, con revocación proporcional de créditos.
* Idempotencia a dos niveles: por evento de proveedor y por clave de checkout.

Todas las operaciones que mutan estado pasan por ``store.transaction()``,
que persiste de forma atómica y revierte los cambios en memoria si algo falla.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from kogniterm.server.payments import providers as prov
from kogniterm.server.payments.credentials import CredentialStore
from kogniterm.server.payments.entitlements import (
    Entitlements,
    build_entitlements,
    effective_tier,
)
from kogniterm.server.payments.errors import (
    ConfigurationError,
    InvalidStateError,
    PlanNotFoundError,
    ProviderAPIError,
    TransactionNotFoundError,
)
from kogniterm.server.payments.models import (
    BillingInterval,
    CreditLedgerEntry,
    CreditPack,
    PaymentProviderType,
    PaymentStatus,
    PlanConfig,
    RefundRecord,
    SubscriptionStatus,
    SubscriptionTier,
    TransactionRecord,
    UserSubscription,
    WebhookEvent,
    new_id,
    now,
)
from kogniterm.server.payments.store import PaymentStore

logger = logging.getLogger("kogniterm.payments")

#: Duración de un periodo según el intervalo del plan (segundos).
PERIOD_SECONDS = {
    BillingInterval.MONTH: 30 * 86400,
    BillingInterval.YEAR: 365 * 86400,
    BillingInterval.ONE_TIME: None,
    BillingInterval.LIFETIME: None,
}

ItemType = Union[PlanConfig, CreditPack]


class PaymentService:
    """Fachada única del dominio de pagos."""

    def __init__(
        self,
        store: Optional[PaymentStore] = None,
        credentials: Optional[CredentialStore] = None,
    ):
        self.store = store or PaymentStore()
        self.credentials = credentials or CredentialStore()
        # Serializa el ciclo completo checkout→webhook→créditos.
        self._mutation_lock = threading.RLock()

    # ── Catálogo ─────────────────────────────────────────────────────────────

    @property
    def settings(self):
        return self.store.data.settings

    def get_plans(self, include_inactive: bool = False) -> List[PlanConfig]:
        plans = [p for p in self.settings.plans if include_inactive or p.active]
        return sorted(plans, key=lambda p: p.sort_order)

    def get_plan(self, plan_id: str, *, must_be_active: bool = True) -> PlanConfig:
        plan = next((p for p in self.settings.plans if p.id == plan_id), None)
        if plan is None:
            raise PlanNotFoundError(
                f"El plan '{plan_id}' no existe.", details={"plan_id": plan_id}
            )
        if must_be_active and not plan.active:
            raise PlanNotFoundError(
                f"El plan '{plan_id}' ya no está disponible.",
                details={"plan_id": plan_id},
            )
        return plan

    def get_credit_packs(self, include_inactive: bool = False) -> List[CreditPack]:
        packs = [c for c in self.settings.credit_packs if include_inactive or c.active]
        return sorted(packs, key=lambda c: c.sort_order)

    def get_credit_pack(self, pack_id: str) -> CreditPack:
        pack = next((c for c in self.settings.credit_packs if c.id == pack_id), None)
        if pack is None or not pack.active:
            raise PlanNotFoundError(
                f"El paquete de créditos '{pack_id}' no existe o está inactivo.",
                details={"pack_id": pack_id},
            )
        return pack

    def get_item(self, item_id: str) -> ItemType:
        """Resuelve un ``plan_id`` o un ``pack_id``."""
        plan = next((p for p in self.settings.plans if p.id == item_id), None)
        if plan:
            return plan
        return self.get_credit_pack(item_id)

    def is_credit_pack(self, item: ItemType) -> bool:
        return isinstance(item, CreditPack)

    # ── Suscripciones ────────────────────────────────────────────────────────

    def get_subscription(self, user_id: str) -> UserSubscription:
        """Devuelve la suscripción, creándola en el plan gratuito si no existe."""
        sub = self.store.get_subscription(user_id)
        if sub is None:
            with self.store.transaction() as data:
                sub = UserSubscription(
                    user_id=user_id,
                    tier=SubscriptionTier.FREE,
                    plan_id="free_plan",
                    status=SubscriptionStatus.ACTIVE,
                    credits_remaining=self.settings.free_credits,
                    credits_granted_total=self.settings.free_credits,
                )
                data.subscriptions[user_id] = sub
                self.store.append_audit(
                    "subscription.created", target=user_id, tier="free"
                )
            logger.info("Suscripción gratuita creada para %s", user_id)
        return sub

    def get_entitlements(self, user_id: str) -> Entitlements:
        sub = self.get_subscription(user_id)
        plan = next((p for p in self.settings.plans if p.id == sub.plan_id), None)
        return build_entitlements(sub, plan)

    def _ensure_subscription(self, data, user_id: str) -> UserSubscription:
        """Devuelve la suscripción, creándola con la asignación gratuita si no existe.

        Todo camino que necesite escribir sobre la suscripción debe pasar por
        aquí. Construir ``UserSubscription(user_id=...)`` a mano arrancaría con
        0 créditos y el usuario perdería la cuota gratuita solo por no haber
        consultado antes su suscripción.
        """
        sub = data.subscriptions.get(user_id)
        if sub is None:
            sub = UserSubscription(
                user_id=user_id,
                tier=SubscriptionTier.FREE,
                plan_id="free_plan",
                status=SubscriptionStatus.ACTIVE,
                credits_remaining=self.settings.free_credits,
                credits_granted_total=self.settings.free_credits,
            )
            data.subscriptions[user_id] = sub
            self.store.append_audit(
                "subscription.created", target=user_id, tier="free"
            )
        return sub

    def _period_end(self, item: ItemType, start: Optional[float] = None) -> Optional[float]:
        if isinstance(item, CreditPack):
            return None
        seconds = PERIOD_SECONDS.get(item.interval)
        if seconds is None:
            return None
        return (start or now()) + seconds

    def _grant_credits(
        self,
        data,
        user_id: str,
        amount: int,
        reason: str,
        *,
        transaction_id: Optional[str] = None,
        **meta: Any,
    ) -> int:
        """Acredita créditos y deja asiento en el libro. Devuelve el saldo."""
        sub = data.subscriptions.get(user_id)
        if sub is None:
            sub = self._ensure_subscription(data, user_id)

        sub.credits_remaining += amount
        sub.credits_granted_total += max(0, amount)
        sub.updated_at = now()

        data.credit_ledger.append(
            CreditLedgerEntry(
                user_id=user_id,
                delta=amount,
                balance_after=sub.credits_remaining,
                reason=reason,
                transaction_id=transaction_id,
                metadata=meta,
            )
        )
        return sub.credits_remaining

    def _revoke_credits(
        self, data, user_id: str, amount: int, reason: str, *, transaction_id: Optional[str] = None
    ) -> int:
        sub = data.subscriptions.get(user_id)
        if sub is None:
            return 0
        revokable = min(amount, sub.credits_remaining)
        if revokable > 0:
            sub.credits_remaining -= revokable
            sub.updated_at = now()
            data.credit_ledger.append(
                CreditLedgerEntry(
                    user_id=user_id,
                    delta=-revokable,
                    balance_after=sub.credits_remaining,
                    reason=reason,
                    transaction_id=transaction_id,
                )
            )
        return revokable

    # ── Checkout ─────────────────────────────────────────────────────────────

    def create_checkout(
        self,
        user_id: str,
        plan_id: str,
        provider: Optional[Union[str, PaymentProviderType]] = None,
        *,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crea la sesión de cobro de un plan o paquete de créditos."""
        item = self.get_item(plan_id)
        selected = self._resolve_provider(provider)
        impl = self._build_provider(selected)

        if not impl.is_ready():
            raise ConfigurationError(
                f"El proveedor '{selected.value}' no está configurado. "
                f"Define {self._secret_env_hint(selected)} o usa el proveedor 'mock'.",
                details={"provider": selected.value},
            )

        if isinstance(item, PlanConfig) and item.price_cents == 0:
            # Plan gratuito: no hay cobro, se activa directamente.
            with self.store.transaction():
                self._activate_free_plan(user_id, item)
            return {
                "status": "activated",
                "provider": selected.value,
                "plan_id": item.id,
                "tier": item.tier.value,
                "message": "Plan gratuito activado; no requiere pago.",
                "subscription": self.get_subscription(user_id).model_dump(mode="json"),
            }

        self._check_rate_limit(user_id)

        key = idempotency_key or new_id("idem")
        with self._mutation_lock:
            with self.store.transaction() as data:
                tx = TransactionRecord(
                    id=new_id("tx"),
                    user_id=user_id,
                    kind="credit_pack" if self.is_credit_pack(item) else "subscription",
                    plan_id=item.id,
                    provider=selected,
                    amount_cents=item.price_cents,
                    currency=item.currency,
                    status=PaymentStatus.PENDING,
                    idempotency_key=key,
                )
                data.transactions.append(tx)
                self.store.append_audit(
                    "checkout.created",
                    target=tx.id,
                    user_id=user_id,
                    plan_id=item.id,
                    provider=selected.value,
                    amount_cents=item.price_cents,
                )

            base = self.settings.public_base_url.rstrip("/")
            checkout = impl.create_checkout(
                user_id=user_id,
                item=item,
                success_url=f"{base}{self.settings.success_path}",
                cancel_url=f"{base}{self.settings.cancel_path}",
                transaction_id=tx.id,
                idempotency_key=key,
                client={"success_url_base": base},
            )

            with self.store.transaction() as data:
                tx.provider_transaction_id = checkout.provider_transaction_id
                tx.updated_at = now()
                tx.metadata.setdefault("checkout_url", checkout.checkout_url)

            logger.info(
                "Checkout creado: tx=%s user=%s plan=%s provider=%s",
                tx.id, user_id, item.id, selected.value,
            )
            return {
                "status": "pending",
                "transaction_id": tx.id,
                "checkout_url": checkout.checkout_url,
                "provider": selected.value,
                "item_id": item.id,
                "amount_cents": item.price_cents,
                "currency": item.currency,
                "idempotency_key": key,
                "expires_at": checkout.expires_at,
            }

    def _activate_free_plan(self, user_id: str, plan: PlanConfig) -> None:
        with self.store.transaction() as data:
            sub = self._ensure_subscription(data, user_id)
            sub.tier = plan.tier
            sub.plan_id = plan.id
            sub.status = SubscriptionStatus.ACTIVE
            sub.active = True
            sub.expires_at = self._period_end(plan)
            sub.period_start = now()
            sub.updated_at = now()
            data.subscriptions[user_id] = sub
            if plan.credits_included:
                self._grant_credits(
                    data, user_id, plan.credits_included, "free_plan_grant", plan_id=plan.id
                )
            self.store.append_audit("plan.activated_free", target=user_id, plan_id=plan.id)

    def _check_rate_limit(self, user_id: str) -> None:
        """Freno anti-abuso: limita los checkouts por usuario y hora."""
        cutoff = now() - 3600
        recent = [
            tx
            for tx in self.store.data.transactions
            if tx.user_id == user_id and tx.created_at > cutoff
        ]
        limit = self.settings.max_checkout_per_hour
        if len(recent) >= limit:
            raise InvalidStateError(
                f"Demasiados intentos de pago ({len(recent)}/{limit} en la última hora).",
                details={"retry_after_seconds": 3600, "limit": limit},
            )

    # ── Procesamiento de eventos ─────────────────────────────────────────────

    def handle_event(self, event: prov.NormalizedEvent) -> Dict[str, Any]:
        """Aplica un evento canónico ya verificado y deduplicado."""
        with self._mutation_lock:
            with self.store.transaction() as data:
                if event.type == prov.EVENT_PAYMENT_SUCCEEDED:
                    return self._apply_payment_succeeded(data, event)
                if event.type in (
                    prov.EVENT_SUBSCRIPTION_RENEWED,
                    prov.EVENT_SUBSCRIPTION_UPDATED,
                ):
                    return self._apply_subscription_active(data, event)
                if event.type == prov.EVENT_PAYMENT_FAILED:
                    return self._apply_payment_failed(data, event)
                if event.type == prov.EVENT_SUBSCRIPTION_CANCELED:
                    return self._apply_subscription_canceled(data, event)
                if event.type == prov.EVENT_SUBSCRIPTION_EXPIRED:
                    return self._apply_subscription_expired(data, event)
                if event.type == prov.EVENT_PAYMENT_REFUNDED:
                    return self._apply_refund(data, event)
                if event.type == prov.EVENT_DISPUTED:
                    return self._apply_dispute(data, event)
                return {"status": "ignored", "event_type": event.type}

    def _locate_transaction(self, data, event: prov.NormalizedEvent) -> Optional[TransactionRecord]:
        if event.user_id:
            pending = [
                tx
                for tx in data.transactions
                if tx.user_id == event.user_id
                and tx.status == PaymentStatus.PENDING
                and tx.plan_id == (event.plan_id or tx.plan_id)
            ]
            if pending:
                return pending[-1]
        if event.provider_transaction_id:
            return next(
                (
                    tx
                    for tx in data.transactions
                    if tx.provider_transaction_id == event.provider_transaction_id
                ),
                None,
            )
        return None

    def _apply_payment_succeeded(self, data, event: prov.NormalizedEvent):
        tx = self._locate_transaction(data, event)
        if tx is None:
            # El webhook llegó sin checkout previo (p. ej. cobro manual).
            user_id = event.user_id or ""
            if not user_id:
                return {"status": "unmatched", "reason": "sin user_id ni transacción previa"}
            tx = TransactionRecord(
                id=new_id("tx"),
                user_id=user_id,
                plan_id=event.plan_id or "unknown",
                provider=event.provider,
                amount_cents=event.amount_cents or 0,
                currency=event.currency,
                status=PaymentStatus.COMPLETED,
                provider_transaction_id=event.provider_transaction_id,
            )
            data.transactions.append(tx)
        elif tx.status == PaymentStatus.COMPLETED:
            return {"status": "already_completed", "transaction_id": tx.id}

        tx.status = PaymentStatus.COMPLETED
        tx.provider_transaction_id = event.provider_transaction_id or tx.provider_transaction_id
        tx.provider_customer_id = event.provider_customer_id or tx.provider_customer_id
        tx.provider_subscription_id = (
            event.provider_subscription_id or tx.provider_subscription_id
        )
        tx.period_start = event.period_start or tx.period_start
        tx.period_end = event.period_end or tx.period_end
        tx.updated_at = now()
        if event.amount_cents:
            tx.amount_cents = event.amount_cents

        item = self._safe_item(tx.plan_id)
        sub = self._ensure_subscription(data, tx.user_id)

        if item is None:
            return {"status": "completed_without_entitlement", "transaction_id": tx.id}

        if self.is_credit_pack(item):
            self._grant_credits(
                data,
                tx.user_id,
                item.total_credits,
                "pack_purchase",
                transaction_id=tx.id,
                pack_id=item.id,
            )
            sub.active = True
            result = {
                "status": "completed",
                "transaction_id": tx.id,
                "credits_granted": item.total_credits,
            }
        else:
            self._activate_plan(data, tx.user_id, item, tx, event)
            result = {
                "status": "completed",
                "transaction_id": tx.id,
                "tier": sub.tier.value,
                "plan_id": sub.plan_id,
                "credits_granted": item.credits_included,
            }

        self.store.append_audit(
            "payment.succeeded",
            target=tx.id,
            user_id=tx.user_id,
            plan_id=tx.plan_id,
            amount_cents=tx.amount_cents,
        )
        return result

    def _activate_plan(
        self,
        data,
        user_id: str,
        plan: PlanConfig,
        tx: TransactionRecord,
        event: Optional[prov.NormalizedEvent] = None,
    ) -> None:
        sub = self._ensure_subscription(data, user_id)
        sub.provider = tx.provider
        sub.provider_customer_id = tx.provider_customer_id
        if tx.provider == PaymentProviderType.STRIPE:
            sub.stripe_customer_id = tx.provider_customer_id
        elif tx.provider == PaymentProviderType.MERCADOPAGO:
            sub.mercadopago_payer_id = tx.provider_customer_id

        event = event or prov.NormalizedEvent(
            id="", type="", provider=tx.provider
        )
        sub.provider_subscription_id = (
            event.provider_subscription_id or tx.provider_subscription_id
        )
        sub.subscription_id = sub.provider_subscription_id
        sub.plan_id = plan.id
        sub.tier = plan.tier
        sub.status = SubscriptionStatus.ACTIVE
        sub.active = True
        sub.cancel_at_period_end = False
        sub.period_start = event.period_start or (tx.period_start or now())
        sub.expires_at = event.period_end or self._period_end(plan, sub.period_start)
        sub.updated_at = now()
        data.subscriptions[user_id] = sub

        if plan.credits_included:
            self._grant_credits(
                data, user_id, plan.credits_included, "plan_grant",
                transaction_id=tx.id, plan_id=plan.id,
            )

    def _apply_subscription_active(self, data, event: prov.NormalizedEvent):
        """Renovación o actualización: extiende el periodo y repone créditos."""
        sub = self._find_subscription(data, event)
        if sub is None:
            if not event.user_id:
                return {"status": "unmatched", "reason": "sin suscripción"}
            sub = UserSubscription(user_id=event.user_id)
            data.subscriptions[event.user_id] = sub

        plan = self._safe_item(sub.plan_id)
        if plan is None:
            return {"status": "no_plan", "subscription_id": sub.user_id}

        sub.status = SubscriptionStatus.ACTIVE
        sub.active = True
        sub.period_start = event.period_start or now()
        sub.expires_at = event.period_end or self._period_end(plan, sub.period_start)
        sub.updated_at = now()
        if event.provider_subscription_id:
            sub.provider_subscription_id = event.provider_subscription_id
            sub.subscription_id = event.provider_subscription_id

        granted = 0
        if plan.credits_included and sub.expires_at:
            granted = plan.credits_included
            self._grant_credits(
                data, sub.user_id, granted, "plan_renewal", plan_id=plan.id
            )

        self.store.append_audit(
            "subscription.renewed",
            target=sub.user_id,
            plan_id=sub.plan_id,
            expires_at=sub.expires_at,
        )
        return {
            "status": "renewed",
            "user_id": sub.user_id,
            "plan_id": sub.plan_id,
            "expires_at": sub.expires_at,
            "credits_granted": granted,
        }

    def _apply_payment_failed(self, data, event: prov.NormalizedEvent):
        tx = self._locate_transaction(data, event)
        if tx is None:
            return {"status": "unmatched", "event_type": event.type}
        if tx.status in (PaymentStatus.FAILED, PaymentStatus.CANCELLED):
            return {"status": "already_failed", "transaction_id": tx.id}
        tx.status = PaymentStatus.FAILED
        tx.failure_reason = "provider_reported_failure"
        tx.updated_at = now()
        self.store.append_audit(
            "payment.failed", target=tx.id, user_id=tx.user_id, plan_id=tx.plan_id
        )
        return {"status": "failed", "transaction_id": tx.id}

    def _apply_subscription_canceled(self, data, event: prov.NormalizedEvent):
        sub = self._find_subscription(data, event)
        if sub is None:
            return {"status": "unmatched", "reason": "sin suscripción"}
        sub.status = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = True
        sub.active = False
        sub.updated_at = now()
        if event.period_end:
            sub.expires_at = event.period_end
        self.store.append_audit(
            "subscription.canceled", target=sub.user_id, plan_id=sub.plan_id
        )
        return {"status": "canceled", "user_id": sub.user_id}

    def _apply_subscription_expired(self, data, event: prov.NormalizedEvent):
        sub = self._find_subscription(data, event)
        if sub is None:
            return {"status": "unmatched", "reason": "sin suscripción"}
        sub.status = SubscriptionStatus.PAST_DUE
        sub.updated_at = now()
        if event.period_end and event.period_end <= now():
            sub.expires_at = event.period_end
        self.store.append_audit(
            "subscription.past_due", target=sub.user_id, plan_id=sub.plan_id
        )
        return {"status": "past_due", "user_id": sub.user_id}

    def _apply_refund(self, data, event: prov.NormalizedEvent):
        tx = next(
            (
                t
                for t in data.transactions
                if t.provider_transaction_id == event.provider_transaction_id
                or t.id == (event.raw.get("transaction_id") or "")
            ),
            None,
        )
        if tx is None:
            return {"status": "unmatched", "reason": "transacción no encontrada"}

        refunded = event.refunded_cents or event.amount_cents or 0
        tx.refunded_cents = min(tx.amount_cents, tx.refunded_cents + refunded)
        tx.status = (
            PaymentStatus.REFUNDED
            if tx.refunded_cents >= tx.amount_cents
            else PaymentStatus.PARTIALLY_REFUNDED
        )
        tx.updated_at = now()

        # Ratio de créditos a revocar proporcional al dinero devuelto.
        plan = self._safe_item(tx.plan_id)
        credits_granted = 0
        if plan is not None and plan.price_cents > 0 and plan.credits_included:
            ratio = tx.refunded_cents / plan.price_cents
            credits_granted = int(plan.credits_included * min(1.0, ratio))
        elif isinstance(plan, CreditPack) and plan.price_cents > 0:
            ratio = tx.refunded_cents / plan.price_cents
            credits_granted = int(plan.total_credits * min(1.0, ratio))

        revoked = self._revoke_credits(
            data, tx.user_id, credits_granted, "refund", transaction_id=tx.id
        )

        if tx.status == PaymentStatus.REFUNDED and self.settings.auto_downgrade:
            sub = data.subscriptions.get(tx.user_id)
            if sub and sub.plan_id == tx.plan_id:
                sub.tier = SubscriptionTier.FREE
                sub.plan_id = "free_plan"
                sub.status = SubscriptionStatus.ACTIVE
                sub.subscription_id = None
                sub.expires_at = None
                sub.updated_at = now()

        data.refunds.append(
            RefundRecord(
                transaction_id=tx.id,
                user_id=tx.user_id,
                amount_cents=refunded,
                currency=tx.currency,
                provider_refund_id=str(event.provider_transaction_id or ""),
                credits_revoked=revoked,
            )
        )
        self.store.append_audit(
            "payment.refunded",
            target=tx.id,
            user_id=tx.user_id,
            refunded_cents=refunded,
            credits_revoked=revoked,
        )
        return {
            "status": "refunded",
            "transaction_id": tx.id,
            "refunded_cents": refunded,
            "credits_revoked": revoked,
        }

    def _apply_dispute(self, data, event: prov.NormalizedEvent):
        tx = next(
            (
                t
                for t in data.transactions
                if t.provider_transaction_id == event.provider_transaction_id
            ),
            None,
        )
        if tx is None:
            return {"status": "unmatched", "reason": "transacción no encontrada"}
        tx.status = PaymentStatus.DISPUTED
        tx.failure_reason = "dispute_opened"
        tx.updated_at = now()
        if self.settings.auto_downgrade:
            sub = data.subscriptions.get(tx.user_id)
            if sub:
                sub.status = SubscriptionStatus.PAST_DUE
                sub.active = False
                sub.updated_at = now()
        self.store.append_audit(
            "payment.disputed", target=tx.id, user_id=tx.user_id
        )
        return {"status": "disputed", "transaction_id": tx.id}

    def _find_subscription(self, data, event: prov.NormalizedEvent):
        if event.user_id and event.user_id in data.subscriptions:
            return data.subscriptions[event.user_id]
        sid = event.provider_subscription_id
        if sid:
            return next(
                (s for s in data.subscriptions.values() if s.subscription_id == sid), None
            )
        customer = event.provider_customer_id
        if customer:
            for sub in data.subscriptions.values():
                if (
                    sub.stripe_customer_id == customer
                    or sub.mercadopago_payer_id == customer
                ):
                    return sub
        return None

    def _safe_item(self, item_id: str) -> Optional[ItemType]:
        for item in self.settings.plans:
            if item.id == item_id:
                return item
        for pack in self.settings.credit_packs:
            if pack.id == item_id:
                return pack
        return None

    # ── Webhooks ─────────────────────────────────────────────────────────────

    def process_webhook(
        self,
        provider: Union[str, PaymentProviderType],
        payload: bytes,
        signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Punto de entrada único de webhooks.

        Orden obligatorio: resolver proveedor → **verificar firma** →
        deduplicar → parsear → aplicar.
        """
        selected = self._resolve_provider(provider)
        impl = self._build_provider(selected)

        if not impl.is_ready():
            raise ConfigurationError(
                f"El proveedor '{selected.value}' no está configurado; "
                "no se puede verificar la firma del evento.",
                details={"provider": selected.value},
            )

        # 1. Verificación criptográfica. Sin firma válida no se continúa.
        body = impl.verify_webhook(payload, signature)

        # 2. Idempotencia por evento.
        event_key = f"{selected.value}:{impl.payload_hash(payload)}"
        existing = self.store.data.processed_events.get(event_key)
        if existing is not None:
            return {
                "status": "duplicate",
                "event_id": existing.id,
                "previous_result": existing.result,
            }

        # 3. Normalización y aplicación.
        try:
            events = impl.parse_event(body)
        except ProviderAPIError as exc:
            raise
        except Exception as exc:
            raise ProviderAPIError(f"Evento de {selected.value} ilegible: {exc}")

        results = []
        for event in events:
            if event.type == "unhandled":
                results.append({"status": "ignored", "event_type": event.type})
                continue
            try:
                results.append(self.handle_event(event))
            except Exception as exc:
                logger.exception("Fallo aplicando evento %s", event.type)
                results.append({"status": "error", "event_type": event.type, "error": str(exc)})

        with self.store.transaction() as data:
            data.processed_events[event_key] = WebhookEvent(
                id=new_id("evt"),
                provider=selected,
                type=events[0].type if events else "empty",
                payload_hash=impl.payload_hash(payload),
                processed=True,
                result=json.dumps(results, default=str)[:500],
            )
            self.store.append_audit(
                "webhook.processed",
                target=event_key,
                provider=selected.value,
                results=len(results),
            )
            # Poda de eventos antiguos para que el documento no crezca sin fin.
            if len(data.processed_events) > 2000:
                ordered = sorted(data.processed_events.items(), key=lambda kv: kv[1].received_at)
                for key, _ in ordered[: len(data.processed_events) - 2000]:
                    data.processed_events.pop(key, None)

        return {
            "status": "processed",
            "provider": selected.value,
            "results": results,
        }

    # ── Reembolsos ───────────────────────────────────────────────────────────

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None,
        reason: Optional[str] = None,
        provider: Optional[Union[str, PaymentProviderType]] = None,
    ) -> Dict[str, Any]:
        tx = self.store.find_transaction(tx_id=transaction_id)
        if tx is None:
            raise TransactionNotFoundError(
                f"No existe la transacción '{transaction_id}'.",
                details={"transaction_id": transaction_id},
            )
        if not tx.is_settled:
            raise InvalidStateError(
                f"La transacción '{transaction_id}' está en estado '{tx.status.value}' "
                "y no admite reembolso.",
                details={"status": tx.status.value},
            )

        remaining = tx.net_cents
        amount = amount_cents or remaining
        if amount <= 0 or amount > remaining:
            raise InvalidStateError(
                f"El importe de reembolso debe estar entre 1 y {remaining} centavos.",
                details={"remaining_cents": remaining, "requested_cents": amount},
            )

        selected = self._resolve_provider(provider or tx.provider)
        impl = self._build_provider(selected)
        if not impl.is_ready():
            raise ConfigurationError(
                f"El proveedor '{selected.value}' no está configurado; "
                "no se puede emitir el reembolso.",
                details={"provider": selected.value},
            )
        if not tx.provider_transaction_id:
            raise InvalidStateError(
                "La transacción no tiene identificador remoto; no se puede reembolsar."
            )

        result = impl.refund(
            provider_transaction_id=tx.provider_transaction_id,
            amount_cents=amount,
            reason=reason,
            client={},
        )

        with self.store.transaction() as data:
            event = prov.NormalizedEvent(
                id=new_id("evt"),
                type=prov.EVENT_PAYMENT_REFUNDED,
                provider=selected,
                provider_transaction_id=tx.provider_transaction_id,
                amount_cents=amount,
                refunded_cents=amount,
                signature_verified=True,
            )
            applied = self._apply_refund(data, event)

        return {
            "status": "refunded",
            "refund_id": result.refund_id,
            "transaction_id": tx.id,
            "amount_cents": amount,
            "provider": selected.value,
            "provider_refund_id": result.provider_refund_id,
            "entitlement_change": applied,
        }

    # ── Créditos ─────────────────────────────────────────────────────────────

    def consume_credits(
        self, user_id: str, amount: int, reason: str = "usage", **meta: Any
    ) -> Dict[str, Any]:
        """Descuenta créditos de forma atómica y registra el asiento."""
        if amount <= 0:
            raise InvalidStateError("El consumo de créditos debe ser positivo.")

        with self._mutation_lock:
            with self.store.transaction() as data:
                sub = data.subscriptions.get(user_id)
                if sub is None:
                    from kogniterm.server.payments.errors import InsufficientCreditsError

                    raise InsufficientCreditsError(
                        "El usuario no tiene suscripción inicializada.",
                        details={"user_id": user_id, "available": 0},
                    )
                if sub.credits_remaining < amount:
                    from kogniterm.server.payments.errors import InsufficientCreditsError

                    raise InsufficientCreditsError(
                        f"Saldo insuficiente: se requieren {amount} créditos y hay "
                        f"{sub.credits_remaining}.",
                        details={"required": amount, "available": sub.credits_remaining},
                    )

                sub.credits_remaining -= amount
                sub.credits_consumed_total += amount
                sub.updated_at = now()
                data.credit_ledger.append(
                    CreditLedgerEntry(
                        user_id=user_id,
                        delta=-amount,
                        balance_after=sub.credits_remaining,
                        reason=reason,
                        metadata=meta,
                    )
                )
                self.store.append_audit(
                    "credits.consumed",
                    target=user_id,
                    amount=amount,
                    reason=reason,
                )
                balance = sub.credits_remaining
                tier = sub.tier.value

        return {"status": "ok", "balance": balance, "tier": tier, "consumed": amount}

    def grant_credits(
        self, user_id: str, amount: int, reason: str = "manual_grant", **meta: Any
    ) -> Dict[str, Any]:
        with self.store.transaction() as data:
            balance = self._grant_credits(
                data, user_id, amount, reason, **meta
            )
        return {"status": "ok", "balance": balance, "granted": amount}

    # ── Mantenimiento ────────────────────────────────────────────────────────

    def reconcile_expirations(self) -> Dict[str, Any]:
        """Degrada a FREE las suscripciones vencidas. Idempotente."""
        with self.store.transaction() as data:
            expired = []
            for sub in data.subscriptions.values():
                if (
                    sub.tier != SubscriptionTier.FREE
                    and sub.expires_at
                    and sub.expires_at <= now()
                    and sub.status != SubscriptionStatus.EXPIRED
                ):
                    sub.status = SubscriptionStatus.EXPIRED
                    sub.tier = SubscriptionTier.FREE
                    sub.plan_id = "free_plan"
                    sub.active = False
                    sub.subscription_id = None
                    sub.updated_at = now()
                    expired.append(sub.user_id)
                    self.store.append_audit(
                        "subscription.expired", target=sub.user_id
                    )
        return {"expired_count": len(expired), "expired_users": expired}

    def provider_status(self) -> Dict[str, Any]:
        active = self.settings.active_provider
        return {
            "active_provider": active.value,
            "credentials": self.credentials.public_view(),
            "ready": self._build_provider(active).is_ready(),
            "data_file": str(self.store.path),
            "schema_version": self.store.data.schema_version,
            "audit_chain_valid": self.store.verify_audit_chain()["valid"],
        }

    def summary(self, user_id: str) -> Dict[str, Any]:
        sub = self.get_subscription(user_id)
        return {
            "subscription": sub.model_dump(mode="json"),
            "entitlements": self.get_entitlements(user_id).to_dict(),
            "transactions": [
                tx.model_dump(mode="json")
                for tx in self.store.transactions_for_user(user_id, limit=20)
            ],
            "credit_ledger": [
                e.model_dump(mode="json")
                for e in self.store.ledger_for_user(user_id, limit=20)
            ],
            "effective_tier": effective_tier(sub).value,
        }

    # ── Proveedores ──────────────────────────────────────────────────────────

    def _resolve_provider(
        self, provider: Optional[Union[str, PaymentProviderType]]
    ) -> PaymentProviderType:
        if provider is None:
            return self.settings.active_provider
        if isinstance(provider, PaymentProviderType):
            return provider
        try:
            return PaymentProviderType(str(provider).lower())
        except ValueError:
            raise ConfigurationError(
                f"Proveedor de pago desconocido: '{provider}'. "
                f"Disponibles: {', '.join(prov.available_providers())}."
            )

    def _build_provider(self, provider: PaymentProviderType) -> prov.PaymentProvider:
        return prov.build_provider(provider, self.credentials.resolve(provider))

    @staticmethod
    def _secret_env_hint(provider: PaymentProviderType) -> str:
        from kogniterm.server.payments.credentials import ENV_KEYS

        return ENV_KEYS.get(provider, {}).get("secret_key", "las credenciales")


# ── Singleton del proceso ────────────────────────────────────────────────────

payment_service: Optional[PaymentService] = None
_service_lock = threading.Lock()


def get_payment_service() -> PaymentService:
    """Devuelve el singleton, creándolo de forma perezosa y segura.

    Se construye *bajo demanda* y no al importar ``kogniterm.server.app`` para
    que los tests puedan fijar ``KOGNITERM_PAYMENTS_FILE`` antes de que se
    resuelva la ruta del almacén (el módulo anterior fallaba justo aquí).
    """
    global payment_service
    if payment_service is None:
        with _service_lock:
            if payment_service is None:
                payment_service = PaymentService()
    return payment_service


def reset_payment_service() -> None:
    """Reinicia el singleton (tests)."""
    global payment_service
    with _service_lock:
        payment_service = None
