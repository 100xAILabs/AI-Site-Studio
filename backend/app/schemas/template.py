"""
Pydantic schemas for Template entity.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from app.models.template import TemplateFramework, TemplateLicense, TemplateStatus
from app.schemas.category import CategoryResponse


class TemplateBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    short_description: str = Field(..., max_length=500)
    description: str
    price: Decimal = Field(..., ge=0)
    original_price: Optional[Decimal] = None
    is_free: bool = False
    is_on_sale: bool = False
    thumbnail_url: str
    preview_url: Optional[str] = None
    video_url: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    category_id: uuid.UUID
    tags: Optional[List[str]] = None
    industry: Optional[str] = None
    color_scheme: Optional[str] = None
    framework: Optional[TemplateFramework] = None
    pages_count: int = Field(1, ge=1)
    has_dark_mode: bool = False
    is_responsive: bool = True
    is_rtl_supported: bool = False
    is_ai_ready: bool = False
    compatibility: Optional[List[str]] = None
    version: str = "1.0.0"
    license_type: TemplateLicense = TemplateLicense.REGULAR
    is_featured: bool = False
    is_bestseller: bool = False
    developer_name: Optional[str] = None
    developer_avatar: Optional[str] = None
    included_pages: Optional[List[str]] = None
    seo_keywords: Optional[List[str]] = None


class TemplateCreate(TemplateBase):
    slug: str
    status: TemplateStatus = TemplateStatus.DRAFT
    download_assets: Optional[Dict[str, str]] = None
    changelog: Optional[Dict[str, Any]] = None


class TemplateUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    slug: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    original_price: Optional[Decimal] = None
    is_free: Optional[bool] = None
    is_on_sale: Optional[bool] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    video_url: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    category_id: Optional[uuid.UUID] = None
    tags: Optional[List[str]] = None
    industry: Optional[str] = None
    color_scheme: Optional[str] = None
    framework: Optional[TemplateFramework] = None
    pages_count: Optional[int] = None
    has_dark_mode: Optional[bool] = None
    is_responsive: Optional[bool] = None
    is_rtl_supported: Optional[bool] = None
    is_ai_ready: Optional[bool] = None
    compatibility: Optional[List[str]] = None
    version: Optional[str] = None
    license_type: Optional[TemplateLicense] = None
    status: Optional[TemplateStatus] = None
    is_featured: Optional[bool] = None
    is_bestseller: Optional[bool] = None
    developer_name: Optional[str] = None
    developer_avatar: Optional[str] = None
    download_assets: Optional[Dict[str, str]] = None
    changelog: Optional[Dict[str, Any]] = None
    included_pages: Optional[List[str]] = None
    seo_keywords: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    description: str
    price: Decimal
    original_price: Optional[Decimal] = None
    is_free: bool
    is_on_sale: bool
    thumbnail_url: str
    preview_url: Optional[str] = None
    video_url: Optional[str] = None
    gallery_images: Optional[List[str]] = None
    category_id: uuid.UUID
    category: Optional[CategoryResponse] = None
    tags: Optional[List[str]] = None
    industry: Optional[str] = None
    color_scheme: Optional[str] = None
    framework: Optional[TemplateFramework] = None
    pages_count: int
    has_dark_mode: bool
    is_responsive: bool
    is_rtl_supported: bool
    is_ai_ready: bool
    compatibility: Optional[List[str]] = None
    version: str
    license_type: TemplateLicense
    status: TemplateStatus
    is_featured: bool
    is_bestseller: bool
    is_new: bool
    downloads_count: int
    views_count: int
    likes_count: int
    rating_avg: float
    rating_count: int
    developer_name: Optional[str] = None
    developer_avatar: Optional[str] = None
    included_pages: Optional[List[str]] = None
    changelog: Optional[Dict[str, Any]] = None
    download_assets: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: datetime

    # User-specific (populated when authenticated)
    is_favorited: Optional[bool] = None
    is_wishlisted: Optional[bool] = None
    is_purchased: Optional[bool] = None

    # Seller / Ownership
    seller_id: Optional[uuid.UUID] = None
    seller_templates_count: Optional[int] = 0
    seller_total_sales: Optional[int] = 0

    model_config = {"from_attributes": True}


class TemplateCardResponse(BaseModel):
    """Lightweight response for marketplace card display."""
    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    price: Decimal
    original_price: Optional[Decimal] = None
    is_free: bool
    is_on_sale: bool
    thumbnail_url: str
    video_url: Optional[str] = None
    category_id: uuid.UUID
    tags: Optional[List[str]] = None
    framework: Optional[TemplateFramework] = None
    pages_count: int
    has_dark_mode: bool
    is_featured: bool
    is_bestseller: bool
    is_new: bool
    downloads_count: int
    rating_avg: float
    rating_count: int
    developer_name: Optional[str] = None
    is_favorited: Optional[bool] = None
    is_wishlisted: Optional[bool] = None

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """Paginated template list response."""
    items: List[TemplateCardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TemplateFilterParams(BaseModel):
    """Query parameters for marketplace filtering."""
    category: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    rating: Optional[float] = None
    is_free: Optional[bool] = None
    is_on_sale: Optional[bool] = None
    framework: Optional[TemplateFramework] = None
    has_dark_mode: Optional[bool] = None
    is_ai_ready: Optional[bool] = None
    industry: Optional[str] = None
    color_scheme: Optional[str] = None
    tags: Optional[List[str]] = None
    license_type: Optional[TemplateLicense] = None
    is_featured: Optional[bool] = None
    sales: Optional[str] = None
    compatibility: Optional[str] = None
    language: Optional[str] = None
    date_added: Optional[str] = None
    sort: str = "newest"  # newest | best_sellers | best_rated | trending | lowest_price | highest_price | most_downloaded
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    q: Optional[str] = None  # text search query
    semantic: Optional[bool] = False
    developer: Optional[str] = None

