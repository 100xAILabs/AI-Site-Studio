"""
Payouts and withdrawals routes.
"""

import uuid
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
from app.models.payment import Payment
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
@router.get("/summary", response_model=EarningsSummaryResponse)
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
                Template.seller_id == current_user.id
            )
        )
        .order_by(Order.created_at.desc())
    )
    sales_res = await db.execute(sales_stmt)
    sales_rows = sales_res.all()

    sales = []
    for row in sales_rows:
        utr = None
        if row.extra_metadata and isinstance(row.extra_metadata, dict):
            utr = row.extra_metadata.get("upi_utr")
        if not utr and row.gateway_payment_id and "UTR:" in str(row.gateway_payment_id):
            utr = str(row.gateway_payment_id).split("UTR:")[-1].strip()

        sales.append(
            SaleItemResponse(
                order_id=row.order_id,
                template_id=row.template_id,
                template_title=row.template_title,
                price=row.price,
                purchaser_email=row.purchaser_email,
                date=row.date,
                order_number=row.order_number,
                license_type=row.license_type,
                upi_utr=utr,
            )
        )

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
            account = stripe.Account.create(
                type="express",
                country="IN",  # Indian platform — payout fields use IFSC/bank codes
                email=current_user.email,
                capabilities={"transfers": {"requested": True}},
                business_type="individual",
            )
            account_id = account.id
            current_user.stripe_connect_account_id = account_id
            await db.commit()

        account_link = stripe.AccountLink.create(
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
        acct = stripe.Account.retrieve(account_id)
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
            WithdrawalRequest.account_number == account_id,
        ).order_by(WithdrawalRequest.created_at.desc()).with_for_update()
    )
    w_req = pending_result.scalars().first()
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

    if not settings.STRIPE_SECRET_KEY or account_id.startswith("acct_mock_"):
        if settings.ENVIRONMENT == "production":
            await db.rollback()
            raise HTTPException(status_code=503, detail="Mock Stripe Connect accounts cannot receive production payouts.")
        w_req.status = WithdrawalStatus.PAID
        await db.commit()
        return {
            "status": "PAID",
            "transfer_id": f"tr_mock_{uuid.uuid4().hex[:12]}",
            "amount": float(amount),
            "message": "Direct Stripe Transfer completed successfully (Development Mode).",
        }

    # Persist the reservation before making the external transfer. If Stripe or
    # the database response is uncertain, a retry can resume this same request.
    await db.commit()
    await db.refresh(w_req)
    payout_request_id = str(w_req.id)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        amount_cents = int(amount * 100)
        transfer = stripe.Transfer.create(
            amount=amount_cents,
            currency="usd",
            destination=account_id,
            description=f"AI Site Studio Seller Payout #{payout_request_id}",
            idempotency_key=f"seller-payout-{payout_request_id}",
        )

        w_req.status = WithdrawalStatus.PAID
        await db.commit()

        return {
            "status": "PAID",
            "transfer_id": transfer.id,
            "amount": float(amount),
            "destination": account_id,
        }
    except Exception as e:
        definite_failure_types = tuple(
            error_type for error_type in (
                getattr(stripe.error, "InvalidRequestError", None),
                getattr(stripe.error, "AuthenticationError", None),
                getattr(stripe.error, "PermissionError", None),
            ) if error_type is not None
        )
        if definite_failure_types and isinstance(e, definite_failure_types):
            w_req.status = WithdrawalStatus.REJECTED
            await db.commit()
            raise HTTPException(status_code=400, detail="Stripe rejected this payout request; the reserved balance has been released.") from e

        await db.rollback()
        # Keep the committed PENDING reservation on every error. The client can
        # retry the same amount, reusing this request's Stripe idempotency key.
        raise HTTPException(
            status_code=502,
            detail=f"Stripe payout status is not confirmed. Payout request {payout_request_id} remains pending; retry the same amount to safely check it again.",
        ) from e

