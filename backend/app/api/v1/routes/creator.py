"""
API Router for Extreme Plan Creators: Onboarding questionnaire, multi-gateway payout setup,
and dedicated branded storefront on our domain (/creator/{slug}).
"""

import re
import uuid
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User, UserRole
from app.models.template import Template, TemplateStatus
from app.schemas.creator import (
    CreatorSetupRequest,
    CreatorProfileResponse,
    CreatorPublicStorefrontResponse,
    CreatorStats,
)
from app.schemas.template import TemplateResponse
from app.core.redis import cache_delete_pattern

router = APIRouter()

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


def _build_creator_profile_response(user: User) -> CreatorProfileResponse:
    slug = user.creator_store_slug or (user.username.lower() if user.username else None)
    storefront_url = f"/creator/{slug}" if slug else None
    payout_details = getattr(user, "creator_payout_details", None) or {}
    enabled_methods = payout_details.get("enabled_methods") or [user.payout_method or "stripe", "razorpay"]

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
        payout_account_number_masked=_mask_account(user.payout_account_number or payout_details.get("account_number")),
        payout_ifsc_code=user.payout_ifsc_code or payout_details.get("ifsc_code"),
        payout_swift_code=payout_details.get("swift_code"),
        payout_iban=payout_details.get("iban"),
        payout_account_holder_name=user.payout_account_holder_name or payout_details.get("account_holder_name"),
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
        creator_payout_details=payout_details,
        storefront_distribution=user.storefront_distribution or "both",
        is_creator_onboarding_completed=user.is_creator_onboarding_completed,
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

    # Payouts
    current_user.payout_method = payout
    if data.payout_stripe_email:
        current_user.payout_stripe_email = data.payout_stripe_email.strip()
    if data.payout_paypal_email:
        current_user.payout_paypal_email = data.payout_paypal_email.strip()
    if data.payout_razorpay_vpa:
        current_user.payout_razorpay_vpa = data.payout_razorpay_vpa.strip()

    if data.payout_bank_name:
        current_user.payout_bank_name = data.payout_bank_name.strip()
    if data.payout_account_number:
        current_user.payout_account_number = data.payout_account_number.strip()
    if data.payout_ifsc_code:
        current_user.payout_ifsc_code = data.payout_ifsc_code.strip()
    if data.payout_account_holder_name:
        current_user.payout_account_holder_name = data.payout_account_holder_name.strip()

    # Build comprehensive creator payout profile dictionary
    current_user.creator_payout_details = {
        "enabled_methods": enabled_methods,
        "primary_method": payout,
        "stripe_email": data.payout_stripe_email.strip() if data.payout_stripe_email else None,
        "stripe_account_id": data.payout_stripe_account_id.strip() if data.payout_stripe_account_id else None,
        "stripe_payment_link": data.payout_stripe_payment_link.strip() if data.payout_stripe_payment_link else None,
        "paypal_email": data.payout_paypal_email.strip() if data.payout_paypal_email else None,
        "paypal_me": data.payout_paypal_me.strip() if data.payout_paypal_me else None,
        "razorpay_vpa": data.payout_razorpay_vpa.strip() if data.payout_razorpay_vpa else None,
        "razorpay_account_id": data.payout_razorpay_account_id.strip() if data.payout_razorpay_account_id else None,
        "bank_name": data.payout_bank_name.strip() if data.payout_bank_name else None,
        "account_holder_name": data.payout_account_holder_name.strip() if data.payout_account_holder_name else None,
        "ifsc_code": data.payout_ifsc_code.strip() if data.payout_ifsc_code else None,
        "swift_code": data.payout_swift_code.strip() if data.payout_swift_code else None,
        "iban": data.payout_iban.strip() if data.payout_iban else None,
        "upi_id": data.payout_upi_id.strip() if data.payout_upi_id else (data.payout_razorpay_vpa.strip() if data.payout_razorpay_vpa else None),
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
    }

    current_user.storefront_distribution = dist
    current_user.is_creator_onboarding_completed = True
    current_user.is_payout_setup_completed = True
    current_user.updated_at = datetime.now(timezone.utc)

    # If user was role USER/BUYER, elevate to SELLER
    if current_user.role in (UserRole.USER, UserRole.BUYER):
        current_user.role = UserRole.SELLER

    await db.commit()
    await db.refresh(current_user)

    # Invalidate cached template queries if any
    await cache_delete_pattern("templates:*")

    return _build_creator_profile_response(current_user)


@router.get("/storefront/{slug}", response_model=CreatorPublicStorefrontResponse)
async def get_public_creator_storefront(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public Endpoint: Get dedicated creator storefront data on our domain (/creator/{slug}).
    Returns creator branding, bio, stats, and all their published templates.
    """
    clean_slug = slug.strip().lower()

    # Find creator by store slug or username
    creator = await db.scalar(
        select(User).where(
            (User.creator_store_slug == clean_slug) |
            ((User.creator_store_slug.is_(None)) & (func.lower(User.username) == clean_slug))
        )
    )

    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator storefront '{clean_slug}' not found on this domain.",
        )

    # Fetch this creator's published templates
    # Exclude user customized preview copies or private drafts
    stmt = (
        select(Template)
        .options(selectinload(Template.category))
        .where(
            Template.seller_id == creator.id,
            Template.status.in_([TemplateStatus.PUBLISHED, TemplateStatus.APPROVED]),
            Template.slug.notlike("%-custom-%"),
            Template.title.notlike("%(Customized)%"),
            Template.title.notlike("Customized %"),
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
    accepted_methods = payout_details.get("enabled_methods") or [creator.payout_method or "stripe", "razorpay"]

    public_payment_options = {
        "primary": creator.payout_method or "stripe",
        "accepted_methods": accepted_methods,
        "stripe": {
            "enabled": "stripe" in accepted_methods,
            "payment_link": payout_details.get("stripe_payment_link"),
            "email": creator.payout_stripe_email or payout_details.get("stripe_email"),
        },
        "razorpay": {
            "enabled": "razorpay" in accepted_methods,
            "vpa": creator.payout_razorpay_vpa or payout_details.get("razorpay_vpa"),
        },
        "paypal": {
            "enabled": "paypal" in accepted_methods,
            "email": creator.payout_paypal_email or payout_details.get("paypal_email"),
            "paypal_me": payout_details.get("paypal_me"),
        },
        "upi": {
            "enabled": "upi" in accepted_methods,
            "vpa": payout_details.get("upi_id") or creator.payout_razorpay_vpa,
        },
        "crypto": {
            "enabled": "crypto" in accepted_methods,
            "currency": payout_details.get("crypto_currency", "USDT"),
            "network": payout_details.get("crypto_network", "TRC20"),
            "address": payout_details.get("crypto_address"),
        },
        "bank_transfer": {
            "enabled": "bank" in accepted_methods or "bank_transfer" in accepted_methods,
            "bank_name": creator.payout_bank_name or payout_details.get("bank_name"),
            "account_holder_name": creator.payout_account_holder_name or payout_details.get("account_holder_name"),
            "ifsc_code": creator.payout_ifsc_code or payout_details.get("ifsc_code"),
            "swift_code": payout_details.get("swift_code"),
            "iban": payout_details.get("iban"),
        },
        "wise": {
            "enabled": "wise" in accepted_methods,
            "email": payout_details.get("wise_email"),
        },
        "revolut": {
            "enabled": "revolut" in accepted_methods,
            "tag": payout_details.get("revolut_tag"),
        },
        "cashapp": {
            "enabled": "cashapp" in accepted_methods,
            "tag": payout_details.get("cashapp_tag"),
        },
        "venmo": {
            "enabled": "venmo" in accepted_methods,
            "tag": payout_details.get("venmo_tag"),
        },
        "flutterwave": {
            "enabled": "flutterwave" in accepted_methods,
            "id": payout_details.get("flutterwave_id"),
        },
        "paystack": {
            "enabled": "paystack" in accepted_methods,
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
        accepted_payment_methods=accepted_methods,
        payment_options=public_payment_options,
        stats=CreatorStats(
            total_templates=total_templates,
            total_sales=total_sales,
            average_rating=avg_rating,
            reviews_count=total_reviews,
        ),
        templates=template_responses,
    )
