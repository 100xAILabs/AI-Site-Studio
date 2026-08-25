from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import List, Optional
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

    model_config = {"from_attributes": True}


class EarningsSummaryResponse(BaseModel):
    total_earned: Decimal
    withdrawn_amount: Decimal
    pending_withdrawal: Decimal
    available_balance: Decimal
    sales: List[SaleItemResponse]


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
