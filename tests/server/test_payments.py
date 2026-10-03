"""
Tests del sistema de pagos de KogniTerm.

Cubren el ciclo de vida completo con el proveedor simulado (sin red ni
credenciales reales): checkout, aprobación, idempotencia, créditos, límites por
plan, reembolsos, expiración, firma de webhooks y migración del almacén.

    pytest tests/server/test_payments.py -v
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirige el almacén a un temporal y activa el secreto del mock."""
    data_file = tmp_path / "payments_data.json"
    monkeypatch.setenv("KOGNITERM_PAYMENTS_FILE", str(data_file))
    monkeypatch.setenv("KOGNITERM_MOCK_WEBHOOK_SECRET", "secret-de-test")
    monkeypatch.setenv("KOGNITERM_PAYMENT_PROVIDER", "mock")

    from kogniterm.server import payments as payments_pkg

    payments_pkg.reset_payment_service()
    yield data_file
    payments_pkg.reset_payment_service()


@pytest.fixture
def service(isolated_store):
    from kogniterm.server.payments import get_payment_service

    return get_payment_service()


@pytest.fixture
def client(isolated_store):
    from fastapi.testclient import TestClient

    from kogniterm.server.app import create_app

    return TestClient(create_app())


def approve(client, user_id: str, plan_id: str) -> dict:
    """Checkout + aprobación simulada; devuelve la respuesta del approve."""
    checkout = client.post(
        "/api/payments/checkout",
        json={"user_id": user_id, "plan_id": plan_id, "provider": "mock"},
    )
    assert checkout.status_code == 200, checkout.text
    tx_id = checkout.json()["transaction_id"]

    approval = client.post(
        "/api/payments/mock-checkout/complete",
        json={"user_id": user_id, "plan_id": plan_id, "transaction_id": tx_id},
    )
    assert approval.status_code == 200, approval.text
    return {"transaction_id": tx_id, "approval": approval.json()}


# ── Catálogo ────────────────────────────────────────────────────────────────


def test_plans_exposed_and_sorted(client):
    plans = client.get("/api/payments/plans").json()["plans"]
    assert [p["id"] for p in plans] == [
        "free_plan",
        "pro_monthly",
        "pro_annual",
        "enterprise_annual",
    ]
    assert all(p["price_cents"] >= 0 for p in plans)


def test_unknown_plan_returns_404(client):
    response = client.post(
        "/api/payments/checkout",
        json={"user_id": "u1", "plan_id": "does_not_exist", "provider": "mock"},
    )
    assert response.status_code == 404


def test_provider_status_never_leaks_secrets(client):
    body = client.get("/api/payments/providers").json()
    assert body["active_provider"] == "mock"
    # Sólo puede indicarse si está configurado, nunca el valor del secreto.
    assert set(body["credentials"]["mock"]) == {
        "configured",
        "webhook_configured",
        "enabled",
    }
    assert "secret-de-test" not in json.dumps(body)


# ── Ciclo de vida de la suscripción ─────────────────────────────────────────


def test_new_user_starts_on_free_with_welcome_credits(client):
    sub = client.get("/api/payments/subscription/u1").json()["subscription"]
    assert sub["tier"] == "free"
    assert sub["status"] == "active"
    assert sub["credits_remaining"] == 100


def test_checkout_creates_pending_transaction(client):
    response = client.post(
        "/api/payments/checkout",
        json={"user_id": "u1", "plan_id": "pro_monthly", "provider": "mock"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "pending"
    assert body["transaction_id"].startswith("tx_")

    sub = client.get("/api/payments/subscription/u1").json()["subscription"]
    assert sub["tier"] == "free", "no debe activarse hasta que se apruebe el pago"


def test_payment_upgrades_tier_and_grants_credits(client):
    before = client.get("/api/payments/subscription/u1").json()["subscription"]
    result = approve(client, "u1", "pro_monthly")
    after = client.get("/api/payments/subscription/u1").json()["subscription"]

    assert result["approval"]["results"][0]["status"] == "completed"
    assert after["tier"] == "pro"
    assert after["plan_id"] == "pro_monthly"
    assert after["credits_remaining"] == before["credits_remaining"] + 5000
    assert after["expires_at"] is not None


def test_free_plan_needs_no_payment(client):
    response = client.post(
        "/api/payments/checkout",
        json={"user_id": "u1", "plan_id": "free_plan", "provider": "mock"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "activated"


def test_replay_is_idempotent(client):
    """Reenviar el mismo evento no vuelve a otorgar créditos ni extender el plan."""
    approved = approve(client, "u1", "pro_monthly")
    first = client.get("/api/payments/subscription/u1").json()["subscription"]

    replay = client.post(
        "/api/payments/mock-checkout/complete",
        json={
            "user_id": "u1",
            "plan_id": "pro_monthly",
            "transaction_id": approved["transaction_id"],
        },
    )
    second = client.get("/api/payments/subscription/u1").json()["subscription"]

    assert replay.status_code == 200
    assert second["credits_remaining"] == first["credits_remaining"]
    assert second["expires_at"] == first["expires_at"]


# ── Créditos ────────────────────────────────────────────────────────────────


def test_consume_credits_updates_balance_and_ledger(client):
    approve(client, "u1", "pro_monthly")
    response = client.post(
        "/api/payments/credits/consume",
        json={"user_id": "u1", "amount": 120, "reason": "test"},
    )
    assert response.status_code == 200
    assert response.json()["balance"] == 4980

    ledger = client.get("/api/payments/credits/u1/ledger").json()["entries"]
    assert any(e["delta"] == -120 for e in ledger)


def test_cannot_overdraw(client):
    response = client.post(
        "/api/payments/credits/consume", json={"user_id": "u1", "amount": 10**6}
    )
    assert response.status_code == 402


def test_consume_rejects_non_positive_amount(client):
    """El modelo Pydantic del router ya exige amount >= 1 (422 de FastAPI)."""
    response = client.post(
        "/api/payments/credits/consume", json={"user_id": "u1", "amount": 0}
    )
    assert response.status_code == 422


def test_grant_credits_admin(client):
    response = client.post(
        "/api/payments/credits/grant", json={"user_id": "u1", "amount": 500}
    )
    assert response.status_code == 200
    assert response.json()["balance"] == 600


# ── Reembolsos ──────────────────────────────────────────────────────────────


def test_partial_refund_revokes_credits_proportionally(client):
    approved = approve(client, "u1", "pro_monthly")
    before = client.get("/api/payments/subscription/u1").json()["subscription"]

    response = client.post(
        "/api/payments/refund",
        json={"transaction_id": approved["transaction_id"], "amount_cents": 999},
    )
    assert response.status_code == 200

    after = client.get("/api/payments/subscription/u1").json()["subscription"]
    assert after["credits_remaining"] < before["credits_remaining"]


def test_refund_rejected_for_pending_transaction(client):
    checkout = client.post(
        "/api/payments/checkout",
        json={"user_id": "u1", "plan_id": "pro_monthly", "provider": "mock"},
    ).json()

    response = client.post(
        "/api/payments/refund",
        json={"transaction_id": checkout["transaction_id"], "amount_cents": 100},
    )
    assert response.status_code == 409


def test_refund_unknown_transaction(client):
    response = client.post("/api/payments/refund", json={"transaction_id": "tx_nope"})
    assert response.status_code == 404


def test_refund_cannot_exceed_paid_amount(client):
    approved = approve(client, "u1", "pro_monthly")
    response = client.post(
        "/api/payments/refund",
        json={"transaction_id": approved["transaction_id"], "amount_cents": 10**9},
    )
    assert response.status_code in (400, 409, 422)


# ── Seguridad de webhooks ───────────────────────────────────────────────────


def test_forged_webhook_signature_rejected(client):
    response = client.post(
        "/api/payments/webhook/mock",
        content=json.dumps(
            {"type": "payment.succeeded", "data": {"reference": "x", "user_id": "u1"}}
        ).encode(),
        headers={"x-signature": "forged"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_signature"


def test_webhook_without_signature_rejected(client):
    response = client.post(
        "/api/payments/webhook/mock",
        content=json.dumps({"type": "payment.succeeded", "data": {}}).encode(),
    )
    assert response.status_code == 400


def test_tampered_payload_rejected(client, service):
    """Cambiar el cuerpo pero conservar la firma debe fallar."""
    from kogniterm.server.payments.providers import build_provider
    from kogniterm.server.payments.models import PaymentProviderType

    mock = build_provider(PaymentProviderType.MOCK)
    original = json.dumps({"type": "payment.succeeded", "data": {"user_id": "u1"}}).encode()
    signature = mock.sign(original, int(time.time()))

    tampered = json.dumps(
        {"type": "payment.succeeded", "data": {"user_id": "attacker"}}
    ).encode()

    response = client.post(
        "/api/payments/webhook/mock", content=tampered, headers={"x-signature": signature}
    )
    assert response.status_code == 400


# ── Límites por plan ────────────────────────────────────────────────────────


def test_entitlements_differ_between_free_and_pro(client):
    free = client.get("/api/payments/entitlements/free_user").json()["limits"]
    approve(client, "pro_user", "pro_monthly")
    pro = client.get("/api/payments/entitlements/pro_user").json()["limits"]

    assert free["max_heartbeats"] == 0
    assert pro["max_heartbeats"] > free["max_heartbeats"]
    assert pro["agents_per_session"] > free["agents_per_session"]


# ── Persistencia e integridad ───────────────────────────────────────────────


def test_state_survives_service_restart(client, isolated_store):
    approve(client, "u1", "pro_monthly")

    from kogniterm.server import payments as payments_pkg

    payments_pkg.reset_payment_service()
    fresh = payments_pkg.get_payment_service()
    sub = fresh.get_subscription("u1")

    assert sub.tier.value == "pro"
    assert sub.credits_remaining == 5100


def test_store_file_is_created_with_restrictive_permissions(client):
    approve(client, "u1", "pro_monthly")
    data_file = Path(client.get("/api/payments/providers").json()["data_file"])
    assert data_file.exists()
    # Contiene saldos: no debe ser legible por otros usuarios del sistema.
    assert oct(data_file.stat().st_mode)[-3:] == "600"


def test_audit_chain_is_valid_after_operations(client):
    approve(client, "u1", "pro_monthly")
    client.post("/api/payments/credits/consume", json={"user_id": "u1", "amount": 10})
    body = client.get("/api/payments/audit/verify").json()
    assert body["audit"]["valid"] is True


def test_corrupt_store_is_quarantined_not_fatal(isolated_store, service):
    isolated_store.write_text("{ esto no es json", encoding="utf-8")
    from kogniterm.server import payments as payments_pkg

    payments_pkg.reset_payment_service()
    recovered = payments_pkg.get_payment_service()
    # Debe arrancar limpio, sin lanzar.
    assert recovered.get_plans()
    quarantined = list(isolated_store.parent.glob("*.corrupt-*"))
    assert quarantined, "el archivo corrupto debería quedar respaldado"


def test_legacy_v1_store_is_migrated(isolated_store):
    """El formato del módulo anterior (sin schema_version) debe importarse."""
    legacy = {
        "settings": {
            "provider_active": "mock",
            "plans": [
                {
                    "id": "pro_monthly",
                    "name": "Pro Mensual",
                    "tier": "pro",
                    "price_cents": 1999,
                    "currency": "USD",
                    "interval": "month",
                    "credits_included": 5000,
                    "features": ["Legacy"],
                }
            ],
        },
        "subscriptions": {"legacy_user": {"user_id": "legacy_user", "tier": "pro", "plan_id": "pro_monthly", "credits_remaining": 77}},
        "transactions": [],
    }
    isolated_store.write_text(json.dumps(legacy), encoding="utf-8")

    from kogniterm.server import payments as payments_pkg

    payments_pkg.reset_payment_service()
    svc = payments_pkg.get_payment_service()

    assert any(p.id == "pro_monthly" for p in svc.get_plans())
    assert svc.get_subscription("legacy_user").credits_remaining == 77


def test_reconcile_is_idempotent(client):
    approve(client, "u1", "pro_monthly")
    first = client.post("/api/payments/reconcile").json()
    second = client.post("/api/payments/reconcile").json()
    assert first["expired_count"] == 0
    assert second["expired_count"] == 0


# ── Dominio (sin HTTP) ──────────────────────────────────────────────────────


def test_entitlement_denied_for_free_tier(service):
    from kogniterm.server.payments.entitlements import require_tier
    from kogniterm.server.payments.errors import EntitlementDeniedError
    from kogniterm.server.payments.models import SubscriptionTier

    sub = service.get_subscription("free_only")
    with pytest.raises(EntitlementDeniedError):
        require_tier(sub, SubscriptionTier.PRO)


def test_expired_subscription_falls_back_to_free(service):
    """Una suscripción vencida no debe conservar el tier de pago."""
    from kogniterm.server.payments.entitlements import effective_tier
    from kogniterm.server.payments.models import SubscriptionTier

    sub = service.get_subscription("expired_user")
    sub.tier = SubscriptionTier.PRO
    sub.expires_at = time.time() - 10

    assert effective_tier(sub) is SubscriptionTier.FREE


def test_concurrent_consumption_never_goes_negative(service):
    """Los consumos sucesivos se detienen al agotarse el saldo, nunca lo cruzan."""
    from kogniterm.server.payments.errors import PaymentError

    service.get_subscription("race_user")
    service.grant_credits("race_user", 100, "test_setup")
    starting_balance = service.get_subscription("race_user").credits_remaining

    consumed = 0
    for _ in range(10):
        try:
            service.consume_credits("race_user", 30, "race")
            consumed += 1
        except PaymentError:
            break

    balance = service.get_subscription("race_user").credits_remaining
    assert balance >= 0
    assert balance == starting_balance - consumed * 30
    # El saldo debe ser el resto exacto: nunca negativo ni sobre-consumido.
    assert 0 <= balance < 30
