"""
Tests for Stripe subscription checkout session binding (F-20).
Enforces caller-session ownership, prevents cross-user activation, rejects mismatched modes,
and guarantees atomic idempotency across direct client return and webhook events.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.subscription import SubscriptionEvent
from app.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_other_users_session_forbidden(auth_client: AsyncClient, db: AsyncSession, monkeypatch):
    """If Stripe checkout session metadata names another user_id, return 403 and write no event."""
    import stripe
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_123")
    other_user_id = str(uuid.uuid4())
    fake_sid = "cs_other_user_forbidden_123"

    mock_session = {
        "id": fake_sid,
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_other_123",
        "subscription": "sub_other_123",
        "metadata": {"user_id": other_user_id, "purchase_type": "user_subscription", "plan_id": "pro"},
        "client_reference_id": other_user_id,
    }
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *args, **kwargs: mock_session)

    res = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res.status_code == 403

    # Ensure no SubscriptionEvent row was created
    event_check = await db.execute(select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == f"stripe_checkout:{fake_sid}"))
    assert event_check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_non_subscription_session_rejected(auth_client: AsyncClient, db: AsyncSession, monkeypatch):
    """If session mode is payment / marketplace_order, reject with 400."""
    import stripe
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_123")
    me_res = await auth_client.get("/api/v1/auth/me")
    my_user_id = me_res.json()["id"]

    fake_sid = "cs_non_sub_rejected_456"
    mock_session = {
        "id": fake_sid,
        "mode": "payment",
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_pay_123",
        "metadata": {"user_id": my_user_id, "purchase_type": "marketplace_order"},
        "client_reference_id": my_user_id,
    }
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *args, **kwargs: mock_session)

    res = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res.status_code == 400
    assert "Not a subscription checkout session" in res.json()["detail"]


@pytest.mark.asyncio
async def test_missing_plan_rejected(auth_client: AsyncClient, db: AsyncSession, monkeypatch):
    """If plan_id is missing from session metadata, reject with 400."""
    import stripe
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_123")
    me_res = await auth_client.get("/api/v1/auth/me")
    my_user_id = me_res.json()["id"]

    fake_sid = "cs_missing_plan_789"
    mock_session = {
        "id": fake_sid,
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_noplan_123",
        "metadata": {"user_id": my_user_id, "purchase_type": "user_subscription"},  # No plan_id
        "client_reference_id": my_user_id,
    }
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *args, **kwargs: mock_session)

    res = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res.status_code == 400
    assert "Not a subscription checkout session" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unpaid_complete_is_pending(auth_client: AsyncClient, db: AsyncSession, monkeypatch):
    """If checkout session status is complete but payment_status is unpaid, return pending."""
    import stripe
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_123")
    me_res = await auth_client.get("/api/v1/auth/me")
    my_user_id = me_res.json()["id"]

    fake_sid = "cs_unpaid_complete_101"
    mock_session = {
        "id": fake_sid,
        "mode": "subscription",
        "status": "complete",
        "payment_status": "unpaid",
        "customer": "cus_unpaid_123",
        "metadata": {"user_id": my_user_id, "purchase_type": "user_subscription", "plan_id": "pro"},
        "client_reference_id": my_user_id,
    }
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *args, **kwargs: mock_session)

    res = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res.status_code == 200
    assert res.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_direct_return_and_webhook_grant_once(auth_client: AsyncClient, db: AsyncSession, monkeypatch):
    """
    Direct return route grants subscription once. Subsequent webhook call with same
    stripe_checkout:{sid} returns already_processed, and calling the route twice also returns already_processed.
    """
    import stripe
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock_123")
    me_res = await auth_client.get("/api/v1/auth/me")
    my_user_id = me_res.json()["id"]

    fake_sid = "cs_grant_once_idempotency_202"
    mock_session = {
        "id": fake_sid,
        "mode": "subscription",
        "status": "complete",
        "payment_status": "paid",
        "customer": "cus_grant_once_123",
        "subscription": "sub_grant_once_123",
        "metadata": {"user_id": my_user_id, "purchase_type": "user_subscription", "plan_id": "pro"},
        "client_reference_id": my_user_id,
    }
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda *args, **kwargs: mock_session)

    # 1. Direct return call
    res1 = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res1.status_code == 200
    assert res1.json()["status"] in ("active", "success", "already_processed")

    # 2. Webhook / service call with same event_id: returns already_processed
    service_result = await SubscriptionService(db).handle_subscription_payment_success(
        provider="stripe",
        event_id=f"stripe_checkout:{fake_sid}",
        user_id=uuid.UUID(my_user_id),
        user_email="testbuyer@gmail.com",
        plan_id="pro",
        billing_cycle="monthly",
        provider_sub_id="sub_grant_once_123",
        payload=mock_session,
    )
    assert service_result.get("status") == "already_processed"

    # 3. Direct return call a second time: returns already_processed
    res2 = await auth_client.post(f"/api/v1/subscriptions/verify-stripe-session/{fake_sid}")
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"
