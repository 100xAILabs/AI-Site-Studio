"""
Payment routes — Razorpay and Stripe payment initiation and verification.
"""

import asyncio
import hashlib
import hmac
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any

ALLOWED_PAYLOAD_KEYS = {
    "id", "object", "type", "event", "status", "amount", "amount_received",
    "amount_paid", "amount_refunded", "currency", "method", "created",
    "created_at", "order_id", "payment_intent", "subscription",
    "subscription_id", "invoice", "captured", "error_code", "error_reason",
    "payment_status", "mode", "livemode"
}
CONTAINER_KEYS = {"data", "object", "payload", "payment", "order", "subscription", "entity"}

def sanitize_gateway_payload(payload: Any) -> Any:
    """Filter provider event payload to only keep allowlisted transaction metadata (F-25)."""
    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            if k in CONTAINER_KEYS and isinstance(v, (dict, list)):
                sanitized[k] = sanitize_gateway_payload(v)
            elif k in ALLOWED_PAYLOAD_KEYS:
                sanitized[k] = sanitize_gateway_payload(v) if isinstance(v, (dict, list)) else v
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_gateway_payload(item) for item in payload]
    return payload

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.template import Template
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.models.deployment import Deployment, Domain
from app.models.hosting_subscription import HostingSubscription
from app.models.webhook_event import WebhookEvent
from app.schemas.payment import (
    PaymentInitRequest, PaymentInitResponse,
    PaymentVerifyRequest, PaymentVerifyResponse,
    PurchaseTokensRequest,
    PurchasePlanRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_secret(secret: Optional[str]) -> str:
    if not secret:
        logger.error("Webhook secret not configured; rejecting request")
        raise HTTPException(status_code=503, detail="Webhook not configured")
    return secret


async def _claim_event(db: AsyncSession, provider: str, event_id: str) -> bool:
    db.add(WebhookEvent(provider=provider, event_id=event_id))
    try:
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        return False


def _minor(amount) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


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


@router.get("/tax-rates")
async def get_country_tax_rates():
    """Return supported country tax rates and definitions."""
    from app.api.v1.routes.orders import COUNTRY_TAX_RATES
    return {
        code: {
            "name": val["name"],
            "rate": float(val["rate"]),
            "label": val["label"]
        }
        for code, val in COUNTRY_TAX_RATES.items()
    }



@router.post("/initiate", response_model=PaymentInitResponse)
async def initiate_payment(
    data: PaymentInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a payment order with Razorpay.
    Returns Razorpay credentials needed by the frontend to open the payment modal.
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
    authenticated_buyer = current_user is not None
    if not current_user:
        current_user = await db.scalar(select(User).where(User.id == order.user_id))
    if not current_user or order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    creator_id_meta = (order.extra_metadata or {}).get("creator_id")
    if creator_id_meta:
        try:
            c_res = await db.execute(select(User).where(User.id == uuid.UUID(creator_id_meta)))
            c_user = c_res.scalar_one_or_none()
            if c_user and not getattr(c_user, "is_payout_setup_completed", False):
                # Inform creator dashboard to connect their bank / payout method
                try:
                    c_meta = dict(c_user.extra_metadata or {})
                    existing_alerts = list(c_meta.get("payout_alerts") or [])
                    new_alert = {
                        "id": str(uuid.uuid4())[:8],
                        "type": "checkout_blocked_unlinked_bank",
                        "title": "Customer Checkout Paused - Payout Setup Needed",
                        "message": f"A customer attempted to purchase from your store for Order #{order.order_number}, but checkout is paused until you connect your bank or payout method.",
                        "order_number": str(order.order_number),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    c_meta["payout_alerts"] = [new_alert] + existing_alerts[:19]
                    c_user.extra_metadata = c_meta
                    await db.commit()
                except Exception as alert_err:
                    logger.warning("Failed to record creator alert: %s", alert_err)

                raise HTTPException(
                    status_code=400,
                    detail=f"Purchasing from {c_user.creator_brand_name or 'this creator'} is temporarily paused: creator has not connected their bank account yet."
                )
        except HTTPException:
            raise
        except Exception:
            pass
    if order.status == OrderStatus.COMPLETED or order.total == Decimal("0"):
        if order.status != OrderStatus.COMPLETED:
            order.status = OrderStatus.COMPLETED
            await db.commit()
        return PaymentInitResponse(
            gateway=PaymentGateway.RAZORPAY,
            gateway_order_id="free_completed",
            amount=0,
            currency="INR",
            key_id="free",
            order_id=str(order.id),
        )
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not in PENDING state")

    is_mock_allowed = (settings.ENVIRONMENT == "test") or getattr(settings, "ALLOW_MOCK_PAYMENTS", False)

    # Resolve seller attribution for marketplace payment routing & earning split
    seller = None
    seller_id = (order.extra_metadata or {}).get("seller_id") or (order.extra_metadata or {}).get("creator_id")
    if seller_id:
        try:
            s_uuid = uuid.UUID(str(seller_id))
            s_res = await db.execute(select(User).where(User.id == s_uuid))
            seller = s_res.scalar_one_or_none()
        except Exception:
            pass

    if not seller and order.items:
        for item in order.items:
            if item.template and item.template.seller_id:
                s_res = await db.execute(select(User).where(User.id == item.template.seller_id))
                seller = s_res.scalar_one_or_none()
                if seller:
                    seller_id = str(seller.id)
                    break

    # Earning split & fee calculation:
    # Extreme creator / retailing subscribers have 0% platform fee (waived)
    # Standard creators have 10% platform commission fee
    is_extreme = bool(getattr(seller, "is_extreme_subscriber", False) or getattr(seller, "can_retail_templates", False))
    platform_fee_rate = Decimal("0.0") if is_extreme else Decimal("0.10")

    # Offline bank transfers reveal creator bank details only to the authenticated
    # buyer who owns this order. Orders stay pending until the creator reconciles the
    # submitted transfer reference against the creator's bank statement.
    if data.gateway == PaymentGateway.BANK_TRANSFER:
        if not authenticated_buyer:
            raise HTTPException(status_code=401, detail="Sign in to the buyer account for this order to view bank transfer details.")
        if not seller:
            raise HTTPException(status_code=400, detail="Bank transfer is available only for creator storefront orders.")
        seller_details = dict(seller.creator_payout_details or {})
        account_number = seller.payout_account_number
        if (
            "bank" not in (seller_details.get("enabled_methods") or [])
            and "bank_transfer" not in (seller_details.get("enabled_methods") or [])
            and seller.payout_method != "bank"
        ):
            raise HTTPException(status_code=409, detail="This creator has not enabled bank transfer payments.")
        if (
            not seller.payout_bank_name
            or not account_number
            or not seller.payout_account_holder_name
            or not (seller.payout_ifsc_code or seller_details.get("iban") or seller_details.get("swift_code"))
        ):
            raise HTTPException(status_code=409, detail="This creator has not completed bank transfer setup.")

        currency = str((order.extra_metadata or {}).get("currency") or "USD").upper()[:3]
        creator_country = str(seller_details.get("country") or "").upper()
        local_currency = {"IN": "INR", "US": "USD", "GB": "GBP", "DE": "EUR", "CA": "CAD", "AU": "AUD", "SG": "SGD"}.get(creator_country)
        if local_currency and currency != local_currency and not (seller_details.get("swift_code") or seller_details.get("iban")):
            raise HTTPException(
                status_code=409,
                detail=f"This order is in {currency}, but the creator's bank is configured for {local_currency}. The creator must add valid SWIFT/BIC or IBAN details for an international transfer, or enable a compatible payment processor.",
            )
        existing_result = await db.execute(select(Payment).where(Payment.order_id == order.id).with_for_update())
        payment = existing_result.scalar_one_or_none()
        if payment and payment.gateway != PaymentGateway.BANK_TRANSFER:
            if payment.status != PaymentStatus.PENDING:
                raise HTTPException(status_code=409, detail="A different payment method has already been used for this order.")
            payment.gateway = PaymentGateway.BANK_TRANSFER
            payment.gateway_payment_id = None
            payment.gateway_signature = None
            payment.gateway_response = None
            payment.gateway_order_id = f"bank_{order.id}"
            payment.amount = order.total
            payment.currency = currency
        elif payment and payment.status == PaymentStatus.FAILED:
            payment.status = PaymentStatus.PENDING
            payment.gateway_payment_id = None
            payment.gateway_signature = None
            payment.gateway_response = None
        elif not payment:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.BANK_TRANSFER,
                gateway_order_id=f"bank_{order.id}",
                amount=order.total,
                currency=currency,
            )
            db.add(payment)
        await db.commit()
        return PaymentInitResponse(
            gateway=PaymentGateway.BANK_TRANSFER,
            gateway_order_id=payment.gateway_order_id,
            amount=_minor(order.total),
            currency=currency,
            key_id="",
            order_id=str(order.id),
            merchant_name=seller.creator_brand_name or seller.full_name or seller.username,
            bank_transfer_details={
                "bank_name": seller.payout_bank_name,
                "account_holder_name": seller.payout_account_holder_name,
                "account_number": account_number,
                "ifsc_code": seller.payout_ifsc_code,
                "swift_code": seller_details.get("swift_code"),
                "iban": seller_details.get("iban"),
            },
        )

    # ── 1. STRIPE PAYMENT INITIATION ──
    if data.gateway == PaymentGateway.STRIPE:
        usd_amount = Decimal(str(order.total)).quantize(Decimal("0.01"))
        amount_in_cents = int(usd_amount * 100)

        existing_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
        existing_payment = existing_result.scalar_one_or_none()
        if (
            existing_payment
            and existing_payment.gateway == PaymentGateway.STRIPE
            and existing_payment.gateway_order_id
            and existing_payment.gateway_order_id.startswith("cs_")
            and settings.STRIPE_SECRET_KEY
        ):
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                existing_sess = await asyncio.to_thread(stripe.checkout.Session.retrieve, existing_payment.gateway_order_id)
                if getattr(existing_sess, "status", None) == "open" and getattr(existing_sess, "url", None):
                    return PaymentInitResponse(
                        gateway=PaymentGateway.STRIPE,
                        gateway_order_id=existing_sess.id,
                        amount=amount_in_cents,
                        currency="USD",
                        key_id=settings.STRIPE_PUBLISHABLE_KEY or "",
                        order_id=str(order.id),
                        checkout_url=existing_sess.url,
                    )
            except Exception as ex_s_err:
                logger.info(f"Existing Stripe session could not be reused ({ex_s_err}); creating fresh session.")

        is_stripe_configured = bool(
            settings.STRIPE_SECRET_KEY
            and not settings.STRIPE_SECRET_KEY.startswith(("sk_test_...", "your-"))
            and "mock" not in settings.STRIPE_SECRET_KEY.lower()
        )

        stripe_session_id = None
        checkout_url = None

        # Check for Stripe Connected Account transfer for instant automated payout
        seller_stripe_account_id = None
        if seller:
            seller_stripe_account_id = (
                getattr(seller, "stripe_connect_account_id", None)
                or getattr(seller, "payout_stripe_account_id", None)
                or (seller.creator_payout_details or {}).get("stripe_account_id")
            )

        # Check for seller direct Stripe link
        seller_stripe_payment_link = (
            (seller.creator_payout_details or {}).get("stripe_payment_link")
            if seller else None
        )

        app_fee_cents = int(round(amount_in_cents * float(platform_fee_rate)))
        payment_intent_data = None

        # Verify whether the seller Stripe account ID is a syntactically valid Stripe connected account (e.g. acct_1234567890ABCDEF)
        # and not a test placeholder string like 'acct_test_creator_payout_id'
        is_real_stripe_acct = bool(
            seller_stripe_account_id
            and str(seller_stripe_account_id).strip().startswith("acct_")
            and not any(x in str(seller_stripe_account_id).lower() for x in ("test", "mock", "placeholder", "dummy", "creator_payout"))
            and re.match(r"^acct_[a-zA-Z0-9]{14,30}$", str(seller_stripe_account_id).strip())
        )

        if is_real_stripe_acct:
            payment_intent_data = {
                "transfer_data": {
                    "destination": str(seller_stripe_account_id).strip(),
                },
                "metadata": {
                    "order_id": str(order.id),
                    "seller_id": str(seller_id) if seller_id else "",
                    "creator_brand": getattr(seller, "creator_brand_name", "") or getattr(seller, "username", ""),
                }
            }
            if app_fee_cents > 0:
                payment_intent_data["application_fee_amount"] = app_fee_cents

        creator_slug_meta = (order.extra_metadata or {}).get("creator_slug")
        if creator_slug_meta:
            success_url = f"{settings.FRONTEND_URL}/creator/{creator_slug_meta}/checkout?success=true&order_id={order.id}&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{settings.FRONTEND_URL}/creator/{creator_slug_meta}/checkout?cancelled=true"
            mock_checkout_url = f"{settings.FRONTEND_URL}/creator/{creator_slug_meta}/checkout?mock_stripe=true&order_id={order.id}"
        else:
            success_url = f"{settings.FRONTEND_URL}/checkout?success=true&order_id={order.id}&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{settings.FRONTEND_URL}/checkout?cancelled=true"
            mock_checkout_url = f"{settings.FRONTEND_URL}/checkout?mock_stripe=true&order_id={order.id}"

        if is_stripe_configured:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                session_params = {
                    "line_items": [{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"AI Site Studio Order #{order.order_number}",
                                "description": f"Templates Lifetime Commercial License ({len(order.items)} item(s))",
                            },
                            "unit_amount": amount_in_cents,
                        },
                        "quantity": 1,
                    }],
                    "mode": "payment",
                    "client_reference_id": str(order.id),
                    "customer_email": current_user.email,
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                    "metadata": {
                        "order_id": str(order.id),
                        "order_number": str(order.order_number),
                        "user_id": str(current_user.id),
                        "seller_id": str(seller_id) if seller_id else "",
                    }
                }
                if payment_intent_data:
                    session_params["payment_intent_data"] = payment_intent_data

                try:
                    session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
                    stripe_session_id = session.id
                    checkout_url = session.url
                except Exception as create_err:
                    err_msg = str(create_err)
                    # NEVER divert creator storefront funds to the platform account.
                    # Only retry on platform account if this is a platform-owned order without an external creator.
                    if not seller and ("destination" in err_msg.lower() or "transfer_data" in err_msg.lower() or "payment method" in err_msg.lower()):
                        logger.warning(f"Platform Stripe retry triggered: {err_msg}. Retrying Checkout on the platform account with Dashboard-configured payment methods...")
                        session_params.pop("payment_intent_data", None)
                        session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)
                        stripe_session_id = session.id
                        checkout_url = session.url
                    else:
                        raise create_err
            except Exception as s_err:
                err_text = str(s_err)
                logger.warning(f"Stripe session creation failed: {err_text}")

                # Inform creator dashboard to update their payment methods
                if seller:
                    try:
                        s_meta = dict(seller.extra_metadata or {})
                        existing_alerts = list(s_meta.get("payout_alerts") or [])
                        if "payment method" in err_text.lower():
                            alert_msg = (
                                f"Action Required: A customer tried to purchase for Order #{order.order_number}, "
                                f"but your Stripe account has no active payment methods for USD. Please activate Card payments in your Stripe Dashboard or update your payout methods in Creator Setup."
                            )
                        elif "destination" in err_text.lower():
                            alert_msg = (
                                f"Action Required: A customer tried to pay for Order #{order.order_number}, "
                                f"but your connected Stripe account ID was rejected by Stripe. Please update your Stripe Connected Account ID in Creator Setup."
                            )
                        else:
                            alert_msg = (
                                f"Payment attempt for Order #{order.order_number} encountered a gateway error: {err_text[:120]}. "
                                f"Please review and update your payment method settings in Creator Setup."
                            )

                        new_alert = {
                            "id": str(uuid.uuid4())[:8],
                            "type": "payment_gateway_configuration_error",
                            "title": "Payment Method Update Required",
                            "message": alert_msg,
                            "order_number": str(order.order_number),
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                        s_meta["payout_alerts"] = [new_alert] + existing_alerts[:19]
                        seller.extra_metadata = s_meta
                        await db.commit()
                    except Exception as alert_err:
                        logger.warning(f"Failed to record seller payout alert: {alert_err}")

                if is_mock_allowed:
                    mock_pi = f"pi_mock_{uuid.uuid4().hex[:12]}"
                    stripe_session_id = f"{mock_pi}_secret_{uuid.uuid4().hex[:12]}"
                    checkout_url = (
                        seller_stripe_payment_link
                        if seller_stripe_payment_link
                        else mock_checkout_url
                    )
                else:
                    raise HTTPException(
                        status_code=502,
                        detail="There is some issue processing your Stripe payment right now. Please try again later.",
                    )
        else:
            if is_mock_allowed:
                mock_pi = f"pi_mock_{uuid.uuid4().hex[:12]}"
                stripe_session_id = f"{mock_pi}_secret_{uuid.uuid4().hex[:12]}"
                checkout_url = (
                    seller_stripe_payment_link
                    if seller_stripe_payment_link
                    else mock_checkout_url
                )
            elif seller_stripe_payment_link and str(seller_stripe_payment_link).startswith(("https://buy.stripe.com/", "https://checkout.stripe.com/")):
                stripe_session_id = f"plink_{uuid.uuid4().hex[:16]}"
                checkout_url = str(seller_stripe_payment_link).strip()
            else:
                raise HTTPException(
                    status_code=503,
                    detail="There is some issue connecting to Stripe right now. Please try again later.",
                )

        if existing_payment:
            existing_payment.gateway = PaymentGateway.STRIPE
            existing_payment.gateway_order_id = stripe_session_id
            existing_payment.amount = usd_amount
            existing_payment.currency = "USD"
        else:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.STRIPE,
                gateway_order_id=stripe_session_id,
                amount=usd_amount,
                currency="USD",
            )
            db.add(payment)
        await db.flush()
        await db.commit()

        return PaymentInitResponse(
            gateway=PaymentGateway.STRIPE,
            gateway_order_id=stripe_session_id,
            amount=amount_in_cents,
            currency="USD",
            key_id=settings.STRIPE_PUBLISHABLE_KEY or "pk_test_mock",
            order_id=str(order.id),
            checkout_url=checkout_url,
        )

    # ── 2. DIRECT UPI PAYMENT INITIATION ──
    if data.gateway == PaymentGateway.UPI:
        upi_vpa = None
        if seller:
            upi_vpa = (
                getattr(seller, "payout_razorpay_vpa", None)
                or (seller.creator_payout_details or {}).get("upi_id")
                or (seller.creator_payout_details or {}).get("razorpay_vpa")
            )
        if not upi_vpa:
            if seller:
                try:
                    s_meta = dict(seller.extra_metadata or {})
                    existing_alerts = list(s_meta.get("payout_alerts") or [])
                    new_alert = {
                        "id": str(uuid.uuid4())[:8],
                        "type": "missing_upi_id",
                        "title": "UPI Payment Method Missing",
                        "message": f"A customer selected Direct UPI for Order #{order.order_number}, but you have not configured a UPI ID yet. Please add your UPI ID in Creator Setup.",
                        "order_number": str(order.order_number),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    s_meta["payout_alerts"] = [new_alert] + existing_alerts[:19]
                    seller.extra_metadata = s_meta
                    await db.commit()
                except Exception as alert_err:
                    logger.warning("Failed to record seller UPI alert: %s", alert_err)

            raise HTTPException(
                status_code=400,
                detail=f"{getattr(seller, 'creator_brand_name', 'The creator')} has not configured a UPI ID for direct payments."
            )

        clean_vpa = str(upi_vpa).strip().lower()
        brand_name = getattr(seller, "creator_brand_name", "") or getattr(seller, "full_name", "") or "AI Site Studio"

        usd_to_inr_rate = await get_usd_to_inr_rate()
        inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
        amount_in_paise = int(inr_amount * 100)

        import urllib.parse
        encoded_brand = urllib.parse.quote(brand_name[:30])
        encoded_note = urllib.parse.quote(f"Order #{order.order_number}")
        upi_uri = f"upi://pay?pa={clean_vpa}&pn={encoded_brand}&am={inr_amount}&cu=INR&tn={encoded_note}"

        existing_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
        existing_payment = existing_result.scalar_one_or_none()
        if existing_payment:
            existing_payment.gateway = PaymentGateway.UPI
            existing_payment.gateway_order_id = f"upi_{order.id}"
            existing_payment.amount = inr_amount
            existing_payment.currency = "INR"
        else:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.UPI,
                gateway_order_id=f"upi_{order.id}",
                amount=inr_amount,
                currency="INR",
                status=PaymentStatus.PENDING,
            )
            db.add(payment)

        await db.flush()
        await db.commit()

        return PaymentInitResponse(
            gateway=PaymentGateway.UPI,
            gateway_order_id=f"upi_{order.id}",
            amount=amount_in_paise,
            currency="INR",
            key_id=clean_vpa,
            order_id=str(order.id),
            checkout_url=upi_uri,
            upi_uri=upi_uri,
            vpa=clean_vpa,
        )

    # ── 2. RAZORPAY PAYMENT INITIATION ──
    usd_to_inr_rate = await get_usd_to_inr_rate()
    inr_amount = calculate_order_inr_amount(order, usd_to_inr_rate)
    amount_in_paise = int(inr_amount * 100)

    # Re-use existing Razorpay payment record if already initiated
    existing_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    existing_payment = existing_result.scalar_one_or_none()
    if existing_payment and existing_payment.gateway_order_id:
        existing_payment.gateway = PaymentGateway.RAZORPAY
        existing_payment.amount = inr_amount
        existing_payment.currency = "INR"
        await db.commit()
        return PaymentInitResponse(
            gateway=PaymentGateway.RAZORPAY,
            gateway_order_id=existing_payment.gateway_order_id,
            amount=amount_in_paise,
            currency="INR",
            key_id=(
                "rzp_test_mockkey"
                if existing_payment.gateway_order_id.startswith("rzp_mock_")
                else (settings.RAZORPAY_KEY_ID or "rzp_test_mockkey")
            ),
            order_id=str(order.id),
        )

    # Mocking check for sandbox/local test execution
    is_mock_key = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
        or "change-me" in settings.RAZORPAY_KEY_ID
        or "mock" in settings.RAZORPAY_KEY_ID.lower()
    )

    if is_mock_key:
        if not is_mock_allowed:
            raise HTTPException(
                status_code=503,
                detail="There is some issue connecting to Razorpay right now. Please try again later.",
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

    rz_order_id = None
    seller_rzp_account_id = (
        (seller.creator_payout_details or {}).get("razorpay_account_id")
        if seller else None
    )
    is_valid_route_acc = bool(
        seller_rzp_account_id
        and str(seller_rzp_account_id).strip().startswith("acc_")
        and not any(x in str(seller_rzp_account_id).lower() for x in ("test", "mock", "placeholder"))
    )

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        rzp_order_payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": str(order.id)[:40],
            "notes": {
                "order_id": str(order.id),
                "order_number": order.order_number,
                "user_email": current_user.email,
                "seller_id": str(seller_id) if seller_id else "",
            }
        }
        if is_valid_route_acc:
            transfer_paise = int(round(amount_in_paise * (1.0 - float(platform_fee_rate))))
            if transfer_paise > 0:
                rzp_order_payload["transfers"] = [{
                    "account": str(seller_rzp_account_id).strip(),
                    "amount": transfer_paise,
                    "currency": "INR",
                    "notes": {
                        "order_id": str(order.id),
                        "seller_id": str(seller_id) if seller_id else "",
                    },
                    "linked_account_notes": ["order_id"],
                    "on_hold": False,
                }]

        try:
            rz_order = await asyncio.to_thread(client.order.create, rzp_order_payload)
        except Exception as route_err:
            # NEVER divert creator storefront funds to the platform account.
            # Only retry on platform account if this is a platform-owned order without an external creator.
            if not seller and "transfers" in rzp_order_payload and ("transfer" in str(route_err).lower() or "account" in str(route_err).lower()):
                logger.warning(f"Razorpay Route transfer order failed ({route_err}); retrying standard merchant order capture.")
                rzp_order_payload.pop("transfers", None)
                rz_order = await asyncio.to_thread(client.order.create, rzp_order_payload)
            else:
                raise route_err
        rz_order_id = rz_order["id"]
    except Exception as rz_err:
        logger.warning(f"Razorpay order create failed: {rz_err}")
        if seller:
            try:
                s_meta = dict(seller.extra_metadata or {})
                existing_alerts = list(s_meta.get("payout_alerts") or [])
                s_meta["payout_alerts"] = [{
                    "id": str(uuid.uuid4())[:8],
                    "type": "razorpay_gateway_error",
                    "title": "Razorpay Checkout Error",
                    "message": f"A customer attempted Razorpay checkout for Order #{order.order_number}, but Razorpay returned: {str(rz_err)[:120]}. Please check your Razorpay setup.",
                    "order_number": str(order.order_number),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }] + existing_alerts[:19]
                seller.extra_metadata = s_meta
                await db.commit()
            except Exception:
                pass
        if is_mock_allowed:
            rz_order_id = f"rzp_mock_{uuid.uuid4().hex[:12]}"
        else:
            raise HTTPException(
                status_code=502,
                detail="There is some issue connecting to Razorpay right now. Please try again later.",
            )

    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        gateway_order_id=rz_order_id,
        amount=inr_amount,
        currency="INR",
    )
    db.add(payment)
    await db.flush()
    await db.commit()

    return PaymentInitResponse(
        gateway=PaymentGateway.RAZORPAY,
        gateway_order_id=rz_order_id,
        amount=amount_in_paise,
        currency="INR",
        key_id=settings.RAZORPAY_KEY_ID if not is_mock_key else "rzp_test_mockkey",
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
        if items:
            t_ids = [it.template_id for it in items]
            item_ids = [it.id for it in items]

            existing_lics_res = await db.execute(
                select(License.template_id).where(License.order_id == order.id, License.template_id.in_(t_ids))
            )
            existing_lic_tids = set(existing_lics_res.scalars().all())

            from app.models.template import Template
            from app.models.marketplace import CreatorEarning, MarketplaceSetting, EarningStatus
            from datetime import datetime, timezone, timedelta

            tmpls_res = await db.execute(select(Template).where(Template.id.in_(t_ids)))
            tmpls_by_id = {t.id: t for t in tmpls_res.scalars().all()}

            existing_earnings_res = await db.execute(
                select(CreatorEarning.order_item_id).where(CreatorEarning.order_item_id.in_(item_ids))
            )
            existing_earning_item_ids = set(existing_earnings_res.scalars().all())

            setting_res = await db.execute(select(MarketplaceSetting).where(MarketplaceSetting.id == "default"))
            m_setting = setting_res.scalar_one_or_none()
            comm_rate = m_setting.platform_commission_percent if m_setting else Decimal("20.00")
            hold_days = m_setting.payout_holding_days if m_setting else 7

            for item in items:
                # Check if license already generated (idempotent for webhook retries)
                if item.template_id in existing_lic_tids:
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

                # Store private template draft copy directly under the buyer's account in database & disk
                tmpl = tmpls_by_id.get(item.template_id)
                if tmpl:
                    try:
                        from app.services.template_service import create_or_get_buyer_draft_copy
                        buyer_draft = await create_or_get_buyer_draft_copy(db, order.user_id, tmpl)
                        lic.notes = f"custom_draft_id={buyer_draft.id}"
                    except Exception as e_draft:
                        logger.warning("Could not create buyer draft for order item %s: %s", item.id, e_draft)

                db.add(lic)
                existing_lic_tids.add(item.template_id)
                if recipient_email:
                    try:
                        send_license_delivery.delay(recipient_email, license_key, f"Template {item.template_id}")
                    except Exception:
                        pass

                # Create CreatorEarning ledger entry if template was created by a creator
                try:
                    tmpl = tmpls_by_id.get(item.template_id)
                    if tmpl:
                        tmpl.downloads_count = (tmpl.downloads_count or 0) + 1
                        if tmpl.seller_id and tmpl.seller_id != order.user_id:
                            # Check if earning record already created (idempotent)
                            if item.id not in existing_earning_item_ids:
                                # Check if seller is Extreme subscriber with 0% platform commission fee
                                seller_obj = None
                                if tmpl.seller_id:
                                    s_res = await db.execute(select(User).where(User.id == tmpl.seller_id))
                                    seller_obj = s_res.scalar_one_or_none()
                                is_seller_extreme = bool(
                                    seller_obj and (
                                        getattr(seller_obj, "is_extreme_subscriber", False)
                                        or getattr(seller_obj, "can_retail_templates", False)
                                        or str(getattr(seller_obj, "subscription_tier", "")).lower() in ("extreme", "agency", "enterprise")
                                    )
                                )
                                effective_comm_rate = Decimal("0.00") if is_seller_extreme else comm_rate
                                gross = Decimal(str(item.price))
                                platform_fee = round(gross * (effective_comm_rate / Decimal("100.00")), 2)
                                net_earning = gross - platform_fee
                                now_utc = datetime.now(timezone.utc)
                                holding_until = now_utc + timedelta(days=0 if is_seller_extreme else hold_days)

                                creator_earning = CreatorEarning(
                                    order_id=order.id,
                                    order_item_id=item.id,
                                    template_id=tmpl.id,
                                    creator_id=tmpl.seller_id,
                                    gross_amount=gross,
                                    platform_commission_percent=effective_comm_rate,
                                    platform_fee=platform_fee,
                                    platform_commission_amount=platform_fee,
                                    net_creator_earning=net_earning,
                                    creator_net_amount=net_earning,
                                    currency=getattr(tmpl, "price_currency", "USD") or "USD",
                                    holding_until=holding_until,
                                    available_at=holding_until,
                                    status=EarningStatus.AVAILABLE if is_seller_extreme else EarningStatus.PENDING,
                                )
                                db.add(creator_earning)
                                existing_earning_item_ids.add(item.id)
                except Exception as e_earn:
                    logger.warning("Could not record creator earning for item %s: %s", item.id, e_earn)

        # Credit AI Gemini tokens ONLY if this order is a standalone credit pack (NOT a subscription plan)
        is_subscription = bool(order.extra_metadata and order.extra_metadata.get("type") == "subscription_plan")
        if order.extra_metadata and order.extra_metadata.get("credits_to_add") and not is_subscription:
            try:
                credits_to_add = int(order.extra_metadata["credits_to_add"])
                if not order.extra_metadata.get("credits_credited"):
                    user_res = await db.execute(select(User).where(User.id == order.user_id))
                    target_user = user_res.scalar_one_or_none()
                    if target_user:
                        target_user.ai_credits = (target_user.ai_credits or 0) + credits_to_add
                        order.extra_metadata = {**order.extra_metadata, "credits_credited": True}
                        logger.info("Credited %d AI tokens to user %s. New balance: %d", credits_to_add, target_user.email, target_user.ai_credits)
            except Exception as cred_err:
                logger.warning("Could not credit AI tokens for order %s: %s", order.id, cred_err)

        # Upgrade user subscription tier if this order is a Pro/Agency subscription
        if is_subscription:
            try:
                plan_id = str(order.extra_metadata.get("plan_id") or "pro").lower()
                billing_cycle = str(order.extra_metadata.get("billing_cycle") or "monthly").lower()
                user_res = await db.execute(select(User).where(User.id == order.user_id))
                target_user = user_res.scalar_one_or_none()
                if target_user:
                    now_utc = datetime.now(timezone.utc)
                    days = 365 if billing_cycle == "annual" else 30
                    target_user.subscription_tier = plan_id
                    target_user.subscription_expires_at = now_utc + timedelta(days=days)
                    target_user.subscription_status = "active"
                    target_user.auto_renew = True
                    target_user.subscription_id = str(order.order_number)

                    # USER RULE: "when they upgrade use only upgraded token not a previous one ok"
                    # Strictly allocate the fresh upgraded plan's credits (no previous token rollover)
                    from app.core.plans import get_plan_config
                    plan_cfg = get_plan_config(plan_id)
                    sub_credits = int(order.extra_metadata.get("credits_to_add") or plan_cfg.get("included_ai_credits", 0))
                    target_user.ai_credits = sub_credits
                    order.extra_metadata = {**order.extra_metadata, "credits_credited": True}

                    # Synchronize authoritative primary UserSubscription record
                    try:
                        from app.services.entitlement_service import EntitlementService
                        ent_svc = EntitlementService(db)
                        sub = await ent_svc.get_or_create_user_subscription(target_user)
                        sub.plan_id = plan_id
                        sub.billing_cycle = billing_cycle
                        sub.payment_provider = (
                            order.payment.gateway.value if order.payment and hasattr(order.payment.gateway, "value")
                            else "razorpay"
                        )
                        sub.status = "active"
                        sub.is_trial = False
                        sub.cancel_at_period_end = False
                        sub.current_period_start = now_utc
                        sub.current_period_end = target_user.subscription_expires_at
                        sub.next_billing_date = target_user.subscription_expires_at
                        sub.last_successful_payment_at = now_utc
                        sub.grace_period_end = None
                    except Exception as ent_err:
                        logger.warning(f"Could not sync UserSubscription record for {target_user.email}: {ent_err}")

                    logger.info(
                        "Upgraded user %s subscription tier to %s (Expires: %s, AI credits: %s)",
                        target_user.email, plan_id, target_user.subscription_expires_at, target_user.ai_credits
                    )
            except Exception as sub_err:
                logger.warning("Could not update subscription tier for order %s: %s", order.id, sub_err)
    except Exception as lic_err:
        print(f"Notice: License fulfillment warning: {lic_err}")


@router.post("/verify", response_model=PaymentVerifyResponse)
async def verify_payment(
    data: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Verify payment from the client-side.
    Note: Order status is finalized via webhook. The verify endpoint checks
    if the order and payment have been successfully confirmed/captured in the DB.
    """
    order_uuid = uuid.UUID(data.order_id)
    result = await db.execute(select(Order).where(Order.id == order_uuid).with_for_update())
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not current_user:
        current_user = await db.scalar(select(User).where(User.id == order.user_id))
    if not current_user or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatus.COMPLETED:
        return PaymentVerifyResponse(
            success=True,
            message="Order is already completed.",
            order_id=str(order.id),
        )

    result = await db.execute(
        select(Payment).where(Payment.order_id == order.id).with_for_update()
    )
    payment = result.scalar_one_or_none()

    # 1. Direct client-side Razorpay signature verification
    if (
        data.gateway == PaymentGateway.RAZORPAY
        and data.gateway_order_id
        and data.gateway_payment_id
        and data.gateway_signature
        and settings.RAZORPAY_KEY_SECRET
        and not data.gateway_order_id.startswith("rzp_mock_")
        and not data.gateway_payment_id.startswith("pay_mock_")
        and data.gateway_signature != "mock_signature_verified"
    ):
        # Validate that order has an initiated payment and matches stored gateway order ID
        if not payment or not payment.gateway_order_id:
            raise HTTPException(status_code=400, detail="No initiated payment record found for this order.")

        if payment.gateway_order_id != data.gateway_order_id:
            raise HTTPException(status_code=400, detail="Gateway order ID mismatch. Order cannot be verified.")

        # Replay prevention: check if this gateway_payment_id was already captured on another order
        dup_check = await db.execute(
            select(Payment.id).where(
                Payment.gateway_payment_id == data.gateway_payment_id,
                Payment.order_id != order.id,
                Payment.status == PaymentStatus.CAPTURED,
            ).limit(1)
        )
        if dup_check.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Payment transaction has already been captured for another order.")

        # Compute HMAC strictly over stored payment.gateway_order_id
        msg = f"{payment.gateway_order_id}|{data.gateway_payment_id}".encode("utf-8")
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            msg,
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(generated_signature, data.gateway_signature):
            # In real non-test runtime, also query Razorpay Payments API to confirm capture/amount
            if settings.ENVIRONMENT != "test" and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=UserWarning)
                        import razorpay
                    rz_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                    rz_pay = await asyncio.to_thread(rz_client.payment.fetch, data.gateway_payment_id)
                    rz_status = str(rz_pay.get("status") or "").lower()
                    rz_ord_id = rz_pay.get("order_id")
                    rz_amt = int(rz_pay.get("amount") or 0)

                    if rz_ord_id and rz_ord_id != payment.gateway_order_id:
                        raise HTTPException(status_code=400, detail="Razorpay payment does not belong to this order.")
                    expected_paise = _minor(payment.amount)
                    if rz_amt and abs(rz_amt - expected_paise) > 5:
                        raise HTTPException(status_code=400, detail="Razorpay payment amount mismatch.")
                    if rz_status == "authorized":
                        await asyncio.to_thread(rz_client.payment.capture, data.gateway_payment_id, rz_amt)
                        rz_status = "captured"
                    if rz_status != "captured":
                        raise HTTPException(status_code=400, detail=f"Payment has not been captured by Razorpay (status: {rz_status}).")
                except HTTPException:
                    raise
                except Exception as fetch_err:
                    logger.warning(f"Razorpay payment.fetch verification failed: {fetch_err}")
                    raise HTTPException(
                        status_code=400,
                        detail="Could not verify captured transaction with Razorpay. Please try again.",
                    )

            payment.status = PaymentStatus.CAPTURED
            payment.gateway = PaymentGateway.RAZORPAY
            payment.gateway_payment_id = data.gateway_payment_id
            payment.gateway_signature = data.gateway_signature

            order.status = OrderStatus.COMPLETED
            await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)
            await db.flush()
            await db.commit()
            return PaymentVerifyResponse(
                success=True,
                message="Payment verified successfully via Razorpay signature.",
                order_id=str(order.id),
            )
        else:
            raise HTTPException(status_code=400, detail="Razorpay signature verification failed. Invalid signature.")

    is_mock_allowed = (settings.ENVIRONMENT == "test") or getattr(settings, "ALLOW_MOCK_PAYMENTS", False)

    # 2. Stripe payment verification (Client-side Session verification)
    if data.gateway == PaymentGateway.STRIPE:
        is_stripe_mock = (
            data.gateway_signature in ("mock_signature_verified", "stripe_mock_sig")
            or (data.gateway_payment_id and data.gateway_payment_id.startswith("pay_mock_"))
            or (data.gateway_order_id and data.gateway_order_id.startswith(("cs_mock_", "pi_mock_")))
        )

        if is_stripe_mock:
            if not is_mock_allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Mock or demo Stripe confirmations are disabled. Please complete payment via Stripe Checkout.",
                )
            if not payment:
                payment = Payment(
                    order_id=order.id,
                    gateway=PaymentGateway.STRIPE,
                    status=PaymentStatus.CAPTURED,
                    gateway_payment_id=data.gateway_payment_id or f"pi_mock_{uuid.uuid4().hex[:12]}",
                    gateway_order_id=data.gateway_order_id or f"cs_mock_{uuid.uuid4().hex[:12]}",
                    amount=order.total,
                    currency="USD",
                )
                db.add(payment)
            else:
                payment.status = PaymentStatus.CAPTURED
                payment.gateway = PaymentGateway.STRIPE
                payment.gateway_payment_id = data.gateway_payment_id or f"pi_mock_{uuid.uuid4().hex[:12]}"

            order.status = OrderStatus.COMPLETED
            await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)
            await db.flush()
            await db.commit()
            return PaymentVerifyResponse(
                success=True,
                message="Payment verified successfully via Stripe (Test).",
                order_id=str(order.id),
            )

        target_session_id = data.gateway_order_id or (payment.gateway_order_id if payment else None)
        if settings.STRIPE_SECRET_KEY and target_session_id and str(target_session_id).startswith("cs_"):
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                session = await asyncio.to_thread(stripe.checkout.Session.retrieve, target_session_id)
                sess_order_id = (getattr(session, "metadata", None) or {}).get("order_id") or getattr(session, "client_reference_id", None)
                if sess_order_id and str(sess_order_id) != str(order.id):
                    raise HTTPException(status_code=400, detail="Stripe session does not match this order.")

                if session.payment_status == "paid":
                    expected_cents = _minor(order.total)
                    paid_cents = getattr(session, "amount_total", None)
                    if paid_cents is not None and abs(int(paid_cents) - expected_cents) > 5:
                        raise HTTPException(status_code=400, detail="Stripe payment amount mismatch.")

                    if not payment:
                        payment = Payment(
                            order_id=order.id,
                            gateway=PaymentGateway.STRIPE,
                            status=PaymentStatus.CAPTURED,
                            gateway_payment_id=session.payment_intent or session.id,
                            gateway_order_id=session.id,
                            amount=order.total,
                            currency="USD",
                        )
                        db.add(payment)
                    else:
                        payment.status = PaymentStatus.CAPTURED
                        payment.gateway = PaymentGateway.STRIPE
                        payment.gateway_payment_id = session.payment_intent or session.id

                    order.status = OrderStatus.COMPLETED
                    await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)
                    await db.flush()
                    await db.commit()
                    return PaymentVerifyResponse(
                        success=True,
                        message="Payment verified successfully via Stripe Checkout.",
                        order_id=str(order.id),
                    )
                else:
                    raise HTTPException(status_code=400, detail=f"Stripe payment is not completed. Status: {session.payment_status}")
            except HTTPException:
                raise
            except Exception as st_err:
                logger.warning(f"Stripe checkout retrieve failed: {st_err}")
                raise HTTPException(status_code=400, detail=f"Stripe verification failed: {st_err}")

    # Bank transfers are offline and cannot be automatically verified from a
    # reference string. Record the reference, but do not capture or fulfill until
    # the creator confirms receipt in their bank account.
    if data.gateway == PaymentGateway.BANK_TRANSFER:
        if not payment or payment.gateway != PaymentGateway.BANK_TRANSFER:
            raise HTTPException(status_code=400, detail="Start bank transfer checkout before submitting a transfer reference.")
        if payment.status != PaymentStatus.PENDING:
            raise HTTPException(status_code=409, detail="This bank transfer has already been reviewed.")
        if (payment.gateway_payment_id or "").startswith("BANKREF:"):
            raise HTTPException(status_code=409, detail="A transfer reference is already awaiting review for this order.")
        if data.gateway_order_id != payment.gateway_order_id:
            raise HTTPException(status_code=400, detail="Bank transfer order reference mismatch.")
        raw_reference = (data.gateway_payment_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{8,40}", raw_reference):
            raise HTTPException(status_code=400, detail="Enter the 8–40 character transfer reference shown by your bank.")
        if any(bad in raw_reference.lower() for bad in ("test", "mock", "demo", "fake")):
            raise HTTPException(status_code=400, detail="Enter the genuine transfer reference from your bank.")
        bank_ref = f"BANKREF:{raw_reference}"
        dup = await db.execute(select(Payment.id).where(Payment.gateway_payment_id == bank_ref, Payment.order_id != order.id).limit(1))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="This transfer reference has already been submitted.")
        payment.gateway_payment_id = bank_ref
        await db.commit()
        return PaymentVerifyResponse(
            success=True,
            message="Transfer reference received. Your order will be completed after the payment is confirmed.",
            order_id=str(order.id),
        )

    # 3. Direct UPI payment verification (strict non-empty, unique 10-35 char bank UTR required)
    if data.gateway == PaymentGateway.UPI:
        raw_utr = (
            data.upi_utr
            or data.gateway_payment_id
            or data.gateway_signature
            or ""
        ).strip()
        if not is_mock_allowed:
            if not raw_utr or not re.match(r"^[A-Za-z0-9]{10,35}$", raw_utr):
                raise HTTPException(
                    status_code=400,
                    detail="Please enter your valid 12-digit UPI UTR / Bank Transaction Reference number (10-35 alphanumeric characters) after completing payment.",
                )
            lower_utr = raw_utr.lower()
            if any(bad in lower_utr for bad in ("test", "mock", "demo", "fake")) or lower_utr in ("1234567890", "123456789012", "000000000000"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid UTR reference. Please provide the genuine UTR / reference number from your UPI app.",
                )
            dup_utr = await db.execute(
                select(Payment.id).where(
                    Payment.gateway_payment_id == raw_utr,
                    Payment.order_id != order.id,
                    Payment.status == PaymentStatus.CAPTURED,
                ).limit(1)
            )
            if dup_utr.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail="This UPI UTR / Transaction Reference has already been used for another order.",
                )

        utr_ref = raw_utr or f"upi_utr_{uuid.uuid4().hex[:12]}"
        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.UPI,
                status=PaymentStatus.CAPTURED,
                gateway_payment_id=utr_ref,
                gateway_order_id=data.gateway_order_id or f"upi_{order.id}",
                amount=order.total,
                currency="INR",
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway = PaymentGateway.UPI
            payment.gateway_payment_id = utr_ref

        order.status = OrderStatus.COMPLETED
        await _fulfill_order_licenses(db, order, user_email=current_user.email if current_user else None)
        await db.flush()
        await db.commit()
        return PaymentVerifyResponse(
            success=True,
            message="Direct UPI payment confirmed successfully. Your licenses and downloads are ready.",
            order_id=str(order.id),
        )

    # 4. Simulated card flow (strictly limited to test environment)
    is_card_mock = (
        data.gateway == PaymentGateway.RAZORPAY
        and (
            (data.gateway_order_id and data.gateway_order_id.startswith("rzp_mock_"))
            or (data.gateway_payment_id and data.gateway_payment_id.startswith("pay_mock_"))
            or (data.gateway_signature in ("mock_signature_verified", "rzp_mock_sig"))
        )
    )

    if is_card_mock:
        if not is_mock_allowed:
            raise HTTPException(status_code=400, detail="Mock or demo payments are disabled. Complete real Razorpay Checkout to verify payment.")
        if not payment:
            payment = Payment(
                order_id=order.id,
                gateway=PaymentGateway.RAZORPAY,
                status=PaymentStatus.CAPTURED,
                gateway_payment_id=data.gateway_payment_id or f"pay_mock_{uuid.uuid4().hex[:12]}",
                gateway_order_id=data.gateway_order_id or f"rzp_mock_{uuid.uuid4().hex[:12]}",
                amount=order.total,
                currency="INR",
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway = PaymentGateway.RAZORPAY
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

    secret = _require_secret(settings.STRIPE_WEBHOOK_SECRET)

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = str(event.get("id") or "")
    if event_id and not await _claim_event(db, "stripe", event_id):
        return {"status": "already_processed", "event_id": event_id}

    if event["type"] in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        checkout_session = event["data"]["object"]
        metadata = checkout_session.get("metadata") or {}
        if metadata.get("purchase_type") == "marketplace_order" or (metadata.get("order_id") and metadata.get("purchase_type") != "hosting_subscription" and metadata.get("purchase_type") != "domain_registration"):
            order_id_str = metadata.get("order_id")
            if order_id_str:
                try:
                    order_uuid = uuid.UUID(order_id_str)
                    order_res = await db.execute(select(Order).where(Order.id == order_uuid).with_for_update())
                    order = order_res.scalar_one_or_none()
                    if order and order.status != OrderStatus.COMPLETED:
                        paid_cents = checkout_session.get("amount_total")
                        pay_res = await db.execute(select(Payment).where(Payment.order_id == order.id).with_for_update())
                        payment = pay_res.scalar_one_or_none()

                        expected_cents = _minor(payment.amount if payment else order.total)
                        expected_ccy = (payment.currency if payment else "USD").upper()
                        paid_ccy = (checkout_session.get("currency") or "USD").upper()

                        if paid_cents is not None and (paid_cents != expected_cents or paid_ccy != expected_ccy):
                            logger.error(
                                "Stripe payment amount/currency mismatch for order %s: paid %s %s, expected %s %s",
                                order.id, paid_cents, paid_ccy, expected_cents, expected_ccy
                            )
                            await db.commit()
                            return {"status": "amount_mismatch"}

                        order.status = OrderStatus.COMPLETED
                        if payment:
                            payment.status = PaymentStatus.CAPTURED
                            payment.gateway_payment_id = checkout_session.get("payment_intent") or checkout_session.get("id")
                            payment.gateway_response = sanitize_gateway_payload(event)
                        await _fulfill_order_licenses(db, order)
                        await db.commit()
                except Exception as ex:
                    await db.rollback()
                    logger.exception(f"Error fulfilling Stripe checkout order: {ex}")
                    raise HTTPException(status_code=500, detail=f"Failed to fulfill order: {str(ex)}")
        elif metadata.get("purchase_type") == "domain_registration":
            from app.services.domain_purchase_service import fulfill_domain_checkout
            await fulfill_domain_checkout(checkout_session, db)
        elif metadata.get("purchase_type") == "user_subscription":
            from app.services.subscription_service import SubscriptionService
            sub_service = SubscriptionService(db)
            sub_id = checkout_session.get("subscription")
            user_id_str = metadata.get("user_id")
            plan_id = metadata.get("plan_id") or "pro"
            billing_cycle = metadata.get("billing_cycle") or "monthly"
            await sub_service.handle_subscription_payment_success(
                provider="stripe",
                event_id=f"stripe_checkout:{checkout_session.get('id') or event['id']}",
                user_id=uuid.UUID(user_id_str) if user_id_str else None,
                user_email=checkout_session.get("customer_email"),
                plan_id=plan_id,
                billing_cycle=billing_cycle,
                provider_sub_id=sub_id,
                payload=event,
            )
        elif metadata.get("purchase_type") == "hosting_subscription":
            subscription_id = checkout_session.get("subscription")
            if subscription_id:
                stripe_subscription = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)
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

            from app.models.subscription import UserSubscription
            u_sub_res = await db.execute(select(UserSubscription).where(
                UserSubscription.provider_subscription_id == subscription_id
            ))
            u_sub = u_sub_res.scalar_one_or_none()
            if u_sub:
                from app.services.subscription_service import SubscriptionService
                sub_svc = SubscriptionService(db)
                await sub_svc.handle_subscription_payment_failure(
                    provider="stripe",
                    event_id=event["id"],
                    user_id=u_sub.user_id,
                    user_email=None,
                    provider_sub_id=subscription_id,
                    payload=event,
                )

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

            from app.models.subscription import UserSubscription
            u_sub_res = await db.execute(select(UserSubscription).where(
                UserSubscription.provider_subscription_id == subscription_id
            ))
            u_sub = u_sub_res.scalar_one_or_none()
            if u_sub:
                from app.services.subscription_service import SubscriptionService
                sub_svc = SubscriptionService(db)
                await sub_svc.handle_subscription_payment_success(
                    provider="stripe",
                    event_id=event["id"],
                    user_id=u_sub.user_id,
                    user_email=None,
                    plan_id=u_sub.plan_id,
                    billing_cycle=u_sub.billing_cycle,
                    provider_sub_id=subscription_id,
                    payload=event,
                )

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
                gateway_response=sanitize_gateway_payload(event)
            )
            db.add(payment)
        else:
            payment.status = PaymentStatus.CAPTURED
            payment.gateway_payment_id = payment_intent_id
            payment.gateway_response = sanitize_gateway_payload(event)

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
    """
    Production-grade Razorpay webhook receiver.
    Subscribed events:
    - payment.captured: Automatically confirms payments even if the user closed their tab before /verify.
    - payment.failed: Logs failure details and flags payment as failed.
    - order.paid: Confirms order completion and generates licenses / tier upgrades.
    - subscription.charged: Grants or extends Pro / Extreme subscription tier & credits AI tokens.
    - subscription.halted / subscription.cancelled / subscription.completed: Downgrades tier to free.
    - subscription.authenticated: Confirms mandate setup.
    """
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature") or request.headers.get("X-Razorpay-Signature")
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    webhook_secret = _require_secret(settings.RAZORPAY_WEBHOOK_SECRET)
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected, signature):
        logger.warning("Razorpay webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    try:
        data = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Deduplicate event ID AFTER cryptographic signature validation
    event_id = request.headers.get("x-razorpay-event-id") or request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(payload).hexdigest()
    if not await _claim_event(db, "razorpay", event_id):
        return {"status": "already_processed", "event_id": event_id}

    event = data.get("event")
    payload_data = data.get("payload", {})
    
    rz_payment = payload_data.get("payment", {}).get("entity", {})
    rz_order = payload_data.get("order", {}).get("entity", {})
    
    gateway_order_id = rz_order.get("id") or rz_payment.get("order_id")
    gateway_payment_id = rz_payment.get("id")

    # Locate Payment record with row lock
    payment = None
    if gateway_order_id:
        pay_res = await db.execute(select(Payment).where(Payment.gateway_order_id == gateway_order_id).with_for_update())
        payment = pay_res.scalar_one_or_none()
    
    if not payment and gateway_payment_id:
        pay_res = await db.execute(select(Payment).where(Payment.gateway_payment_id == gateway_payment_id).with_for_update())
        payment = pay_res.scalar_one_or_none()

    if event in ("payment.captured", "order.paid"):
        if not payment:
            logger.warning(f"Razorpay webhook: No matching payment found for order={gateway_order_id}, payment={gateway_payment_id}")
            await db.commit()
            return {"status": "ignored_no_order", "event": event}

        # Idempotent check: if already captured, do not re-fulfill
        if payment.status == PaymentStatus.CAPTURED:
            await db.commit()
            return {"status": "already_captured", "order_id": str(payment.order_id), "payment_id": payment.gateway_payment_id}

        # Validate paid amount and currency against expected payment amount
        paid = int(rz_payment.get("amount") or rz_order.get("amount_paid") or 0)
        ccy = (rz_payment.get("currency") or rz_order.get("currency") or "").upper()
        expected_minor = _minor(payment.amount)
        expected_ccy = (payment.currency or "INR").upper()

        if paid != expected_minor or ccy != expected_ccy:
            logger.error(
                "Razorpay webhook amount/currency mismatch for payment %s: paid %s %s, expected %s %s",
                payment.id, paid, ccy, expected_minor, expected_ccy
            )
            await db.commit()
            return {"status": "amount_mismatch"}

        try:
            payment.status = PaymentStatus.CAPTURED
            if gateway_payment_id:
                payment.gateway_payment_id = gateway_payment_id
            payment.gateway_signature = signature
            payment.gateway_response = sanitize_gateway_payload(data)

            order_res = await db.execute(
                select(Order)
                .options(selectinload(Order.user), selectinload(Order.items).selectinload(OrderItem.template))
                .where(Order.id == payment.order_id)
                .with_for_update()
            )
            order = order_res.scalar_one_or_none()
            if order and order.status != OrderStatus.COMPLETED:
                order.status = OrderStatus.COMPLETED
                await _fulfill_order_licenses(db, order, user_email=order.user.email if order.user else None)

            await db.flush()
            await db.commit()
            logger.info(f"Razorpay webhook: Payment {gateway_payment_id} successfully captured for order {payment.order_id}")
            return {"status": "captured_and_fulfilled", "order_id": str(payment.order_id), "payment_id": gateway_payment_id}
        except Exception as ex:
            await db.rollback()
            logger.exception("Failed to fulfill Razorpay order %s: %s", payment.order_id, ex)
            raise HTTPException(status_code=500, detail="Failed to fulfill payment")

    elif event == "payment.failed":
        if payment:
            payment.status = PaymentStatus.FAILED
            if gateway_payment_id:
                payment.gateway_payment_id = gateway_payment_id
            payment.gateway_response = sanitize_gateway_payload(data)
            await db.commit()
            logger.info(f"Razorpay webhook: Marked payment {gateway_payment_id} as FAILED")
            return {"status": "failed_recorded", "payment_id": gateway_payment_id}
        return {"status": "ignored_failed_no_record", "event": event}

    elif event == "subscription.charged":
        rz_sub = payload_data.get("subscription", {}).get("entity", {})
        rz_sub_payment = payload_data.get("payment", {}).get("entity", {})
        sub_notes = rz_sub.get("notes", {}) or rz_sub_payment.get("notes", {})
        user_email = sub_notes.get("user_email") or rz_sub_payment.get("email")
        user_id_str = sub_notes.get("user_id")
        plan_id = (sub_notes.get("plan_id") or "pro").lower()
        billing_cycle = (sub_notes.get("billing_cycle") or "monthly").lower()
        sub_id = rz_sub.get("id") or rz_sub_payment.get("subscription_id")

        from app.services.subscription_service import SubscriptionService
        sub_svc = SubscriptionService(db)
        parsed_user_id = None
        if user_id_str:
            try:
                parsed_user_id = uuid.UUID(user_id_str)
            except Exception:
                pass

        res = await sub_svc.handle_subscription_payment_success(
            provider="razorpay",
            event_id=event_id,
            user_id=parsed_user_id,
            user_email=user_email,
            plan_id=plan_id,
            billing_cycle=billing_cycle,
            provider_sub_id=sub_id,
            payload=payload_data,
        )
        if isinstance(res, dict) and res.get("status") == "success":
            res["status"] = "subscription_charged"
            res["tier"] = res.get("plan_id", plan_id)
        return res

    elif event in ("subscription.halted", "subscription.completed", "subscription.cancelled"):
        rz_sub = payload_data.get("subscription", {}).get("entity", {})
        rz_sub_payment = payload_data.get("payment", {}).get("entity", {})
        sub_notes = rz_sub.get("notes", {}) or rz_sub_payment.get("notes", {})
        user_email = sub_notes.get("user_email") or rz_sub_payment.get("email")
        user_id_str = sub_notes.get("user_id")
        sub_id = rz_sub.get("id") or rz_sub_payment.get("subscription_id")

        from app.services.subscription_service import SubscriptionService
        sub_svc = SubscriptionService(db)
        parsed_user_id = None
        if user_id_str:
            try:
                parsed_user_id = uuid.UUID(user_id_str)
            except Exception:
                pass

        try:
            await sub_svc.handle_subscription_payment_failure(
                provider="razorpay",
                event_id=event_id,
                user_id=parsed_user_id,
                user_email=user_email,
                provider_sub_id=sub_id,
                error_reason=f"Razorpay {event}",
                payload=payload_data,
            )
        except Exception:
            pass

        target_user = None
        if user_id_str:
            try:
                target_user = await db.get(User, uuid.UUID(user_id_str))
            except Exception:
                pass
        if not target_user and user_email:
            u_res = await db.execute(select(User).where(User.email == user_email))
            target_user = u_res.scalar_one_or_none()

        if target_user:
            target_user.subscription_tier = "free"
            target_user.subscription_status = "canceled"
            target_user.ai_credits = 0  # Finished/revoked plan = 0 tokens
            await db.commit()
            logger.info(f"Razorpay webhook: {event} downgraded {target_user.email} to free")
            return {"status": "subscription_revoked", "user_email": target_user.email, "tier": "free"}
        return {"status": "user_not_found_for_sub", "event": event}

    elif event == "subscription.authenticated":
        logger.info("Razorpay webhook: subscription.authenticated received")
        return {"status": "subscription_authenticated", "event": event}

    return {"status": "unhandled_event", "event": event}



@router.get("/billing-report")
async def get_billing_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Consolidated billing & payment report for the authenticated user.
    Aggregates:
    - Real completed & pending orders (template purchases, token compute packs)
    - Active & historical recurring hosting subscriptions
    - Current Gemini AI token balance & quota
    - Financial aggregates (total spent, active subscriptions, total orders)
    """
    orders_res = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.template),
            selectinload(Order.payment)
        )
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    orders = orders_res.scalars().all()

    subs_res = await db.execute(
        select(HostingSubscription)
        .where(HostingSubscription.user_id == current_user.id)
        .order_by(HostingSubscription.created_at.desc())
    )
    subscriptions = subs_res.scalars().all()

    deployment_ids = [s.deployment_id for s in subscriptions]
    deployments_map = {}
    if deployment_ids:
        deps_res = await db.execute(select(Deployment).where(Deployment.id.in_(deployment_ids)))
        deployments_map = {d.id: d for d in deps_res.scalars().all()}

    completed_orders = [o for o in orders if o.status == OrderStatus.COMPLETED]
    total_spent_usd = sum(float(o.total) for o in completed_orders)
    active_subs = [s for s in subscriptions if s.status in ("active", "trialing")]
    monthly_hosting_cost = len(active_subs) * 12.00

    order_records = []
    for o in orders:
        items_desc = []
        is_token_order = bool(o.extra_metadata and o.extra_metadata.get("type") == "ai_credits")
        credits_to_add = (o.extra_metadata or {}).get("credits_to_add", 0)

        if is_token_order:
            items_desc.append(f"AI Gemini Compute Pack (+{credits_to_add} Credits)")
        elif o.items:
            for it in o.items:
                t_title = it.template.title if it.template else "Template Package"
                items_desc.append(f"{t_title} ({it.license_type or 'Standard'})")
        else:
            items_desc.append(o.notes or "Digital Product / Service")

        order_records.append({
            "id": str(o.id),
            "order_number": o.order_number,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "total": float(o.total),
            "subtotal": float(o.subtotal),
            "tax": float(o.tax),
            "currency": (o.extra_metadata or {}).get("currency", "USD"),
            "gateway": (
                o.payment.gateway.value if (o.payment and hasattr(o.payment.gateway, "value"))
                else ("UPI" if (o.extra_metadata or {}).get("upi_utr") else "Stripe")
            ),
            "items_summary": ", ".join(items_desc) if items_desc else "Site Studio Order",
            "receipt_url": f"/dashboard/receipt/{o.id}",
            "is_token_purchase": is_token_order,
            "credits_added": credits_to_add,
        })

    sub_records = []
    for s in subscriptions:
        dep = deployments_map.get(s.deployment_id)
        sub_records.append({
            "id": str(s.id),
            "deployment_id": str(s.deployment_id),
            "site_title": dep.title if dep else "Studio Hosted Website",
            "subdomain": dep.subdomain if dep else None,
            "custom_domain": dep.custom_domain if dep else None,
            "status": s.status,
            "monthly_price": 12.00,
            "currency": "USD",
            "stripe_subscription_id": s.stripe_subscription_id,
            "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
            "cancel_at_period_end": s.cancel_at_period_end,
        })

    ai_credits = current_user.ai_credits if current_user.ai_credits is not None else 10

    return {
        "summary": {
            "total_spent_usd": round(total_spent_usd, 2),
            "total_orders_count": len(orders),
            "completed_orders_count": len(completed_orders),
            "active_hosting_subscriptions": len(active_subs),
            "monthly_recurring_spend_usd": round(monthly_hosting_cost, 2),
            "current_ai_credits": ai_credits,
            "user_email": current_user.email,
            "user_currency": current_user.currency or "USD",
        },
        "orders": order_records,
        "subscriptions": sub_records,
        "token_packs": [
            {
                "id": "tokens_50",
                "name": "Starter Compute Pack",
                "credits": 50,
                "price_usd": 5.00,
                "badge": "Entry",
                "description": "50 Gemini AI Credits for autonomous repairs, code analysis, and AI Fill edits.",
                "popular": False,
            },
            {
                "id": "tokens_200",
                "name": "Pro Creator Pack",
                "credits": 200,
                "price_usd": 15.00,
                "badge": "Popular - Save 25%",
                "description": "200 Gemini AI Credits for heavy multi-site workflows, instant AI Doctor auto-healing, and copy generation.",
                "popular": True,
            },
            {
                "id": "tokens_500",
                "name": "Studio Enterprise Pack",
                "credits": 500,
                "price_usd": 30.00,
                "badge": "Best Value - Save 40%",
                "description": "500 Gemini AI Credits for high-volume agency builds, multi-agent synthesis, and production deployments.",
                "popular": False,
            },
        ],
    }


@router.post("/purchase-tokens")
async def purchase_tokens(
    payload: PurchaseTokensRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initialize purchase of an AI Gemini Token Compute Pack via Razorpay.
    Creates an official Order and initializes a Razorpay order.
    """
    user_tier = str(getattr(current_user, "subscription_tier", "free") or "free").lower()
    
    # Tier-based token pricing:
    # 1. Free users pay standard token rates
    # 2. Pro users get 40% discount on token packs
    # 3. Extreme users get 60% discount on token packs
    if user_tier in ("extreme", "agency", "enterprise"):
        tier_pricing = {
            "tokens_50": {"credits": 50, "price": Decimal("4.00"), "title": "50 Gemini AI Credits (Extreme 60% OFF)"},
            "tokens_200": {"credits": 200, "price": Decimal("12.00"), "title": "200 Gemini AI Credits (Extreme 60% OFF)"},
            "tokens_500": {"credits": 500, "price": Decimal("24.00"), "title": "500 Gemini AI Credits (Extreme 60% OFF)"},
        }
    elif user_tier in ("pro", "creator_pro"):
        tier_pricing = {
            "tokens_50": {"credits": 50, "price": Decimal("6.00"), "title": "50 Gemini AI Credits (Pro Discount - 40% OFF)"},
            "tokens_200": {"credits": 200, "price": Decimal("18.00"), "title": "200 Gemini AI Credits (Pro Discount - 40% OFF)"},
            "tokens_500": {"credits": 500, "price": Decimal("35.00"), "title": "500 Gemini AI Credits (Pro Discount - 42% OFF)"},
        }
    else:
        tier_pricing = {
            "tokens_50": {"credits": 50, "price": Decimal("10.00"), "title": "50 Gemini AI Credits (Free Tier Rate)"},
            "tokens_200": {"credits": 200, "price": Decimal("30.00"), "title": "200 Gemini AI Credits (Free Tier Rate)"},
            "tokens_500": {"credits": 500, "price": Decimal("60.00"), "title": "500 Gemini AI Credits (Free Tier Rate)"},
        }

    pack = tier_pricing.get(payload.pack_id)
    if not pack:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pack_id '{payload.pack_id}'. Choose from: {list(tier_pricing.keys())}"
        )

    usd_to_inr_rate = await get_usd_to_inr_rate()
    inr_amount = (pack["price"] * Decimal(str(usd_to_inr_rate))).quantize(Decimal("0.01"))
    amount_in_paise = int(inr_amount * 100)

    import random, string
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    order_num = f"TOK-{suffix}"

    order = Order(
        user_id=current_user.id,
        order_number=order_num,
        status=OrderStatus.PENDING,
        subtotal=pack["price"],
        discount=Decimal("0"),
        tax=Decimal("0"),
        total=pack["price"],
        notes=f"AI Compute Top-Up: {pack['title']}",
        extra_metadata={
            "type": "ai_credits",
            "pack_id": payload.pack_id,
            "credits_to_add": pack["credits"],
            "currency": "USD",
            "inr_amount": float(inr_amount),
        },
    )
    db.add(order)
    await db.flush()

    is_mock_allowed = (settings.ENVIRONMENT == "test") or getattr(settings, "ALLOW_MOCK_PAYMENTS", False)

    # ── 1. STRIPE TOKEN PACK CHECKOUT ──
    if payload.gateway == PaymentGateway.STRIPE:
        price_usd = pack["price"]
        amount_in_cents = int(price_usd * 100)
        is_stripe_configured = bool(
            settings.STRIPE_SECRET_KEY
            and not settings.STRIPE_SECRET_KEY.startswith(("sk_test_...", "your-"))
            and "mock" not in settings.STRIPE_SECRET_KEY.lower()
        )
        stripe_session_id = None
        checkout_url = None

        if is_stripe_configured:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                session = await asyncio.to_thread(
                    stripe.checkout.Session.create,
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"AI Site Studio Token Top-Up: {pack['title']}",
                                "description": f"{pack['credits']} AI Automation & Synthesis Tokens",
                            },
                            "unit_amount": amount_in_cents,
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    client_reference_id=str(order.id),
                    customer_email=current_user.email,
                    success_url=f"{settings.FRONTEND_URL}/dashboard?tab=ai-tokens&success=true&order_id={order.id}&session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{settings.FRONTEND_URL}/dashboard?tab=ai-tokens&cancelled=true",
                    metadata={
                        "order_id": str(order.id),
                        "order_number": str(order.order_number),
                        "user_id": str(current_user.id),
                        "type": "ai_credits",
                        "pack_id": payload.pack_id,
                        "credits_to_add": str(pack["credits"]),
                    }
                )
                stripe_session_id = session.id
                checkout_url = session.url
            except Exception as s_err:
                logger.warning(f"Stripe token pack session create failed: {s_err}")
                if is_mock_allowed:
                    stripe_session_id = f"cs_mock_tok_{uuid.uuid4().hex[:12]}"
                    checkout_url = f"{settings.FRONTEND_URL}/dashboard?tab=ai-tokens&mock_stripe=true&order_id={order.id}"
                else:
                    raise HTTPException(status_code=502, detail="There is some issue processing your Stripe payment right now. Please try again later.")
        else:
            if not is_mock_allowed:
                raise HTTPException(status_code=503, detail="Stripe payment gateway is unavailable right now. Please try again later.")
            stripe_session_id = f"cs_mock_tok_{uuid.uuid4().hex[:12]}"
            checkout_url = f"{settings.FRONTEND_URL}/dashboard?tab=ai-tokens&mock_stripe=true&order_id={order.id}"

        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            status=PaymentStatus.PENDING,
            amount=price_usd,
            currency="USD",
            gateway_order_id=stripe_session_id,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(order)

        return {
            "status": "initiated",
            "order_id": str(order.id),
            "order_number": order.order_number,
            "gateway": "stripe",
            "gateway_order_id": stripe_session_id,
            "amount": amount_in_cents,
            "amount_usd": float(price_usd),
            "currency": "USD",
            "checkout_url": checkout_url,
            "key_id": settings.STRIPE_PUBLISHABLE_KEY or "pk_test_mock",
            "pack_id": payload.pack_id,
            "title": pack["title"],
            "credits": pack["credits"],
        }

    # ── 2. RAZORPAY SUBSCRIPTION CHECKOUT ──
    is_mock_key = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
        or "change-me" in settings.RAZORPAY_KEY_ID
        or "mock" in settings.RAZORPAY_KEY_ID.lower()
    )

    rz_order_id = None
    if not is_mock_key:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            rz_order = await asyncio.to_thread(
                client.order.create,
                {
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "receipt": str(order.id)[:40],
                    "notes": {
                        "type": "ai_credits",
                        "pack_id": payload.pack_id,
                        "user_email": current_user.email,
                    }
                }
            )
            rz_order_id = rz_order["id"]
        except Exception as err:
            logger.warning(f"Could not create Razorpay order for token pack: {err}")
            if is_mock_allowed:
                rz_order_id = f"rzp_mock_tok_{uuid.uuid4().hex[:12]}"
            else:
                raise HTTPException(status_code=502, detail="There is some issue connecting to Razorpay right now. Please try again later.")
    else:
        if not is_mock_allowed:
            raise HTTPException(status_code=503, detail="Razorpay payment gateway is unavailable right now. Please try again later.")
        rz_order_id = f"rzp_mock_tok_{uuid.uuid4().hex[:12]}"

    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        status=PaymentStatus.PENDING,
        amount=inr_amount,
        currency="INR",
        gateway_order_id=rz_order_id,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(order)

    return {
        "status": "initiated",
        "order_id": str(order.id),
        "order_number": order.order_number,
        "gateway": "razorpay",
        "gateway_order_id": rz_order_id,
        "amount": amount_in_paise,
        "amount_inr": float(inr_amount),
        "amount_usd": float(pack["price"]),
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID if not is_mock_key else "rzp_test_mockkey",
        "credits": pack["credits"],
        "title": pack["title"],
    }


@router.post("/purchase-plan")
async def purchase_plan(
    payload: PurchasePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initialize purchase of a Studio Pro or Extreme subscription plan via Razorpay.
    Creates an official Order and initializes a Razorpay order.
    """
    from app.core.plans import get_plan_config, normalize_plan_id
    clean_plan_id = normalize_plan_id(payload.plan_id)
    plan_cfg = get_plan_config(clean_plan_id)

    # Free plan instant switch
    if clean_plan_id == "free":
        current_user.subscription_tier = "free"
        current_user.subscription_expires_at = None
        current_user.subscription_status = "canceled"
        current_user.auto_renew = False
        current_user.ai_credits = 0  # Finished/canceled plan = 0 tokens
        from app.services.entitlement_service import EntitlementService
        ent_svc = EntitlementService(db)
        sub = await ent_svc.get_or_create_user_subscription(current_user)
        sub.plan_id = "free"
        sub.status = "active"
        sub.cancel_at_period_end = False
        await db.commit()
        return {
            "status": "completed",
            "plan_id": "free",
            "title": plan_cfg["name"],
            "message": "Switched to Free plan successfully.",
            "free": True,
        }

    is_annual = payload.billing_cycle.lower() == "annual"
    total_price = plan_cfg["annual_price_usd"] if is_annual else plan_cfg["monthly_price_usd"]
    inr_amount = plan_cfg["annual_price_inr"] if is_annual else plan_cfg["monthly_price_inr"]
    amount_in_paise = int(inr_amount * 100)

    import random, string
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    order_num = f"SUB-{suffix}"

    order = Order(
        user_id=current_user.id,
        order_number=order_num,
        status=OrderStatus.PENDING,
        subtotal=total_price,
        discount=Decimal("0"),
        tax=Decimal("0"),
        total=total_price,
        notes=f"Subscription: {plan_cfg['name']} ({payload.billing_cycle.title()})",
        extra_metadata={
            "type": "subscription_plan",
            "plan_id": clean_plan_id,
            "billing_cycle": payload.billing_cycle,
            "credits_to_add": plan_cfg["included_ai_credits"],
            "currency": "USD",
            "inr_amount": float(inr_amount),
        },
    )
    db.add(order)
    await db.flush()

    is_mock_allowed = (settings.ENVIRONMENT == "test") or getattr(settings, "ALLOW_MOCK_PAYMENTS", False)

    # ── 1. STRIPE SUBSCRIPTION CHECKOUT ──
    if payload.gateway == PaymentGateway.STRIPE:
        amount_in_cents = int(total_price * 100)
        is_stripe_configured = bool(
            settings.STRIPE_SECRET_KEY
            and not settings.STRIPE_SECRET_KEY.startswith(("sk_test_...", "your-"))
            and "mock" not in settings.STRIPE_SECRET_KEY.lower()
        )
        stripe_session_id = None
        checkout_url = None

        if is_stripe_configured:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                session = await asyncio.to_thread(
                    stripe.checkout.Session.create,
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"AI Site Studio {plan_cfg['name']} Subscription",
                                "description": f"{payload.billing_cycle.title()} membership — {plan_cfg['included_ai_credits']} Monthly Automation Tokens",
                            },
                            "unit_amount": amount_in_cents,
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    client_reference_id=str(order.id),
                    customer_email=current_user.email,
                    success_url=f"{settings.FRONTEND_URL}/subscribe?success=true&order_id={order.id}&session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{settings.FRONTEND_URL}/subscribe?cancelled=true",
                    metadata={
                        "order_id": str(order.id),
                        "order_number": str(order.order_number),
                        "user_id": str(current_user.id),
                        "type": "subscription_plan",
                        "plan_id": clean_plan_id,
                        "billing_cycle": payload.billing_cycle,
                    }
                )
                stripe_session_id = session.id
                checkout_url = session.url
            except Exception as s_err:
                logger.warning(f"Stripe subscription session create failed: {s_err}")
                if is_mock_allowed:
                    stripe_session_id = f"cs_mock_sub_{uuid.uuid4().hex[:12]}"
                    checkout_url = f"{settings.FRONTEND_URL}/subscribe?mock_stripe=true&order_id={order.id}"
                else:
                    raise HTTPException(status_code=502, detail="There is some issue connecting to Stripe right now. Please try again later.")
        else:
            if not is_mock_allowed:
                raise HTTPException(status_code=503, detail="Stripe payment gateway is unavailable right now. Please try again later.")
            stripe_session_id = f"cs_mock_sub_{uuid.uuid4().hex[:12]}"
            checkout_url = f"{settings.FRONTEND_URL}/subscribe?mock_stripe=true&order_id={order.id}"

        payment = Payment(
            order_id=order.id,
            gateway=PaymentGateway.STRIPE,
            status=PaymentStatus.PENDING,
            amount=total_price,
            currency="USD",
            gateway_order_id=stripe_session_id,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(order)

        return {
            "status": "initiated",
            "order_id": str(order.id),
            "order_number": order.order_number,
            "gateway": "stripe",
            "gateway_order_id": stripe_session_id,
            "amount": amount_in_cents,
            "amount_usd": float(total_price),
            "currency": "USD",
            "checkout_url": checkout_url,
            "key_id": settings.STRIPE_PUBLISHABLE_KEY or "pk_test_mock",
            "plan_id": clean_plan_id,
            "billing_cycle": payload.billing_cycle,
            "title": f"{plan_cfg['name']} ({payload.billing_cycle.title()})",
        }

    # ── 2. RAZORPAY SUBSCRIPTION CHECKOUT ──
    is_mock_key = (
        not settings.RAZORPAY_KEY_ID
        or settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
        or "change-me" in settings.RAZORPAY_KEY_ID
        or "mock" in settings.RAZORPAY_KEY_ID.lower()
    )

    rz_order_id = None
    if not is_mock_key:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            rz_order = await asyncio.to_thread(
                client.order.create,
                {
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "receipt": str(order.id)[:40],
                    "notes": {
                        "type": "subscription_plan",
                        "plan_id": clean_plan_id,
                        "user_email": current_user.email,
                    }
                }
            )
            rz_order_id = rz_order["id"]
        except Exception as err:
            logger.warning(f"Could not create Razorpay order for subscription: {err}")
            if is_mock_allowed:
                rz_order_id = f"rzp_mock_sub_{uuid.uuid4().hex[:12]}"
            else:
                raise HTTPException(status_code=502, detail="There is some issue connecting to Razorpay right now. Please try again later.")
    else:
        if not is_mock_allowed:
            raise HTTPException(status_code=503, detail="Razorpay payment gateway is unavailable right now. Please try again later.")
        rz_order_id = f"rzp_mock_sub_{uuid.uuid4().hex[:12]}"

    payment = Payment(
        order_id=order.id,
        gateway=PaymentGateway.RAZORPAY,
        status=PaymentStatus.PENDING,
        amount=inr_amount,
        currency="INR",
        gateway_order_id=rz_order_id,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(order)

    return {
        "status": "initiated",
        "order_id": str(order.id),
        "order_number": order.order_number,
        "gateway": "razorpay",
        "gateway_order_id": rz_order_id,
        "amount": amount_in_paise,
        "amount_inr": float(inr_amount),
        "amount_usd": float(total_price),
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID if not is_mock_key else "rzp_test_mockkey",
        "plan_id": clean_plan_id,
        "title": plan_cfg["name"],
        "credits": plan_cfg["included_ai_credits"],
        "billing_cycle": payload.billing_cycle,
    }


@router.get("/subscription-status")
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the user's active subscription tier, expiration timestamp,
    days remaining, auto_renew state, and live deployment allowances.
    """
    now = datetime.now(timezone.utc)
    is_pro = current_user.is_pro_subscriber
    tier = (current_user.subscription_tier or "free").lower()
    expires_at = current_user.subscription_expires_at

    days_remaining = 0
    is_expired = False
    if expires_at:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if exp > now:
            days_remaining = max(0, (exp - now).days)
        else:
            is_expired = True

    # Count user's current live deployments
    from app.models.deployment import Deployment
    dep_res = await db.execute(
        select(func.count(Deployment.id)).where(
            Deployment.user_id == current_user.id,
            Deployment.status == "live",
        )
    )
    active_deployments_count = dep_res.scalar_one() or 0

    if tier in ("extreme", "agency"):
        max_deployments = 999
    elif is_pro:
        max_deployments = 3
    else:
        max_deployments = 1

    return {
        "tier": tier,
        "is_pro": is_pro,
        "is_expired": is_expired,
        "status": current_user.subscription_status or ("active" if is_pro else "free"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "days_remaining": days_remaining,
        "auto_renew": current_user.auto_renew,
        "max_deployments": max_deployments,
        "active_deployments": active_deployments_count,
        "included_hosting": is_pro or tier in ("extreme", "agency"),
        "hosting_cost_per_extra_site": 12.00,
    }
