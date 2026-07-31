"""
Payouts and withdrawals routes.
"""

import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_seller_or_admin, require_admin
from app.models.user import User, UserRole
from app.models.order import Order, OrderItem, OrderStatus
from app.models.template import Template
from app.models.withdrawal_request import WithdrawalRequest, WithdrawalStatus
from app.schemas.payout import (
    EarningsSummaryResponse,
    SaleItemResponse,
    WithdrawalCreateRequest,
    WithdrawalResponse,
    WithdrawalStatusUpdateRequest,
)

router = APIRouter()


async def calculate_seller_earnings(db: AsyncSession, seller_id: uuid.UUID) -> dict:
    """Helper function to calculate seller's total earnings, withdrawn, pending and available balance."""
    # 1. Total Earned from completed orders
    stmt = (
        select(
            func.coalesce(func.sum(OrderItem.price), Decimal("0.00")).label("total")
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Template, OrderItem.template_id == Template.id)
        .where(
            and_(
                Order.status == OrderStatus.COMPLETED,
                Template.seller_id == seller_id
            )
        )
    )
    res = await db.execute(stmt)
    total_earned = res.scalar_one()

    # 2. Withdrawn/Paid requests
    stmt_paid = (
        select(
            func.coalesce(func.sum(WithdrawalRequest.amount), Decimal("0.00")).label("total")
        )
        .where(
            and_(
                WithdrawalRequest.seller_id == seller_id,
                WithdrawalRequest.status.in_([WithdrawalStatus.APPROVED, WithdrawalStatus.PAID])
            )
        )
    )
    res_paid = await db.execute(stmt_paid)
    withdrawn_amount = res_paid.scalar_one()

    # 3. Pending requests
    stmt_pending = (
        select(
            func.coalesce(func.sum(WithdrawalRequest.amount), Decimal("0.00")).label("total")
        )
        .where(
            and_(
                WithdrawalRequest.seller_id == seller_id,
                WithdrawalRequest.status == WithdrawalStatus.PENDING
            )
        )
    )
    res_pending = await db.execute(stmt_pending)
    pending_withdrawal = res_pending.scalar_one()

    # 4. Available Balance
    available_balance = total_earned - withdrawn_amount - pending_withdrawal
    if available_balance < Decimal("0.00"):
        available_balance = Decimal("0.00")

    return {
        "total_earned": total_earned,
        "withdrawn_amount": withdrawn_amount,
        "pending_withdrawal": pending_withdrawal,
        "available_balance": available_balance
    }


@router.get("/earnings", response_model=EarningsSummaryResponse)
async def get_seller_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Get detailed earnings ledger and summary stats for the current seller.
    """
    summary = await calculate_seller_earnings(db, current_user.id)

    # Fetch individual sales
    sales_stmt = (
        select(
            Order.id.label("order_id"),
            OrderItem.price,
            OrderItem.license_type,
            OrderItem.template_id,
            Template.title.label("template_title"),
            Order.order_number,
            Order.created_at.label("date"),
            User.email.label("purchaser_email")
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(Template, OrderItem.template_id == Template.id)
        .join(User, Order.user_id == User.id)
        .where(
            and_(
                Order.status == OrderStatus.COMPLETED,
                Template.seller_id == current_user.id
            )
        )
        .order_by(Order.created_at.desc())
    )
    sales_res = await db.execute(sales_stmt)
    sales_rows = sales_res.all()

    sales = [
        SaleItemResponse(
            order_id=row.order_id,
            template_id=row.template_id,
            template_title=row.template_title,
            price=row.price,
            purchaser_email=row.purchaser_email,
            date=row.date,
            order_number=row.order_number,
            license_type=row.license_type
        )
        for row in sales_rows
    ]

    return EarningsSummaryResponse(
        total_earned=summary["total_earned"],
        withdrawn_amount=summary["withdrawn_amount"],
        pending_withdrawal=summary["pending_withdrawal"],
        available_balance=summary["available_balance"],
        sales=sales
    )


@router.post("/withdrawals", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
async def create_withdrawal_request(
    data: WithdrawalCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Submit a request to withdraw a portion or all of the seller's available balance.
    """
    summary = await calculate_seller_earnings(db, current_user.id)
    available = summary["available_balance"]

    if data.amount > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. You only have ${available:.2f} available to withdraw."
        )

    # Use specified details or fallback to user settings
    bank_name = data.bank_name or current_user.payout_bank_name
    account_number = data.account_number or current_user.payout_account_number
    ifsc_code = data.ifsc_code or current_user.payout_ifsc_code
    account_holder_name = data.account_holder_name or current_user.payout_account_holder_name

    if not bank_name or not account_number or not ifsc_code or not account_holder_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account details are incomplete. Please provide them or save them in your profile settings."
        )

    request = WithdrawalRequest(
        seller_id=current_user.id,
        amount=data.amount,
        status=WithdrawalStatus.PENDING,
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        account_holder_name=account_holder_name,
    )
    db.add(request)
    await db.flush()
    await db.commit()
    await db.refresh(request)

    return request


@router.get("/withdrawals", response_model=List[WithdrawalResponse])
async def list_seller_withdrawals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    List all withdrawal requests submitted by the current seller.
    """
    stmt = (
        select(WithdrawalRequest)
        .where(WithdrawalRequest.seller_id == current_user.id)
        .order_by(WithdrawalRequest.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def get_withdrawal_request(
    withdrawal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Get details of a specific withdrawal request.
    """
    stmt = select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id)
    res = await db.execute(stmt)
    request = res.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    if request.seller_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    return request


@router.get("/withdrawals/{withdrawal_id}/receipt")
async def get_withdrawal_receipt(
    withdrawal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Fetch a custom payout receipt for the withdrawal request.
    """
    stmt = select(WithdrawalRequest).options(selectinload(WithdrawalRequest.seller)).where(WithdrawalRequest.id == withdrawal_id)
    res = await db.execute(stmt)
    request = res.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    if request.seller_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "receipt_number": f"PAY-{request.id.hex[:8].upper()}",
        "date": request.created_at,
        "payout_date": request.updated_at if request.status == WithdrawalStatus.PAID else None,
        "amount": request.amount,
        "status": request.status,
        "seller_name": request.seller.full_name or request.seller.username or "Site Studio Creator",
        "seller_email": request.seller.email,
        "bank_name": request.bank_name,
        "account_number": f"****{request.account_number[-4:]}" if request.account_number else "N/A",
        "ifsc_code": request.ifsc_code,
        "account_holder_name": request.account_holder_name,
    }


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/withdrawals", response_model=List[WithdrawalResponse])
async def list_all_withdrawals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    [Admin] List all withdrawal requests submitted on the platform.
    """
    stmt = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.patch("/admin/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def update_withdrawal_status(
    withdrawal_id: uuid.UUID,
    data: WithdrawalStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    [Admin] Approve, reject, or mark a withdrawal request as completed/paid.
    """
    stmt = select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id)
    res = await db.execute(stmt)
    request = res.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    request.status = data.status
    await db.flush()
    await db.commit()
    await db.refresh(request)

    return request
