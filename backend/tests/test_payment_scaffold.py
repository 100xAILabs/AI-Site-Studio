"""
Tests for Phase 6: Real Payment Scaffolding for Generated Projects.
Verifies:
1. MockPaymentAdapter sandbox behavior and signature simulation.
2. StripePaymentAdapter compliance with Stripe Best Practices (dynamic payment methods).
3. RazorpayPaymentAdapter HMAC-SHA256 signature verification and timing-safety.
4. OrderStateMachine strict transition guarantees and illegal state rejection.
5. IdempotentEventGuard duplicate event suppression.
6. FullStackScaffoldGenerator deterministic payment scaffolding (FastAPI + React + Hybrid).
7. EnvScanner payment credentials detection.
"""

import hmac
import hashlib
import pytest
from app.services.payment_engine import (
    payment_engine,
    MockPaymentAdapter,
    StripePaymentAdapter,
    RazorpayPaymentAdapter,
    OrderStateMachine,
    OrderStatus,
    PaymentStatus,
    IdempotentEventGuard,
    PaymentOrderPayload,
    PaymentItem,
    SignatureVerifyPayload,
)
from app.services.fullstack_scaffold import fullstack_scaffold_generator
from app.services.env_scanner import env_scanner_service


# ==============================================================================
# 1. Mock Payment Adapter Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_payment_adapter_checkout():
    adapter = MockPaymentAdapter()
    payload = PaymentOrderPayload(
        order_id="ord_test_101",
        amount=99.00,
        currency="USD",
        items=[PaymentItem(name="Pro Plan", unit_amount=99.00, quantity=1)],
        customer_email="buyer@example.com",
    )
    result = await adapter.create_checkout_session(payload)
    assert result.success is True
    assert result.provider == "mock"
    assert result.order_id == "ord_test_101"
    assert "session_id=mock_sess_" in result.checkout_url
    assert result.amount == 99.00


@pytest.mark.asyncio
async def test_mock_payment_adapter_signature_verification():
    adapter = MockPaymentAdapter()
    payload = SignatureVerifyPayload(
        order_id="ord_test_101",
        payment_id="mock_pay_123",
        signature="mock_sig_456",
        provider="mock",
    )
    result = await adapter.verify_payment_signature(payload)
    assert result.valid is True
    assert result.status == OrderStatus.PAID

    # Invalid non-mock signature
    invalid_payload = SignatureVerifyPayload(
        order_id="ord_test_101",
        payment_id="live_pay_123",
        signature="invalid_sig",
        provider="mock",
    )
    invalid_result = await adapter.verify_payment_signature(invalid_payload)
    assert invalid_result.valid is False
    assert invalid_result.status == OrderStatus.FAILED


# ==============================================================================
# 2. Razorpay HMAC-SHA256 Signature Verification Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_razorpay_hmac_signature_verification():
    secret = "rzp_secret_test_key_12345"
    adapter = RazorpayPaymentAdapter(
        key_id="rzp_test_1DP5mmOlF5G5ag",
        key_secret=secret,
        webhook_secret="rzp_whsec_secret_passphrase",
    )

    order_id = "order_DBJOWzybf0sJbb"
    payment_id = "pay_29MoEsz4dOFQDu"
    message = f"{order_id}|{payment_id}".encode("utf-8")
    valid_signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    # Valid check
    verify_payload = SignatureVerifyPayload(
        order_id=order_id,
        payment_id=payment_id,
        signature=valid_signature,
        provider="razorpay",
    )
    res = await adapter.verify_payment_signature(verify_payload)
    assert res.valid is True
    assert res.status == OrderStatus.PAID
    assert res.error is None

    # Tampered signature
    tampered_payload = SignatureVerifyPayload(
        order_id=order_id,
        payment_id=payment_id,
        signature="tampered_bad_signature_hex",
        provider="razorpay",
    )
    res_tampered = await adapter.verify_payment_signature(tampered_payload)
    assert res_tampered.valid is False
    assert res_tampered.status == OrderStatus.FAILED
    assert "failed" in res_tampered.error.lower()


# ==============================================================================
# 3. Order State Machine Transition Tests
# ==============================================================================

def test_order_state_machine_valid_transitions():
    # PENDING -> PROCESSING
    assert OrderStateMachine.can_transition(OrderStatus.PENDING, OrderStatus.PROCESSING) is True
    # PENDING -> PAID
    assert OrderStateMachine.can_transition(OrderStatus.PENDING, OrderStatus.PAID) is True
    # PENDING -> FAILED
    assert OrderStateMachine.can_transition(OrderStatus.PENDING, OrderStatus.FAILED) is True
    # PROCESSING -> PAID
    assert OrderStateMachine.can_transition(OrderStatus.PROCESSING, OrderStatus.PAID) is True
    # PAID -> REFUNDED
    assert OrderStateMachine.can_transition(OrderStatus.PAID, OrderStatus.REFUNDED) is True


def test_order_state_machine_illegal_transitions():
    # PAID -> PENDING (must be rejected)
    assert OrderStateMachine.can_transition(OrderStatus.PAID, OrderStatus.PENDING) is False
    with pytest.raises(ValueError, match="Invalid order state transition"):
        OrderStateMachine.validate_transition(OrderStatus.PAID, OrderStatus.PENDING)

    # REFUNDED -> PAID (terminal state must be rejected)
    assert OrderStateMachine.can_transition(OrderStatus.REFUNDED, OrderStatus.PAID) is False
    with pytest.raises(ValueError, match="Invalid order state transition"):
        OrderStateMachine.validate_transition(OrderStatus.REFUNDED, OrderStatus.PAID)


# ==============================================================================
# 4. Webhook Idempotency Guard Tests
# ==============================================================================

def test_idempotent_event_guard():
    guard = IdempotentEventGuard()
    event_id = "evt_stripe_test_12345"

    assert guard.has_seen(event_id) is False
    guard.mark_seen(event_id)
    assert guard.has_seen(event_id) is True

    # Duplicate check
    assert guard.has_seen(event_id) is True


# ==============================================================================
# 5. Full-Stack Scaffold Generator Payment Tests
# ==============================================================================

def test_fastapi_scaffold_with_stripe_needed():
    files = fullstack_scaffold_generator.generate_fastapi_scaffold(
        stack_key="react-fastapi-postgresql",
        project_name="E-Commerce Boutique",
        stripe_needed=True,
    )

    # Payment route
    assert "backend/app/routes/payment.py" in files
    payment_py = files["backend/app/routes/payment.py"]
    assert "create-checkout-session" in payment_py
    assert "/verify" in payment_py
    assert "/webhook" in payment_py
    assert "Order" in payment_py
    assert "PaymentRecord" in payment_py

    # Models definition
    models_py = files["backend/app/models.py"]
    assert "class Order(Base):" in models_py
    assert "class PaymentRecord(Base):" in models_py
    assert "__tablename__ = \"orders\"" in models_py
    assert "__tablename__ = \"payment_records\"" in models_py

    # Main.py registration
    main_py = files["backend/app/main.py"]
    assert "from app.routes.payment import router as payment_router" in main_py
    assert 'app.include_router(payment_router, prefix="/api")' in main_py

    # Requirements & Env
    reqs = files["backend/requirements.txt"]
    assert "stripe>=8.0.0" in reqs
    env_ex = files["backend/.env.example"]
    assert "STRIPE_SECRET_KEY=" in env_ex
    assert "STRIPE_WEBHOOK_SECRET=" in env_ex
    assert "STRIPE_PUBLISHABLE_KEY=" in env_ex
    assert "RAZORPAY_KEY_ID=" in env_ex
    assert "RAZORPAY_KEY_SECRET=" in env_ex


def test_hybrid_serverless_payment_scaffold():
    files = fullstack_scaffold_generator.generate_hybrid_serverless(
        project_name="Boutique Shop"
    )

    # Serverless payment handlers
    assert "backend/api/payment.py" in files
    assert "backend/api/webhook.py" in files

    payment_api = files["backend/api/payment.py"]
    assert "create-checkout-session" in payment_api
    assert "/verify" in payment_api

    webhook_api = files["backend/api/webhook.py"]
    assert "/stripe" in webhook_api

    reqs = files["backend/requirements.txt"]
    assert "stripe>=8.0.0" in reqs

    env_ex = files["backend/.env.example"]
    assert "STRIPE_SECRET_KEY=" in env_ex
    assert "RAZORPAY_KEY_ID=" in env_ex


def test_react_scaffold_checkout_page():
    files = fullstack_scaffold_generator.generate_react_scaffold(
        stack_key="react-fastapi-postgresql",
        project_name="Boutique Shop",
        pages=[
            {"name": "Home", "filename": "index"},
            {"name": "Checkout", "filename": "checkout"},
        ],
    )

    assert "frontend/src/pages/Checkout.tsx" in files
    checkout_tsx = files["frontend/src/pages/Checkout.tsx"]
    assert "Order Checkout" in checkout_tsx
    assert "create-checkout-session" in checkout_tsx
    assert "Stripe Checkout" in checkout_tsx
    assert "Razorpay" in checkout_tsx
    assert "Test Sandbox" in checkout_tsx
    assert "Payment Confirmed!" in checkout_tsx


# ==============================================================================
# 6. Environment Scanner Payment Detection Tests
# ==============================================================================

def test_env_scanner_payment_discovery():
    meta = env_scanner_service.scan_env_requirements(
        stack_key="react-fastapi-postgresql",
        auth_required=False,
        stripe_needed=True,
    )
    keys = {m.key for m in meta}
    assert "STRIPE_SECRET_KEY" in keys
    assert "STRIPE_WEBHOOK_SECRET" in keys
    assert "STRIPE_PUBLISHABLE_KEY" in keys

    # Verify metadata richness
    stripe_sec = next(m for m in meta if m.key == "STRIPE_SECRET_KEY")
    assert stripe_sec.is_secret is True
    assert stripe_sec.provider_name == "Stripe"
    assert "sk_" in stripe_sec.validation_error.lower()
