"""
Payouts and withdrawals routes.
"""

import asyncio
import uuid
import logging
from datetime import datetime, timedelta, timezone
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
from app.models.payment import Payment, PaymentStatus
from app.models.template import Template, TemplateStatus
from app.models.marketplace import MarketplaceSetting, CreatorEarning, EarningStatus
from app.models.withdrawal_request import WithdrawalRequest, WithdrawalStatus
from app.schemas.payout import (
    EarningsSummaryResponse,
    SaleItemResponse,
    WithdrawalCreateRequest,
    WithdrawalResponse,
    AdminWithdrawalResponse,
    WithdrawalStatusUpdateRequest,
    MarketplaceSettingsResponse,
    MarketplaceSettingsUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


async def calculate_seller_earnings(db: AsyncSession, seller_id: uuid.UUID) -> dict:
    """
    Calculates seller's real financial metrics:
    - Gross sales
    - Configured platform commission rate & total platform fee (default 20%)
    - Net creator earnings (default 80%)
    - Pending earnings (sales within the dispute/refund holding period, e.g. 7 days)
    - Available earnings (sales that have cleared the holding period)
    - Withdrawn/paid amount
    - Pending withdrawals
    - Net withdrawable available balance
    """
    now_utc = datetime.now(timezone.utc)

    # 1. Fetch platform settings
    setting_res = await db.execute(select(MarketplaceSetting).where(MarketplaceSetting.id == "default"))
    m_setting = setting_res.scalar_one_or_none()
    commission_rate = m_setting.platform_commission_percent if m_setting else Decimal("20.00")
    from app.core.config import settings
    default_holding = getattr(settings, "SELLER_PAYOUT_HOLD_DAYS", 14)
    holding_days = m_setting.payout_holding_days if (m_setting and m_setting.payout_holding_days) else default_holding

    # 2. Completed sales query
    stmt = (
        select(
            OrderItem.price,
            Order.created_at.label("order_date")
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Payment, Payment.order_id == Order.id)
        .join(Template, OrderItem.template_id == Template.id)
        .where(
            and_(
                Order.status == OrderStatus.COMPLETED,
                Payment.status == PaymentStatus.CAPTURED,
                Order.user_id != seller_id,  # Exclude self-purchases
                Template.seller_id == seller_id
            )
        )
    )
    res = await db.execute(stmt)
    order_items = res.all()

    gross_sales = Decimal("0.00")
    total_net_earnings = Decimal("0.00")
    available_net_earnings = Decimal("0.00")
    pending_net_earnings = Decimal("0.00")

    holding_delta = timedelta(days=holding_days)

    for item in order_items:
        gross_val = Decimal(str(item.price))
        gross_sales += gross_val
        platform_fee = round(gross_val * (commission_rate / Decimal("100.00")), 2)
        net_val = gross_val - platform_fee
        total_net_earnings += net_val

        # Check holding period
        order_date = item.order_date
        if order_date.tzinfo is None:
            order_date = order_date.replace(tzinfo=timezone.utc)

        if (order_date + holding_delta) <= now_utc:
            available_net_earnings += net_val
        else:
            pending_net_earnings += net_val

    platform_commission_total = gross_sales - total_net_earnings

    # 3. Withdrawn/Paid requests
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

    # 4. Pending requests
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

    # 5. Withdrawable Available Balance
    available_balance = available_net_earnings - withdrawn_amount - pending_withdrawal
    if available_balance < Decimal("0.00"):
        available_balance = Decimal("0.00")

    return {
        "gross_sales": gross_sales,
        "platform_commission": platform_commission_total,
        "total_earned": total_net_earnings,  # Total net creator earnings
        "net_earnings": total_net_earnings,
        "available_net_earnings": available_net_earnings,
        "pending_earnings": pending_net_earnings,
        "withdrawn_amount": withdrawn_amount,
        "pending_withdrawal": pending_withdrawal,
        "available_balance": available_balance,
        "commission_rate": commission_rate,
        "holding_days": holding_days,
    }


@router.get("/earnings", response_model=EarningsSummaryResponse)
@router.get("/summary", response_model=EarningsSummaryResponse)
async def get_seller_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Get detailed earnings ledger and full Creator Studio analytics for the current creator.
    Uses real database calculations with dispute holding periods and platform commission rates.
    """
    now_utc = datetime.now(timezone.utc)
    summary = await calculate_seller_earnings(db, current_user.id)
    holding_delta = timedelta(days=summary["holding_days"])
    comm_rate = summary["commission_rate"]

    # 1. Fetch individual sales ledger
    sales_stmt = (
        select(
            Order.id.label("order_id"),
            OrderItem.price,
            OrderItem.license_type,
            OrderItem.template_id,
            Template.title.label("template_title"),
            Order.order_number,
            Order.created_at.label("date"),
            Order.extra_metadata,
            User.email.label("purchaser_email"),
            Payment.gateway_payment_id,
        )
        .join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Payment, Payment.order_id == Order.id)
        .join(Template, OrderItem.template_id == Template.id)
        .join(User, Order.user_id == User.id)
        .where(
            and_(
                Order.status == OrderStatus.COMPLETED,
                Template.seller_id == current_user.id,
                Order.user_id != current_user.id,
            )
        )
        .order_by(Order.created_at.desc())
    )
    sales_res = await db.execute(sales_stmt)
    sales_rows = sales_res.all()

    sales = []
    recent_orders = []
    for row in sales_rows:
        utr = None
        if row.extra_metadata and isinstance(row.extra_metadata, dict):
            utr = row.extra_metadata.get("upi_utr")
        if not utr and row.gateway_payment_id and "UTR:" in str(row.gateway_payment_id):
            utr = str(row.gateway_payment_id).split("UTR:")[-1].strip()

        gross_val = Decimal(str(row.price))
        fee = round(gross_val * (comm_rate / Decimal("100.00")), 2)
        net_val = gross_val - fee

        row_date = row.date
        if row_date.tzinfo is None:
            row_date = row_date.replace(tzinfo=timezone.utc)
        hold_until = row_date + holding_delta
        is_avail = hold_until <= now_utc

        sale_item = SaleItemResponse(
            order_id=row.order_id,
            template_id=row.template_id,
            template_title=row.template_title,
            price=row.price,
            purchaser_email=row.purchaser_email,
            date=row.date,
            order_number=row.order_number,
            license_type=row.license_type,
            upi_utr=utr,
            gross_amount=gross_val,
            platform_fee=fee,
            net_creator_earning=net_val,
            holding_until=hold_until,
            is_available=is_avail,
        )
        sales.append(sale_item)

        if len(recent_orders) < 10:
            recent_orders.append({
                "order_number": row.order_number,
                "template_title": row.template_title,
                "buyer_email": row.purchaser_email,
                "gross": float(gross_val),
                "net": float(net_val),
                "date": row.date.isoformat(),
                "is_available": is_avail,
            })

    # 2. Template counts (Published vs Pending review)
    pub_stmt = select(func.count(Template.id)).where(
        Template.seller_id == current_user.id,
        Template.status == TemplateStatus.PUBLISHED,
    )
    pub_res = await db.execute(pub_stmt)
    published_templates_count = pub_res.scalar_one()

    pend_stmt = select(func.count(Template.id)).where(
        Template.seller_id == current_user.id,
        Template.status.in_([TemplateStatus.SUBMITTED, TemplateStatus.UNDER_REVIEW]),
    )
    pend_res = await db.execute(pend_stmt)
    pending_templates_count = pend_res.scalar_one()

    # 3. Total views and purchases
    views_stmt = select(func.coalesce(func.sum(Template.views_count), 0)).where(
        Template.seller_id == current_user.id
    )
    views_res = await db.execute(views_stmt)
    total_views = views_res.scalar_one()

    total_purchases = len(sales_rows)

    # 4. Best performing templates (top by sales count)
    best_stmt = (
        select(
            Template.id,
            Template.title,
            Template.thumbnail_url,
            Template.price,
            func.count(OrderItem.id).label("sales_count"),
            func.coalesce(func.sum(OrderItem.price), Decimal("0.00")).label("total_gross")
        )
        .join(OrderItem, OrderItem.template_id == Template.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Template.seller_id == current_user.id,
            Order.status == OrderStatus.COMPLETED,
            Order.user_id != current_user.id,
        )
        .group_by(Template.id, Template.title, Template.thumbnail_url, Template.price)
        .order_by(func.count(OrderItem.id).desc())
        .limit(5)
    )
    best_res = await db.execute(best_stmt)
    best_templates = [
        {
            "id": str(r.id),
            "title": r.title,
            "thumbnail_url": r.thumbnail_url,
            "price": float(r.price),
            "sales_count": r.sales_count,
            "total_gross": float(r.total_gross),
        }
        for r in best_res.all()
    ]

    # 5. Sales chart aggregation (last 6 months or 30 days)
    sales_chart = []
    # Build daily or monthly buckets from sales_rows
    from collections import defaultdict
    day_buckets = defaultdict(lambda: {"count": 0, "gross": Decimal("0.00"), "net": Decimal("0.00")})
    for s in sales:
        day_key = s.date.strftime("%Y-%m-%d")
        day_buckets[day_key]["count"] += 1
        day_buckets[day_key]["gross"] += (s.gross_amount or Decimal("0.00"))
        day_buckets[day_key]["net"] += (s.net_creator_earning or Decimal("0.00"))

    # Sort days
    for day in sorted(day_buckets.keys())[-14:]:
        sales_chart.append({
            "date": day,
            "count": day_buckets[day]["count"],
            "gross": float(day_buckets[day]["gross"]),
            "net": float(day_buckets[day]["net"]),
        })

    return EarningsSummaryResponse(
        total_earned=summary["total_earned"],
        withdrawn_amount=summary["withdrawn_amount"],
        pending_withdrawal=summary["pending_withdrawal"],
        available_balance=summary["available_balance"],
        sales=sales,
        gross_sales=summary["gross_sales"],
        platform_commission=summary["platform_commission"],
        net_earnings=summary["net_earnings"],
        pending_earnings=summary["pending_earnings"],
        commission_rate=summary["commission_rate"],
        holding_days=summary["holding_days"],
        published_templates_count=published_templates_count,
        pending_templates_count=pending_templates_count,
        total_views=total_views,
        total_purchases=total_purchases,
        recent_orders=recent_orders,
        best_performing_templates=best_templates,
        sales_chart=sales_chart,
    )


@router.post("/withdrawals", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
async def create_withdrawal_request(
    data: WithdrawalCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Submit a request to withdraw a portion or all of the seller's available balance.
    Uses a pessimistic row-level lock to prevent concurrent double-withdrawal race conditions.
    """
    # Acquire a row-level lock on the seller's user record to serialize concurrent withdrawal attempts
    locked_user_res = await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    )
    locked_user = locked_user_res.scalar_one_or_none()
    if not locked_user:
        raise HTTPException(status_code=404, detail="User not found.")

    summary = await calculate_seller_earnings(db, current_user.id)
    available = summary["available_balance"]

    setting_res = await db.execute(select(MarketplaceSetting).where(MarketplaceSetting.id == "default"))
    m_setting = setting_res.scalar_one_or_none()
    min_amount = m_setting.min_payout_amount if m_setting else Decimal("10.00")

    if data.amount < min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum payout request is ${min_amount:.2f} USD."
        )

    if data.amount > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient available balance. You only have ${available:.2f} available to withdraw (pending earnings are held for {summary['holding_days']} days)."
        )

    # Use specified details or fallback to user settings
    bank_name = data.bank_name or current_user.payout_bank_name
    account_number = data.account_number or current_user.payout_account_number
    ifsc_code = data.ifsc_code or current_user.payout_ifsc_code
    account_holder_name = data.account_holder_name or current_user.payout_account_holder_name

    if not bank_name or not account_number or not ifsc_code or not account_holder_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account details are incomplete. Please provide Bank Name, Account Number, IFSC/Swift Code, and Account Holder Name."
        )

    # Sync provided bank details to user profile for future seamless payouts
    if data.bank_name:
        current_user.payout_bank_name = data.bank_name
    if data.account_number:
        current_user.payout_account_number = data.account_number
    if data.ifsc_code:
        current_user.payout_ifsc_code = data.ifsc_code
    if data.account_holder_name:
        current_user.payout_account_holder_name = data.account_holder_name
    current_user.is_payout_setup_completed = True

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
        "seller_name": request.seller.full_name or request.seller.username or "Site Studio Seller",
        "seller_email": request.seller.email,
        "bank_name": request.bank_name,
        "account_number": f"****{request.account_number[-4:]}" if request.account_number else "N/A",
        "ifsc_code": request.ifsc_code,
        "account_holder_name": request.account_holder_name,
    }


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/withdrawals", response_model=List[AdminWithdrawalResponse])
async def list_all_withdrawals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    [Admin] List all withdrawal requests submitted on the platform.
    Suppresses account holder names from broad list for privacy.
    """
    stmt = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/admin/withdrawals/{withdrawal_id}/bank-details")
async def get_withdrawal_bank_details(
    withdrawal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    [Admin Only] Secure endpoint to inspect unmasked bank details for manual wire processing.
    Emits an audit log warning for every invocation.
    """
    stmt = select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id)
    res = await db.execute(stmt)
    w = res.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    logger.warning("bank_details_viewed admin=%s withdrawal=%s", current_user.id, w.id)
    return {
        "id": str(w.id),
        "seller_id": str(w.seller_id),
        "amount": float(w.amount),
        "bank_name": w.bank_name,
        "account_number": w.account_number,
        "ifsc_code": w.ifsc_code,
        "account_holder_name": w.account_holder_name,
    }


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
    stmt = select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id).with_for_update()
    res = await db.execute(stmt)
    request = res.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")

    if request.ifsc_code == "STRIPE-CONNECT":
        if request.status != WithdrawalStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only unresolved Stripe Connect payout requests can be reconciled.")
        created_at = request.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at < timedelta(hours=23):
            raise HTTPException(status_code=409, detail="A recent Stripe Connect payout must be reconciled by retrying its idempotent request.")
        if data.status not in {WithdrawalStatus.PAID, WithdrawalStatus.REJECTED}:
            raise HTTPException(status_code=409, detail="An expired Stripe Connect payout can only be reconciled as paid or rejected.")

    allowed_transitions = {
        WithdrawalStatus.PENDING: {WithdrawalStatus.APPROVED, WithdrawalStatus.REJECTED},
        WithdrawalStatus.APPROVED: {WithdrawalStatus.PAID, WithdrawalStatus.REJECTED},
        WithdrawalStatus.REJECTED: set(),
        WithdrawalStatus.PAID: set(),
    }
    if request.ifsc_code != "STRIPE-CONNECT" and data.status not in allowed_transitions[request.status]:
        raise HTTPException(status_code=409, detail=f"Cannot change a {request.status.value} withdrawal to {data.status.value}.")
    request.status = data.status
    await db.flush()
    await db.commit()
    await db.refresh(request)

    return request


# ── Stripe Connect Multi-Vendor Endpoints ─────────────────────────────────────

@router.post("/stripe-connect/onboard")
async def onboard_seller_stripe_connect(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Creates or retrieves a Stripe Connect Express account for the seller
    and generates an Account Link onboarding URL.
    """
    from app.core.config import settings
    import stripe

    frontend_url = settings.FRONTEND_URL.rstrip("/")
    mock_return_url = f"{frontend_url}/dashboard?tab=earnings&connected=true"

    if not settings.STRIPE_SECRET_KEY:
        if settings.ENVIRONMENT == "production":
            raise HTTPException(status_code=503, detail="Stripe Connect is not configured for production payouts.")
        # Development fallback mode
        if not current_user.stripe_connect_account_id:
            current_user.stripe_connect_account_id = f"acct_mock_{uuid.uuid4().hex[:12]}"
            current_user.is_payout_setup_completed = True
            await db.commit()

        return {
            "account_id": current_user.stripe_connect_account_id,
            "onboarding_url": mock_return_url,
            "is_mock": True,
            "message": "Stripe Connect Express onboarding link generated (Development Mode).",
        }

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        account_id = current_user.stripe_connect_account_id
        if not account_id:
            account = await asyncio.to_thread(
                stripe.Account.create,
                type="express",
                country="IN",  # Indian platform — payout fields use IFSC/bank codes
                email=current_user.email,
                capabilities={"transfers": {"requested": True}},
                business_type="individual",
            )
            account_id = account.id
            current_user.stripe_connect_account_id = account_id
            await db.commit()

        account_link = await asyncio.to_thread(
            stripe.AccountLink.create,
            account=account_id,
            refresh_url=f"{frontend_url}/dashboard?tab=earnings&connect_refresh=true",
            return_url=f"{frontend_url}/dashboard?tab=earnings&connect_success=true",
            type="account_onboarding",
        )

        return {
            "account_id": account_id,
            "onboarding_url": account_link.url,
            "is_mock": False,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe Connect onboarding failed: {type(e).__name__}") from e


@router.get("/stripe-connect/status")
async def get_stripe_connect_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Retrieves real-time KYC and payout capability status from Stripe for the seller's connected account.
    """
    account_id = current_user.stripe_connect_account_id
    if not account_id:
        return {
            "is_connected": False,
            "payouts_enabled": False,
            "details_submitted": False,
            "account_id": None,
        }

    from app.core.config import settings
    import stripe

    if not settings.STRIPE_SECRET_KEY or account_id.startswith("acct_mock_"):
        if settings.ENVIRONMENT == "production":
            raise HTTPException(status_code=503, detail="Mock Stripe Connect accounts cannot be used for production payouts.")
        return {
            "is_connected": True,
            "payouts_enabled": True,
            "details_submitted": True,
            "account_id": account_id,
            "is_mock": True,
        }

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        acct = await asyncio.to_thread(stripe.Account.retrieve, account_id)
        payouts_enabled = acct.payouts_enabled
        details_submitted = acct.details_submitted

        if payouts_enabled and not current_user.is_payout_setup_completed:
            current_user.is_payout_setup_completed = True
            await db.commit()

        return {
            "is_connected": True,
            "payouts_enabled": payouts_enabled,
            "details_submitted": details_submitted,
            "account_id": account_id,
            "charges_enabled": acct.charges_enabled,
            "is_mock": False,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Stripe Connect account status: {str(e)}")


@router.post("/stripe-connect/transfer")
async def transfer_seller_earnings(
    amount: Decimal,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Executes a direct Stripe Transfer to the seller's connected account.
    """
    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than zero.")

    locked = await db.execute(select(User).where(User.id == current_user.id).with_for_update())
    if locked.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Seller account not found.")
    amount = amount.quantize(Decimal("0.01"))
    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Transfer amount must be at least one cent.")
    account_id = current_user.stripe_connect_account_id
    if not account_id:
        raise HTTPException(status_code=400, detail="Please complete Stripe Connect onboarding first before requesting payouts.")

    # Reuse an unresolved Stripe transfer record. Stripe's stable idempotency key
    # means a retry returns the original transfer if the first response was lost.
    pending_result = await db.execute(
        select(WithdrawalRequest).where(
            WithdrawalRequest.seller_id == current_user.id,
            WithdrawalRequest.status == WithdrawalStatus.PENDING,
            WithdrawalRequest.ifsc_code == "STRIPE-CONNECT",
        ).order_by(WithdrawalRequest.created_at.desc()).with_for_update()
    )
    candidates = pending_result.scalars().all()
    w_req = next((c for c in candidates if c.account_number == account_id), None)
    if w_req:
        if w_req.amount != amount:
            raise HTTPException(
                status_code=409,
                detail=f"A Stripe payout of {w_req.amount} is still being confirmed (request {w_req.id}). Retry that amount to safely resume it.",
            )
        pending_created_at = w_req.created_at
        if pending_created_at.tzinfo is None:
            pending_created_at = pending_created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - pending_created_at >= timedelta(hours=23):
            raise HTTPException(
                status_code=409,
                detail=f"Payout request {w_req.id} is older than Stripe's safe idempotency retry window. Have an administrator reconcile it before retrying.",
            )
    else:
        earnings = await calculate_seller_earnings(db, current_user.id)
        if earnings["available_balance"] < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient available balance ({earnings['available_balance']}) for requested transfer of {amount}."
            )

    from app.core.config import settings
    import stripe

    if w_req is None:
        w_req = WithdrawalRequest(
            seller_id=current_user.id,
            amount=amount,
            status=WithdrawalStatus.PENDING,
            bank_name="Stripe Connect Express Account",
            account_number=account_id,
            ifsc_code="STRIPE-CONNECT",
            account_holder_name=current_user.full_name or current_user.username or "Seller",
        )
        db.add(w_req)
        await db.flush()

    # PENDING reservation is safely stored and queued for admin execution
    await db.commit()
    await db.refresh(w_req)

    return {
        "status": "PENDING_APPROVAL",
        "withdrawal_id": str(w_req.id),
        "amount": float(amount),
        "destination": account_id,
        "message": "Payout request submitted for administrator review and Stripe transfer execution.",
    }


@router.post("/admin/withdrawals/{withdrawal_id}/stripe-transfer")
async def execute_admin_stripe_transfer(
    withdrawal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Admin-only endpoint to approve and execute a queued Stripe Connect payout.
    Enforces the dual-control principle to prevent unauthorized immediate fund drains.
    """
    stmt = (
        select(WithdrawalRequest)
        .where(
            WithdrawalRequest.id == withdrawal_id,
            WithdrawalRequest.status == WithdrawalStatus.PENDING,
            WithdrawalRequest.ifsc_code == "STRIPE-CONNECT",
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    w_req = res.scalar_one_or_none()
    if not w_req:
        raise HTTPException(status_code=404, detail="Pending Stripe Connect withdrawal request not found.")

    # Re-verify seller available balance
    earnings = await calculate_seller_earnings(db, w_req.seller_id)
    if earnings["available_balance"] + w_req.amount < w_req.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient seller balance ({earnings['available_balance']}) for withdrawal."
        )

    account_id = w_req.account_number
    amount_in_cents = int(w_req.amount * 100)

    from app.core.config import settings
    import stripe

    if not settings.STRIPE_SECRET_KEY or account_id.startswith("acct_mock_"):
        if settings.ENVIRONMENT.lower() not in ("development", "local", "test"):
            raise HTTPException(status_code=503, detail="Mock Stripe Connect accounts cannot receive payouts in non-local environments.")
        w_req.status = WithdrawalStatus.PAID
        w_req.processed_at = datetime.now(timezone.utc)
        w_req.admin_notes = f"Approved & processed (Mock Mode) by {admin_user.email}"
        await db.commit()
        return {
            "success": True,
            "withdrawal_id": str(w_req.id),
            "transfer_id": f"tr_mock_{uuid.uuid4().hex[:12]}",
            "message": "Stripe Transfer executed successfully (Development Mock).",
            "amount": float(w_req.amount),
        }

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        transfer = await asyncio.to_thread(
            stripe.Transfer.create,
            amount=amount_in_cents,
            currency="usd",
            destination=account_id,
            description=f"Creator Earnings Payout #{w_req.id} (Approved by {admin_user.email})",
            metadata={
                "withdrawal_id": str(w_req.id),
                "seller_id": str(w_req.seller_id),
                "admin_id": str(admin_user.id),
            },
            idempotency_key=f"transfer_{w_req.id}",
        )
        w_req.status = WithdrawalStatus.PAID
        w_req.processed_at = datetime.now(timezone.utc)
        w_req.admin_notes = f"Approved & processed via Stripe Transfer {transfer.id} by {admin_user.email}"
        await db.commit()
        return {
            "success": True,
            "withdrawal_id": str(w_req.id),
            "transfer_id": transfer.id,
            "message": "Direct Stripe Transfer completed successfully.",
            "amount": float(w_req.amount),
        }
    except Exception as e:
        logger.error("Admin Stripe transfer execution failed for %s: %s", w_req.id, e)
        raise HTTPException(status_code=502, detail=f"Stripe transfer execution failed: {str(e)}")

