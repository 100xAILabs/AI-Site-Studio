"""
Pydantic schemas for Creator Onboarding, Multi-Gateway Payouts, and Dedicated Storefront.
"""

import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr
from app.schemas.template import TemplateResponse


class CreatorSetupRequest(BaseModel):
    """Payload submitted when Extreme user sets up their brand, store slug, payouts & distribution."""
    brand_name: str = Field(..., min_length=2, max_length=100, description="Studio or Brand name")
    creator_name: Optional[str] = Field(None, max_length=100, description="Display or Legal creator name")
    store_slug: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$",
        description="URL slug on our domain: aisitestudio.com/creator/{slug}",
    )
    tagline: Optional[str] = Field(None, max_length=255, description="Short brand motto or tagline")
    bio: Optional[str] = Field(None, max_length=2000, description="Creator story, background or details")
    support_email: Optional[str] = Field(None, max_length=255, description="Customer contact email")
    website: Optional[str] = Field(None, max_length=500, description="Official portfolio or company URL")
    logo_url: Optional[str] = Field(None, max_length=500, description="Brand logo image URL")
    banner_url: Optional[str] = Field(None, max_length=500, description="Storefront hero banner image URL")
    social_links: Optional[Dict[str, str]] = Field(default_factory=dict, description="Social handles: twitter, github, linkedin, etc.")

    # Payment Gateway section (Stripe, Razorpay, PayPal, Bank, UPI, Crypto, Wise, Revolut, etc.)
    payout_method: str = Field("stripe", description="Primary payout preference: stripe, razorpay, paypal, bank, upi, crypto, etc.")
    enabled_payment_methods: Optional[List[str]] = Field(
        default_factory=lambda: ["stripe", "razorpay"],
        description="List of all payment methods the creator accepts (e.g. stripe, razorpay, paypal, bank, upi, crypto, wise, revolut, cashapp, paystack, flutterwave, mercadopago)"
    )
    
    # Gateway-specific fields
    payout_stripe_email: Optional[str] = Field(None, max_length=255)
    payout_stripe_account_id: Optional[str] = Field(None, max_length=255)
    payout_stripe_payment_link: Optional[str] = Field(None, max_length=500)

    payout_razorpay_vpa: Optional[str] = Field(None, max_length=255)
    payout_razorpay_account_id: Optional[str] = Field(None, max_length=255)

    payout_paypal_email: Optional[str] = Field(None, max_length=255)
    payout_paypal_me: Optional[str] = Field(None, max_length=255)

    payout_bank_name: Optional[str] = Field(None, max_length=255)
    payout_account_number: Optional[str] = Field(None, max_length=100)
    payout_ifsc_code: Optional[str] = Field(None, max_length=50)
    payout_swift_code: Optional[str] = Field(None, max_length=50)
    payout_iban: Optional[str] = Field(None, max_length=100)
    payout_account_holder_name: Optional[str] = Field(None, max_length=255)

    payout_upi_id: Optional[str] = Field(None, max_length=255)
    payout_crypto_currency: Optional[str] = Field(None, max_length=50) # USDT, BTC, ETH, SOL
    payout_crypto_network: Optional[str] = Field(None, max_length=50)  # TRC20, ERC20, Polygon, Solana, Native
    payout_crypto_address: Optional[str] = Field(None, max_length=255)

    payout_wise_email: Optional[str] = Field(None, max_length=255)
    payout_revolut_tag: Optional[str] = Field(None, max_length=100)
    payout_cashapp_tag: Optional[str] = Field(None, max_length=100)
    payout_venmo_tag: Optional[str] = Field(None, max_length=100)
    payout_flutterwave_id: Optional[str] = Field(None, max_length=255)
    payout_paystack_code: Optional[str] = Field(None, max_length=255)
    payout_mercadopago_email: Optional[str] = Field(None, max_length=255)
    payout_custom_instructions: Optional[str] = Field(None, max_length=2000)

    # Storefront distribution choice
    # "marketplace": Global Site Studio marketplace
    # "storefront": Dedicated storefront on our domain (/creator/{slug})
    # "both": Dual distribution (both global marketplace + dedicated storefront)
    storefront_distribution: str = Field("both", description="Distribution mode: marketplace, storefront, or both")


class CreatorProfileResponse(BaseModel):
    """Full creator configuration returned to the logged-in creator."""
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    is_extreme_subscriber: bool = False
    can_retail_templates: bool = False
    creator_brand_name: Optional[str] = None
    creator_store_slug: Optional[str] = None
    creator_logo_url: Optional[str] = None
    creator_banner_url: Optional[str] = None
    creator_tagline: Optional[str] = None
    creator_bio: Optional[str] = None
    creator_support_email: Optional[str] = None
    creator_website: Optional[str] = None
    creator_social_links: Optional[Dict[str, Any]] = None
    payout_method: Optional[str] = "stripe"
    enabled_payment_methods: Optional[List[str]] = Field(default_factory=lambda: ["stripe", "razorpay"])
    payout_stripe_email: Optional[str] = None
    payout_stripe_account_id: Optional[str] = None
    payout_stripe_payment_link: Optional[str] = None
    payout_paypal_email: Optional[str] = None
    payout_paypal_me: Optional[str] = None
    payout_razorpay_vpa: Optional[str] = None
    payout_razorpay_account_id: Optional[str] = None
    payout_bank_name: Optional[str] = None
    payout_account_number_masked: Optional[str] = None
    payout_ifsc_code: Optional[str] = None
    payout_swift_code: Optional[str] = None
    payout_iban: Optional[str] = None
    payout_account_holder_name: Optional[str] = None
    payout_upi_id: Optional[str] = None
    payout_crypto_currency: Optional[str] = None
    payout_crypto_network: Optional[str] = None
    payout_crypto_address: Optional[str] = None
    payout_wise_email: Optional[str] = None
    payout_revolut_tag: Optional[str] = None
    payout_cashapp_tag: Optional[str] = None
    payout_venmo_tag: Optional[str] = None
    payout_flutterwave_id: Optional[str] = None
    payout_paystack_code: Optional[str] = None
    payout_mercadopago_email: Optional[str] = None
    payout_custom_instructions: Optional[str] = None
    creator_payout_details: Optional[Dict[str, Any]] = None
    storefront_distribution: Optional[str] = "both"
    is_creator_onboarding_completed: bool = False
    is_payout_setup_completed: bool = False
    storefront_url: Optional[str] = None

    model_config = {"from_attributes": True}


class CreatorStats(BaseModel):
    total_templates: int = 0
    total_sales: int = 0
    average_rating: float = 5.0
    reviews_count: int = 0


class CreatorPublicStorefrontResponse(BaseModel):
    """Public data for a creator's dedicated storefront on our domain (/creator/{slug})."""
    creator_id: Optional[str] = None
    brand_name: str
    creator_name: Optional[str] = None
    store_slug: str
    tagline: Optional[str] = None
    bio: Optional[str] = None
    support_email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    social_links: Optional[Dict[str, Any]] = None
    is_verified: bool = True
    is_bank_connected: bool = True
    payout_status_message: Optional[str] = None
    accepted_payment_methods: List[str] = []
    payment_options: Optional[Dict[str, Any]] = None
    stats: CreatorStats
    templates: List[TemplateResponse] = []
