from datetime import datetime, timezone

import pytest

from kogniterm.server.payments.models import (
    PlanInfo,
    PlanTier,
    BillingCycle,
    PaymentProvider,
    SubscriptionStatus,
)
from kogniterm.server.payments.service import PaymentService, AVAILABLE_PLANS


@pytest.fixture()
def payment_service():
    service = PaymentService()
    service._subscriptions_db.clear()
    service._usage_db.clear()
    service._checkout_sessions.clear()
    return service


def test_available_plans_contains_free_pro_and_enterprise():
    plan_ids = set(AVAILABLE_PLANS)
    assert "plan_free" in plan_ids
    assert "plan_pro_monthly" in plan_ids
    assert "plan_pro_yearly" in plan_ids
    assert "plan_enterprise" in plan_ids


def test_default_subscription_is_free(payment_service):
    sub = payment_service.get_user_subscription("user-1")
    assert sub.plan_id == "plan_free"
    assert sub.status == SubscriptionStatus.ACTIVE
    assert isinstance(datetime.fromisoformat(sub.current_period_start), datetime)


def test_create_mock_checkout_session_activates_plan(payment_service):
    req = type("Req", (), {"plan_id": "plan_pro_monthly", "success_url": "http://example.com/success", "cancel_url": "http://example.com/cancel", "customer_email": "test@example.com", "user_id": "user-1", "provider": PaymentProvider.MOCK})()
    response = payment_service.create_checkout_session("user-1", req)
    assert response.provider == PaymentProvider.MOCK
    assert "session_id=" in response.checkout_url or response.checkout_url.startswith("http")

    sub = payment_service.get_user_subscription("user-1")
    assert sub.plan_id == "plan_pro_monthly"


def test_complete_checkout_sets_active_subscription(payment_service):
    req = type("Req", (), {"plan_id": "plan_pro_yearly", "success_url": "http://example.com/success", "cancel_url": "http://example.com/cancel", "customer_email": "test@example.com", "user_id": "user-1", "provider": PaymentProvider.MOCK})()
    checkout = payment_service.create_checkout_session("user-1", req)
    completed = payment_service.complete_checkout_session("user-1", type("CReq", (), {"session_id": checkout.session_id, "user_id": "user-1", "plan_id": None})())
    assert completed.status == "success"
    assert completed.subscription.plan_id == "plan_pro_yearly"


def test_switch_plan_changes_subscription(payment_service):
    initial = payment_service.get_user_subscription("user-1")
    assert initial.plan_id == "plan_free"

    switched = payment_service.switch_plan("user-1", type("SwitchReq", (), {"plan_id": "plan_enterprise", "provider": PaymentProvider.MOCK, "prorate": True})())
    sub = payment_service.get_user_subscription("user-1")
    assert sub.plan_id == "plan_enterprise"


def test_cancel_subscription_downgrades_to_free(payment_service):
    req = type("Req", (), {"plan_id": "plan_pro_monthly", "success_url": "http://example.com/success", "cancel_url": "http://example.com/cancel", "customer_email": "test@example.com", "user_id": "user-1", "provider": PaymentProvider.MOCK})()
    payment_service.create_checkout_session("user-1", req)
    canceled = payment_service.cancel_subscription("user-1", at_period_end=False)
    assert canceled.plan_id == "plan_free"
    assert canceled.status == SubscriptionStatus.CANCELED


def test_usage_quota_reflects_plan_limits(payment_service):
    req = type("Req", (), {"plan_id": "plan_free", "success_url": "http://example.com/success", "cancel_url": "http://example.com/cancel", "customer_email": "test@example.com", "user_id": "user-1", "provider": PaymentProvider.MOCK})()
    payment_service.create_checkout_session("user-1", req)
    quota = payment_service.get_usage_quota("user-1", active_sessions_count=1)
    assert quota.tier == PlanTier.FREE
    assert quota.sessions_limit == 2
    assert quota.sessions_active == 1
