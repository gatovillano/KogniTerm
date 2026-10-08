"""
Lógica de negocio y servicio de integración con Stripe / MercadoPago / Pasarela de pagos para KogniTerm.
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
    CompleteCheckoutRequest,
    CompleteCheckoutResponse,
    SwitchPlanRequest,
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

        self.mercadopago_access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
        self._mercadopago_available = False

        if self.stripe_api_key:
            try:
                import stripe  # type: ignore
                stripe.api_key = self.stripe_api_key
                self._stripe_available = True
                logger.info("💳 Stripe SDK inicializado correctamente.")
            except ImportError:
                logger.warning("⚠️ Biblioteca `stripe` no instalada. Se utilizará el modo Mock de pagos.")

        if self.mercadopago_access_token:
            try:
                import mercadopago  # type: ignore
                self._mercadopago = mercadopago.SDK(self.mercadopago_access_token)
                self._mercadopago_available = True
                logger.info("🇦🇷 MercadoPago SDK inicializado correctamente.")
            except ImportError:
                logger.warning("⚠️ Biblioteca `mercadopago` no instalada. Se utilizará el modo Mock de pagos.")

        if not self._stripe_available and not self._mercadopago_available:
            logger.info("ℹ️ No se detectó pasarela configurada. El sistema de pagos funcionará en modo Mock/Simulación.")

        # Almacenamiento en memoria para suscripciones de demo / persistencia local
        self._subscriptions_db: Dict[str, SubscriptionDetails] = {}
        self._usage_db: Dict[str, Dict[str, int]] = {}
        self._checkout_sessions: Dict[str, Dict[str, Any]] = {}

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

    def _build_period_dates(self, plan: PlanInfo) -> tuple[str, str]:
        now = datetime.datetime.now(datetime.timezone.utc)
        if plan.billing_cycle == BillingCycle.YEARLY:
            end = now + datetime.timedelta(days=365)
        else:
            end = now + datetime.timedelta(days=30)
        return now.isoformat(), end.isoformat()

    def _activate_plan(self, user_id: str, plan_id: str) -> SubscriptionDetails:
        plan = self.get_plan(plan_id) or AVAILABLE_PLANS["plan_free"]
        start, end = self._build_period_dates(plan)
        subscription = SubscriptionDetails(
            user_id=user_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=start,
            current_period_end=end,
            cancel_at_period_end=False,
        )
        self._subscriptions_db[user_id] = subscription
        return subscription

    def create_checkout_session(
        self, user_id: str, req: CreateCheckoutSessionRequest
    ) -> CreateCheckoutSessionResponse:
        """Crea una sesión de Checkout (Stripe, MercadoPago o Mock)."""
        provider = req.provider or PaymentProvider.MOCK
        plan = self.get_plan(req.plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {req.plan_id}")

        if provider == PaymentProvider.STRIPE and self._stripe_available:
            try:
                import stripe  # type: ignore
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
                self._checkout_sessions[session.id] = {
                    "user_id": user_id,
                    "plan_id": plan.id,
                    "provider": PaymentProvider.STRIPE,
                }
                return CreateCheckoutSessionResponse(
                    checkout_url=session.url,
                    session_id=session.id,
                    provider=PaymentProvider.STRIPE,
                )
            except Exception as e:
                logger.error(f"Error creando sesión de checkout en Stripe: {e}")

        if provider == PaymentProvider.MOCK and self._mercadopago_available:
            try:
                return self._create_mercadopago_checkout(user_id, req, plan)
            except Exception as e:
                logger.error(f"Error delegando checkout a MercadoPago: {e}")

        # Modo Mock / Simulador de Checkout
        session_id = f"cs_mock_{os.urandom(8).hex()}"
        mock_checkout_url = f"{req.success_url}?session_id={session_id}&mock=true&plan_id={plan.id}"
        self._checkout_sessions[session_id] = {
            "user_id": user_id,
            "plan_id": plan.id,
            "provider": PaymentProvider.MOCK,
        }
        self._activate_plan(user_id, plan.id)
        return CreateCheckoutSessionResponse(
            checkout_url=mock_checkout_url,
            session_id=session_id,
            provider=PaymentProvider.MOCK,
        )

    def _create_mercadopago_checkout(
        self,
        user_id: str,
        req: CreateCheckoutSessionRequest,
        plan: PlanInfo,
    ) -> CreateCheckoutSessionResponse:
        preference_data = {
            "items": [
                {
                    "title": plan.name,
                    "quantity": 1,
                    "currency_id": plan.currency.upper(),
                    "unit_price": float(plan.price),
                }
            ],
            "external_reference": user_id,
            "metadata": {
                "plan_id": plan.id,
                "user_id": user_id,
            },
            "back_urls": {
                "success": req.success_url,
                "failure": req.cancel_url,
                "pending": req.cancel_url,
            },
            "auto_return": "approved",
        }
        preference = self._mercadopago.preference().create(preference_data)
        preference_id = preference.get("response", {}).get("id") or preference.get("id")
        if not preference_id:
            raise ValueError("MercadoPago no devolvió un ID de preferencia válido.")

        checkout_url = (
            preference.get("response", {}).get("sandbox_init_point")
            or preference.get("response", {}).get("init_point")
            or f"https://www.mercadopago.com/checkout/v1/redirect?pref_id={preference_id}"
        )
        session_id = f"cs_mp_{preference_id}"
        self._checkout_sessions[session_id] = {
            "user_id": user_id,
            "plan_id": plan.id,
            "provider": PaymentProvider.MOCK,
            "preference_id": preference_id,
        }
        return CreateCheckoutSessionResponse(
            checkout_url=checkout_url,
            session_id=session_id,
            provider=PaymentProvider.MOCK,
        )

    def complete_checkout_session(
        self, user_id: str, req: CompleteCheckoutRequest
    ) -> CompleteCheckoutResponse:
        session = self._checkout_sessions.get(req.session_id)
        if not session:
            if req.plan_id and self.get_plan(req.plan_id):
                subscription = self._activate_plan(user_id, req.plan_id)
                return CompleteCheckoutResponse(
                    status="success",
                    message="Checkout completado en modo simulación.",
                    subscription=subscription,
                )
            raise ValueError("Sesión de checkout inválida o inexistente.")

        resolved_user_id = req.user_id or user_id or session.get("user_id")
        plan_id = req.plan_id or session.get("plan_id")
        if not plan_id:
            raise ValueError("No se pudo resolver el plan para completar el checkout.")

        subscription = self._activate_plan(resolved_user_id, plan_id)
        subscription.metadata = {**subscription.metadata, "checkout_session_id": req.session_id}
        self._subscriptions_db[resolved_user_id] = subscription
        return CompleteCheckoutResponse(
            status="success",
            message="Checkout completado correctamente.",
            subscription=subscription,
        )

    def switch_plan(self, user_id: str, req: SwitchPlanRequest) -> SubscriptionDetails:
        plan = self.get_plan(req.plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {req.plan_id}")

        current = self.get_user_subscription(user_id)
        if current.plan_id == req.plan_id:
            return current

        if plan.price == 0:
            return self._activate_plan(user_id, req.plan_id)

        checkout_req = CreateCheckoutSessionRequest(
            plan_id=req.plan_id,
            success_url=f"/api/payments/checkout/complete?user_id={user_id}",
            cancel_url=f"/api/payments/subscription?user_id={user_id}",
            user_id=user_id,
            provider=req.provider,
        )
        checkout = self.create_checkout_session(user_id, checkout_req)
        if checkout.provider == PaymentProvider.MOCK:
            return self.complete_checkout_session(user_id, CompleteCheckoutRequest(session_id=checkout.session_id, user_id=user_id))
        current.metadata = {**current.metadata, "pending_switch_checkout": checkout.session_id}
        self._subscriptions_db[user_id] = current
        return current

    def cancel_subscription(self, user_id: str, at_period_end: bool = True) -> SubscriptionDetails:
        """Cancela la suscripción del usuario."""
        sub = self.get_user_subscription(user_id)

        if self._stripe_available and sub.stripe_subscription_id:
            try:
                import stripe  # type: ignore
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
        """Procesa un evento de webhook de Stripe o simulación básica."""
        if self._stripe_available and self.webhook_secret:
            try:
                import stripe  # type: ignore
                event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
                return self._process_stripe_event(event)
            except Exception as e:
                logger.error(f"Firma de Webhook de Stripe inválida: {e}")
                raise ValueError(f"Webhook signature verification failed: {e}")

        logger.info("Webhook recibido en modo desarrollo / mock.")
        return {"status": "ignored", "reason": "stripe_not_configured"}

    def handle_mercadopago_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_type = payload.get("type") or payload.get("action") or payload.get("topic")
        data = payload.get("data", {}).get("object") or payload.get("resource") or {}
        external_reference = data.get("external_reference") or payload.get("external_reference")
        metadata = data.get("metadata") or {}
        user_id = external_reference or metadata.get("user_id")
        plan_id = metadata.get("plan_id")
        status = data.get("status") or payload.get("status")

        if user_id and plan_id and status in {"approved", "paid", "authorized"}:
            self._activate_plan(user_id, plan_id)
            return {"status": "success", "event_type": event_type, "user_id": user_id, "plan_id": plan_id}

        return {"status": "ignored", "event_type": event_type}

    def _process_stripe_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            user_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("user_id")
            plan_id = data_object.get("metadata", {}).get("plan_id")
            sub_id = data_object.get("subscription")
            cust_id = data_object.get("customer")

            if user_id and plan_id:
                subscription = self._activate_plan(user_id, plan_id)
                subscription.stripe_customer_id = cust_id
                subscription.stripe_subscription_id = sub_id
                self._subscriptions_db[user_id] = subscription
                logger.info(f"✅ Suscripción activada para usuario {user_id} en plan {plan_id}")

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

    def record_usage(self, user_id: str, tokens: int = 0, sessions_delta: int = 0) -> UsageQuotaInfo:
        """Registra consumo de uso y devuelve la cuota actualizada."""
        usage = self._usage_db.setdefault(user_id, {"tokens": 0})
        usage["tokens"] = max(0, usage.get("tokens", 0) + tokens)
        if sessions_delta:
            usage["sessions_delta"] = max(0, usage.get("sessions_delta", 0) + sessions_delta)
        return self.get_usage_quota(user_id, active_sessions_count=usage.get("sessions_delta", 0))

    def simulate_payment_success(self, user_id: str, plan_id: str) -> SubscriptionDetails:
        """Simula un pago exitoso para desarrollo sin pasarela."""
        if plan_id not in AVAILABLE_PLANS:
            raise ValueError(f"Plan no encontrado: {plan_id}")
        return self._activate_plan(user_id, plan_id)


payment_service = PaymentService()
