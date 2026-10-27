"""
Payment routes — Razorpay and Stripe payment initiation and verification.
"""

import hashlib
import hmac
import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.models.deployment import Deployment, Domain
from app.models.hosting_subscription import HostingSubscription
from app.schemas.payment import (
    PaymentInitRequest, PaymentInitResponse,
    PaymentVerifyRequest, PaymentVerifyResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def calculate_order_inr_amount(order: Order, usd_to_inr_rate: float) -> Decimal:
    """
    Accurately calculate INR amount for an order.
    If templates are in INR, use the exact template price without currency conversion
    to prevent rounding losses (e.g., ₹5 becoming ₹4.80).
    """
    # 1. Check if order or items are explicitly in INR
    is_inr = False
    if order.extra_metadata and str(order.extra_metadata.get("currency", "")).upper() == "INR":
        is_inr = True
    elif order.items and all(item.template and str(getattr(item.template, "price_currency", "USD")).upper() == "INR" for item in order.items):
        is_inr = True

    if is_inr:
        return Decimal(str(order.total)).quantize(Decimal("0.01"))

    # 2. Check individual items for mixed or INR items
    if order.items:
        total_inr = Decimal("0")
        has_inr = False
        for item in order.items:
            curr = str(getattr(item.template, "price_currency", "USD") or "USD").upper() if item.template else "USD"
            if curr == "INR":
                has_inr = True
                total_inr += Decimal(str(item.price))
            else:
                total_inr += Decimal(str(item.price)) * Decimal(str(usd_to_inr_rate))
        if has_inr:
            return total_inr.quantize(Decimal("0.01"))

    # 3. Fallback: USD order converted to INR
    raw_inr = order.total * Decimal(str(usd_to_inr_rate))

    # Anti-rounding loss guard: If seller listed at 5 INR, old frontend converted 5 / 96 = 0.05 USD.
    # 0.05 * 95.48 = 4.77 or 4.80. If order total is 0.05 (or 0.052), restore the original ₹5.00!
    if Decimal("0.045") <= order.total <= Decimal("0.055") and Decimal("4.60") <= raw_inr <= Decimal("5.10"):
        return Decimal("5.00")

    return raw_inr.quantize(Decimal("0.01"))


_cached_rates = {}
_cached_time = 0.0


async def get_all_exchange_rates() -> dict:
    """Fetch real-time global exchange rates for all currencies from open.er-api.com."""
    import time
    import httpx
    global _cached_rates, _cached_time
    now = time.time()
    if _cached_rates and (now - _cached_time < 3600):
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
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get("https://open.er-api.com/v6/latest/USD")
            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})
                if rates:
                    _cached_rates = rates
                    _cached_time = now
                    return rates
    except Exception:
        pass

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
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.template))
        .where(Order.id == order_uuid)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not in PENDING state")
    if settings.TEMPLATE_DOWNLOADS_FREE and any(item.template_id for item in (order.items or [])):
        raise HTTPException(
            status_code=410,
            detail="Marketplace templates are free to download right now. No payment is due.",
        )

    if data.gateway == PaymentGateway.UPI:
        merchant_vpa = settings.UPI_MERCHANT_VPA.strip()
        if not merchant_vpa or "yourname" in merchant_vpa.lower():
            raise HTTPException(status_code=503, detail="UPI payments are not configured. Please choose another payment method.")

    # Fetch live USD-to-INR rate if using Razorpay or UPI
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
            inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
            amount_in_paise = int(inr_amount * 100)
            existing_payment.amount = inr_amount
            await db.commit()
            upi_order_id = existing_payment.gateway_order_id or f"upi_qr_{uuid.uuid4().hex[:12]}"
            merchant_vpa = settings.UPI_MERCHANT_VPA.strip()
            merchant_name = getattr(settings, "UPI_MERCHANT_NAME", "AI Site Studio")
            upi_uri = f"upi://pay?pa={merchant_vpa}&pn={merchant_name}&am={inr_amount}&cu=INR&tn=Order%20{str(order.id)[:8]}&tr={upi_order_id}"
            return PaymentInitResponse(
                gateway=PaymentGateway.UPI,
                gateway_order_id=upi_order_id,
                amount=amount_in_paise,
                currency="INR",
                key_id="upi_qr_key",
                order_id=str(order.id),
                upi_uri=upi_uri,
                vpa=merchant_vpa,
                merchant_name=merchant_name,
            )
        if data.gateway == PaymentGateway.RAZORPAY:
            inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
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
        inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
        amount_in_paise = int(inr_amount * 100)
        upi_order_id = f"upi_qr_{uuid.uuid4().hex[:12]}"
        merchant_vpa = settings.UPI_MERCHANT_VPA.strip()
        merchant_name = getattr(settings, "UPI_MERCHANT_NAME", "AI Site Studio")
        upi_uri = f"upi://pay?pa={merchant_vpa}&pn={merchant_name}&am={inr_amount}&cu=INR&tn=Order%20{str(order.id)[:8]}&tr={upi_order_id}"

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
            vpa=merchant_vpa,
            merchant_name=merchant_name,
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
        
        inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
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
        
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
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

    # 1. UPI Payment Verification with 12-Digit Bank Reference (UTR)
    if data.gateway == PaymentGateway.UPI:
        raw_utr = (data.upi_utr or "").strip()
        if not raw_utr and data.gateway_payment_id:
            raw_utr = data.gateway_payment_id.replace("UTR:", "").replace("utr_", "").strip()

        # Reject bypass attempts, empty UTRs, or mock tokens
        if not raw_utr or raw_utr in ("mock_signature_verified", "upi_utr_verified") or raw_utr.startswith("upi_pay_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid 12-digit UPI Reference (UTR) number is required from your payment receipt."
            )

        # Enforce exact 12 numeric digits
        if not (raw_utr.isdigit() and len(raw_utr) == 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid UPI Reference (UTR) number '{raw_utr}'. UTR must be exactly 12 numeric digits from your GPay, PhonePe, or Paytm receipt."
            )

        # Reject obvious fake/dummy test sequences
        bogus_utrs = {"000000000000", "111111111111", "123456789012", "999999999999", "123456123456"}
        if raw_utr in bogus_utrs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid test UTR entered. Please enter the genuine 12-digit transaction ID from your UPI payment receipt."
            )

        # Anti-fraud: Check if this UTR has already been claimed for another order
        if payment and payment.gateway != PaymentGateway.UPI:
            raise HTTPException(status_code=409, detail="This order already has a payment through a different gateway.")

        dup_query = select(Payment).where(
            or_(
                Payment.gateway_payment_id == f"UTR:{raw_utr}",
                Payment.gateway_payment_id == raw_utr
            ),
            Payment.order_id != order.id
        ).limit(1)
        dup_res = await db.execute(dup_query)
        existing_claimed = dup_res.scalar_one_or_none()
        if existing_claimed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This UPI Reference (UTR: {raw_utr}) has already been used for another order. Each transaction requires a unique payment receipt."
            )

        utr_formatted = f"UTR:{raw_utr}"
        if payment and payment.status == PaymentStatus.CAPTURED:
            return PaymentVerifyResponse(
                success=True,
                message="This UPI payment has already been confirmed.",
                order_id=str(order.id),
            )

        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.UPI,
                status=PaymentStatus.PENDING,
                gateway_payment_id=utr_formatted,
                amount=order.total,
                currency="INR",
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.PENDING
            payment.gateway_payment_id = utr_formatted

        from datetime import datetime, timezone
        meta = dict(order.extra_metadata or {})
        meta["upi_utr"] = raw_utr
        meta["upi_utr_submitted_at"] = datetime.now(timezone.utc).isoformat()
        order.extra_metadata = meta

        await db.flush()
        await db.commit()

        return PaymentVerifyResponse(
            success=True,
            message="UPI reference submitted. Your order stays pending until the payment is confirmed.",
            order_id=str(order.id),
        )

    # 2. Simulated card flow (Stripe/Razorpay test mode only)
    is_card_mock = (
        data.gateway in (PaymentGateway.STRIPE, PaymentGateway.RAZORPAY)
        and (
            (data.gateway_order_id and data.gateway_order_id.startswith(("rzp_mock_", "pi_mock_")))
            or (data.gateway_payment_id and data.gateway_payment_id.startswith(("pi_mock_", "pay_mock_")))
            or (data.gateway_signature == "mock_signature_verified")
        )
    )

    if is_card_mock:
        if settings.ENVIRONMENT not in ("development", "local", "test"):
            raise HTTPException(status_code=400, detail="Mock payments are not allowed in this environment.")
        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=data.gateway,
                status=PaymentStatus.CAPTURED,
                gateway_payment_id=data.gateway_payment_id or f"pay_mock_{uuid.uuid4().hex[:12]}",
                amount=order.total,
                currency="USD" if data.gateway == PaymentGateway.STRIPE else "INR"
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway_payment_id = data.gateway_payment_id or payment.gateway_payment_id or f"pay_mock_{uuid.uuid4().hex[:12]}"
            
        order.status = OrderStatus.COMPLETED
        await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)

        await db.flush()
        await db.commit()
        return PaymentVerifyResponse(
            success=True,
            message="Payment verified successfully in test sandbox.",
            order_id=str(order.id),
        )

    # 2. Direct client-side Razorpay signature verification
    if (
        data.gateway == PaymentGateway.RAZORPAY
        and data.gateway_order_id
        and data.gateway_payment_id
        and data.gateway_signature
        and settings.RAZORPAY_KEY_SECRET
    ):
        import hmac
        import hashlib
        msg = f"{data.gateway_order_id}|{data.gateway_payment_id}".encode("utf-8")
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            msg,
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(generated_signature, data.gateway_signature):
            if not payment:
                payment = Payment(
                    order_id=order.id,
                    gateway=PaymentGateway.RAZORPAY,
                    status=PaymentStatus.CAPTURED,
                    gateway_order_id=data.gateway_order_id,
                    gateway_payment_id=data.gateway_payment_id,
                    amount=order.total,
                    currency="INR",
                )
                db.add(payment)
            else:
                payment.status = PaymentStatus.CAPTURED
                payment.gateway_payment_id = data.gateway_payment_id

            order.status = OrderStatus.COMPLETED
            await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)
            await db.flush()
            await db.commit()
            return PaymentVerifyResponse(
                success=True,
                message="Payment verified successfully via Razorpay signature.",
                order_id=str(order.id),
            )

    # 3. In production/staging with webhooks, check if captured
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
        "upi_utr": (order.extra_metadata or {}).get("upi_utr") if order.extra_metadata else None,
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

    if event["type"] in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        checkout_session = event["data"]["object"]
        metadata = checkout_session.get("metadata") or {}
        if metadata.get("purchase_type") == "domain_registration":
            from app.services.domain_purchase_service import fulfill_domain_checkout
            await fulfill_domain_checkout(checkout_session, db)
        elif metadata.get("purchase_type") == "hosting_subscription":
            subscription_id = checkout_session.get("subscription")
            if subscription_id:
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                sub_metadata = stripe_subscription.get("metadata") or metadata
                deployment_id = sub_metadata.get("deployment_id") or metadata.get("deployment_id")
                user_id = sub_metadata.get("user_id") or metadata.get("user_id")
                if deployment_id and user_id:
                    row_result = await db.execute(select(HostingSubscription).where(
                        (HostingSubscription.stripe_subscription_id == subscription_id)
                        | (HostingSubscription.deployment_id == uuid.UUID(deployment_id))
                    ))
                    row = row_result.scalar_one_or_none()
                    if not row:
                        row = HostingSubscription(
                            deployment_id=uuid.UUID(deployment_id),
                            user_id=uuid.UUID(user_id),
                            stripe_subscription_id=subscription_id,
                            stripe_customer_id=checkout_session.get("customer"),
                            status=stripe_subscription.get("status", "active"),
                        )
                        db.add(row)
                    else:
                        row.stripe_subscription_id = subscription_id
                        row.user_id = uuid.UUID(user_id)
                        row.status = stripe_subscription.get("status", row.status)
                    period_end = stripe_subscription.get("current_period_end")
                    if period_end:
                        from datetime import datetime, timezone
                        row.current_period_end = datetime.fromtimestamp(period_end, timezone.utc)
                    deployment_result = await db.execute(select(Deployment).where(Deployment.id == uuid.UUID(deployment_id)))
                    hosting_deployment = deployment_result.scalar_one_or_none()
                    if hosting_deployment and hosting_deployment.hosting_checkout_session_id == checkout_session.get("id"):
                        hosting_deployment.hosting_checkout_session_id = None
                    await db.commit()

    elif event["type"] in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        subscription_data = event["data"]["object"]
        subscription_id = subscription_data["id"]
        sub_metadata = subscription_data.get("metadata") or {}
        deployment_id = sub_metadata.get("deployment_id")
        row_result = await db.execute(select(HostingSubscription).where(
            HostingSubscription.stripe_subscription_id == subscription_id
        ))
        row = row_result.scalar_one_or_none()
        stale_subscription_event = False
        if not row and deployment_id:
            deployment_row_result = await db.execute(select(HostingSubscription).where(
                HostingSubscription.deployment_id == uuid.UUID(deployment_id)
            ))
            candidate = deployment_row_result.scalar_one_or_none()
            if candidate and candidate.stripe_subscription_id != subscription_id:
                terminal_states = {"canceled", "unpaid", "incomplete_expired"}
                if event["type"] == "customer.subscription.deleted" or candidate.status not in terminal_states:
                    stale_subscription_event = True
                else:
                    row = candidate
            else:
                row = candidate
        deployment = None
        if not row and not stale_subscription_event and event["type"] != "customer.subscription.deleted" and sub_metadata.get("deployment_id") and sub_metadata.get("user_id"):
            row = HostingSubscription(
                deployment_id=uuid.UUID(sub_metadata["deployment_id"]),
                user_id=uuid.UUID(sub_metadata["user_id"]),
                stripe_subscription_id=subscription_id,
                stripe_customer_id=subscription_data.get("customer"),
                status=subscription_data.get("status", "incomplete"),
            )
            db.add(row)
        if row:
            row.stripe_subscription_id = subscription_id
            row.status = subscription_data.get("status", row.status)
            row.stripe_customer_id = subscription_data.get("customer") or row.stripe_customer_id
            row.cancel_at_period_end = bool(subscription_data.get("cancel_at_period_end", False))
            if row.status in {"active", "trialing"}:
                row.last_payment_failed_at = None
            if row.status == "past_due":
                from datetime import datetime, timezone, timedelta
                if not row.last_payment_failed_at:
                    row.last_payment_failed_at = datetime.now(timezone.utc)
                failed_at = row.last_payment_failed_at
                if failed_at.tzinfo is None:
                    failed_at = failed_at.replace(tzinfo=timezone.utc)
                try:
                    from app.tasks.hosting_tasks import cancel_unpaid_hosting_after_grace
                    cancel_unpaid_hosting_after_grace.apply_async(
                        args=[str(row.id)],
                        countdown=max(0, int((failed_at + timedelta(days=max(0, settings.HOSTING_GRACE_PERIOD_DAYS)) - datetime.now(timezone.utc)).total_seconds())),
                    )
                except Exception:
                    logger.exception("Could not queue hosting grace-period cancellation")
            period_end = subscription_data.get("current_period_end")
            if period_end:
                from datetime import datetime, timezone
                row.current_period_end = datetime.fromtimestamp(period_end, timezone.utc)
            deployment_result = await db.execute(select(Deployment).where(Deployment.id == row.deployment_id))
            deployment = deployment_result.scalar_one_or_none()
            if deployment and row.status in {"unpaid", "canceled", "incomplete_expired"}:
                from app.services.deployment_providers import get_deployment_provider
                provider = get_deployment_provider(deployment.provider)
                if deployment.status != "suspended":
                    await provider.stop(deployment.site_id)
                    deployment.status = "suspended"
                    deployment.is_suspended = True
            elif deployment and row.status in {"active", "trialing"} and deployment.is_suspended:
                from app.services.deployment_providers import get_deployment_provider
                provider = get_deployment_provider(deployment.provider)
                ok, _ = await provider.rollback(deployment.site_id, deployment.current_version)
                if ok:
                    deployment.status = "live"
                    deployment.is_suspended = False
            await db.commit()

    elif event["type"] in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
        checkout_session = event["data"]["object"]
        metadata = checkout_session.get("metadata") or {}
        if metadata.get("purchase_type") == "hosting_subscription":
            deployment_id = metadata.get("deployment_id")
            if deployment_id:
                deployment_result = await db.execute(select(Deployment).where(Deployment.id == uuid.UUID(deployment_id)))
                hosting_deployment = deployment_result.scalar_one_or_none()
                if hosting_deployment and hosting_deployment.hosting_checkout_session_id == checkout_session.get("id"):
                    hosting_deployment.hosting_checkout_session_id = None
                    await db.commit()
        if metadata.get("purchase_type") == "domain_registration":
            domain_result = await db.execute(select(Domain).where(Domain.id == uuid.UUID(metadata["domain_id"])))
            domain = domain_result.scalar_one_or_none()
            if domain and domain.registrar_status == "pending_payment":
                domain.registrar_status = "payment_failed" if event["type"].endswith("failed") else "checkout_expired"
                domain.verification_status = domain.registrar_status
                await db.commit()

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if subscription_id:
            row_result = await db.execute(select(HostingSubscription).where(
                HostingSubscription.stripe_subscription_id == subscription_id
            ))
            row = row_result.scalar_one_or_none()
            if row:
                from datetime import datetime, timezone, timedelta
                if not row.last_payment_failed_at:
                    row.status = "past_due"
                    row.last_payment_failed_at = datetime.now(timezone.utc)
                else:
                    row.status = "past_due"
                failed_at = row.last_payment_failed_at
                if failed_at.tzinfo is None:
                    failed_at = failed_at.replace(tzinfo=timezone.utc)
                try:
                    from app.tasks.hosting_tasks import cancel_unpaid_hosting_after_grace
                    cancel_unpaid_hosting_after_grace.apply_async(
                        args=[str(row.id)],
                        countdown=max(0, int((failed_at + timedelta(days=max(0, settings.HOSTING_GRACE_PERIOD_DAYS)) - datetime.now(timezone.utc)).total_seconds())),
                    )
                except Exception:
                    logger.exception("Could not queue hosting grace-period cancellation")
                await db.commit()

    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if subscription_id:
            row_result = await db.execute(select(HostingSubscription).where(
                HostingSubscription.stripe_subscription_id == subscription_id
            ))
            row = row_result.scalar_one_or_none()
            if row:
                row.status = "active"
                row.last_payment_failed_at = None
                await db.commit()

    elif event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        payment_intent_id = intent["id"]
        order_id_str = intent.get("metadata", {}).get("order_id")
        amount_received = intent["amount_received"] / 100.0  # Convert cents to dollars

        if not order_id_str:
            raise HTTPException(status_code=400, detail="Missing order_id in payment metadata")

        try:
            order_uuid = uuid.UUID(order_id_str)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid order_id format in payment metadata")

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
