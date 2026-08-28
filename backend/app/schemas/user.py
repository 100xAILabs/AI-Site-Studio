"""
Pydantic schemas for User entity.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    email: EmailStr
    google_id: Optional[str] = None
    facebook_id: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
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
    payout_account_number: str = Field(..., min_length=5, max_length=100)
    payout_ifsc_code: str = Field(..., min_length=4, max_length=50)
    payout_account_holder_name: str = Field(..., min_length=2, max_length=255)


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
    country: Optional[str] = None
    country_code: Optional[str] = None
    city: Optional[str] = None
    currency: Optional[str] = None
    detected_ip: Optional[str] = None

    model_config = {"from_attributes": True}


class UserPublicResponse(BaseModel):
    """Public user profile (limited fields)."""
    id: uuid.UUID
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}
