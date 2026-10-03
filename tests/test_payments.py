"""
Suite de pruebas del sistema de pagos de KogniTerm.

Cubre los flujos críticos y, sobre todo, los casos de seguridad donde el
módulo original fallaba:

* Verificación de firma obligatoria (sin ella no se procesa nada).
* Idempotencia de webhooks (reintentos no duplican créditos).
* Aislamiento del almacén por test (nada escribe en el archivo real).
* Atomicidad: un fallo a mitad de operación no deja estado parcial.
* Degradación por expiración y reembolso.
* Conservación de datos al migrar del esquema v1.

    pytest tests/test_payments.py -v
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirige el almacén y el archivo de credenciales a un temporal.

    Es la regresión directa del bug del módulo v1: ``DATA_FILE`` se resolvía al
    importar el módulo, por lo que fijar la variable de entorno en el test
    arriving tarde no surtía efecto y las pruebas escribían sobre el archivo
    real del usuario.
    """
    data_file = tmp_path / "payments.json"
    creds_file = tmp_path / "credentials.json"
    monkeypatch.setenv("KOGNITERM_PAYMENTS_FILE", str(data_file))
    monkeypatch.setenv("KOGNITERM_PAYMENTS_CREDENTIALS_FILE", str(creds_file))
    monkeypatch.setenv("KOGNITERM_MOCK_WEBHOOK_SECRET", "test-secret-mock")
    monkeypatch.delenv("KOGNITERM_PAYMENT_PROVIDER", raising=False)

    from kogniterm.server import payments as pkg

    pkg.reset_payment_service()
    yield data_file
    pkg.reset_payment_service()


@pytest.fixture
def service(isolated_store):
    from kogniterm.server.payments import get_payment_service

    return get_payment_service()


def signed_event(payload: dict, secret: str = "test-secret-mock", timestamp: int | None = None):
    """Construye (body, firma) válidos para el proveedor MOCK."""
    body = json.dumps(payload).encode()
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(
        secret.encode(), f"{ts}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return body, f"t={ts},v1={digest}"


APPROVED = {
    "action": "payment.approved",
    "status": "approved",
    "user_id": "alice",
    "plan_id": "pro_monthly",
    "amount_cents": 1999,
    "currency": "USD",
}


# ── Catálogo ─────────────────────────────────────────────────────────────────


class TestCatalog:
    def test_plans_por_defecto(self, service):
        ids = {p.id for p in service.get_plans()}
        assert {"free_plan", "pro_monthly", "pro_annual", "enterprise_annual"} <= ids

    def test_catalogo_ordenado(self, service):
        planes = service.get_plans()
        assert [p.sort_order for p in planes] == sorted(p.sort_order for p in planes)

    def test_plan_inexistente(self, service):
        from kogniterm.server.payments import PlanNotFoundError

        with pytest.raises(PlanNotFoundError):
            service.get_plan("no_existe")

    def test_precios_no_negativos(self, service):
        assert all(p.price_cents >= 0 for p in service.get_plans())

    def test_packs_incluyen_bonus(self, service):
        packs = {p.id: p for p in service.get_credit_packs()}
        assert packs["credits_25k"].total_credits == 27500


# ── Suscripciones ────────────────────────────────────────────────────────────


class TestSubscriptions:
    def test_nuevo_usuario_es_free(self, service):
        sub = service.get_subscription("nuevo")
        assert sub.tier.value == "free"
        assert sub.plan_id == "free_plan"
        assert sub.credits_remaining == 100

    def test_suscripcion_persiste_entre_llamadas(self, service):
        service.grant_credits("nuevo", 250)
        assert service.get_subscription("nuevo").credits_remaining == 350

    def test_reload_desde_disco(self, service, isolated_store):
        service.grant_credits("nuevo", 500)
        from kogniterm.server.payments import get_payment_service

        get_payment_service().store.reload()
        assert get_payment_service().get_subscription("nuevo").credits_remaining == 600

    def test_almacen_tiene_permisos_0600(self, service, isolated_store):
        service.get_subscription("permisos")
        assert oct(isolated_store.stat().st_mode)[-3:] == "600"

    def test_entitlements_de_free(self, service):
        ent = service.get_entitlements("free_user")
        assert ent.tier.value == "free"
        assert ent.limit("parallel_subagents") == 1
        assert ent.limit("max_heartbeats") == 0

    def test_plan_free_se_activa_sin_pago(self, service):
        result = service.create_checkout("gratis", "free_plan", "mock")
        assert result["status"] == "activated"
        assert result["tier"] == "free"


# ── Checkout ─────────────────────────────────────────────────────────────────


class TestCheckout:
    def test_crea_checkout_mock(self, service):
        result = service.create_checkout("alice", "pro_monthly", "mock")
        assert result["status"] == "pending"
        assert result["provider"] == "mock"
        assert result["transaction_id"].startswith("tx_")
        assert result["checkout_url"]

    def test_transaccion_registrada_como_pendiente(self, service):
        result = service.create_checkout("alice", "pro_monthly", "mock")
        tx = service.store.find_transaction(tx_id=result["transaction_id"])
        assert tx.status.value == "pending"
        assert tx.amount_cents == 1999

    def test_plan_inexistente_falla(self, service):
        from kogniterm.server.payments import PlanNotFoundError

        with pytest.raises(PlanNotFoundError):
            service.create_checkout("alice", "inventado", "mock")

    def test_proveedor_sin_credenciales_falla(self, service, monkeypatch):
        from kogniterm.server.payments import ConfigurationError

        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        with pytest.raises(ConfigurationError):
            service.create_checkout("alice", "pro_monthly", "stripe")

    def test_rate_limit_de_checkouts(self, service):
        from kogniterm.server.payments import InvalidStateError

        service.settings.max_checkout_per_hour = 2
        service.create_checkout("spammer", "pro_monthly", "mock")
        service.create_checkout("spammer", "pro_monthly", "mock")
        with pytest.raises(InvalidStateError):
            service.create_checkout("spammer", "pro_monthly", "mock")


# ── Seguridad: verificación de firma ─────────────────────────────────────────


class TestWebhookSecurity:
    def test_webhook_sin_firma_se_rechaza(self, service):
        from kogniterm.server.payments import SignatureVerificationError

        body, _ = signed_event(APPROVED)
        with pytest.raises(SignatureVerificationError):
            service.process_webhook("mock", body, None)
        assert service.get_subscription("alice").tier.value == "free"

    def test_webhook_con_firma_invalida_se_rechaza(self, service):
        from kogniterm.server.payments import SignatureVerificationError

        body, _ = signed_event(APPROVED)
        with pytest.raises(SignatureVerificationError):
            service.process_webhook("mock", body, "t=1,v1=deadbeef")
        assert service.get_subscription("alice").tier.value == "free"

    def test_webhook_con_secreto_distinto_se_rechaza(self, service):
        from kogniterm.server.payments import SignatureVerificationError

        body, sig = signed_event(APPROVED, secret="secreto-del-atacante")
        with pytest.raises(SignatureVerificationError):
            service.process_webhook("mock", body, sig)

    def test_webhook_con_timestamp_viejo_se_rechaza(self, service):
        from kogniterm.server.payments import SignatureVerificationError

        body, sig = signed_event(APPROVED, timestamp=int(time.time()) - 4000)
        with pytest.raises(SignatureVerificationError):
            service.process_webhook("mock", body, sig)

    def test_firma_bien_formada_pero_falsa(self, service):
        from kogniterm.server.payments import SignatureVerificationError

        body, _ = signed_event(APPROVED)
        ts = int(time.time())
        fake = "t=%d,v1=%s" % (ts, "a" * 64)
        with pytest.raises(SignatureVerificationError):
            service.process_webhook("mock", body, fake)

    def test_stripe_sin_webhook_secret_no_procesa(self, service, monkeypatch):
        """Sin secreto configurado el sistema rechaza, nunca 'degrada'."""
        from kogniterm.server.payments import ConfigurationError, SignatureVerificationError

        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        body = json.dumps({"id": "evt_1", "type": "checkout.session.completed"}).encode()
        with pytest.raises((ConfigurationError, SignatureVerificationError)):
            service.process_webhook("stripe", body, "t=1,v1=x")

    def test_mercadopago_sin_secreto_no_procesa(self, service, monkeypatch):
        from kogniterm.server.payments import ConfigurationError, SignatureVerificationError

        monkeypatch.setenv("MERCADOPAGO_ACCESS_TOKEN", "APP_USR-test")
        monkeypatch.delenv("MERCADOPAGO_WEBHOOK_SECRET", raising=False)
        body = json.dumps({"action": "payment.approved", "data": {"id": "1"}}).encode()
        with pytest.raises((ConfigurationError, SignatureVerificationError)):
            service.process_webhook("mercadopago", body, "ts=1,v1=x")


# ── Flujo de compra completo ─────────────────────────────────────────────────


class TestPurchaseFlow:
    def test_pago_activa_plan_y_creditos(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        result = service.process_webhook("mock", *signed_event(APPROVED))

        assert result["status"] == "processed"
        sub = service.get_subscription("alice")
        assert sub.tier.value == "pro"
        assert sub.plan_id == "pro_monthly"
        assert sub.credits_remaining == 5100  # 100 gratis + 5000 del plan
        assert sub.expires_at is not None
        assert sub.days_remaining() > 25

    def test_transaccion_queda_completada(self, service):
        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        tx = service.store.find_transaction(tx_id=checkout["transaction_id"])
        assert tx.status.value == "completed"

    def test_replay_no_duplica_creditos(self, service):
        """Regresión de idempotencia: el reenvío no debe pagar dos veces."""
        service.create_checkout("alice", "pro_monthly", "mock")
        body, sig = signed_event(APPROVED)

        first = service.process_webhook("mock", body, sig)
        second = service.process_webhook("mock", body, sig)

        assert first["status"] == "processed"
        assert second["status"] == "duplicate"
        assert service.get_subscription("alice").credits_remaining == 5100

    def test_evento_distinto_siempre_procesado(self, service):
        """Un segundo pago real (importe distinto) sí debe aplicarse."""
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        service.create_checkout("bob", "pro_annual", "mock")
        body, sig = signed_event(
            {**APPROVED, "user_id": "bob", "plan_id": "pro_annual", "event_id": "e2"}
        )
        service.process_webhook("mock", body, sig)
        assert service.get_subscription("bob").tier.value == "pro"

    def test_libro_de_creditos_auditable(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        entries = service.store.ledger_for_user("alice")
        assert entries, "el libro debe registrar los movimientos"
        assert entries[0].balance_after == service.get_subscription("alice").credits_remaining

    def test_compra_de_paquete_de_creditos(self, service):
        service.create_checkout("carlos", "credits_5k", "mock")
        body, sig = signed_event(
            {
                "action": "payment.approved",
                "status": "approved",
                "user_id": "carlos",
                "plan_id": "credits_5k",
                "amount_cents": 990,
                "currency": "USD",
            }
        )
        service.process_webhook("mock", body, sig)
        sub = service.get_subscription("carlos")
        assert sub.tier.value == "free"  # el pack no cambia de plan
        assert sub.credits_remaining == 5100  # 100 gratis + 5000 del pack

    def test_pago_rechazado_no_activa(self, service):
        service.create_checkout("mallory", "pro_monthly", "mock")
        body, sig = signed_event(
            {
                "action": "payment.rejected",
                "status": "rejected",
                "user_id": "mallory",
                "plan_id": "pro_monthly",
            }
        )
        service.process_webhook("mock", body, sig)
        assert service.get_subscription("mallory").tier.value == "free"


# ── Créditos ─────────────────────────────────────────────────────────────────


class TestCredits:
    def test_consumo_descuenta(self, service):
        service.grant_credits("u", 1000)  # usuario nuevo: 100 gratis + 1000
        result = service.consume_credits("u", 300)
        assert result["balance"] == 800
        assert service.get_subscription("u").credits_remaining == 800

    def test_consumo_insuficiente_rechazado(self, service):
        from kogniterm.server.payments import InsufficientCreditsError

        with pytest.raises(InsufficientCreditsError):
            service.consume_credits("u", 9999)

    def test_consumo_insuficiente_no_altera_saldo(self, service):
        from kogniterm.server.payments import InsufficientCreditsError

        service.grant_credits("u", 100)  # 100 gratis + 100 = 200
        with pytest.raises(InsufficientCreditsError):
            service.consume_credits("u", 500)
        assert service.get_subscription("u").credits_remaining == 200

    def test_consumo_no_positivo_rechazado(self, service):
        from kogniterm.server.payments import InvalidStateError

        with pytest.raises(InvalidStateError):
            service.consume_credits("u", 0)

    def test_acumulacion_de_conteos(self, service):
        service.grant_credits("u", 1000)
        service.consume_credits("u", 400)
        sub = service.get_subscription("u")
        assert sub.credits_granted_total == 1100  # 100 gratis + 1000
        assert sub.credits_consumed_total == 400


# ── Reembolsos ───────────────────────────────────────────────────────────────


class TestRefunds:
    def test_reembolso_total_revierte_plan(self, service):
        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))

        result = service.refund(checkout["transaction_id"])

        assert result["status"] == "refunded"
        sub = service.get_subscription("alice")
        assert sub.tier.value == "free"
        assert sub.credits_remaining == 100

    def test_reembolso_parcial(self, service):
        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))

        result = service.refund(checkout["transaction_id"], amount_cents=1000)

        assert result["amount_cents"] == 1000
        # 1000/1999 del paquete -> ~2500 créditos revocados
        assert 2400 <= result["entitlement_change"]["credits_revoked"] <= 2600

    def test_reembolso_inexistente_falla(self, service):
        from kogniterm.server.payments import TransactionNotFoundError

        with pytest.raises(TransactionNotFoundError):
            service.refund("tx_nope")

    def test_no_se_reembolsa_lo_pendiente(self, service):
        from kogniterm.server.payments import InvalidStateError

        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        with pytest.raises(InvalidStateError):
            service.refund(checkout["transaction_id"])

    def test_no_se_reembolsa_mas_de_lo_pagado(self, service):
        from kogniterm.server.payments import InvalidStateError

        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        with pytest.raises(InvalidStateError):
            service.refund(checkout["transaction_id"], amount_cents=99999)

    def test_webhook_de_reembolso(self, service):
        checkout = service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        tx = service.store.find_transaction(tx_id=checkout["transaction_id"])

        body, sig = signed_event(
            {
                "action": "refund",
                "status": "refunded",
                "user_id": "alice",
                "provider_transaction_id": tx.provider_transaction_id,
                "amount_cents": 1999,
            }
        )
        service.process_webhook("mock", body, sig)

        assert (
            service.store.find_transaction(tx_id=checkout["transaction_id"]).status.value
            == "refunded"
        )
        assert service.get_subscription("alice").tier.value == "free"


# ── Ciclos de vida de la suscripción ─────────────────────────────────────────


class TestLifecycle:
    def test_renovacion_extiende_y_repone(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        saldo_tras_pago = service.get_subscription("alice").credits_remaining

        body, sig = signed_event(
            {
                "action": "subscription.renewed",
                "status": "approved",
                "user_id": "alice",
                "plan_id": "pro_monthly",
                "period_end": time.time() + 60 * 86400,
            }
        )
        service.process_webhook("mock", body, sig)

        sub = service.get_subscription("alice")
        assert sub.credits_remaining == saldo_tras_pago + 5000
        # El proveedor es la fuente de verdad del periodo: si no lo envía, se
        # recalcula con la duración del plan.
        assert sub.days_remaining() > 25

    def test_cancelacion_deja_marca(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))

        body, sig = signed_event(
            {"action": "subscription.canceled", "user_id": "alice", "plan_id": "pro_monthly"}
        )
        service.process_webhook("mock", body, sig)

        sub = service.get_subscription("alice")
        assert sub.status.value == "canceled"
        assert sub.cancel_at_period_end is True
        assert service.get_entitlements("alice").tier.value == "free"

    def test_reconciliacion_degrada_vencidas(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        service.store.data.subscriptions["alice"].expires_at = time.time() - 10

        result = service.reconcile_expirations()

        assert result["expired_count"] == 1
        sub = service.get_subscription("alice")
        assert sub.tier.value == "free"
        assert sub.status.value == "expired"

    def test_reconciliacion_es_idempotente(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        service.store.data.subscriptions["alice"].expires_at = time.time() - 10

        assert service.reconcile_expirations()["expired_count"] == 1
        assert service.reconcile_expirations()["expired_count"] == 0

    def test_reconciliacion_no_toca_vigentes(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        assert service.reconcile_expirations()["expired_count"] == 0
        assert service.get_subscription("alice").tier.value == "pro"


# ── Persistencia, migración e integridad ─────────────────────────────────────


class TestPersistence:
    def test_migracion_desde_v1(self, isolated_store):
        """El esquema v1 (módulo anterior) se importa sin perder datos."""
        legacy = {
            "settings": {
                "provider_active": "stripe",
                "plans": [
                    {
                        "id": "pro_monthly",
                        "name": "Pro Mensual",
                        "tier": "pro",
                        "price_cents": 1999,
                        "currency": "USD",
                        "interval": "month",
                        "credits_included": 5000,
                        "features": ["x"],
                    }
                ],
            },
            "subscriptions": {
                "legacy_user": {
                    "user_id": "legacy_user",
                    "tier": "pro",
                    "plan_id": "pro_monthly",
                    "credits_remaining": 4321,
                    "stripe_customer_id": "cus_123",
                    "subscription_id": "sub_456",
                    "active": True,
                    "updated_at": 1_700_000_000.0,
                }
            },
            "transactions": [
                {
                    "id": "tx_legacy",
                    "user_id": "legacy_user",
                    "plan_id": "pro_monthly",
                    "provider": "stripe",
                    "amount_cents": 1999,
                    "currency": "USD",
                    "status": "completed",
                    "created_at": 1_700_000_000.0,
                }
            ],
        }
        isolated_store.write_text(json.dumps(legacy), encoding="utf-8")

        from kogniterm.server.payments import get_payment_service

        service = get_payment_service()

        assert service.store.data.schema_version == 2
        sub = service.get_subscription("legacy_user")
        assert sub.credits_remaining == 4321
        assert sub.stripe_customer_id == "cus_123"
        assert sub.provider_customer_id == "cus_123"
        assert sub.provider_subscription_id == "sub_456"
        assert len(service.store.transactions_for_user("legacy_user")) == 1
        assert any(p.id == "pro_monthly" for p in service.get_plans())

    def test_migracion_descarta_secretos_v1(self, isolated_store):
        """Los secretos del v1 no se arrastran: deben rotarse de nuevo."""
        isolated_store.write_text(
            json.dumps(
                {
                    "settings": {
                        "stripe_secret_key": "sk_live_OLD",
                        "stripe_webhook_secret": "whsec_OLD",
                        "plans": [],
                    },
                    "subscriptions": {},
                    "transactions": [],
                }
            ),
            encoding="utf-8",
        )
        from kogniterm.server.payments import get_payment_service

        service = get_payment_service()
        service.get_plans()  # fuerza la escritura del documento migrado
        raw = isolated_store.read_text(encoding="utf-8")
        assert "sk_live_OLD" not in raw
        assert "whsec_OLD" not in raw

    def test_json_corrupto_se_aisla_y_reinicia(self, isolated_store):
        isolated_store.parent.mkdir(parents=True, exist_ok=True)
        isolated_store.write_text("{ esto no es json", encoding="utf-8")

        from kogniterm.server.payments import get_payment_service

        service = get_payment_service()
        assert service.get_plans()  # arranca con el catálogo por defecto
        assert list(isolated_store.parent.glob("*.corrupt-*"))

    def test_escritura_atomica_no_deja_temporales(self, service, isolated_store):
        for _ in range(5):
            service.grant_credits("u", 10)
        assert not list(isolated_store.parent.glob(".*.tmp"))

    def test_rollback_en_memoria_si_falla(self, service):
        """Si el cuerpo del transaction() revienta, no queda estado a medias."""
        from kogniterm.server.payments import InvalidStateError

        before = service.get_subscription("alice").credits_remaining
        with pytest.raises(InvalidStateError):
            with service.store.transaction() as data:
                data.subscriptions["alice"].credits_remaining = 999_999
                raise InvalidStateError("fallo simulado")
        assert service.get_subscription("alice").credits_remaining == before

    def test_bitacora_cadena_intacta(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.process_webhook("mock", *signed_event(APPROVED))
        assert service.store.verify_audit_chain()["valid"] is True

    def test_bitacora_detecta_manipulacion(self, service):
        service.create_checkout("alice", "pro_monthly", "mock")
        service.store.data.audit_log[0].action = "otro_cosa"
        assert service.store.verify_audit_chain()["valid"] is False

    def test_credenciales_no_en_el_almacen(self, service, isolated_store):
        from kogniterm.server.payments.models import PaymentProviderType

        # materializa el almacén antes de leerlo
        service.get_subscription("u")
        service.credentials.set(
            PaymentProviderType.STRIPE,
            secret_key="sk_test_muy_secreto",
            webhook_secret="whsec_muy_secreto",
        )
        raw = isolated_store.read_text(encoding="utf-8")
        assert "sk_test_muy_secreto" not in raw
        assert "whsec_muy_secreto" not in raw

    def test_credenciales_en_archivo_separado_0600(self, service):
        from kogniterm.server.payments.models import PaymentProviderType

        service.credentials.set(
            PaymentProviderType.STRIPE, secret_key="sk_test_x", webhook_secret="whsec_x"
        )
        path = service.credentials.path
        assert path.exists()
        assert oct(path.stat().st_mode)[-3:] == "600"
        assert "sk_test_x" in path.read_text(encoding="utf-8")

    def test_env_tiene_prioridad_sobre_archivo(self, service, monkeypatch):
        from kogniterm.server.payments.models import PaymentProviderType

        service.credentials.set(PaymentProviderType.STRIPE, secret_key="sk_desde_archivo")
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_desde_env")
        assert (
            service.credentials.resolve(PaymentProviderType.STRIPE)["secret_key"]
            == "sk_desde_env"
        )

    def test_public_view_no_filtra_secretos(self, service):
        from kogniterm.server.payments.models import PaymentProviderType

        service.credentials.set(PaymentProviderType.STRIPE, secret_key="sk_secreto_total")
        view = service.credentials.public_view()
        assert "sk_secreto_total" not in json.dumps(view)
        assert view["stripe"]["configured"] is True


# ── Endpoint HTTP ────────────────────────────────────────────────────────────


@pytest.fixture
def client(isolated_store):
    from fastapi.testclient import TestClient
    from kogniterm.server.app import app

    return TestClient(app)


class TestHTTPApi:
    def test_listar_planes(self, client):
        response = client.get("/api/payments/plans")
        assert response.status_code == 200
        assert any(p["id"] == "pro_monthly" for p in response.json()["plans"])

    def test_listar_proveedores(self, client):
        response = client.get("/api/payments/providers")
        assert response.status_code == 200
        assert response.json()["active_provider"] == "mock"

    def test_checkout_crea_transaccion(self, client):
        response = client.post(
            "/api/payments/checkout",
            json={"user_id": "api_user", "plan_id": "pro_monthly", "provider": "mock"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    def test_checkout_con_plan_invalido(self, client):
        response = client.post(
            "/api/payments/checkout",
            json={"user_id": "api_user", "plan_id": "fantasma"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "plan_not_found"

    def test_checkout_sin_plan_id(self, client):
        response = client.post("/api/payments/checkout", json={"user_id": "api_user"})
        assert response.status_code == 422  # validación de pydantic

    def test_suscripcion_crea_gratis(self, client):
        response = client.get("/api/payments/subscription/api_user")
        assert response.status_code == 200
        body = response.json()
        assert body["subscription"]["tier"] == "free"
        assert "entitlements" in body

    def test_entitlements(self, client):
        response = client.get("/api/payments/entitlements/api_user")
        assert response.status_code == 200
        assert response.json()["tier"] == "free"

    def test_consumo_sin_saldo(self, client):
        response = client.post(
            "/api/payments/credits/consume", json={"user_id": "api_user", "amount": 99999}
        )
        assert response.status_code == 402
        assert response.json()["detail"]["error"] == "insufficient_credits"

    def test_reembolso_inexistente(self, client):
        response = client.post("/api/payments/refund", json={"transaction_id": "tx_nada"})
        assert response.status_code == 404

    def test_webhook_sin_firma_rechazado(self, client):
        response = client.post(
            "/api/payments/webhook/mock",
            content=json.dumps(APPROVED).encode(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "invalid_signature"

    def test_webhook_con_firma_invalida_rechazado(self, client):
        response = client.post(
            "/api/payments/webhook/mock",
            content=json.dumps(APPROVED).encode(),
            headers={"content-type": "application/json", "x-kogniterm-signature": "t=1,v1=x"},
        )
        assert response.status_code == 400

    def test_audit_verify(self, client):
        response = client.get("/api/payments/audit/verify")
        assert response.status_code == 200
        assert response.json()["audit"]["valid"] is True

    def test_reconcile(self, client):
        response = client.post("/api/payments/reconcile")
        assert response.status_code == 200
        assert "expired_count" in response.json()
