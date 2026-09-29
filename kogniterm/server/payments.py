"""
Sistema de Pagos y Suscripciones para KogniTerm (Backend & Manager)

Soporta proveedores de pago extensibles (Stripe, MercadoPago, Mock/Simulado).
Proporciona gestión de planes, suscripciones, tokens/créditos, transacciones y webhooks.
"""

import os
import json
import time
import hmac
import hashlib
import logging
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("kogniterm.payments")


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PaymentProviderType(str, Enum):
    MOCK = "mock"
    STRIPE = "stripe"
    MERCADOPAGO = "mercadopago"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PlanConfig(BaseModel):
    id: str
    name: str
    tier: SubscriptionTier
    price_cents: int  # Precio en centavos USD / ARS / local
    currency: str = "USD"
    interval: str = "month"  # month, year, one_time
    credits_included: int = 1000  # Créditos de tokens o consultas IA
    features: List[str] = Field(default_factory=list)


class TransactionRecord(BaseModel):
    id: str
    user_id: str
    plan_id: str
    provider: PaymentProviderType
    provider_transaction_id: Optional[str] = None
    amount_cents: int
    currency: str
    status: PaymentStatus
    created_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserSubscription(BaseModel):
    user_id: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    plan_id: str = "free_plan"
    credits_remaining: int = 100
    stripe_customer_id: Optional[str] = None
    mercadopago_payer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    active: bool = True
    expires_at: Optional[float] = None
    updated_at: float = Field(default_factory=time.time)


class PaymentSettings(BaseModel):
    provider_active: PaymentProviderType = PaymentProviderType.MOCK
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    mercadopago_access_token: Optional[str] = None
    mercadopago_webhook_secret: Optional[str] = None
    plans: List[PlanConfig] = [
        PlanConfig(
            id="free_plan",
            name="Gratuito",
            tier=SubscriptionTier.FREE,
            price_cents=0,
            currency="USD",
            interval="month",
            credits_included=100,
            features=["Acceso básico a CLI", "100 créditos mensuales de IA", "Soporte comunitario"]
        ),
        PlanConfig(
            id="pro_monthly",
            name="Pro Mensual",
            tier=SubscriptionTier.PRO,
            price_cents=1999,  # $19.99
            currency="USD",
            interval="month",
            credits_included=5000,
            features=["Acceso completo CLI & Web", "5,000 créditos mensuales", "Modelos avanzados (Claude/GPT-4)", "Soporte prioritario"]
        ),
        PlanConfig(
            id="enterprise_annual",
            name="Enterprise Anual",
            tier=SubscriptionTier.ENTERPRISE,
            price_cents=19900,  # $199.00
            currency="USD",
            interval="year",
            credits_included=100000,
            features=["Agentes ilimitados", "100k créditos anuales", "Heartbeats personalizados", "Soporte 24/7 y SLA"]
        )
    ]


class PaymentService:
    """
    Servicio central de procesamiento de pagos y gestión de suscripciones.
    """
    DATA_FILE = Path(os.getenv("KOGNITERM_PAYMENTS_FILE", str(Path.home() / ".kogniterm" / "payments_data.json")))

    def __init__(self):
        self.settings = PaymentSettings()
        self.subscriptions: Dict[str, UserSubscription] = {}
        self.transactions: List[TransactionRecord] = []
        self._load_data()

    def _load_data(self):
        if not self.DATA_FILE.exists():
            self._save_data()
            return
        try:
            with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "settings" in data:
                    self.settings = PaymentSettings(**data["settings"])
                if "subscriptions" in data:
                    self.subscriptions = {
                        uid: UserSubscription(**sub) for uid, sub in data["subscriptions"].items()
                    }
                if "transactions" in data:
                    self.transactions = [TransactionRecord(**tx) for tx in data["transactions"]]
        except Exception as e:
            logger.error(f"Error cargando datos de pagos: {e}")

    def _save_data(self):
        self.DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "settings": self.settings.model_dump(),
            "subscriptions": {uid: sub.model_dump() for uid, sub in self.subscriptions.items()},
            "transactions": [tx.model_dump() for tx in self.transactions]
        }
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def get_plans(self) -> List[PlanConfig]:
        return self.settings.plans

    def get_user_subscription(self, user_id: str) -> UserSubscription:
        if user_id not in self.subscriptions:
            self.subscriptions[user_id] = UserSubscription(user_id=user_id)
            self._save_data()
        return self.subscriptions[user_id]

    def create_checkout_session(
        self, user_id: str, plan_id: str, provider: Optional[PaymentProviderType] = None
    ) -> Dict[str, Any]:
        """
        Crea una sesión de pago / checkout para un usuario y plan determinado.
        """
        plan = next((p for p in self.settings.plans if p.id == plan_id), None)
        if not plan:
            raise ValueError(f"Plan '{plan_id}' no encontrado.")

        selected_provider = provider or self.settings.provider_active
        tx_id = f"tx_{int(time.time()*1000)}"

        # Proveedor MOCK (Desarrollo y Pruebas)
        if selected_provider == PaymentProviderType.MOCK:
            checkout_url = f"/api/payments/mock-checkout?tx_id={tx_id}"
            tx = TransactionRecord(
                id=tx_id,
                user_id=user_id,
                plan_id=plan_id,
                provider=PaymentProviderType.MOCK,
                amount_cents=plan.price_cents,
                currency=plan.currency,
                status=PaymentStatus.PENDING,
                metadata={"checkout_url": checkout_url}
            )
            self.transactions.append(tx)
            self._save_data()
            return {
                "transaction_id": tx_id,
                "checkout_url": checkout_url,
                "provider": "mock",
                "message": "Sesión de checkout creada exitosamente."
            }

        # Proveedor STRIPE
        elif selected_provider == PaymentProviderType.STRIPE:
            stripe_key = self.settings.stripe_secret_key or os.getenv("STRIPE_SECRET_KEY")
            if not stripe_key:
                raise ValueError("Secret Key de Stripe no configurada.")
            
            import stripe
            stripe.api_key = stripe_key
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': plan.currency.lower(),
                        'product_data': {'name': plan.name},
                        'unit_amount': plan.price_cents,
                    },
                    'quantity': 1,
                }],
                mode='subscription' if plan.interval != 'one_time' else 'payment',
                success_url='http://localhost:5173/payment-success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url='http://localhost:5173/payment-cancel',
                client_reference_id=user_id,
                metadata={"plan_id": plan.id, "user_id": user_id}
            )
            
            tx = TransactionRecord(
                id=tx_id,
                user_id=user_id,
                plan_id=plan_id,
                provider=PaymentProviderType.STRIPE,
                provider_transaction_id=session.id,
                amount_cents=plan.price_cents,
                currency=plan.currency,
                status=PaymentStatus.PENDING
            )
            self.transactions.append(tx)
            self._save_data()

            return {
                "transaction_id": tx_id,
                "checkout_url": session.url,
                "provider": "stripe",
                "session_id": session.id
            }

        # Proveedor MERCADOPAGO
        elif selected_provider == PaymentProviderType.MERCADOPAGO:
            mp_token = self.settings.mercadopago_access_token or os.getenv("MERCADOPAGO_ACCESS_TOKEN")
            if not mp_token:
                raise ValueError("Access Token de MercadoPago no configurado.")

            import mercadopago
            sdk = mercadopago.SDK(mp_token)

            preference_data = {
                "items": [
                    {
                        "title": plan.name,
                        "quantity": 1,
                        "unit_price": plan.price_cents / 100.0,
                        "currency_id": plan.currency.upper()
                    }
                ],
                "back_urls": {
                    "success": "http://localhost:5173/payment-success",
                    "failure": "http://localhost:5173/payment-cancel",
                    "pending": "http://localhost:5173/payment-pending"
                },
                "auto_return": "approved",
                "external_reference": json.dumps({"user_id": user_id, "plan_id": plan.id, "tx_id": tx_id})
            }

            preference_response = sdk.preference().create(preference_data)
            preference = preference_response["response"]

            tx = TransactionRecord(
                id=tx_id,
                user_id=user_id,
                plan_id=plan_id,
                provider=PaymentProviderType.MERCADOPAGO,
                provider_transaction_id=preference["id"],
                amount_cents=plan.price_cents,
                currency=plan.currency,
                status=PaymentStatus.PENDING
            )
            self.transactions.append(tx)
            self._save_data()

            return {
                "transaction_id": tx_id,
                "checkout_url": preference["init_point"],
                "provider": "mercadopago",
                "preference_id": preference["id"]
            }

        else:
            raise ValueError(f"Proveedor '{selected_provider}' no soportado.")

    def complete_transaction(self, tx_id: str, provider_tx_id: Optional[str] = None) -> UserSubscription:
        """
        Completa una transacción y activa/actualiza la suscripción del usuario.
        """
        tx = next((t for t in self.transactions if t.id == tx_id or t.provider_transaction_id == provider_tx_id), None)
        if not tx:
            raise ValueError(f"Transacción '{tx_id or provider_tx_id}' no encontrada.")

        if tx.status == PaymentStatus.COMPLETED:
            return self.get_user_subscription(tx.user_id)

        tx.status = PaymentStatus.COMPLETED
        if provider_tx_id:
            tx.provider_transaction_id = provider_tx_id

        plan = next((p for p in self.settings.plans if p.id == tx.plan_id), None)
        if not plan:
            raise ValueError(f"Plan '{tx.plan_id}' no encontrado.")

        sub = self.get_user_subscription(tx.user_id)
        sub.tier = plan.tier
        sub.plan_id = plan.id
        sub.credits_remaining += plan.credits_included
        sub.active = True
        sub.updated_at = time.time()
        if plan.interval == "month":
            sub.expires_at = time.time() + 30 * 86400
        elif plan.interval == "year":
            sub.expires_at = time.time() + 365 * 86400

        self._save_data()
        logger.info(f" Transacción {tx.id} completada. Suscripción de {tx.user_id} actualizada a {sub.tier}.")
        return sub

    def process_webhook(self, provider: str, payload: bytes, signature_header: Optional[str] = None) -> Dict[str, Any]:
        """
        Procesa eventos/webhooks provenientes de Stripe o MercadoPago.
        """
        if provider == "stripe":
            webhook_secret = self.settings.stripe_webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")
            import stripe
            event = None
            if webhook_secret and signature_header:
                try:
                    event = stripe.Webhook.construct_event(payload, signature_header, webhook_secret)
                except Exception as e:
                    raise ValueError(f"Firma de Webhook de Stripe inválida: {e}")
            else:
                event = json.loads(payload.decode("utf-8"))

            if event.get("type") == "checkout.session.completed":
                session = event["data"]["object"]
                user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id")
                plan_id = session.get("metadata", {}).get("plan_id")
                session_id = session.get("id")

                # Buscar transacción pendiente o completar
                sub = self.complete_transaction(tx_id="", provider_tx_id=session_id)
                return {"status": "success", "event": "checkout.session.completed", "user_id": user_id}

        elif provider == "mercadopago":
            data = json.loads(payload.decode("utf-8"))
            if data.get("action") == "payment.created" or data.get("type") == "payment":
                payment_id = data.get("data", {}).get("id")
                # En producción se consulta la API de MercadoPago con el ID para obtener el status y external_reference
                return {"status": "success", "event": "payment.created", "payment_id": payment_id}

        return {"status": "ignored", "provider": provider}


# Singleton del servicio de pagos
payment_service = PaymentService()
