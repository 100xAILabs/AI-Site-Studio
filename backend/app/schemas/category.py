"""
Pydantic schemas for Category entity.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    is_featured: bool = False
    parent_id: Optional[uuid.UUID] = None


class CategoryCreate(CategoryBase):
    slug: str


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    image_url: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    parent_id: Optional[uuid.UUID] = None


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    slug: str
    created_at: datetime
    updated_at: datetime
    children: List["CategoryResponse"] = []
    # Computed
    template_count: Optional[int] = None

    model_config = {"from_attributes": True}


# Needed for self-referencing
CategoryResponse.model_rebuild()
