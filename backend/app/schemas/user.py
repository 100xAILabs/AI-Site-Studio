"""
Pydantic schemas for User entity.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr, Field, field_validator
import re
from app.core.config import settings

from app.models.user import UserRole


class UserBase(BaseModel):
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

    @field_validator("avatar_url", mode="before")
    @classmethod
    def normalize_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        base = settings.RESOLVED_STORAGE_BASE_URL
        return re.sub(r"^https?://(localhost|127\.0\.0\.1):8000/api/v1/files", base, str(v))


class UserCreate(UserBase):
    email: EmailStr
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    subscription_tier: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    currency: Optional[str] = None


class UserAdminUpdate(UserUpdate):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    ai_credits: Optional[int] = None


class PayoutSetupRequest(BaseModel):
    payout_bank_name: str = Field(..., min_length=2, max_length=255)
    payout_account_number: str = Field(..., pattern=r"^[0-9A-Za-z]{5,34}$")
    payout_ifsc_code: str = Field(..., min_length=4, max_length=50)
    payout_account_holder_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("payout_account_number")
    @classmethod
    def validate_not_masked(cls, v: str) -> str:
        if "*" in v or "•" in v:
            raise ValueError("Masked account numbers cannot be submitted. Please provide the real account number.")
        return v


class UserResponse(UserBase):
    id: uuid.UUID
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None
    github_id: Optional[str] = None
    has_github_token: bool = False
    role: UserRole
    is_active: bool
    is_email_verified: bool
    ai_credits: int
    created_at: datetime
    updated_at: datetime
    payout_bank_name: Optional[str] = None
    payout_account_number: Optional[str] = None
    payout_ifsc_code: Optional[str] = None
    payout_account_holder_name: Optional[str] = None
    is_payout_setup_completed: bool = False
    subscription_tier: Optional[str] = "free"
    is_pro_subscriber: bool = False
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
    payout_stripe_email: Optional[str] = None
    payout_paypal_email: Optional[str] = None
    payout_razorpay_vpa: Optional[str] = None
    storefront_distribution: Optional[str] = "both"
    is_creator_onboarding_completed: bool = False
    country: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    currency: Optional[str] = None

    @field_validator("payout_account_number", mode="before")
    @classmethod
    def mask_account_number(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        clean = str(v).strip()
        if len(clean) <= 4:
            return "****"
        return f"****{clean[-4:]}"

    model_config = {"from_attributes": True}


class AdminUserResponse(UserResponse):
    """Admin view of user profile: strictly suppresses bank account holder names for privacy."""
    payout_account_holder_name: Optional[str] = Field(None, exclude=True)


class UserPublicResponse(BaseModel):
    """Public user profile (limited fields)."""
    id: uuid.UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator("avatar_url", mode="before")
    @classmethod
    def normalize_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        base = settings.RESOLVED_STORAGE_BASE_URL
        return re.sub(r"^https?://(localhost|127\.0\.0\.1):8000/api/v1/files", base, str(v))

    model_config = {"from_attributes": True}
