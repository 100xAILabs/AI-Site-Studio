"""
Subscription & Entitlement Routes.

Exposes authoritative plan configurations, user entitlement checks,
recurring billing initiation, and cancellation workflows.
"""

from typing import Dict, Any, List, Optional
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.plans import PLANS, AI_OPERATION_CREDIT_COSTS, FAIR_USE_POLICY
from app.models.user import User
from app.models.subscription import UsageLedger
from app.services.entitlement_service import EntitlementService
from app.services.subscription_service import SubscriptionService

router = APIRouter()


class SubscriptionCheckoutRequest(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"  # monthly, annual
    gateway: str = "razorpay"       # razorpay, stripe


@router.get("/plans")
async def list_subscription_plans():
    """
    Returns the authoritative plan specifications and operation credit costs.
    Shared by frontend pricing, subscribe flows, and backend validation.
    """
    plans_list = []
    for pid, p in PLANS.items():
        plans_list.append({
            "id": p["id"],
            "name": p["name"],
            "badge": p["badge"],
            "description": p["description"],
            "monthly_price_usd": float(p["monthly_price_usd"]),
            "annual_price_usd": float(p["annual_price_usd"]),
            "annual_monthly_equivalent_usd": float(p["annual_monthly_equivalent_usd"]),
            "monthly_price_inr": float(p["monthly_price_inr"]),
            "annual_price_inr": float(p["annual_price_inr"]),
            "included_ai_credits": p["included_ai_credits"],
            "max_deployment_slots": p["max_deployment_slots"],
            "included_hosted_websites": p["included_hosted_websites"],
            "additional_hosting_price_usd": float(p["additional_hosting_price_usd"]),
            "custom_domain_allowed": p["custom_domain_allowed"],
            "auto_heal_allowed": p["auto_heal_allowed"],
            "auto_heal_sites_limit": p["auto_heal_sites_limit"],
            "deployment_versions_limit": p["deployment_versions_limit"],
            "backup_retention_days": p["backup_retention_days"],
            "token_discount_percent": p["token_discount_percent"],
            "support_tier": p["support_tier"],
            "features": p["features"],
        })

    return {
        "plans": plans_list,
        "operation_costs": AI_OPERATION_CREDIT_COSTS,
        "fair_use_policy": FAIR_USE_POLICY,
    }


@router.get("/my-subscription")
async def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns complete entitlements, remaining usage, billing cycle, and renewal dates
    for the authenticated user.
    """
    entitlement_service = EntitlementService(db)
    entitlements = await entitlement_service.get_user_entitlements(current_user)
    await db.commit()
    return entitlements


@router.post("/checkout")
async def create_subscription_checkout(
    payload: SubscriptionCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiates a recurring subscription checkout with provider-native recurring objects.
    """
    sub_service = SubscriptionService(db)
    res = await sub_service.initiate_subscription_checkout(
        user=current_user,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        gateway=payload.gateway,
    )
    return res


@router.post("/verify-stripe-session/{session_id}")
@router.get("/verify-stripe-session/{session_id}")
async def verify_stripe_subscription_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Direct client-return fallback for Stripe Checkout subscriptions.
    Verifies the Stripe Checkout Session directly and immediately activates the subscription.
    """
    from app.core.config import settings
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Stripe secret key not configured")
        
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    try:
        checkout = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Stripe checkout session not found")
        
    if checkout.get("status") != "complete" or checkout.get("payment_status") not in ("paid", "no_payment_required"):
        return {"status": "pending", "message": "Payment not yet confirmed by Stripe."}
        
    metadata = checkout.get("metadata") or {}
    meta_user_id = metadata.get("user_id")
    client_ref_id = checkout.get("client_reference_id")
    uid = str(current_user.id)
    if meta_user_id != uid or (client_ref_id not in (None, uid)):
        raise HTTPException(
            status_code=403,
            detail="This checkout session belongs to another account.",
        )

    mode = checkout.get("mode")
    purchase_type = metadata.get("purchase_type")
    plan_id = metadata.get("plan_id")
    from app.core.plans import PLANS
    if mode != "subscription" or purchase_type != "user_subscription" or plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Not a subscription checkout session.")

    billing_cycle = metadata.get("billing_cycle") or "monthly"
    provider_sub_id = checkout.get("subscription")
    
    sub_service = SubscriptionService(db)
    res = await sub_service.handle_subscription_payment_success(
        provider="stripe",
        event_id=f"stripe_checkout:{session_id}",
        user_id=current_user.id,
        user_email=current_user.email,
        plan_id=plan_id,
        billing_cycle=billing_cycle,
        provider_sub_id=provider_sub_id,
        payload=dict(checkout),
    )
    return res


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Schedules cancellation at the end of the paid billing period.
    The customer retains full access until their paid period expires.
    """
    sub_service = SubscriptionService(db)
    res = await sub_service.cancel_subscription_at_period_end(current_user)
    return res


@router.post("/reactivate")
async def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reactivates a subscription that was scheduled for cancellation at period end.
    """
    sub_service = SubscriptionService(db)
    res = await sub_service.reactivate_subscription(current_user)
    return res


@router.get("/usage")
async def get_my_usage_history(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns auditable usage history of AI generations, edits, auto-heals, and builds.
    """
    stmt = (
        select(UsageLedger)
        .where(UsageLedger.user_id == current_user.id)
        .order_by(desc(UsageLedger.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    return {
        "usage": [
            {
                "id": str(r.id),
                "operation": r.operation,
                "credits_consumed": r.credits_consumed,
                "provider": r.provider,
                "model_name": r.model_name,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
    }

