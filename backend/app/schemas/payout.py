from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict, Any
from app.models.withdrawal_request import WithdrawalStatus


class SaleItemResponse(BaseModel):
    order_id: UUID
    template_id: UUID
    template_title: str
    price: Decimal
    purchaser_email: str
    date: datetime
    order_number: str
    license_type: str
    upi_utr: Optional[str] = None
    gross_amount: Optional[Decimal] = None
    platform_fee: Optional[Decimal] = None
    net_creator_earning: Optional[Decimal] = None
    holding_until: Optional[datetime] = None
    is_available: Optional[bool] = None

    model_config = {"from_attributes": True}


class EarningsSummaryResponse(BaseModel):
    total_earned: Decimal
    withdrawn_amount: Decimal
    pending_withdrawal: Decimal
    available_balance: Decimal
    sales: List[SaleItemResponse]
    gross_sales: Optional[Decimal] = None
    platform_commission: Optional[Decimal] = None
    net_earnings: Optional[Decimal] = None
    pending_earnings: Optional[Decimal] = None
    commission_rate: Optional[Decimal] = None
    holding_days: Optional[int] = None
    published_templates_count: Optional[int] = None
    pending_templates_count: Optional[int] = None
    total_views: Optional[int] = None
    total_purchases: Optional[int] = None
    recent_orders: Optional[List[Dict[str, Any]]] = None
    best_performing_templates: Optional[List[Dict[str, Any]]] = None
    sales_chart: Optional[List[Dict[str, Any]]] = None


class WithdrawalCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    account_holder_name: Optional[str] = None


class WithdrawalResponse(BaseModel):
    id: UUID
    seller_id: UUID
    amount: Decimal
    status: WithdrawalStatus
    bank_name: Optional[str]
    account_number: Optional[str]
    ifsc_code: Optional[str]
    account_holder_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WithdrawalStatusUpdateRequest(BaseModel):
    status: WithdrawalStatus


class MarketplaceSettingsResponse(BaseModel):
    platform_commission_percent: Decimal
    payout_holding_days: int
    min_payout_amount: Decimal
    is_marketplace_active: bool
    updated_at: Optional[datetime] = None


class MarketplaceSettingsUpdate(BaseModel):
    platform_commission_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    payout_holding_days: Optional[int] = Field(None, ge=0, le=90)
    min_payout_amount: Optional[Decimal] = Field(None, ge=1)
    is_marketplace_active: Optional[bool] = None
