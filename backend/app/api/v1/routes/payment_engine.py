"""
AI Site Studio — Payment Engine REST Endpoints
Handles checkout session creation, signature verification, webhook processing, and config diagnostics.
Features:
- Stripe Checkout Session creation (omits payment_method_types per Stripe best practices)
- Razorpay order creation and HMAC-SHA256 signature verification
- Raw webhook verification with idempotency check
- Diagnostic configuration verification
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, status, Header
from app.schemas.payment_scaffold import (
    ScaffoldCheckoutRequest,
    ScaffoldCheckoutResponse,
    ScaffoldVerifyRequest,
    ScaffoldVerifyResponse,
    ScaffoldWebhookResponse,
)
from app.services.payment_engine import (
    payment_engine,
    PaymentOrderPayload,
    PaymentItem,
    SignatureVerifyPayload,
    OrderStatus,
)

logger = logging.getLogger("app.api.v1.routes.payment_engine")

router = APIRouter(tags=["Payment Engine & Checkout"])


@router.get(
    "/verify-config",
    summary="Verify Payment Gateway Configuration",
    description="Inspects active Stripe, Razorpay, or Mock payment gateway credentials and readiness.",
)
async def verify_payment_config():
    adapter = payment_engine.get_adapter()
    return adapter.verify_config()


@router.post(
    "/create-checkout-session",
    response_model=ScaffoldCheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Checkout Session / Payment Order",
    description="Initializes a Stripe Checkout Session or Razorpay Order with order metadata.",
)
async def create_checkout_session(payload: ScaffoldCheckoutRequest):
    items = [
        PaymentItem(
            name=it.name,
            unit_amount=it.unit_amount,
            quantity=it.quantity,
            description=it.description,
        )
        for it in payload.items
    ]

    order_payload = PaymentOrderPayload(
        order_id=payload.order_id or f"ord_{int(1000000000 + 9000000000 * 0.1)}",
        amount=payload.amount,
        currency=payload.currency,
        items=items,
        customer_email=payload.customer_email,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        metadata=payload.metadata,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )

    result = await payment_engine.initiate_checkout(order_payload, provider=payload.provider)
    return ScaffoldCheckoutResponse(
        success=result.success,
        provider=result.provider,
        order_id=result.order_id,
        session_id=result.session_id,
        checkout_url=result.checkout_url,
        amount=result.amount,
        currency=result.currency,
        publishable_key=result.publishable_key,
        client_secret=result.client_secret,
        metadata=result.metadata,
        error=result.error,
    )


@router.post(
    "/verify",
    response_model=ScaffoldVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Payment Signature",
    description="Cryptographically verifies payment capture from client redirect or callback.",
)
async def verify_payment_signature(payload: ScaffoldVerifyRequest):
    sig_payload = SignatureVerifyPayload(
        order_id=payload.order_id,
        payment_id=payload.payment_id,
        signature=payload.signature,
        provider=payload.provider,
    )
    result = await payment_engine.verify_signature(sig_payload)
    return ScaffoldVerifyResponse(
        valid=result.valid,
        order_id=result.order_id,
        payment_id=result.payment_id,
        provider=result.provider,
        status=result.status.value,
        error=result.error,
    )


@router.post(
    "/webhook/{provider}",
    response_model=ScaffoldWebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Payment Gateway Webhook",
    description="Receives raw webhook events, validates cryptographic signatures, and guarantees idempotency.",
)
async def process_payment_webhook(provider: str, request: Request):
    raw_body = await request.body()
    headers_dict = dict(request.headers)

    try:
        res = await payment_engine.process_webhook(
            provider=provider.lower().strip(),
            raw_body=raw_body,
            headers=headers_dict,
        )
        return ScaffoldWebhookResponse(
            status=res.get("status", "processed"),
            event_id=res.get("event_id"),
            event_type=res.get("event_type"),
            order_id=res.get("order_id"),
            amount=res.get("amount"),
            provider=provider,
        )
    except Exception as exc:
        logger.error(f"Webhook processing error for provider '{provider}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook verification failed: {str(exc)}",
        )
