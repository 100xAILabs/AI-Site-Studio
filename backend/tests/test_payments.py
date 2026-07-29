"""
Unit tests for payments flow with Stripe webhook validation.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch
import stripe

from app.models.category import Category
from app.models.template import Template
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus


@pytest.mark.asyncio
async def test_complete_payment_flow(auth_client: AsyncClient, db: AsyncSession):
    # 1. Seed a Category
    category = Category(name="SaaS Templates", slug="saas-templates")
    db.add(category)
    await db.flush()

    # 2. Seed a Template
    from decimal import Decimal
    template = Template(
        title="Premium SaaS Theme",
        slug="premium-saas-theme",
        short_description="Clean design for business startup",
        description="Premium SaaS Theme with animations and components.",
        price=Decimal("49.00"),
        thumbnail_url="https://picsum.photos/seed/saas/600/400",
        category_id=category.id,
        pages_count=3,
        status="published",
        download_assets={"zip": "https://storage.googleapis.com/test.zip"},
    )
    db.add(template)
    await db.flush()
    await db.commit()

    # 3. Create Order via POST /api/v1/orders
    order_payload = {
        "items": [
            {
                "template_id": str(template.id),
                "license_type": "regular"
            }
        ]
    }
    response = await auth_client.post("/api/v1/orders", json=order_payload)
    assert response.status_code == 201
    order_data = response.json()
    assert order_data["status"] == "pending"
    order_id = order_data["id"]

    # 4. Initiate Payment session via POST /api/v1/payment/initiate
    initiate_payload = {
        "order_id": order_id,
        "gateway": "stripe"
    }
    init_res = await auth_client.post("/api/v1/payment/initiate", json=initiate_payload)
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert "gateway_order_id" in init_data
    
    # Since we are in the "test" environment, initiate returns mock keys/ids
    mock_client_secret = init_data["gateway_order_id"]
    gateway_payment_id = mock_client_secret.split("_secret_")[0]

    # 5. Assert client-only confirmations (without webhooks) are rejected
    verify_payload = {
        "order_id": order_id,
        "gateway": "stripe",
        "gateway_payment_id": "pi_real_payment_id_not_mock",
        "gateway_order_id": mock_client_secret,
        "gateway_signature": "mock_sig_val",
    }
    verify_res = await auth_client.post("/api/v1/payment/verify", json=verify_payload)
    # Production/real flow expects captured status in DB. If no webhook ran, it must fail.
    assert verify_res.status_code == 400

    # 6. Simulate Stripe Webhook for succeeded payment intent
    # Mismatched amount webhook should fail
    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": gateway_payment_id,
                    "amount": 2500, # $25.00 instead of $49.00
                    "amount_received": 2500,
                    "metadata": {
                        "order_id": str(order_id)
                    }
                }
            }
        }
        webhook_res = await auth_client.post(
            "/api/v1/payment/webhook/stripe",
            content=b"dummy_payload",
            headers={"stripe-signature": "dummy_sig"}
        )
        assert webhook_res.status_code == 400

    # Invalid signature webhook should fail
    with patch("stripe.Webhook.construct_event", side_effect=stripe.error.SignatureVerificationError("Invalid sig", "sig")):
        webhook_res = await auth_client.post(
            "/api/v1/payment/webhook/stripe",
            content=b"dummy_payload",
            headers={"stripe-signature": "invalid_sig"}
        )
        assert webhook_res.status_code == 400

    # Successful webhook confirmation
    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": gateway_payment_id,
                    "amount": 4900, # $49.00
                    "amount_received": 4900,
                    "metadata": {
                        "order_id": str(order_id)
                    }
                }
            }
        }
        webhook_res = await auth_client.post(
            "/api/v1/payment/webhook/stripe",
            content=b"dummy_payload",
            headers={"stripe-signature": "dummy_sig"}
        )
        assert webhook_res.status_code == 200

    # 7. Verify call should now succeed
    verify_res = await auth_client.post("/api/v1/payment/verify", json=verify_payload)
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True

    # 8. Retrieve order to confirm it is COMPLETED now
    get_res = await auth_client.get(f"/api/v1/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "completed"
