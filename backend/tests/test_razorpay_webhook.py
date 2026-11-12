"""
Tests for Production Razorpay Webhooks and Tax-Free Template Pricing.
"""

import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.template import Template, TemplateFramework
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.models.license import License


@pytest.mark.asyncio
async def test_order_creation_has_zero_tax(auth_client: AsyncClient, db: AsyncSession):
    """Verify that templates are charged strictly the template price with $0 extra tax."""
    from app.models.category import Category

    cat = Category(name="Modern", slug="modern-templates")
    db.add(cat)
    await db.flush()

    from app.models.template import TemplateStatus

    # 1. Create a test template
    template = Template(
        title="Zero Tax Modern Template",
        slug="zero-tax-modern-template",
        short_description="Clean template test",
        description="Clean template test full description",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.HTML,
        category_id=cat.id,
    )
    db.add(template)
    await db.flush()
    await db.commit()
    await db.refresh(template)

    # 2. Place order
    res = await auth_client.post("/api/v1/orders", json={
        "items": [{"template_id": str(template.id), "license_type": "regular"}],
        "country_code": "IN",
    })
    assert res.status_code == 201
    order_data = res.json()

    # Verify: Tax is exactly 0 and total equals template price
    assert float(order_data["tax"]) == 0.0
    assert float(order_data["subtotal"]) == 49.0
    assert float(order_data["total"]) == 49.0


@pytest.mark.asyncio
async def test_razorpay_webhook_signature_validation(client: AsyncClient):
    """Webhook must reject calls without signature or with fraudulent signatures."""
    payload = json.dumps({"event": "payment.captured"}).encode("utf-8")

    # Missing signature
    res1 = await client.post("/api/v1/payment/webhook/razorpay", content=payload)
    assert res1.status_code == 400
    assert "signature" in res1.json()["detail"].lower()

    # Fraudulent signature
    res2 = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload,
        headers={"X-Razorpay-Signature": "fraudulent_signature_hex_12345"}
    )
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_razorpay_webhook_payment_captured_and_idempotency(client: AsyncClient, db: AsyncSession):
    """
    Webhook confirms payment, captures order, and fulfills licenses even if the
    user closed their browser tab before client-side verify ran.
    """
    secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET

    # Seed test user, template, order, and pending payment
    user = User(
        email="webhook_buyer@example.com",
        username="webhook_buyer",
        full_name="Webhook Buyer",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    from app.models.category import Category

    cat = Category(name="Business", slug=f"business-{user.id.hex[:6]}")
    db.add(cat)
    await db.flush()

    template = Template(
        title="Webhook Test SaaS Starter",
        slug="webhook-saas-starter",
        short_description="Full SaaS starter codebase",
        description="Production SaaS starter bundle",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("59.00"),
        framework=TemplateFramework.REACT,
        category_id=cat.id,
    )
    db.add(template)
    await db.flush()

    order = Order(
        user_id=user.id,
        order_number="ASS-WH-1001",
        subtotal=Decimal("59.00"),
        tax=Decimal("0.00"),
        total=Decimal("59.00"),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()

    order_item = OrderItem(
        order_id=order.id,
        template_id=template.id,
        price=Decimal("59.00"),
    )
    db.add(order_item)
    await db.flush()

    rz_order_id = "order_wh_test_998877"
    rz_payment_id = "pay_wh_test_112233"

    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        amount=Decimal("4950.00"),
        currency="INR",
        status=PaymentStatus.PENDING,
        gateway_order_id=rz_order_id,
    )
    db.add(payment)
    await db.commit()

    # Construct Razorpay payment.captured webhook payload
    webhook_data = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": rz_payment_id,
                    "order_id": rz_order_id,
                    "amount": 495000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {"order_id": str(order.id)},
                }
            },
            "order": {
                "entity": {
                    "id": rz_order_id,
                    "amount": 495000,
                    "currency": "INR",
                    "status": "paid",
                }
            }
        }
    }
    raw_payload = json.dumps(webhook_data).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    # 1. Deliver webhook
    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_payload,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "captured_and_fulfilled"

    # Verify DB: Payment captured, Order completed, License created
    await db.refresh(payment)
    await db.refresh(order)
    assert payment.status == PaymentStatus.CAPTURED
    assert payment.gateway_payment_id == rz_payment_id
    assert order.status == OrderStatus.COMPLETED

    lic_res = await db.execute(select(License).where(License.order_id == order.id))
    licenses = lic_res.scalars().all()
    assert len(licenses) == 1
    assert licenses[0].template_id == template.id

    # 2. Idempotency test: delivering the same webhook event again must not fail or duplicate
    res_retry = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_payload,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] == "already_captured"

    # Licenses count must remain 1
    lic_res_retry = await db.execute(select(License).where(License.order_id == order.id))
    assert len(lic_res_retry.scalars().all()) == 1


@pytest.mark.asyncio
async def test_razorpay_webhook_payment_failed(client: AsyncClient, db: AsyncSession):
    """Webhook records payment.failed accurately."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET

    user = User(
        email="failed_buyer@example.com",
        username="failed_buyer",
        full_name="Failed Buyer",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    order = Order(
        user_id=user.id,
        order_number="ASS-WH-FAIL-1",
        subtotal=Decimal("29.00"),
        tax=Decimal("0.00"),
        total=Decimal("29.00"),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()

    rz_order_id = "order_fail_test_4455"
    rz_payment_id = "pay_fail_test_6677"

    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        amount=Decimal("2400.00"),
        currency="INR",
        status=PaymentStatus.PENDING,
        gateway_order_id=rz_order_id,
    )
    db.add(payment)
    await db.commit()

    webhook_data = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": rz_payment_id,
                    "order_id": rz_order_id,
                    "amount": 240000,
                    "error_description": "Bank servers declined transaction",
                }
            }
        }
    }
    raw_payload = json.dumps(webhook_data).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_payload,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "failed_recorded"

    await db.refresh(payment)
    assert payment.status == PaymentStatus.FAILED


@pytest.mark.asyncio
async def test_razorpay_webhook_event_id_deduplication(client: AsyncClient):
    """X-Razorpay-Event-Id header deduplicates repeated webhook deliveries."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET
    event_id = "evt_dedup_unique_test_123"

    webhook_data = {
        "event": "subscription.authenticated",
        "payload": {}
    }
    raw_payload = json.dumps(webhook_data).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    # First delivery
    res1 = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_payload,
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
            "Content-Type": "application/json"
        }
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "subscription_authenticated"

    # Second delivery (retried with same event id)
    res2 = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_payload,
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
            "Content-Type": "application/json"
        }
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"
    assert res2.json()["event_id"] == event_id


@pytest.mark.asyncio
async def test_razorpay_webhook_subscription_lifecycle(client: AsyncClient, db: AsyncSession):
    """
    subscription.charged activates the Extreme subscription and adds tokens.
    subscription.cancelled downgrades tier back to free.
    """
    secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET

    user = User(
        email="sub_lifecycle_user@example.com",
        username="sub_lifecycle_user",
        full_name="Subscriber Lifecycle",
        role=UserRole.BUYER,
        subscription_tier="free",
        ai_credits=50,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    assert user.is_pro_subscriber is False

    # 1. subscription.charged event for Extreme tier
    charge_data = {
        "event": "subscription.charged",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test_ext_8899",
                    "plan_id": "plan_extreme",
                    "notes": {
                        "user_id": str(user.id),
                        "user_email": user.email,
                        "plan_id": "extreme",
                    }
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_sub_ext_1122",
                    "amount": 420000,
                    "currency": "INR",
                    "email": user.email,
                }
            }
        }
    }
    raw_charge = json.dumps(charge_data).encode("utf-8")
    sig_charge = hmac.new(secret.encode("utf-8"), raw_charge, hashlib.sha256).hexdigest()

    res_charge = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_charge,
        headers={
            "X-Razorpay-Signature": sig_charge,
            "X-Razorpay-Event-Id": f"evt_charge_{user.id.hex[:6]}",
            "Content-Type": "application/json"
        }
    )
    assert res_charge.status_code == 200
    assert res_charge.json()["status"] == "subscription_charged"
    assert res_charge.json()["tier"] == "extreme"

    await db.refresh(user)
    assert user.subscription_tier == "extreme"
    assert user.is_pro_subscriber is True
    assert user.ai_credits == 1050  # 50 initial + 1000 extreme bonus

    # 2. subscription.cancelled event
    cancel_data = {
        "event": "subscription.cancelled",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test_ext_8899",
                    "notes": {
                        "user_id": str(user.id),
                        "user_email": user.email,
                    }
                }
            }
        }
    }
    raw_cancel = json.dumps(cancel_data).encode("utf-8")
    sig_cancel = hmac.new(secret.encode("utf-8"), raw_cancel, hashlib.sha256).hexdigest()

    res_cancel = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=raw_cancel,
        headers={
            "X-Razorpay-Signature": sig_cancel,
            "X-Razorpay-Event-Id": f"evt_cancel_{user.id.hex[:6]}",
            "Content-Type": "application/json"
        }
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "subscription_revoked"
    assert res_cancel.json()["tier"] == "free"

    await db.refresh(user)
    assert user.subscription_tier == "free"
    assert user.is_pro_subscriber is False
