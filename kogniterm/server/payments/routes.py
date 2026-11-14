"""FastAPI routes for payments, billing and subscriptions."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from .models import (
    CancelSubscriptionResponse,
    CheckoutCompleteRequest,
    CheckoutCompleteResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentHistoryItem,
    PaymentMethod,
    PaymentProvider,
    PlanInfo,
    Subscription,
    SwitchPlanRequest,
    UsageQuota,
    WebhookEvent,
)
from .service import payment_service

router = APIRouter(prefix="/api/payments", tags=["Payments"])


def get_user_id(x_user_id: Optional[str] = Header(default=None, alias="X-User-ID")) -> str:
    return x_user_id or "local-user"


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans() -> list[PlanInfo]:
    return payment_service.list_plans()


@router.get("/plans/{plan_id}", response_model=PlanInfo)
async def get_plan(plan_id: str) -> PlanInfo:
    return payment_service.get_plan(plan_id)


@router.get("/subscription", response_model=Subscription)
async def get_subscription(user_id: str = Depends(get_user_id)) -> Subscription:
    return payment_service.get_user_subscription(user_id)


@router.post("/checkout/session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    req: CheckoutSessionRequest,
    user_id: str = Depends(get_user_id),
) -> CheckoutSessionResponse:
    return payment_service.create_checkout_session(user_id, req)


@router.post("/checkout/complete", response_model=CheckoutCompleteResponse)
async def complete_checkout_session(
    req: CheckoutCompleteRequest,
    user_id: str = Depends(get_user_id),
) -> CheckoutCompleteResponse:
    return payment_service.complete_checkout_session(user_id, req)


@router.post("/subscription/switch", response_model=Subscription)
async def switch_subscription_plan(
    req: SwitchPlanRequest,
    user_id: str = Depends(get_user_id),
) -> Subscription:
    return payment_service.switch_plan(user_id, req)


@router.post("/subscription/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    at_period_end: bool = Query(default=False),
    user_id: str = Depends(get_user_id),
) -> CancelSubscriptionResponse:
    sub = payment_service.cancel_subscription(user_id, at_period_end=at_period_end)
    return CancelSubscriptionResponse(status="ok", subscription=sub)


@router.get("/usage", response_model=UsageQuota)
async def get_usage_quota(
    active_sessions_count: int = Query(default=0, ge=0),
    user_id: str = Depends(get_user_id),
) -> UsageQuota:
    return payment_service.get_usage_quota(user_id, active_sessions_count=active_sessions_count)


@router.get("/methods", response_model=list[PaymentMethod])
async def list_payment_methods(user_id: str = Depends(get_user_id)) -> list[PaymentMethod]:
    return payment_service.list_payment_methods(user_id)


@router.post("/methods/mock", response_model=PaymentMethod)
async def add_mock_payment_method(
    brand: str = Query(default="visa"),
    last4: str = Query(default="4242"),
    user_id: str = Depends(get_user_id),
) -> PaymentMethod:
    return payment_service.add_mock_payment_method(user_id, brand=brand, last4=last4)


@router.get("/history", response_model=list[PaymentHistoryItem])
async def list_payment_history(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_user_id),
) -> list[PaymentHistoryItem]:
    return payment_service.list_payment_history(user_id, limit=limit)


@router.post("/webhooks/mock", response_model=WebhookEvent)
async def mock_webhook(payload: dict) -> WebhookEvent:
    return payment_service.handle_webhook(payload, provider=PaymentProvider.MOCK)


@router.post("/webhooks/stripe", response_model=WebhookEvent)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
) -> WebhookEvent:
    body = await request.body()
    if not payment_service.verify_stripe_signature(body, stripe_signature):
        raise HTTPException(status_code=400, detail="Firma de webhook Stripe inválida")
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON inválido")
    return payment_service.handle_webhook(payload, provider=PaymentProvider.STRIPE)
