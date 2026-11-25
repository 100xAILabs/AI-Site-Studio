"""
API Router for Extreme Plan Creators: Onboarding questionnaire, multi-gateway payout setup,
and dedicated branded storefront on our domain (/creator/{slug}).
"""

import re
import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User, UserRole
from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentGateway, PaymentStatus
from app.models.category import Category
from app.schemas.creator import (
    CreatorSetupRequest,
    CreatorProfileResponse,
    CreatorPublicStorefrontResponse,
    CreatorStats,
    RazorpayProvisionRequest,
    StripeConnectProvisionRequest,
    GatewayConnectResponse,
)
from app.schemas.template import TemplateResponse
from app.core.redis import cache_delete_pattern
from app.services.gateway_provisioning import (
    is_placeholder_value,
    validate_real_upi_vpa,
    validate_bank_details,
    provision_razorpay_account,
    provision_stripe_connect_account,
    verify_razorpay_account_live,
)

router = APIRouter()


class CreatorBankTransferReview(BaseModel):
    decision: str


@router.get("/payments/bank-transfers/pending")
async def list_creator_pending_bank_transfers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List transfer references for the creator's own template orders only."""
    stmt = (
        select(Payment)
        .join(Order, Payment.order_id == Order.id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Template, Template.id == OrderItem.template_id)
        .options(selectinload(Payment.order).selectinload(Order.user))
        .where(
            Template.seller_id == current_user.id,
            Payment.gateway == PaymentGateway.BANK_TRANSFER,
            Payment.status == PaymentStatus.PENDING,
            Payment.gateway_payment_id.like("BANKREF:%"),
        )
        .distinct()
        .order_by(Payment.created_at.asc())
    )
    result = await db.execute(stmt)
    return [
        {
            "id": str(payment.id),
            "order_id": str(payment.order_id),
            "order_number": payment.order.order_number if payment.order else None,
            "reference": (payment.gateway_payment_id or "").removeprefix("BANKREF:"),
            "amount": float(payment.amount),
            "currency": payment.currency,
            "submitted_at": payment.updated_at.isoformat() if payment.updated_at else None,
        }
        for payment in result.scalars().all()
    ]


@router.patch("/payments/bank-transfers/{payment_id}/review")
async def review_creator_bank_transfer(
    payment_id: uuid.UUID,
    review: CreatorBankTransferReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creator confirms receipt from their own bank account before buyer fulfillment."""
    if review.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Decision must be approve or reject.")
    result = await db.execute(
        select(Payment)
        .options(
            selectinload(Payment.order).selectinload(Order.items).selectinload(OrderItem.template),
            selectinload(Payment.order).selectinload(Order.user),
        )
        .where(Payment.id == payment_id)
        .with_for_update()
    )
    payment = result.scalar_one_or_none()
    if not payment or not payment.order:
        raise HTTPException(status_code=404, detail="Transfer order not found.")
    if payment.gateway != PaymentGateway.BANK_TRANSFER or not (payment.gateway_payment_id or "").startswith("BANKREF:"):
        raise HTTPException(status_code=400, detail="This order has no submitted bank transfer reference.")
    if payment.status != PaymentStatus.PENDING or payment.order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=409, detail="This transfer has already been reviewed.")
    if not payment.order.items or any(
        not item.template or item.template.seller_id != current_user.id for item in payment.order.items
    ):
        raise HTTPException(status_code=403, detail="You can only review transfers for your own storefront orders.")

    if review.decision == "approve":
        payment.status = PaymentStatus.CAPTURED
        payment.order.status = OrderStatus.COMPLETED
        from app.api.v1.routes.payment import _fulfill_order_licenses
        buyer_email = payment.order.user.email if payment.order.user else None
        await _fulfill_order_licenses(db, payment.order, user_email=buyer_email)
    else:
        payment.status = PaymentStatus.FAILED

    await db.commit()
    return {"payment_id": str(payment.id), "status": payment.status.value, "order_id": str(payment.order_id)}

RESERVED_SLUGS = {
    "api", "admin", "setup", "dashboard", "marketplace", "preview",
    "studio", "settings", "pricing", "auth", "terms", "privacy",
    "orders", "cart", "checkout", "login", "register", "verify-otp",
    "forgot-password", "about", "contact", "storybook", "support",
    "help", "docs", "null", "undefined", "system", "root", "creator"
}


def _mask_account(acc: Optional[str]) -> Optional[str]:
    if not acc:
        return None
    clean = str(acc).strip()
    if len(clean) <= 4:
        return "******"
    return f"{'*' * (len(clean) - 4)}{clean[-4:]}"


def _compute_verified_payout_status(user: User, payout_details: dict, strict: bool = True) -> dict:
    """Evaluate verified payout connectivity across configured gateways."""
    has_bank = bool(
        (user.payout_bank_name or payout_details.get("bank_name"))
        and user.payout_account_number
        and user.payout_account_holder_name
        and (user.payout_ifsc_code or payout_details.get("ifsc_code") or payout_details.get("iban") or payout_details.get("swift_code"))
    )
    upi_vpa = payout_details.get("upi_id") or user.payout_razorpay_vpa or payout_details.get("razorpay_vpa")
    has_upi = bool(upi_vpa and "@" in str(upi_vpa) and not is_placeholder_value(upi_vpa))

    rzp_id = payout_details.get("razorpay_account_id")
    rzp_status = str(payout_details.get("razorpay_status") or "").lower()
    if strict:
        has_razorpay = bool(
            rzp_id
            and str(rzp_id).startswith(("acc_", "fa_"))
            and not is_placeholder_value(rzp_id)
            and rzp_status != "error"
        )
    else:
        has_razorpay = bool(rzp_id or payout_details.get("razorpay_vpa") or user.payout_razorpay_vpa)

    stripe_id = payout_details.get("stripe_account_id")
    stripe_link = payout_details.get("stripe_payment_link")
    stripe_submitted = bool(payout_details.get("stripe_details_submitted") or payout_details.get("stripe_charges_enabled") or payout_details.get("stripe_payouts_enabled"))
    valid_stripe_link = bool(
        stripe_link
        and str(stripe_link).startswith(("https://buy.stripe.com/", "https://checkout.stripe.com/"))
        and not is_placeholder_value(stripe_link)
    )
    if strict:
        has_stripe = bool(
            (stripe_id and str(stripe_id).startswith("acct_") and not is_placeholder_value(stripe_id) and stripe_submitted)
            or valid_stripe_link
        )
    else:
        has_stripe = bool(stripe_id or stripe_link or user.payout_stripe_email or payout_details.get("stripe_email"))

    has_paypal = bool((user.payout_paypal_email or payout_details.get("paypal_email") or payout_details.get("paypal_me")) and not is_placeholder_value(payout_details.get("paypal_email")))
    has_crypto = bool(payout_details.get("crypto_address") and len(str(payout_details.get("crypto_address"))) >= 16)
    has_other = bool(
        payout_details.get("wise_email")
        or payout_details.get("revolut_tag")
        or payout_details.get("cashapp_tag")
        or payout_details.get("venmo_tag")
        or payout_details.get("paystack_code")
        or payout_details.get("flutterwave_id")
        or (not strict and payout_details.get("custom_instructions"))
    )

    return {
        "bank": has_bank,
        "upi": has_upi,
        "razorpay": has_razorpay,
        "stripe": has_stripe,
        "paypal": has_paypal,
        "crypto": has_crypto,
        "other": has_other,
        "any": bool(has_bank or has_upi or has_razorpay or has_stripe or has_paypal or has_crypto or has_other),
    }


def _sanitized_payout_details_dict(user: User, raw: Optional[dict]) -> dict:
    """Return a copy of creator_payout_details with any raw account number strictly masked."""
    details = dict(raw or {})
    acc = user.payout_account_number or details.pop("account_number", None)
    details.pop("account_holder_name", None)
    if acc:
        details["account_number_masked"] = _mask_account(acc)
    return details


def _build_creator_profile_response(
    user: User,
    stripe_onboarding_url: Optional[str] = None,
) -> CreatorProfileResponse:
    slug = user.creator_store_slug or (user.username.lower() if user.username else None)
    storefront_url = f"/creator/{slug}" if slug else None
    raw_details = getattr(user, "creator_payout_details", None) or {}
    payout_details = _sanitized_payout_details_dict(user, raw_details)
    enabled_methods = payout_details.get("enabled_methods") or [user.payout_method or "stripe", "razorpay"]
    masked_acc = _mask_account(user.payout_account_number) or payout_details.get("account_number_masked")
    is_strict = settings.ENVIRONMENT != "test"
    conn_status = _compute_verified_payout_status(user, raw_details, strict=is_strict)

    return CreatorProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name or user.username,
        is_extreme_subscriber=user.is_extreme_subscriber,
        can_retail_templates=user.can_retail_templates,
        creator_brand_name=user.creator_brand_name or user.full_name or "Studio Creator",
        creator_store_slug=user.creator_store_slug,
        creator_logo_url=user.creator_logo_url or user.avatar_url,
        creator_banner_url=user.creator_banner_url,
        creator_tagline=user.creator_tagline,
        creator_bio=user.creator_bio,
        creator_support_email=user.creator_support_email or user.email,
        creator_website=user.creator_website,
        creator_social_links=user.creator_social_links or {},
        payout_method=user.payout_method or "stripe",
        enabled_payment_methods=enabled_methods,
        payout_stripe_email=user.payout_stripe_email or payout_details.get("stripe_email"),
        payout_stripe_account_id=payout_details.get("stripe_account_id"),
        payout_stripe_payment_link=payout_details.get("stripe_payment_link"),
        payout_paypal_email=user.payout_paypal_email or payout_details.get("paypal_email"),
        payout_paypal_me=payout_details.get("paypal_me"),
        payout_razorpay_vpa=user.payout_razorpay_vpa or payout_details.get("razorpay_vpa"),
        payout_razorpay_account_id=payout_details.get("razorpay_account_id"),
        payout_bank_name=user.payout_bank_name or payout_details.get("bank_name"),
        payout_account_number=masked_acc,
        payout_account_number_masked=masked_acc,
        payout_ifsc_code=user.payout_ifsc_code or payout_details.get("ifsc_code"),
        payout_swift_code=payout_details.get("swift_code"),
        payout_iban=payout_details.get("iban"),
        payout_account_holder_name=user.payout_account_holder_name,
        payout_upi_id=payout_details.get("upi_id") or user.payout_razorpay_vpa,
        payout_crypto_currency=payout_details.get("crypto_currency", "USDT"),
        payout_crypto_network=payout_details.get("crypto_network", "TRC20"),
        payout_crypto_address=payout_details.get("crypto_address"),
        payout_wise_email=payout_details.get("wise_email"),
        payout_revolut_tag=payout_details.get("revolut_tag"),
        payout_cashapp_tag=payout_details.get("cashapp_tag"),
        payout_venmo_tag=payout_details.get("venmo_tag"),
        payout_flutterwave_id=payout_details.get("flutterwave_id"),
        payout_paystack_code=payout_details.get("paystack_code"),
        payout_mercadopago_email=payout_details.get("mercadopago_email"),
        payout_custom_instructions=payout_details.get("custom_instructions"),
        payout_alerts=(user.extra_metadata or {}).get("payout_alerts", []),
        creator_payout_details=payout_details,
        phone=payout_details.get("phone"),
        country=payout_details.get("country", "IN"),
        business_type=payout_details.get("business_type", "individual"),
        stripe_onboarding_url=stripe_onboarding_url,
        gateway_connections=conn_status,
        storefront_distribution=user.storefront_distribution or "both",
        is_creator_onboarding_completed=user.is_creator_onboarding_completed,
        is_payout_setup_completed=bool(user.is_payout_setup_completed and conn_status["any"]),
        storefront_url=storefront_url,
    )


@router.get("/profile", response_model=CreatorProfileResponse)
async def get_creator_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Fetch the authenticated creator's profile, onboarding status, and storefront configuration.
    """
    return _build_creator_profile_response(current_user)


@router.post("/connect/razorpay", response_model=GatewayConnectResponse)
async def auto_connect_razorpay_account(
    data: RazorpayProvisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Automatically create (or verify) a genuine Razorpay Linked Account / Fund Account
    for an Extreme creator so they can collect real Razorpay payments & receive payouts.
    """
    if not current_user.can_retail_templates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Extreme Plan subscription required to connect creator payment gateways.",
        )

    existing_details = dict(current_user.creator_payout_details or {})
    acc_num = data.account_number
    if not acc_num or "*" in acc_num or "•" in acc_num:
        acc_num = current_user.payout_account_number

    holder = data.account_holder_name or current_user.payout_account_holder_name or data.creator_name or current_user.full_name
    ifsc = data.ifsc_code or current_user.payout_ifsc_code
    vpa = data.upi_vpa or current_user.payout_razorpay_vpa or existing_details.get("upi_id")
    phone = data.phone or existing_details.get("phone")
    brand = data.brand_name or current_user.creator_brand_name or current_user.full_name or "Site Studio Creator"

    res = await provision_razorpay_account(
        user_id=str(current_user.id),
        email=data.email or current_user.creator_support_email or current_user.email,
        phone=phone,
        brand_name=brand,
        creator_name=data.creator_name or current_user.full_name,
        business_type=data.business_type or existing_details.get("business_type", "individual"),
        pan=data.pan or existing_details.get("pan"),
        bank_name=data.bank_name or current_user.payout_bank_name,
        account_number=acc_num,
        ifsc_code=ifsc,
        account_holder_name=holder,
        upi_vpa=vpa,
        existing_account_id=data.existing_account_id,
    )

    if not res.success or not res.connected or not res.account_id:
        existing_details["razorpay_status"] = "error"
        existing_details["razorpay_last_error"] = res.error
        current_user.creator_payout_details = existing_details
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "There is some issue creating or connecting your Razorpay account right now. Please try again later.",
        )

    # Persist real verified Razorpay connection & encrypted bank details
    if data.bank_name:
        current_user.payout_bank_name = data.bank_name.strip()
    if acc_num and "*" not in acc_num and "•" not in acc_num:
        current_user.payout_account_number = re.sub(r"\s+", "", acc_num)
    if ifsc:
        current_user.payout_ifsc_code = ifsc.strip().upper()
    if holder:
        current_user.payout_account_holder_name = holder.strip()
    if vpa and "@" in vpa:
        current_user.payout_razorpay_vpa = vpa.strip().lower()

    enabled = list(existing_details.get("enabled_methods") or [])
    if "razorpay" not in enabled:
        enabled.append("razorpay")
    existing_details["enabled_methods"] = enabled
    existing_details["razorpay_account_id"] = res.account_id
    existing_details["razorpay_account_type"] = res.account_type
    existing_details["razorpay_status"] = res.status_label
    existing_details.pop("razorpay_last_error", None)
    existing_details["razorpay_verified_at"] = datetime.now(timezone.utc).isoformat()
    if phone:
        existing_details["phone"] = phone.strip()
    if data.pan:
        existing_details["pan"] = data.pan.strip().upper()
    if data.business_type:
        existing_details["business_type"] = data.business_type.strip().lower()
    if current_user.payout_account_number:
        existing_details["account_number_masked"] = _mask_account(current_user.payout_account_number)
    existing_details.pop("account_number", None)
    existing_details.pop("account_holder_name", None)

    current_user.creator_payout_details = existing_details
    current_user.is_payout_setup_completed = True
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    return GatewayConnectResponse(
        success=True,
        provider="razorpay",
        connected=True,
        account_id=res.account_id,
        account_type=res.account_type,
        status_label=res.status_label,
        message=f"Razorpay account connected successfully ({res.account_id}).",
    )


@router.post("/connect/stripe", response_model=GatewayConnectResponse)
async def auto_connect_stripe_account(
    data: StripeConnectProvisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or verify a genuine Stripe Connect Express account and generate an onboarding link.
    """
    if not current_user.can_retail_templates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Extreme Plan subscription required to connect Stripe payouts.",
        )

    existing_details = dict(current_user.creator_payout_details or {})
    res = await provision_stripe_connect_account(
        user_id=str(current_user.id),
        email=data.email or current_user.payout_stripe_email or current_user.creator_support_email or current_user.email,
        brand_name=data.brand_name or current_user.creator_brand_name or current_user.full_name or "Site Studio Creator",
        country=data.country or existing_details.get("country", "US"),
        existing_account_id=data.existing_account_id or existing_details.get("stripe_account_id"),
        return_url=data.return_url,
        refresh_url=data.refresh_url,
    )

    if not res.success or not res.account_id:
        existing_details["stripe_status"] = "error"
        existing_details["stripe_last_error"] = res.error
        current_user.creator_payout_details = existing_details
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "There is some issue connecting your Stripe account right now. Please try again later.",
        )

    enabled = list(existing_details.get("enabled_methods") or [])
    if "stripe" not in enabled:
        enabled.append("stripe")
    existing_details["enabled_methods"] = enabled
    existing_details["stripe_account_id"] = res.account_id
    existing_details["stripe_status"] = res.status_label
    existing_details["stripe_details_submitted"] = bool(res.metadata.get("details_submitted"))
    existing_details["stripe_charges_enabled"] = bool(res.metadata.get("charges_enabled"))
    existing_details["stripe_payouts_enabled"] = bool(res.metadata.get("payouts_enabled"))
    existing_details.pop("stripe_last_error", None)
    if data.country:
        existing_details["country"] = data.country.strip().upper()[:5]
    if data.email:
        current_user.payout_stripe_email = data.email.strip().lower()
        existing_details["stripe_email"] = current_user.payout_stripe_email

    current_user.creator_payout_details = existing_details
    if res.connected:
        current_user.is_payout_setup_completed = True
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    return GatewayConnectResponse(
        success=True,
        provider="stripe",
        connected=res.connected,
        account_id=res.account_id,
        account_type=res.account_type,
        status_label=res.status_label,
        onboarding_url=res.onboarding_url,
        message=(
            "Stripe Express account verified and active."
            if res.connected
            else "Stripe Express account initialized. Complete the secure Stripe onboarding link to activate card & bank payouts."
        ),
    )


@router.get("/connect/status", response_model=CreatorProfileResponse)
async def refresh_gateway_connection_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-check live connection status from Stripe & Razorpay APIs (e.g. after onboarding return).
    """
    details = dict(current_user.creator_payout_details or {})
    changed = False

    if settings.ENVIRONMENT != "test":
        stripe_id = details.get("stripe_account_id")
        if stripe_id and not is_placeholder_value(stripe_id):
            st_res = await provision_stripe_connect_account(
                user_id=str(current_user.id),
                email=current_user.email,
                brand_name=current_user.creator_brand_name or "Creator",
                existing_account_id=stripe_id,
            )
            if st_res.success:
                details["stripe_status"] = st_res.status_label
                details["stripe_details_submitted"] = bool(st_res.metadata.get("details_submitted"))
                details["stripe_charges_enabled"] = bool(st_res.metadata.get("charges_enabled"))
                details["stripe_payouts_enabled"] = bool(st_res.metadata.get("payouts_enabled"))
                changed = True

        rzp_id = details.get("razorpay_account_id")
        if rzp_id and str(rzp_id).startswith(("acc_", "fa_")) and not is_placeholder_value(rzp_id):
            rz_res = await verify_razorpay_account_live(rzp_id)
            if rz_res.success:
                details["razorpay_status"] = rz_res.status_label
                changed = True

    if changed:
        current_user.creator_payout_details = details
        conn = _compute_verified_payout_status(current_user, details, strict=(settings.ENVIRONMENT != "test"))
        current_user.is_payout_setup_completed = conn["any"]
        await db.commit()
        await db.refresh(current_user)

    return _build_creator_profile_response(current_user)


@router.get("/check-slug")
async def check_slug_availability(
    slug: str = Query(..., min_length=3, max_length=50),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Validate storefront slug format and check if it is available on our domain.
    """
    clean_slug = slug.strip().lower()

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$", clean_slug):
        return {
            "available": False,
            "slug": clean_slug,
            "reason": "Slug must contain only lowercase letters, numbers, and hyphens (3-50 chars). Cannot start or end with a hyphen.",
        }

    if clean_slug in RESERVED_SLUGS:
        return {
            "available": False,
            "slug": clean_slug,
            "reason": f"'{clean_slug}' is a reserved platform keyword.",
        }

    # Check database
    query = select(User.id).where(User.creator_store_slug == clean_slug)
    if current_user:
        query = query.where(User.id != current_user.id)

    existing_id = await db.scalar(query)
    if existing_id:
        return {
            "available": False,
            "slug": clean_slug,
            "reason": f"'{clean_slug}' is already taken by another creator.",
        }

    return {"available": True, "slug": clean_slug, "reason": None}


@router.put("/profile", response_model=CreatorProfileResponse)
async def update_creator_profile(
    data: CreatorSetupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save creator questions: Branding name, Creator's name, details, payment gateway choice,
    and storefront distribution (marketplace, dedicated storefront, or both).
    Exclusively available to Extreme Plan subscribers and platform administrators.
    """
    if not current_user.can_retail_templates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Selling templates and launching a dedicated branded storefront is an exclusive "
                "privilege of the Extreme Plan ($50/mo). Please upgrade your subscription to proceed."
            ),
        )

    # Validate slug
    clean_slug = data.store_slug.strip().lower()
    if clean_slug in RESERVED_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storefront slug '{clean_slug}' is a reserved system keyword. Please pick another name.",
        )

    existing = await db.scalar(
        select(User.id).where(
            User.creator_store_slug == clean_slug,
            User.id != current_user.id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storefront slug '{clean_slug}' is already in use by another creator.",
        )

    # Validate distribution
    dist = (data.storefront_distribution or "both").lower()
    if dist not in ("marketplace", "storefront", "both"):
        dist = "both"

    # Validate payout method
    payout = (data.payout_method or "stripe").lower()
    valid_payouts = {
        "stripe", "razorpay", "paypal", "bank", "upi", "crypto",
        "wise", "revolut", "cashapp", "venmo", "flutterwave", "paystack", "mercadopago"
    }
    if payout not in valid_payouts:
        payout = "stripe"

    # Normalize enabled payment methods
    enabled_methods = []
    if data.enabled_payment_methods:
        for m in data.enabled_payment_methods:
            clean_m = str(m).strip().lower()
            if clean_m in valid_payouts and clean_m not in enabled_methods:
                enabled_methods.append(clean_m)
    if not enabled_methods:
        enabled_methods = [payout]
    if payout not in enabled_methods:
        enabled_methods.insert(0, payout)

    # If creator provided a valid UPI VPA, ensure upi is enabled so buyers can pay via UPI
    if (data.payout_upi_id or data.payout_razorpay_vpa) and "upi" not in enabled_methods:
        enabled_methods.append("upi")
    if (data.payout_bank_name and data.payout_account_number) and "bank" not in enabled_methods:
        enabled_methods.append("bank")

    # Update creator profile fields
    current_user.creator_brand_name = data.brand_name.strip()
    if data.creator_name and data.creator_name.strip():
        current_user.full_name = data.creator_name.strip()

    current_user.creator_store_slug = clean_slug
    current_user.creator_tagline = data.tagline.strip() if data.tagline else None
    current_user.creator_bio = data.bio.strip() if data.bio else None
    current_user.creator_support_email = (
        data.support_email.strip() if data.support_email else current_user.email
    )
    current_user.creator_website = data.website.strip() if data.website else None
    current_user.creator_logo_url = data.logo_url.strip() if data.logo_url else current_user.avatar_url
    current_user.creator_banner_url = data.banner_url.strip() if data.banner_url else None
    current_user.creator_social_links = data.social_links or {}

    prev_details = dict(current_user.creator_payout_details or {})
    is_strict = settings.ENVIRONMENT != "test"
    stripe_onboarding_url: Optional[str] = None

    # Payouts & strict privacy handling (encrypt account numbers via User property; keep masked in JSON)
    current_user.payout_method = payout
    if data.payout_stripe_email:
        current_user.payout_stripe_email = data.payout_stripe_email.strip()
    if data.payout_paypal_email:
        current_user.payout_paypal_email = data.payout_paypal_email.strip()
    if data.payout_razorpay_vpa:
        current_user.payout_razorpay_vpa = data.payout_razorpay_vpa.strip().lower()

    if data.payout_bank_name:
        current_user.payout_bank_name = data.payout_bank_name.strip()
    if data.payout_account_number:
        raw_acc = data.payout_account_number.strip()
        # Preserve encrypted stored account number if masked UI value (****1234) was resubmitted unchanged
        if "*" not in raw_acc and "•" not in raw_acc:
            if is_strict and is_placeholder_value(raw_acc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please enter a real, valid bank account number (placeholder values are not allowed).",
                )
            current_user.payout_account_number = re.sub(r"\s+", "", raw_acc)
    if data.payout_ifsc_code:
        current_user.payout_ifsc_code = data.payout_ifsc_code.strip().upper()
    if data.payout_account_holder_name:
        current_user.payout_account_holder_name = data.payout_account_holder_name.strip()

    new_details = dict(prev_details)
    new_details.update({
        "enabled_methods": enabled_methods,
        "primary_method": payout,
        "stripe_email": data.payout_stripe_email.strip() if data.payout_stripe_email else prev_details.get("stripe_email"),
        "stripe_account_id": (data.payout_stripe_account_id.strip() if data.payout_stripe_account_id else prev_details.get("stripe_account_id")),
        "stripe_payment_link": data.payout_stripe_payment_link.strip() if data.payout_stripe_payment_link else None,
        "paypal_email": data.payout_paypal_email.strip() if data.payout_paypal_email else None,
        "paypal_me": data.payout_paypal_me.strip() if data.payout_paypal_me else None,
        "razorpay_vpa": (data.payout_razorpay_vpa.strip().lower() if data.payout_razorpay_vpa else (data.payout_upi_id.strip().lower() if data.payout_upi_id else None)),
        "razorpay_account_id": (data.payout_razorpay_account_id.strip() if data.payout_razorpay_account_id else prev_details.get("razorpay_account_id")),
        "bank_name": current_user.payout_bank_name,
        "ifsc_code": current_user.payout_ifsc_code,
        "swift_code": data.payout_swift_code.strip().upper() if data.payout_swift_code else None,
        "iban": data.payout_iban.strip().upper() if data.payout_iban else None,
        "upi_id": data.payout_upi_id.strip().lower() if data.payout_upi_id else (data.payout_razorpay_vpa.strip().lower() if data.payout_razorpay_vpa else None),
        "crypto_currency": data.payout_crypto_currency.strip() if data.payout_crypto_currency else "USDT",
        "crypto_network": data.payout_crypto_network.strip() if data.payout_crypto_network else "TRC20",
        "crypto_address": data.payout_crypto_address.strip() if data.payout_crypto_address else None,
        "wise_email": data.payout_wise_email.strip() if data.payout_wise_email else None,
        "revolut_tag": data.payout_revolut_tag.strip() if data.payout_revolut_tag else None,
        "cashapp_tag": data.payout_cashapp_tag.strip() if data.payout_cashapp_tag else None,
        "venmo_tag": data.payout_venmo_tag.strip() if data.payout_venmo_tag else None,
        "flutterwave_id": data.payout_flutterwave_id.strip() if data.payout_flutterwave_id else None,
        "paystack_code": data.payout_paystack_code.strip() if data.payout_paystack_code else None,
        "mercadopago_email": data.payout_mercadopago_email.strip() if data.payout_mercadopago_email else None,
        "custom_instructions": data.payout_custom_instructions.strip() if data.payout_custom_instructions else None,
        "phone": data.phone.strip() if data.phone else prev_details.get("phone"),
        "country": (data.country or prev_details.get("country") or "IN").strip().upper()[:5],
        "business_type": (data.business_type or prev_details.get("business_type") or "individual").strip().lower(),
        "pan": data.pan.strip().upper() if data.pan else prev_details.get("pan"),
    })
    new_details.pop("account_number", None)
    new_details.pop("account_holder_name", None)
    if current_user.payout_account_number:
        new_details["account_number_masked"] = _mask_account(current_user.payout_account_number)

    if is_strict:
        # 1. Validate direct bank details if bank method selected or bank fields provided
        if "bank" in enabled_methods:
            ok_bank, bank_err = validate_bank_details(
                bank_name=current_user.payout_bank_name,
                account_number=current_user.payout_account_number,
                account_holder_name=current_user.payout_account_holder_name,
                ifsc_code=current_user.payout_ifsc_code,
                iban=new_details.get("iban"),
                swift_code=new_details.get("swift_code"),
            )
            if not ok_bank:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=bank_err)

        # 2. Validate UPI strictly if enabled
        if "upi" in enabled_methods:
            ok_upi, upi_msg = validate_real_upi_vpa(new_details.get("upi_id"))
            if not ok_upi:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=upi_msg)

        # 3. Auto-create or verify genuine Razorpay account when Razorpay is enabled
        if "razorpay" in enabled_methods:
            rzp_acc_id = new_details.get("razorpay_account_id")
            if rzp_acc_id and is_placeholder_value(rzp_acc_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Fake or placeholder Razorpay account IDs are not permitted. Leave blank to auto-create one for you.",
                )
            already_verified_same = bool(
                rzp_acc_id
                and rzp_acc_id == prev_details.get("razorpay_account_id")
                and prev_details.get("razorpay_status") not in (None, "error")
            )
            if not already_verified_same:
                rz_res = await provision_razorpay_account(
                    user_id=str(current_user.id),
                    email=current_user.creator_support_email or current_user.email,
                    phone=new_details.get("phone"),
                    brand_name=current_user.creator_brand_name or "Studio Creator",
                    creator_name=current_user.full_name,
                    business_type=new_details.get("business_type", "individual"),
                    pan=new_details.get("pan"),
                    bank_name=current_user.payout_bank_name,
                    account_number=current_user.payout_account_number,
                    ifsc_code=current_user.payout_ifsc_code,
                    account_holder_name=current_user.payout_account_holder_name,
                    upi_vpa=new_details.get("razorpay_vpa") or new_details.get("upi_id"),
                    existing_account_id=rzp_acc_id,
                )
                if not rz_res.success or not rz_res.connected or not rz_res.account_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=rz_res.error or "There is some issue creating or connecting your Razorpay account right now. Please try again later.",
                    )
                new_details["razorpay_account_id"] = rz_res.account_id
                new_details["razorpay_account_type"] = rz_res.account_type
                new_details["razorpay_status"] = rz_res.status_label
                new_details["razorpay_verified_at"] = datetime.now(timezone.utc).isoformat()
                new_details.pop("razorpay_last_error", None)

        # 4. Verify or provision genuine Stripe Connect account when Stripe is enabled
        if "stripe" in enabled_methods:
            st_acc_id = new_details.get("stripe_account_id")
            st_link = new_details.get("stripe_payment_link")
            if st_acc_id and is_placeholder_value(st_acc_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Fake or placeholder Stripe Account IDs are not permitted. Connect your real Stripe Express account instead.",
                )
            if st_link and (is_placeholder_value(st_link) or not st_link.startswith(("https://buy.stripe.com/", "https://checkout.stripe.com/"))):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Stripe Payment Link. It must be a real HTTPS link from dashboard.stripe.com (https://buy.stripe.com/...).",
                )
            if st_acc_id:
                st_res = await provision_stripe_connect_account(
                    user_id=str(current_user.id),
                    email=new_details.get("stripe_email") or current_user.creator_support_email or current_user.email,
                    brand_name=current_user.creator_brand_name or "Studio Creator",
                    country=new_details.get("country", "US"),
                    existing_account_id=st_acc_id,
                )
                if not st_res.success:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=st_res.error or "There is some issue connecting your Stripe account right now. Please try again later.",
                    )
                new_details["stripe_account_id"] = st_res.account_id
                new_details["stripe_status"] = st_res.status_label
                new_details["stripe_details_submitted"] = bool(st_res.metadata.get("details_submitted"))
                new_details["stripe_charges_enabled"] = bool(st_res.metadata.get("charges_enabled"))
                new_details["stripe_payouts_enabled"] = bool(st_res.metadata.get("payouts_enabled"))
                stripe_onboarding_url = st_res.onboarding_url
            elif not st_link:
                # Auto-create a real Stripe Express Connect account and generate onboarding link
                st_res = await provision_stripe_connect_account(
                    user_id=str(current_user.id),
                    email=new_details.get("stripe_email") or current_user.creator_support_email or current_user.email,
                    brand_name=current_user.creator_brand_name or "Studio Creator",
                    country=new_details.get("country", "US"),
                )
                if not st_res.success or not st_res.account_id:
                    # If Stripe Express auto-provisioning was rejected (e.g. platform Stripe account needs dashboard activation),
                    # allow the storefront to proceed if the creator has another verified gateway configured (Razorpay, Bank, or UPI).
                    has_other_verified = bool(
                        ("razorpay" in enabled_methods and new_details.get("razorpay_account_id"))
                        or ("bank" in enabled_methods and current_user.payout_bank_name and current_user.payout_account_number)
                        or ("upi" in enabled_methods and new_details.get("upi_id"))
                    )
                    if has_other_verified:
                        logger.warning("Stripe Express auto-creation was skipped (%s); continuing with other ready payout gateways.", st_res.error)
                        new_details["stripe_status"] = "unverified"
                        new_details["stripe_last_error"] = st_res.error
                        if payout == "stripe":
                            if "razorpay" in enabled_methods and new_details.get("razorpay_account_id"):
                                current_user.payout_method = "razorpay"
                                new_details["primary_method"] = "razorpay"
                            elif "upi" in enabled_methods and new_details.get("upi_id"):
                                current_user.payout_method = "upi"
                                new_details["primary_method"] = "upi"
                            elif "bank" in enabled_methods:
                                current_user.payout_method = "bank"
                                new_details["primary_method"] = "bank"
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=st_res.error or "There is some issue connecting your Stripe account right now. Please try again later.",
                        )
                else:
                    new_details["stripe_account_id"] = st_res.account_id
                    new_details["stripe_status"] = st_res.status_label
                    new_details["stripe_details_submitted"] = False
                    new_details["stripe_charges_enabled"] = False
                    new_details["stripe_payouts_enabled"] = False
                    stripe_onboarding_url = st_res.onboarding_url

    current_user.creator_payout_details = new_details
    conn_status = _compute_verified_payout_status(current_user, new_details, strict=is_strict)

    if is_strict and not conn_status["any"]:
        # E.g. Stripe Express created but KYC onboarding not yet completed, and no other connected method
        current_user.storefront_distribution = dist
        current_user.is_creator_onboarding_completed = True
        current_user.is_payout_setup_completed = False
        current_user.updated_at = datetime.now(timezone.utc)
        if current_user.role in (UserRole.USER, UserRole.BUYER):
            current_user.role = UserRole.SELLER
        await db.commit()
        await db.refresh(current_user)
        await cache_delete_pattern("templates:*")
        return _build_creator_profile_response(current_user, stripe_onboarding_url=stripe_onboarding_url)

    current_user.storefront_distribution = dist
    current_user.is_creator_onboarding_completed = True
    current_user.is_payout_setup_completed = conn_status["any"]
    current_user.updated_at = datetime.now(timezone.utc)

    # If user was role USER/BUYER, elevate to SELLER
    if current_user.role in (UserRole.USER, UserRole.BUYER):
        current_user.role = UserRole.SELLER

    await db.commit()
    await db.refresh(current_user)

    # Invalidate cached template queries if any
    await cache_delete_pattern("templates:*")

    return _build_creator_profile_response(current_user, stripe_onboarding_url=stripe_onboarding_url)


@router.get("/storefront/{slug}", response_model=CreatorPublicStorefrontResponse)
async def get_public_creator_storefront(
    slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Public Endpoint: Get dedicated creator storefront data on our domain (/creator/{slug}).
    Returns creator branding, bio, stats, and all their published templates.
    """
    clean_slug = slug.strip().lower()

    # Find creator by store slug, username, or user ID
    query = select(User).where(
        (func.lower(User.creator_store_slug) == clean_slug) |
        ((User.creator_store_slug.is_(None)) & (func.lower(User.username) == clean_slug)) |
        (func.lower(User.username) == clean_slug)
    )
    creator = await db.scalar(query)

    if not creator:
        # Fallback check if clean_slug is uuid
        try:
            u_id = uuid.UUID(clean_slug)
            creator = await db.scalar(select(User).where(User.id == u_id))
        except (ValueError, TypeError):
            pass

    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator storefront '{clean_slug}' not found on this domain.",
        )

    # Auto-attribute browsing authenticated user as a client of this creator
    if current_user and current_user.id != creator.id and not current_user.client_of_creator_id:
        try:
            current_user.client_of_creator_id = creator.id
            current_user.client_of_creator_slug = creator.creator_store_slug or clean_slug
            current_user.client_of_brand = creator.creator_brand_name or creator.full_name or creator.username
            meta = dict(current_user.extra_metadata or {})
            meta["client_of_creator_id"] = str(creator.id)
            meta["client_of_creator_slug"] = creator.creator_store_slug or clean_slug
            meta["client_of_brand"] = creator.creator_brand_name or creator.full_name or creator.username
            current_user.extra_metadata = meta
            await db.commit()
        except Exception as e_attr:
            logger.info("Auto attribution notice on storefront visit: %s", e_attr)

    # Fetch this creator's published templates
    stmt = (
        select(Template)
        .options(selectinload(Template.category).selectinload(Category.children))
        .where(
            Template.seller_id == creator.id,
            Template.status.in_([TemplateStatus.PUBLISHED, TemplateStatus.APPROVED]),
            Template.is_deleted.is_(False),
            or_(
                cast(Template.tags, String).ilike("%retailed%"),
                Template.template_origin == "marketplace",
                and_(
                    Template.slug.notlike("%-custom-%"),
                    Template.title.notlike("%(Customized)%"),
                    Template.title.notlike("Customized %"),
                ),
            ),
        )
        .order_by(Template.is_featured.desc(), Template.downloads_count.desc(), Template.created_at.desc())
    )

    result = await db.execute(stmt)
    templates = list(result.scalars().all())

    total_templates = len(templates)
    total_sales = sum(t.downloads_count for t in templates)
    ratings = [t.rating_avg for t in templates if (t.rating_avg or 0) > 0]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 5.0
    total_reviews = sum(t.rating_count for t in templates)

    brand_name = creator.creator_brand_name or creator.full_name or creator.username or "Studio Creator"

    # Extract public payment options for buyers
    payout_details = getattr(creator, "creator_payout_details", None) or {}
    strict_mode = settings.ENVIRONMENT != "test"
    conn_status = _compute_verified_payout_status(creator, payout_details, strict=strict_mode)
    raw_enabled = payout_details.get("enabled_methods")
    if strict_mode:
        accepted_methods = list(raw_enabled) if raw_enabled else ([creator.payout_method] if creator.payout_method else [])
    else:
        accepted_methods = list(raw_enabled) if raw_enabled else [creator.payout_method or "stripe", "razorpay"]

    has_valid_upi = bool(conn_status.get("upi"))
    stripe_enabled = bool("stripe" in accepted_methods and (not strict_mode or conn_status.get("stripe")))
    razorpay_enabled = bool("razorpay" in accepted_methods and (not strict_mode or conn_status.get("razorpay")))
    # If the creator provided a verified UPI handle, enable Direct UPI automatically
    upi_enabled = bool(("upi" in accepted_methods or has_valid_upi) and (not strict_mode or has_valid_upi))
    paypal_enabled = bool("paypal" in accepted_methods and (not strict_mode or creator.payout_paypal_email or payout_details.get("paypal_email") or payout_details.get("paypal_me")))
    bank_enabled = bool(
        ("bank" in accepted_methods or "bank_transfer" in accepted_methods)
        and (not strict_mode or conn_status.get("bank"))
    )

    if strict_mode:
        public_accepted_methods = [
            m for m in accepted_methods
            if (
                (m == "stripe" and stripe_enabled)
                or (m == "razorpay" and razorpay_enabled)
                or (m == "upi" and upi_enabled)
                or (m == "paypal" and paypal_enabled)
                or (m in ("bank", "bank_transfer") and bank_enabled)
                or (m not in ("stripe", "razorpay", "upi", "paypal", "bank", "bank_transfer", "custom"))
            )
        ]
        if upi_enabled and "upi" not in public_accepted_methods:
            public_accepted_methods.append("upi")
    else:
        public_accepted_methods = accepted_methods
        if upi_enabled and "upi" not in public_accepted_methods:
            public_accepted_methods.append("upi")

    public_payment_options = {
        "primary": creator.payout_method or "stripe",
        "accepted_methods": public_accepted_methods,
        "stripe": {
            "enabled": stripe_enabled,
            "connected": bool(conn_status.get("stripe")),
            "payment_link": payout_details.get("stripe_payment_link"),
            "email": creator.payout_stripe_email or payout_details.get("stripe_email"),
        },
        "razorpay": {
            "enabled": razorpay_enabled,
            "connected": bool(conn_status.get("razorpay")),
            "vpa": creator.payout_razorpay_vpa or payout_details.get("razorpay_vpa"),
        },
        "paypal": {
            "enabled": paypal_enabled,
            "email": creator.payout_paypal_email or payout_details.get("paypal_email"),
            "paypal_me": payout_details.get("paypal_me"),
        },
        "upi": {
            "enabled": upi_enabled,
            "connected": bool(conn_status.get("upi")),
            "vpa": payout_details.get("upi_id") or creator.payout_razorpay_vpa,
        },
        "crypto": {
            "enabled": bool("crypto" in accepted_methods and (not strict_mode or payout_details.get("crypto_address"))),
            "currency": payout_details.get("crypto_currency", "USDT"),
            "network": payout_details.get("crypto_network", "TRC20"),
            "address": payout_details.get("crypto_address"),
        },
        "bank_transfer": {
            "enabled": bank_enabled,
        },
        "wise": {
            "enabled": bool("wise" in accepted_methods and (not strict_mode or payout_details.get("wise_email"))),
            "email": payout_details.get("wise_email"),
        },
        "revolut": {
            "enabled": bool("revolut" in accepted_methods and (not strict_mode or payout_details.get("revolut_tag"))),
            "tag": payout_details.get("revolut_tag"),
        },
        "cashapp": {
            "enabled": bool("cashapp" in accepted_methods and (not strict_mode or payout_details.get("cashapp_tag"))),
            "tag": payout_details.get("cashapp_tag"),
        },
        "venmo": {
            "enabled": bool("venmo" in accepted_methods and (not strict_mode or payout_details.get("venmo_tag"))),
            "tag": payout_details.get("venmo_tag"),
        },
        "flutterwave": {
            "enabled": bool("flutterwave" in accepted_methods and (not strict_mode or payout_details.get("flutterwave_id"))),
            "id": payout_details.get("flutterwave_id"),
        },
        "paystack": {
            "enabled": bool("paystack" in accepted_methods and (not strict_mode or payout_details.get("paystack_code"))),
            "code": payout_details.get("paystack_code"),
        },
        "custom_instructions": payout_details.get("custom_instructions"),
    }
    
    # Map templates to TemplateResponse
    template_responses = []
    for t in templates:
        resp = TemplateResponse.model_validate(t)
        # Ensure seller branding is consistent
        resp.developer_name = brand_name
        if creator.creator_logo_url:
            resp.developer_avatar = creator.creator_logo_url
        template_responses.append(resp)

    is_bank_connected = bool(creator.is_payout_setup_completed and conn_status["any"])
    payout_status_message = (
        "Payout details are configured. Bank transfers are released after the creator confirms receipt."
        if is_bank_connected
        else "Creator bank account or payment gateway is not connected yet. Direct purchases are temporarily paused."
    )

    return CreatorPublicStorefrontResponse(
        creator_id=str(creator.id),
        brand_name=brand_name,
        creator_name=creator.full_name or creator.username,
        store_slug=creator.creator_store_slug or clean_slug,
        tagline=creator.creator_tagline or "Curated premium templates tailored for production deployment.",
        bio=creator.creator_bio or "Official creator storefront on AI Site Studio.",
        support_email=creator.creator_support_email or creator.email,
        website=creator.creator_website,
        logo_url=creator.creator_logo_url or creator.avatar_url,
        banner_url=creator.creator_banner_url,
        social_links=creator.creator_social_links or {},
        is_verified=True,
        is_bank_connected=is_bank_connected,
        payout_status_message=payout_status_message,
        accepted_payment_methods=public_accepted_methods,
        payment_options=public_payment_options,
        stats=CreatorStats(
            total_templates=total_templates,
            total_sales=total_sales,
            average_rating=avg_rating,
            reviews_count=total_reviews,
        ),
        templates=template_responses,
    )


@router.get("/customers")
async def get_creator_customers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all clients and customers registered under or purchased from this creator.
    """
    creator_id_str = str(current_user.id)
    creator_slug = current_user.creator_store_slug or ""

    # 1. Users whose attribution marks them as a client of this creator
    conditions = [User.client_of_creator_id == current_user.id]
    if creator_slug:
        conditions.append(func.lower(User.client_of_creator_slug) == creator_slug.lower())
    
    client_query = select(User).where(or_(*conditions))
    client_res = await db.execute(client_query)
    registered_clients = client_res.scalars().all()

    # 2. Users who bought templates authored/retailed by this creator
    order_items_query = (
        select(OrderItem, Order, Template, User)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Template, OrderItem.template_id == Template.id)
        .join(User, Order.user_id == User.id)
        .where(
            Template.seller_id == current_user.id
        )
    )
    order_res = await db.execute(order_items_query)
    order_rows = order_res.all()

    customers_map = {}

    # Add registered clients
    for u in registered_clients:
        if u.id == current_user.id:
            continue
        u_id = str(u.id)
        customers_map[u_id] = {
            "id": u_id,
            "email": u.email,
            "name": u.full_name or u.username or u.email.split("@")[0],
            "avatar_url": u.avatar_url,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_buyer": False,
            "orders_count": 0,
            "total_spent": 0.0,
            "templates_owned": [],
            "source": "Registered Client"
        }

    # Add template purchasers
    for item, order, tmpl, u in order_rows:
        if u.id == current_user.id:
            continue
        u_id = str(u.id)
        if u_id not in customers_map:
            customers_map[u_id] = {
                "id": u_id,
                "email": u.email,
                "name": u.full_name or u.username or u.email.split("@")[0],
                "avatar_url": u.avatar_url,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "is_buyer": True,
                "orders_count": 0,
                "total_spent": 0.0,
                "templates_owned": [],
                "source": "Template Buyer"
            }
        c = customers_map[u_id]
        c["is_buyer"] = True
        c["orders_count"] += 1
        c["total_spent"] += float(item.price or 0)
        tmpl_title = tmpl.title if tmpl else "Template"
        if tmpl_title not in c["templates_owned"]:
            c["templates_owned"].append(tmpl_title)

    customers_list = list(customers_map.values())
    customers_list.sort(key=lambda x: (x["total_spent"], x["orders_count"]), reverse=True)

    return {
        "creator_brand_name": current_user.creator_brand_name or current_user.username,
        "creator_slug": current_user.creator_store_slug,
        "total_customers": len(customers_list),
        "customers": customers_list
    }


@router.post("/{slug}/attribute")
async def attribute_client_to_creator(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly associate an authenticated user as a client of this creator storefront.
    """
    clean_slug = slug.strip().lower()
    creator = await db.scalar(
        select(User).where(func.lower(User.creator_store_slug) == clean_slug)
    )
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    if current_user.id != creator.id and not current_user.client_of_creator_id:
        current_user.client_of_creator_id = creator.id
        current_user.client_of_creator_slug = creator.creator_store_slug or clean_slug
        current_user.client_of_brand = creator.creator_brand_name or creator.username
        meta = dict(current_user.extra_metadata or {})
        meta["client_of_creator_id"] = str(creator.id)
        meta["client_of_creator_slug"] = creator.creator_store_slug or clean_slug
        meta["client_of_brand"] = creator.creator_brand_name or creator.username
        current_user.extra_metadata = meta
        await db.commit()
        await db.refresh(current_user)

    return {
        "status": "attributed",
        "creator_slug": creator.creator_store_slug or clean_slug,
        "brand_name": creator.creator_brand_name or creator.username,
        "client_email": current_user.email
    }

