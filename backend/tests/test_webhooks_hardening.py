"""
Hardened webhook security tests covering Razorpay and Stripe fail-closed behavior,
signature enforcement, PostgreSQL event deduplication, amount matching, and row-locking (F-12).
"""

import hmac
import hashlib
import json
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus, TemplateFramework
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.models.license import License
from app.models.webhook_event import WebhookEvent


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _seed_test_order(db: AsyncSession, amount_decimal: Decimal = Decimal("4900.00"), currency: str = "INR"):
    user = User(
        email="webhook_buyer@example.com",
        username="webhook_buyer",
        full_name="Webhook Buyer",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    cat = Category(name="Hardened Webhook Cat", slug="hardened-webhook-cat")
    db.add(cat)
    await db.flush()

    template = Template(
        title="Hardened Webhook Template",
        slug="hardened-webhook-template",
        short_description="Hardened template",
        description="Hardened template full",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.HTML,
        category_id=cat.id,
    )
    db.add(template)
    await db.flush()

    order = Order(
        user_id=user.id,
        order_number="WH-HARD-001",
        subtotal=Decimal("49.00"),
        tax=Decimal("0.00"),
        total=Decimal("49.00"),
        status=OrderStatus.PENDING,
    )
    db.add(order)
    await db.flush()

    order_item = OrderItem(
        order_id=order.id,
        template_id=template.id,
        license_type="regular",
        price=Decimal("49.00"),
    )
    db.add(order_item)
    await db.flush()

    rz_order_id = "order_wh_hardened_123"
    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        amount=amount_decimal,
        currency=currency,
        status=PaymentStatus.PENDING,
        gateway_order_id=rz_order_id,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(order)
    await db.refresh(template)
    await db.refresh(payment)

    return user, template, order, payment


@pytest.mark.asyncio
async def test_razorpay_secret_unset_returns_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=b"{}",
        headers={"X-Razorpay-Signature": "some_sig"},
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "Webhook not configured"


@pytest.mark.asyncio
async def test_razorpay_mock_signature_rejected(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_test_secret_123")
    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=b"{}",
        headers={"X-Razorpay-Signature": "mock_webhook_signature"},
    )
    assert res.status_code == 400
    assert "Invalid webhook signature" in res.json()["detail"]


@pytest.mark.asyncio
async def test_bad_signature_does_not_record_event(client: AsyncClient, db: AsyncSession, monkeypatch):
    secret = "whsec_test_secret_123"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    _, template, order, payment = await _seed_test_order(db)

    event_id = "evt_bad_sig_test_001"
    webhook_data = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_bad_sig_123",
                    "order_id": payment.gateway_order_id,
                    "amount": 490000,
                    "currency": "INR",
                }
            }
        }
    }
    payload_bytes = json.dumps(webhook_data).encode("utf-8")

    # Bad signature
    bad_res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": "invalid_sig", "X-Razorpay-Event-Id": event_id},
    )
    assert bad_res.status_code == 400

    # Ensure no WebhookEvent was recorded
    evt_check = await db.execute(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    assert evt_check.scalar_one_or_none() is None

    # Now deliver valid event with same event_id: it MUST fulfill successfully
    valid_sig = sign_payload(payload_bytes, secret)
    good_res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": valid_sig, "X-Razorpay-Event-Id": event_id},
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] in ("captured", "captured_and_fulfilled", "already_processed")


@pytest.mark.asyncio
async def test_duplicate_event_fulfils_once(client: AsyncClient, db: AsyncSession, monkeypatch):
    secret = "whsec_test_secret_123"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    _, template, order, payment = await _seed_test_order(db)
    order_id_val = order.id

    event_id = "evt_dup_test_002"
    webhook_data = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dup_123",
                    "order_id": payment.gateway_order_id,
                    "amount": 490000,
                    "currency": "INR",
                }
            }
        }
    }
    payload_bytes = json.dumps(webhook_data).encode("utf-8")
    sig = sign_payload(payload_bytes, secret)

    # 1. First post: fulfils
    res1 = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id},
    )
    assert res1.status_code == 200

    # 2. Second post: duplicate returns already_processed
    res2 = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] in ("already_processed", "already_captured")

    # Licenses count must be strictly 1
    lic_res = await db.execute(select(License).where(License.order_id == order_id_val))
    assert len(lic_res.scalars().all()) == 1


@pytest.mark.asyncio
async def test_amount_mismatch_not_fulfilled(client: AsyncClient, db: AsyncSession, monkeypatch):
    secret = "whsec_test_secret_123"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    _, template, order, payment = await _seed_test_order(db, amount_decimal=Decimal("4900.00"), currency="INR")
    order_id_val = order.id

    webhook_data = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_mismatch_123",
                    "order_id": payment.gateway_order_id,
                    "amount": 100,  # 1 INR instead of 4900 INR
                    "currency": "INR",
                }
            }
        }
    }
    payload_bytes = json.dumps(webhook_data).encode("utf-8")
    sig = sign_payload(payload_bytes, secret)

    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "amount_mismatch"

    # Order stays pending, 0 licenses
    ord_check = await db.execute(select(Order).where(Order.id == order_id_val))
    assert ord_check.scalar_one().status == OrderStatus.PENDING

    lic_check = await db.execute(select(License).where(License.order_id == order_id_val))
    assert len(lic_check.scalars().all()) == 0


@pytest.mark.asyncio
async def test_notes_order_id_without_payment_ignored(client: AsyncClient, db: AsyncSession, monkeypatch):
    secret = "whsec_test_secret_123"
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)

    # Payload references order without a matching Payment row in DB
    webhook_data = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_no_pmt_row_123",
                    "order_id": "order_non_existent_404",
                    "amount": 490000,
                    "currency": "INR",
                }
            }
        }
    }
    payload_bytes = json.dumps(webhook_data).encode("utf-8")
    sig = sign_payload(payload_bytes, secret)

    res = await client.post(
        "/api/v1/payment/webhook/razorpay",
        content=payload_bytes,
        headers={"X-Razorpay-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ignored_no_order"


@pytest.mark.asyncio
async def test_stripe_secret_unset_returns_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    res = await client.post(
        "/api/v1/payment/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "some_sig"},
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "Webhook not configured"


@pytest.mark.asyncio
async def test_stripe_fulfilment_error_returns_500(client: AsyncClient, db: AsyncSession, monkeypatch):
    import stripe
    from app.api.v1.routes import payment as payment_module

    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_stripe_test_456")
    _, template, order, payment = await _seed_test_order(db)
    order_id_val = order.id

    mock_event = {
        "id": "evt_stripe_err_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_stripe_err_123",
                "payment_intent": "pi_stripe_err_123",
                "amount_total": 490000,
                "currency": "inr",
                "payment_status": "paid",
                "metadata": {"order_id": str(order_id_val)},
            }
        }
    }

    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *args, **kwargs: mock_event)

    async def _failing_fulfillment(*args, **kwargs):
        raise RuntimeError("Simulated fulfillment crash")

    monkeypatch.setattr(payment_module, "_fulfill_order_licenses", _failing_fulfillment)

    res = await client.post(
        "/api/v1/payment/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=123,v1=abc"},
    )
    assert res.status_code == 500

    ord_check = await db.execute(select(Order).where(Order.id == order_id_val))
    assert ord_check.scalar_one().status == OrderStatus.PENDING
