"""
Unit tests for Creator Onboarding, Payout Gateway Setup, and Dedicated Storefront routes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus


@pytest.mark.asyncio
async def test_check_slug_availability(client: AsyncClient):
    # Test valid slug
    res = await client.get("/api/v1/creator/check-slug?slug=apex-studios")
    assert res.status_code == 200
    assert res.json()["available"] is True

    # Test reserved keyword
    res_reserved = await client.get("/api/v1/creator/check-slug?slug=admin")
    assert res_reserved.status_code == 200
    assert res_reserved.json()["available"] is False
    assert "reserved" in res_reserved.json()["reason"]

    # Test invalid slug format
    res_invalid = await client.get("/api/v1/creator/check-slug?slug=-bad-slug-")
    assert res_invalid.status_code == 200
    assert res_invalid.json()["available"] is False


@pytest.mark.asyncio
async def test_creator_profile_free_user_forbidden(auth_client: AsyncClient):
    # Regular free/buyer user tries to save creator profile
    payload = {
        "brand_name": "Freebie Studio",
        "creator_name": "Freebie User",
        "store_slug": "freebie-studio",
        "tagline": "We make cheap sites",
        "payout_method": "stripe",
        "storefront_distribution": "both",
    }
    res = await auth_client.put("/api/v1/creator/profile", json=payload)
    assert res.status_code == 403
    assert "Extreme Plan" in res.json()["detail"]


@pytest.mark.asyncio
async def test_creator_profile_extreme_user_success(admin_client: AsyncClient, db: AsyncSession):
    # Admin / Extreme user setup
    payload = {
        "brand_name": "Apex Digital Labs",
        "creator_name": "Alex Apex",
        "store_slug": "apex-digital",
        "tagline": "Next-gen sleek templates",
        "bio": "Award winning digital boutique creating high-conversion themes.",
        "support_email": "hello@apexdigital.io",
        "website": "https://apexdigital.io",
        "logo_url": "https://images.unsplash.com/photo-logo.png",
        "banner_url": "https://images.unsplash.com/photo-banner.png",
        "social_links": {
            "twitter": "https://x.com/apexdigital",
            "github": "https://github.com/apexdigital"
        },
        "payout_method": "razorpay",
        "payout_razorpay_vpa": "apex@okhdfcbank",
        "storefront_distribution": "both"
    }

    res = await admin_client.put("/api/v1/creator/profile", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["creator_brand_name"] == "Apex Digital Labs"
    assert data["creator_store_slug"] == "apex-digital"
    assert data["payout_method"] == "razorpay"
    assert data["payout_razorpay_vpa"] == "apex@okhdfcbank"
    assert data["storefront_distribution"] == "both"
    assert data["is_creator_onboarding_completed"] is True
    assert data["storefront_url"] == "/creator/apex-digital"

    # Fetch public storefront
    storefront_res = await admin_client.get("/api/v1/creator/storefront/apex-digital")
    assert storefront_res.status_code == 200
    sf_data = storefront_res.json()
    assert sf_data["brand_name"] == "Apex Digital Labs"
    assert sf_data["store_slug"] == "apex-digital"
    assert sf_data["tagline"] == "Next-gen sleek templates"
    assert sf_data["website"] == "https://apexdigital.io"
    assert sf_data["stats"]["total_templates"] >= 0


@pytest.mark.asyncio
async def test_creator_multi_gateway_payment_methods(admin_client: AsyncClient, db: AsyncSession):
    # Setup creator with comprehensive multi-gateway payment methods
    payload = {
        "brand_name": "MultiPay Studio",
        "creator_name": "Jordan Dev",
        "store_slug": "multipay-studio",
        "tagline": "Accepts everything",
        "payout_method": "stripe",
        "enabled_payment_methods": ["stripe", "razorpay", "paypal", "upi", "crypto", "bank"],
        "payout_stripe_payment_link": "https://buy.stripe.com/test_12345",
        "payout_paypal_me": "https://paypal.me/multipaystudio",
        "payout_razorpay_vpa": "multipay@razor",
        "payout_upi_id": "multipay@okhdfcbank",
        "payout_crypto_currency": "USDT",
        "payout_crypto_network": "TRC20",
        "payout_crypto_address": "TL1xYTestAddressTRC20MultiPayStudio",
        "payout_bank_name": "Silicon Valley Bank",
        "payout_account_holder_name": "Jordan Dev LLC",
        "payout_ifsc_code": "SVB0001234",
        "payout_swift_code": "SVBUS33XXX",
        "payout_iban": "US12SVB00012345678901",
        "payout_custom_instructions": "Contact for enterprise licenses",
        "storefront_distribution": "both"
    }

    res = await admin_client.put("/api/v1/creator/profile", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "stripe" in data["enabled_payment_methods"]
    assert "crypto" in data["enabled_payment_methods"]

    # Verify public storefront delivers accepted methods and sanitized payment options
    sf_res = await admin_client.get("/api/v1/creator/storefront/multipay-studio")
    assert sf_res.status_code == 200
    sf_data = sf_res.json()
    assert "stripe" in sf_data["accepted_payment_methods"]
    assert "paypal" in sf_data["accepted_payment_methods"]
    assert "crypto" in sf_data["accepted_payment_methods"]
    assert "upi" in sf_data["accepted_payment_methods"]

    opts = sf_data["payment_options"]
    assert opts["stripe"]["payment_link"] == "https://buy.stripe.com/test_12345"
    assert opts["paypal"]["paypal_me"] == "https://paypal.me/multipaystudio"
    assert opts["upi"]["vpa"] == "multipay@okhdfcbank"
    assert opts["crypto"]["address"] == "TL1xYTestAddressTRC20MultiPayStudio"
    assert opts["crypto"]["network"] == "TRC20"
    assert opts["bank_transfer"]["bank_name"] == "Silicon Valley Bank"
    assert opts["bank_transfer"]["swift_code"] == "SVBUS33XXX"
    assert opts["custom_instructions"] == "Contact for enterprise licenses"
