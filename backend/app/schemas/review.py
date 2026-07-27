"""
Review Pydantic schemas.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.user import UserPublicResponse

class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = None


class ReviewCreate(ReviewBase):
    template_id: uuid.UUID


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = None


class ReviewTemplateInfo(BaseModel):
    id: uuid.UUID
    title: str
    slug: str

    model_config = {"from_attributes": True}


class ReviewResponse(ReviewBase):
    id: uuid.UUID
    template_id: uuid.UUID
    user_id: uuid.UUID
    user: Optional[UserPublicResponse] = None
    template: Optional[ReviewTemplateInfo] = None
    is_verified_purchase: bool
    is_approved: bool
    helpful_count: int
    admin_reply: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
