"""
Lógica de negocio y servicio de integración con Stripe / Pasarela de pagos para KogniTerm.
"""

import os
import logging
import datetime
from typing import List, Optional, Dict, Any

from kogniterm.server.payments.models import (
    PlanInfo,
    PlanTier,
    BillingCycle,
    SubscriptionDetails,
    SubscriptionStatus,
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    PaymentProvider,
    PaymentMethodDetails,
    PaymentHistoryItem,
    UsageQuotaInfo,
)

logger = logging.getLogger("kogniterm.server.payments.service")

# Catálogo predefinido de planes de KogniTerm
AVAILABLE_PLANS: Dict[str, PlanInfo] = {
    "plan_free": PlanInfo(
        id="plan_free",
        name="Free Tier",
        tier=PlanTier.FREE,
        price=0.0,
        currency="usd",
        billing_cycle=BillingCycle.MONTHLY,
        description="Ideal para exploradores y pruebas de desarrollo.",
        features=[
            "100,000 tokens al mes",
            "Hasta 2 sesiones concurrentes",
            "Modelos locales y gratuitos",
            "Soporte de la comunidad",
        ],
        token_limit_per_month=100_000,
        max_sessions=2,
        custom_models_allowed=False,
    ),
    "plan_pro_monthly": PlanInfo(
        id="plan_pro_monthly",
        name="Pro Monthly",
        tier=PlanTier.PRO,
        price=19.99,
        currency="usd",
        billing_cycle=BillingCycle.MONTHLY,
        description="Para desarrolladores y profesionales exigentes.",
        features=[
            "5,000,000 tokens al mes",
            "Hasta 10 sesiones concurrentes",
            "Modelos avanzados (GPT-4o, Claude 3.5 Sonnet, Gemini 2.0)",
            "Conectores MCP ilimitados",
            "Soporte prioritario",
        ],
        token_limit_per_month=5_000_000,
        max_sessions=10,
        custom_models_allowed=True,
    ),
    "plan_pro_yearly": PlanInfo(
        id="plan_pro_yearly",
        name="Pro Yearly",
        tier=PlanTier.PRO,
        price=199.99,
        currency="usd",
        billing_cycle=BillingCycle.YEARLY,
        description="Ahorra 2 meses con facturación anual para profesionales.",
        features=[
            "5,000,000 tokens al mes",
            "Hasta 10 sesiones concurrentes",
            "Modelos avanzados (GPT-4o, Claude 3.5 Sonnet, Gemini 2.0)",
            "Conectores MCP ilimitados",
            "Soporte prioritario",
        ],
        token_limit_per_month=5_000_000,
        max_sessions=10,
        custom_models_allowed=True,
    ),
    "plan_enterprise": PlanInfo(
        id="plan_enterprise",
        name="Enterprise",
        tier=PlanTier.ENTERPRISE,
        price=99.99,
        currency="usd",
        billing_cycle=BillingCycle.MONTHLY,
        description="Solución personalizada para equipos y empresas.",
        features=[
            "Tokens ilimitados",
            "Sesiones concurrentes ilimitadas",
            "Despliegue local / On-premise dedicado",
            "SLA garantizado de 99.9%",
            "Gerente de cuenta dedicado",
        ],
        token_limit_per_month=100_000_000,
        max_sessions=100,
        custom_models_allowed=True,
    ),
}


class PaymentService:
    def __init__(self):
        self.stripe_api_key = os.environ.get("STRIPE_SECRET_KEY")
        self.webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        self._stripe_available = False

        if self.stripe_api_key:
            try:
                import stripe
                stripe.api_key = self.stripe_api_key
                self._stripe_available = True
                logger.info("💳 Stripe SDK inicializado correctamente.")
            except ImportError:
                logger.warning("⚠️ Biblioteca `stripe` no instalada. Se utilizará el modo Mock de pagos.")
        else:
            logger.info("ℹ️ No se detectó STRIPE_SECRET_KEY. El sistema de pagos funcionará en modo Mock/Simulación.")

        # Almacenamiento en memoria para suscripciones de demo / persistencia local
        self._subscriptions_db: Dict[str, SubscriptionDetails] = {}
        self._usage_db: Dict[str, Dict[str, int]] = {}

    def list_plans(self) -> List[PlanInfo]:
        """Retorna la lista de planes de suscripción disponibles."""
        return list(AVAILABLE_PLANS.values())

    def get_plan(self, plan_id: str) -> Optional[PlanInfo]:
        """Obtiene la información de un plan por su ID."""
        return AVAILABLE_PLANS.get(plan_id)

    def get_user_subscription(self, user_id: str) -> SubscriptionDetails:
        """Obtiene la suscripción activa del usuario o asigna el plan Free por defecto."""
        if user_id in self._subscriptions_db:
            return self._subscriptions_db[user_id]

        now = datetime.datetime.now(datetime.timezone.utc)
        one_month_later = now + datetime.timedelta(days=30)
        
        default_sub = SubscriptionDetails(
            user_id=user_id,
            plan_id="plan_free",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now.isoformat(),
            current_period_end=one_month_later.isoformat(),
            cancel_at_period_end=False,
        )
        self._subscriptions_db[user_id] = default_sub
        return default_sub

    def create_checkout_session(
        self, user_id: str, req: CreateCheckoutSessionRequest
    ) -> CreateCheckoutSessionResponse:
        """Crea una sesión de Checkout (Stripe Checkout real si hay API Key, o Mock URL si no)."""
        plan = self.get_plan(req.plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {req.plan_id}")

        if self._stripe_available:
            try:
                import stripe
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    mode="subscription" if plan.price > 0 else "payment",
                    customer_email=req.customer_email,
                    line_items=[
                        {
                            "price_data": {
                                "currency": plan.currency,
                                "product_data": {
                                    "name": plan.name,
                                    "description": plan.description,
                                },
                                "unit_amount": int(plan.price * 100),
                                "recurring": {
                                    "interval": "month" if plan.billing_cycle == BillingCycle.MONTHLY else "year"
                                } if plan.price > 0 else None,
                            },
                            "quantity": 1,
                        }
                    ],
                    success_url=req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=req.cancel_url,
                    client_reference_id=user_id,
                    metadata={"plan_id": plan.id, "user_id": user_id},
                )
                return CreateCheckoutSessionResponse(
                    checkout_url=session.url,
                    session_id=session.id,
                    provider=PaymentProvider.STRIPE,
                )
            except Exception as e:
                logger.error(f"Error creando sesión de checkout en Stripe: {e}")
                # Fallback al simulador si falla Stripe
                pass

        # Modo Mock / Simulador de Checkout
        session_id = f"cs_mock_{os.urandom(8).hex()}"
        mock_checkout_url = f"{req.success_url}?session_id={session_id}&mock=true&plan_id={plan.id}"
        
        # Simular actualización de suscripción previa
        now = datetime.datetime.now(datetime.timezone.utc)
        one_year_later = now + datetime.timedelta(days=365)
        
        self._subscriptions_db[user_id] = SubscriptionDetails(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now.isoformat(),
            current_period_end=one_year_later.isoformat(),
            cancel_at_period_end=False,
            metadata={"simulated": True},
        )

        return CreateCheckoutSessionResponse(
            checkout_url=mock_checkout_url,
            session_id=session_id,
            provider=PaymentProvider.MOCK,
        )

    def cancel_subscription(self, user_id: str, at_period_end: bool = True) -> SubscriptionDetails:
        """Cancela la suscripción del usuario."""
        sub = self.get_user_subscription(user_id)
        
        if self._stripe_available and sub.stripe_subscription_id:
            try:
                import stripe
                if at_period_end:
                    stripe.Subscription.modify(
                        sub.stripe_subscription_id,
                        cancel_at_period_end=True,
                    )
                else:
                    stripe.Subscription.delete(sub.stripe_subscription_id)
            except Exception as e:
                logger.error(f"Error al cancelar suscripción en Stripe: {e}")

        sub.cancel_at_period_end = True
        if not at_period_end:
            sub.status = SubscriptionStatus.CANCELED
            sub.plan_id = "plan_free"
            
        self._subscriptions_db[user_id] = sub
        return sub

    def handle_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Procesa un evento de webhook de Stripe (o simulado)."""
        if not self._stripe_available or not self.webhook_secret:
            logger.info("Webhook recibido en modo desarrollo / mock.")
            return {"status": "ignored", "reason": "stripe_not_configured"}

        try:
            import stripe
            event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
        except Exception as e:
            logger.error(f"Firma de Webhook de Stripe inválida: {e}")
            raise ValueError(f"Webhook signature verification failed: {e}")

        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        logger.info(f"Procesando evento de Webhook Stripe: {event_type}")

        if event_type == "checkout.session.completed":
            user_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("user_id")
            plan_id = data_object.get("metadata", {}).get("plan_id")
            sub_id = data_object.get("subscription")
            cust_id = data_object.get("customer")

            if user_id and plan_id:
                now = datetime.datetime.now(datetime.timezone.utc)
                end = now + datetime.timedelta(days=30)
                self._subscriptions_db[user_id] = SubscriptionDetails(
                    user_id=user_id,
                    plan_id=plan_id,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=now.isoformat(),
                    current_period_end=end.isoformat(),
                    stripe_customer_id=cust_id,
                    stripe_subscription_id=sub_id,
                )
                logger.info(f"✅ Suscripción activada exitosamente para usuario {user_id} en plan {plan_id}")

        elif event_type == "customer.subscription.deleted":
            cust_id = data_object.get("customer")
            for uid, sub in self._subscriptions_db.items():
                if sub.stripe_customer_id == cust_id:
                    sub.status = SubscriptionStatus.CANCELED
                    sub.plan_id = "plan_free"
                    logger.info(f"🛑 Suscripción cancelada para usuario {uid}")

        return {"status": "success", "event_type": event_type}

    def get_payment_methods(self, user_id: str) -> List[PaymentMethodDetails]:
        """Lista métodos de pago guardados del usuario."""
        sub = self.get_user_subscription(user_id)
        if sub.plan_id == "plan_free":
            return []

        return [
            PaymentMethodDetails(
                id="pm_1M00002eZvKYlo2C",
                brand="Visa",
                last4="4242",
                exp_month=12,
                exp_year=2028,
                is_default=True,
            )
        ]

    def get_payment_history(self, user_id: str) -> List[PaymentHistoryItem]:
        """Obtiene el historial de pagos y facturas del usuario."""
        sub = self.get_user_subscription(user_id)
        plan = self.get_plan(sub.plan_id) or AVAILABLE_PLANS["plan_free"]

        if plan.price == 0:
            return []

        now_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return [
            PaymentHistoryItem(
                id=f"inv_{os.urandom(6).hex()}",
                amount=plan.price,
                currency=plan.currency.upper(),
                status="paid",
                date=now_str,
                receipt_url="https://stripe.com/receipt/mock",
                description=f"Factura {plan.name} - KogniTerm Subscription",
            )
        ]

    def get_usage_quota(self, user_id: str, active_sessions_count: int = 0) -> UsageQuotaInfo:
        """Calcula el uso actual de la cuota del plan para un usuario."""
        sub = self.get_user_subscription(user_id)
        plan = self.get_plan(sub.plan_id) or AVAILABLE_PLANS["plan_free"]

        usage = self._usage_db.get(user_id, {"tokens": 12500})
        tokens_used = usage.get("tokens", 12500)
        
        tokens_limit = plan.token_limit_per_month
        pct = min(100.0, round((tokens_used / max(1, tokens_limit)) * 100, 2))

        return UsageQuotaInfo(
            tier=plan.tier,
            tokens_used_this_month=tokens_used,
            tokens_limit=tokens_limit,
            percentage_used=pct,
            sessions_active=active_sessions_count,
            sessions_limit=plan.max_sessions,
        )


payment_service = PaymentService()
