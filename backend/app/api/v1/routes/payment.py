"""
Payment routes — Razorpay and Stripe payment initiation and verification.
"""

import hashlib
import hmac
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.schemas.payment import (
    PaymentInitRequest, PaymentInitResponse,
    PaymentVerifyRequest, PaymentVerifyResponse,
)

router = APIRouter()


_cached_rates = {}
_cached_time = 0.0


async def get_all_exchange_rates() -> dict:
    """Fetch real-time global exchange rates for all currencies from open.er-api.com."""
    import time
    import httpx
    global _cached_rates, _cached_time
    now = time.time()
    if _cached_rates and (now - _cached_time < 300):
        return _cached_rates

    fallback_rates = {
        "USD": 1.0,
        "INR": 95.48,
        "EUR": 0.92,
        "GBP": 0.78,
        "CAD": 1.36,
        "AUD": 1.52,
        "JPY": 154.20,
        "SGD": 1.34,
        "AED": 3.67,
        "BRL": 5.65,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://open.er-api.com/v6/latest/USD")
            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})
                if rates:
                    _cached_rates = rates
                    _cached_time = now
                    return rates
    except Exception as e:
        print(f"Error fetching live global exchange rates: {e}")

    _cached_rates = fallback_rates
    _cached_time = now
    return fallback_rates


async def get_usd_to_inr_rate() -> float:
    """Fetch the real-time USD to INR exchange rate from open.er-api.com with fallback."""
    rates = await get_all_exchange_rates()
    return float(rates.get("INR", 95.48))


class ExchangeRateResponse(BaseModel):
    rate: float
    currency: str = "INR"


class AllRatesResponse(BaseModel):
    base: str = "USD"
    rates: dict
    symbols: dict


@router.get("/exchange-rate", response_model=ExchangeRateResponse)
async def get_exchange_rate():
    """Fetch live USD to INR exchange rate."""
    rate = await get_usd_to_inr_rate()
    return ExchangeRateResponse(rate=rate, currency="INR")


@router.get("/exchange-rates", response_model=AllRatesResponse)
async def get_exchange_rates(base: str = "USD"):
    """Fetch live real-time exchange rates for all global currencies."""
    rates = await get_all_exchange_rates()
    symbols = {
        "USD": "$",
        "INR": "₹",
        "EUR": "€",
        "GBP": "£",
        "CAD": "CA$",
        "AUD": "A$",
        "JPY": "¥",
        "SGD": "S$",
        "AED": "AED ",
        "BRL": "R$",
    }
    return AllRatesResponse(base=base.upper(), rates=rates, symbols=symbols)



@router.post("/initiate", response_model=PaymentInitResponse)
async def initiate_payment(
    data: PaymentInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a payment order with Razorpay or Stripe.
    Returns gateway-specific data needed by the frontend to open the payment modal.
    """
    order_uuid = uuid.UUID(data.order_id)
    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not in PENDING state")

    # Fetch live USD-to-INR rate if using Razorpay
    usd_to_inr_rate = 83.50
    if data.gateway in (PaymentGateway.RAZORPAY, PaymentGateway.UPI):
        usd_to_inr_rate = await get_usd_to_inr_rate()

    # An order has a one-to-one payment record. Reuse its gateway session on a
    # retry instead of inserting a second row and violating the unique key.
    existing_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    existing_payment = existing_result.scalar_one_or_none()
    if existing_payment:
        if existing_payment.gateway != data.gateway:
            raise HTTPException(
                status_code=400,
                detail=f"Payment has already been initiated with {existing_payment.gateway.value}.",
            )
        if data.gateway == PaymentGateway.UPI:
            inr_amount = (order.total * Decimal(str(usd_to_inr_rate))).quantize(Decimal("0.01"))
            amount_in_paise = int(inr_amount * 100)
            existing_payment.amount = inr_amount
            await db.commit()
            upi_order_id = existing_payment.gateway_order_id or f"upi_qr_{uuid.uuid4().hex[:12]}"
            upi_uri = f"upi://pay?pa=aisitestudio@upi&pn=AI%20Site%20Studio&am={inr_amount}&cu=INR&tn=Order%20{str(order.id)[:8]}&tr={upi_order_id}"
            return PaymentInitResponse(
                gateway=PaymentGateway.UPI,
                gateway_order_id=upi_order_id,
                amount=amount_in_paise,
                currency="INR",
                key_id="upi_qr_key",
                order_id=str(order.id),
                upi_uri=upi_uri,
                vpa="aisitestudio@upi",
                merchant_name="AI Site Studio",
            )
        if data.gateway == PaymentGateway.RAZORPAY:
            inr_amount = (order.total * Decimal(str(usd_to_inr_rate))).quantize(Decimal("0.01"))
            amount_in_paise = int(inr_amount * 100)
            existing_payment.amount = inr_amount
            await db.commit()
            
            return PaymentInitResponse(
                gateway=PaymentGateway.RAZORPAY,
                gateway_order_id=existing_payment.gateway_order_id,
                amount=amount_in_paise,
                currency="INR",
                key_id=(
                    "rzp_test_mockkey"
                    if existing_payment.gateway_order_id and existing_payment.gateway_order_id.startswith("rzp_mock_")
                    else settings.RAZORPAY_KEY_ID
                ),
                order_id=str(order.id),
            )
        if existing_payment.gateway_order_id:
            return PaymentInitResponse(
                gateway=PaymentGateway.STRIPE,
                gateway_order_id=existing_payment.gateway_order_id,
                amount=int(order.total * 100),
                currency="USD",
                key_id=(
                    "pk_test_mockkey"
                    if existing_payment.gateway_payment_id and existing_payment.gateway_payment_id.startswith("pi_mock_")
                    else settings.STRIPE_PUBLISHABLE_KEY
                ),
                order_id=str(order.id),
            )

        # Records created before client secrets were persisted can still be retried.
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(existing_payment.gateway_payment_id)
        existing_payment.gateway_order_id = intent.client_secret
        await db.commit()
        return PaymentInitResponse(
            gateway=PaymentGateway.STRIPE,
            gateway_order_id=intent.client_secret,
            amount=int(order.total * 100),
            currency="USD",
            key_id=settings.STRIPE_PUBLISHABLE_KEY,
            order_id=str(order.id),
        )

    if data.gateway == PaymentGateway.UPI:
        inr_amount = (order.total * Decimal(str(usd_to_inr_rate))).quantize(Decimal("0.01"))
        amount_in_paise = int(inr_amount * 100)
        upi_order_id = f"upi_qr_{uuid.uuid4().hex[:12]}"
        upi_uri = f"upi://pay?pa=aisitestudio@upi&pn=AI%20Site%20Studio&am={inr_amount}&cu=INR&tn=Order%20{str(order.id)[:8]}&tr={upi_order_id}"

        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.UPI,
            gateway_order_id=upi_order_id,
            amount=inr_amount,
            currency="INR",
        )
        db.add(payment)
        await db.flush()
        await db.commit()

        return PaymentInitResponse(
            gateway=PaymentGateway.UPI,
            gateway_order_id=upi_order_id,
            amount=amount_in_paise,
            currency="INR",
            key_id="upi_qr_key",
            order_id=str(order.id),
            upi_uri=upi_uri,
            vpa="aisitestudio@upi",
            merchant_name="AI Site Studio",
        )

    if data.gateway == PaymentGateway.RAZORPAY:
        # Mocking check: only allow mock gateway requests in local / test / development environments
        is_mock_allowed = settings.ENVIRONMENT in ("development", "local", "test")
        is_mock_key = (
            not settings.RAZORPAY_KEY_ID
            or settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
            or "change-me" in settings.RAZORPAY_KEY_ID
            or "mock" in settings.RAZORPAY_KEY_ID.lower()
        )
        
        inr_amount = (order.total * Decimal(str(usd_to_inr_rate))).quantize(Decimal("0.01"))
        amount_in_paise = int(inr_amount * 100)

        if is_mock_key:
            if not is_mock_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mock payment gateways are not allowed in this environment."
                )
            mock_order_id = f"rzp_mock_{uuid.uuid4().hex[:12]}"
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.RAZORPAY,
                gateway_order_id=mock_order_id,
                amount=inr_amount,
                currency="INR",
            )
            db.add(payment)
            await db.flush()
            await db.commit()
            return PaymentInitResponse(
                gateway=PaymentGateway.RAZORPAY,
                gateway_order_id=mock_order_id,
                amount=amount_in_paise,
                currency="INR",
                key_id="rzp_test_mockkey",
                order_id=str(order.id),
            )
        
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        rz_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": str(order.id),
        })

        # Record payment initiation
        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.RAZORPAY,
            gateway_order_id=rz_order["id"],
            amount=inr_amount,
            currency="INR",
        )
        db.add(payment)
        await db.flush()
        await db.commit()

        return PaymentInitResponse(
            gateway=PaymentGateway.RAZORPAY,
            gateway_order_id=rz_order["id"],
            amount=amount_in_paise,
            currency="INR",
            key_id=settings.RAZORPAY_KEY_ID,
            order_id=str(order.id),
        )

    elif data.gateway == PaymentGateway.STRIPE:
        is_mock_allowed = settings.ENVIRONMENT in ("development", "local", "test")
        is_mock_key = (
            not settings.STRIPE_SECRET_KEY
            or settings.STRIPE_SECRET_KEY.startswith(("sk_test_...", "your-"))
            or "change-me" in settings.STRIPE_SECRET_KEY
            or "mock" in settings.STRIPE_SECRET_KEY.lower()
        )

        if is_mock_key:
            if not is_mock_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mock payment gateways are not allowed in this environment."
                )
            mock_payment_id = f"pi_mock_{uuid.uuid4().hex[:12]}"
            mock_client_secret = f"{mock_payment_id}_secret_{uuid.uuid4().hex[:12]}"
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.STRIPE,
                gateway_payment_id=mock_payment_id,
                gateway_order_id=mock_client_secret,
                amount=order.total,
                currency="USD",
            )
            db.add(payment)
            await db.flush()
            await db.commit()
            return PaymentInitResponse(
                gateway=PaymentGateway.STRIPE,
                gateway_order_id=mock_client_secret,
                amount=int(order.total * 100),
                currency="USD",
                key_id="pk_test_mockkey",
                order_id=str(order.id),
            )

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(order.total * 100),  # cents
            currency="usd",
            metadata={"order_id": str(order.id)},
            payment_method_types=["card"],
        )

        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            gateway_payment_id=intent.id,
            gateway_order_id=intent.client_secret,
            amount=order.total,
            currency="USD",
        )
        db.add(payment)
        await db.flush()
        await db.commit()

        return PaymentInitResponse(
            gateway=PaymentGateway.STRIPE,
            gateway_order_id=intent.client_secret,
            amount=int(order.total * 100),
            currency="USD",
            key_id=settings.STRIPE_PUBLISHABLE_KEY,
            order_id=str(order.id),
        )


async def _fulfill_order_licenses(db: AsyncSession, order: Order, user_email: Optional[str] = None):
    """
    Idempotently creates License records for all order items and dispatches delivery emails.
    Works for both real webhook fulfillment and development test verifications.
    """
    try:
        from app.models.license import License, LicenseType
        from app.models.order import OrderItem
        from app.models.user import User
        from app.tasks.email_tasks import send_license_delivery
        import random, string

        recipient_email = user_email
        if not recipient_email and order.user_id:
            user_res = await db.execute(select(User).where(User.id == order.user_id))
            user = user_res.scalar_one_or_none()
            if user:
                recipient_email = user.email

        items_res = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        items = items_res.scalars().all()
        for item in items:
            # Check if license already generated (idempotent for webhook retries)
            existing_lic = await db.execute(
                select(License).where(
                    License.order_id == order.id,
                    License.template_id == item.template_id
                )
            )
            if existing_lic.scalar_one_or_none():
                continue

            license_key = f"LIC-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
            lic = License(
                user_id=order.user_id,
                template_id=item.template_id,
                order_id=order.id,
                license_key=license_key,
                license_type=LicenseType.REGULAR if item.license_type != "extended" else LicenseType.EXTENDED,
                is_active=True,
            )
            db.add(lic)
            if recipient_email:
                try:
                    send_license_delivery.delay(recipient_email, license_key, f"Template {item.template_id}")
                except Exception:
                    pass
    except Exception as lic_err:
        print(f"Notice: License fulfillment warning: {lic_err}")


@router.post("/verify", response_model=PaymentVerifyResponse)
async def verify_payment(
    data: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify payment from the client-side.
    Note: Order status is finalized via webhook. The verify endpoint checks
    if the order and payment have been successfully confirmed/captured in the DB.
    """
    order_uuid = uuid.UUID(data.order_id)
    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    result = await db.execute(
        select(Payment).where(Payment.order_id == order.id)
    )
    payment = result.scalar_one_or_none()

    # If local/test mode and using mocks or explicit mock signature, we can bypass webhook requirement
    is_mock = (
        settings.ENVIRONMENT in ("development", "local", "test")
        and (
            data.gateway == PaymentGateway.UPI
            or (data.gateway_order_id and data.gateway_order_id.startswith(("rzp_mock_", "upi_qr_")))
            or (data.gateway_payment_id and data.gateway_payment_id.startswith("pi_mock_"))
            or (data.gateway_signature == "mock_signature_verified")
        )
    )

    if is_mock:
        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=data.gateway,
                status=PaymentStatus.CAPTURED,
                gateway_payment_id=data.gateway_payment_id or f"upi_pay_{uuid.uuid4().hex[:12]}",
                amount=order.total,
                currency="USD" if data.gateway == PaymentGateway.STRIPE else "INR"
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway_payment_id = data.gateway_payment_id or payment.gateway_payment_id or f"upi_pay_{uuid.uuid4().hex[:12]}"
            
        order.status = OrderStatus.COMPLETED
        await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)

        await db.flush()
        await db.commit()
        return PaymentVerifyResponse(
            success=True,
            message="Payment verified successfully.",
            order_id=str(order.id),
        )

    # In production/staging, the webhook does the verification.
    if not payment or payment.status != PaymentStatus.CAPTURED:
        raise HTTPException(
            status_code=400,
            detail="Payment not confirmed. Please wait for webhook processing or check payment status."
        )

    return PaymentVerifyResponse(
        success=True,
        message="Payment verified successfully",
        order_id=str(order.id),
    )


@router.get("/status/{order_id}")
async def get_payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check status of a payment for dynamic polling (e.g. UPI QR code)."""
    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order_id format")

    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    pay_res = await db.execute(select(Payment).where(Payment.order_id == order.id))
    payment = pay_res.scalar_one_or_none()

    is_paid = order.status == OrderStatus.COMPLETED or (payment and payment.status == PaymentStatus.CAPTURED)

    return {
        "order_id": str(order.id),
        "order_status": order.status.value,
        "payment_status": payment.status.value if payment else "pending",
        "is_paid": is_paid,
    }


# ── Webhook Endpoints ────────────────────────────────────────────────────────
from fastapi import Request

@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe payment success webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing signature header")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        payment_intent_id = intent["id"]
        order_id_str = intent.get("metadata", {}).get("order_id")
        amount_received = intent["amount_received"] / 100.0  # Convert cents to dollars

        if not order_id_str:
            raise HTTPException(status_code=400, detail="Missing order_id in payment metadata")

        order_uuid = uuid.UUID(order_id_str)
        order_res = await db.execute(select(Order).where(Order.id == order_uuid))
        order = order_res.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Bind gateway ID and check matching amounts
        if abs(float(order.total) - amount_received) > 0.01:
            raise HTTPException(status_code=400, detail="Amount mismatch detected")

        pay_res = await db.execute(select(Payment).where(Payment.order_id == order.id))
        payment = pay_res.scalar_one_or_none()
        
        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.STRIPE,
                gateway_payment_id=payment_intent_id,
                amount=order.total,
                currency="USD",
                status=PaymentStatus.CAPTURED,
                gateway_response=event
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway_payment_id = payment_intent_id
            payment.gateway_response = event

        order.status = OrderStatus.COMPLETED
        await _fulfill_order_licenses(db, order)
        await db.flush()
        await db.commit()

    return {"status": "success"}


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Razorpay payment success webhooks."""
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    # Verify signature
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    data = json.loads(payload.decode("utf-8"))
    
    if data.get("event") == "order.paid":
        payload_data = data.get("payload", {})
        rz_payment = payload_data.get("payment", {}).get("entity", {})
        rz_order = payload_data.get("order", {}).get("entity", {})
        
        gateway_order_id = rz_order.get("id")
        gateway_payment_id = rz_payment.get("id")
        amount_paid = rz_payment.get("amount") / 100.0  # Paise to INR
        
        # Look up by gateway order ID
        pay_res = await db.execute(select(Payment).where(Payment.gateway_order_id == gateway_order_id))
        payment = pay_res.scalar_one_or_none()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found for gateway order ID")

        order_res = await db.execute(select(Order).where(Order.id == payment.order_id))
        order = order_res.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if abs(float(payment.amount) - amount_paid) > 0.01:
            raise HTTPException(status_code=400, detail="Amount mismatch detected")

        payment.status = PaymentStatus.CAPTURED
        payment.gateway_payment_id = gateway_payment_id
        payment.gateway_signature = signature
        payment.gateway_response = data
        
        order.status = OrderStatus.COMPLETED
        await _fulfill_order_licenses(db, order)
        await db.flush()
        await db.commit()

    return {"status": "success"}
