"""
Subscription Service — Handles recurring billing lifecycle, customer mandates,
Stripe Billing, Razorpay Subscriptions, webhook idempotency, and grace periods.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import get_plan_config, normalize_plan_id
from app.models.user import User
from app.models.subscription import UserSubscription, SubscriptionEvent, UsageLedger
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger("subscriptions")


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.entitlement_service = EntitlementService(db)

    async def initiate_subscription_checkout(
        self,
        user: User,
        plan_id: str,
        billing_cycle: str = "monthly",
        gateway: str = "razorpay",
    ) -> Dict[str, Any]:
        """
        Initiates a recurring subscription checkout using native recurring payment objects.
        Razorpay: Creates a recurring subscription mandate (or test order in mock/dev).
        Stripe: Creates a Stripe Checkout Session in mode='subscription'.
        """
        normalized_plan = normalize_plan_id(plan_id)
        if normalized_plan == "free":
            # Immediate downgrade/switch to free
            sub = await self.entitlement_service.get_or_create_user_subscription(user)
            sub.plan_id = "free"
            sub.status = "active"
            sub.cancel_at_period_end = False
            sub.is_trial = True
            user.subscription_tier = "free"
            user.subscription_status = "active"
            await self.db.commit()
            return {
                "status": "completed",
                "plan_id": "free",
                "message": "Switched to Free Starter tier successfully.",
                "free": True,
            }

        plan_cfg = get_plan_config(normalized_plan)
        is_annual = billing_cycle.lower() == "annual"

        usd_price = plan_cfg["annual_price_usd"] if is_annual else plan_cfg["monthly_price_usd"]
        inr_price = plan_cfg["annual_price_inr"] if is_annual else plan_cfg["monthly_price_inr"]

        # -------------------------------------------------------------------
        # STRIPE SUBSCRIPTION FLOW
        # -------------------------------------------------------------------
        if gateway.lower() == "stripe" and settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith("your-"):
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY

            # Ensure Stripe customer exists
            customer_id = user.stripe_customer_id
            if not customer_id:
                try:
                    c = stripe.Customer.create(
                        email=user.email,
                        name=user.full_name or user.username or user.email,
                        metadata={"user_id": str(user.id)},
                    )
                    customer_id = c.id
                    user.stripe_customer_id = customer_id
                    self.db.add(user)
                    await self.db.flush()
                except Exception as ex:
                    logger.warning(f"Could not create Stripe customer: {ex}")

            unit_amount_cents = int(usd_price * 100)
            interval = "year" if is_annual else "month"

            session_params = {
                "mode": "subscription",
                "payment_method_types": ["card"],
                "customer": customer_id,
                "customer_email": user.email if not customer_id else None,
                "client_reference_id": str(user.id),
                "metadata": {
                    "purchase_type": "user_subscription",
                    "user_id": str(user.id),
                    "plan_id": normalized_plan,
                    "billing_cycle": billing_cycle,
                },
                "subscription_data": {
                    "metadata": {
                        "user_id": str(user.id),
                        "plan_id": normalized_plan,
                        "billing_cycle": billing_cycle,
                    }
                },
                "line_items": [
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Site Studio {plan_cfg['name']}",
                                "description": f"{plan_cfg['description']} ({billing_cycle.title()})",
                            },
                            "unit_amount": unit_amount_cents,
                            "recurring": {"interval": interval},
                        },
                        "quantity": 1,
                    }
                ],
                "success_url": f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=billing&session_id={{CHECKOUT_SESSION_ID}}&status=success",
                "cancel_url": f"{settings.FRONTEND_URL.rstrip('/')}/pricing?cancelled=true",
            }
            # Clean None kwargs
            clean_params = {k: v for k, v in session_params.items() if v is not None}
            checkout_session = stripe.checkout.Session.create(**clean_params)

            return {
                "status": "initiated",
                "gateway": "stripe",
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
                "plan_id": normalized_plan,
                "billing_cycle": billing_cycle,
                "amount_usd": float(usd_price),
            }

        # -------------------------------------------------------------------
        # RAZORPAY SUBSCRIPTION FLOW
        # -------------------------------------------------------------------
        amount_paise = int(inr_price * 100)
        is_mock_key = (
            not settings.RAZORPAY_KEY_ID
            or settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
            or "change-me" in settings.RAZORPAY_KEY_ID
            or "mock" in settings.RAZORPAY_KEY_ID.lower()
        )

        rz_sub_id = None
        if not is_mock_key:
            try:
                import razorpay
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

                # Create or fetch razorpay recurring plan
                period = "yearly" if is_annual else "monthly"
                plan_res = client.plan.create({
                    "period": period,
                    "interval": 1,
                    "item": {
                        "name": f"Site Studio {plan_cfg['name']}",
                        "amount": amount_paise,
                        "currency": "INR",
                        "description": f"Site Studio {plan_cfg['name']} ({billing_cycle.title()})",
                    },
                    "notes": {"plan_id": normalized_plan, "billing_cycle": billing_cycle},
                })
                rz_plan_id = plan_res["id"]

                # Create Subscription object
                sub_res = client.subscription.create({
                    "plan_id": rz_plan_id,
                    "total_count": 12 if is_annual else 36,
                    "quantity": 1,
                    "customer_notify": 1,
                    "notes": {
                        "user_id": str(user.id),
                        "user_email": user.email,
                        "plan_id": normalized_plan,
                        "billing_cycle": billing_cycle,
                    },
                })
                rz_sub_id = sub_res["id"]
            except Exception as e_rz:
                logger.warning(f"Razorpay subscription creation failed: {e_rz}. Falling back to standard order checkout.")
                # Fallback to standard checkout order if recurring mandates are unconfigured in test mode
                try:
                    order_res = client.order.create({
                        "amount": amount_paise,
                        "currency": "INR",
                        "receipt": f"sub_{uuid.uuid4().hex[:12]}",
                        "notes": {
                            "user_id": str(user.id),
                            "user_email": user.email,
                            "plan_id": normalized_plan,
                            "billing_cycle": billing_cycle,
                        },
                    })
                    rz_sub_id = order_res["id"]
                except Exception:
                    rz_sub_id = f"rzp_mock_sub_{uuid.uuid4().hex[:12]}"
        else:
            rz_sub_id = f"rzp_mock_sub_{uuid.uuid4().hex[:12]}"

        # Record intent in user subscription
        sub = await self.entitlement_service.get_or_create_user_subscription(user)
        sub.provider_subscription_id = rz_sub_id
        sub.payment_provider = "razorpay"
        sub.billing_cycle = billing_cycle
        await self.db.commit()

        return {
            "status": "initiated",
            "gateway": "razorpay",
            "subscription_id": rz_sub_id,
            "key_id": settings.RAZORPAY_KEY_ID if not is_mock_key else "rzp_test_mockkey",
            "amount": amount_paise,
            "amount_inr": float(inr_price),
            "amount_usd": float(usd_price),
            "currency": "INR",
            "plan_id": normalized_plan,
            "title": plan_cfg["name"],
            "credits": plan_cfg["included_ai_credits"],
            "billing_cycle": billing_cycle,
        }

    # -----------------------------------------------------------------------
    # DURABLE WEBHOOK & SUBSCRIPTION LIFECYCLE PROCESSING
    # -----------------------------------------------------------------------

    async def handle_subscription_payment_success(
        self,
        provider: str,
        event_id: str,
        user_id: Optional[uuid.UUID],
        user_email: Optional[str],
        plan_id: str,
        billing_cycle: str,
        provider_sub_id: Optional[str],
        payload: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Handles verified subscription payment success (initial or renewal).
        - Enforces idempotency via SubscriptionEvent table.
        - Grants monthly credit allowance once per cycle.
        - Updates period boundaries and clears past_due status.
        """
        # 1. Idempotency Check
        stmt = select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == event_id)
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none():
            logger.info(f"Subscription event {event_id} already processed. Skipping duplicate.")
            return {"status": "already_processed", "event_id": event_id}

        # Record event initially
        sub_event = SubscriptionEvent(
            provider=provider,
            provider_event_id=event_id,
            provider_event_type="subscription.payment_success",
            subscription_id=provider_sub_id,
            user_id=user_id,
            payload=payload,
            status="processed",
        )
        self.db.add(sub_event)

        # 2. Find User
        user = None
        if user_id:
            user = await self.db.get(User, user_id)
        if not user and user_email:
            u_res = await self.db.execute(select(User).where(User.email == user_email))
            user = u_res.scalar_one_or_none()

        if not user:
            sub_event.status = "failed"
            sub_event.error_message = f"User not found for payment success (id: {user_id}, email: {user_email})"
            await self.db.commit()
            return {"status": "error", "message": "User not found"}

        # 3. Apply Plan Entitlements
        normalized_plan = normalize_plan_id(plan_id)
        plan_cfg = get_plan_config(normalized_plan)
        now = datetime.now(timezone.utc)
        cycle_days = 365 if billing_cycle.lower() == "annual" else 30

        user.subscription_tier = normalized_plan
        user.subscription_status = "active"
        user.subscription_expires_at = now + timedelta(days=cycle_days)
        user.auto_renew = True

        # Grant monthly credits
        credits_to_grant = plan_cfg["included_ai_credits"]
        user.ai_credits = (user.ai_credits or 0) + credits_to_grant

        # Update primary UserSubscription
        user_sub = await self.entitlement_service.get_or_create_user_subscription(user)
        user_sub.plan_id = normalized_plan
        user_sub.billing_cycle = billing_cycle
        user_sub.payment_provider = provider
        user_sub.provider_subscription_id = provider_sub_id or user_sub.provider_subscription_id
        user_sub.status = "active"
        user_sub.current_period_start = now
        user_sub.current_period_end = now + timedelta(days=cycle_days)
        user_sub.next_billing_date = now + timedelta(days=cycle_days)
        user_sub.last_successful_payment_at = now
        user_sub.grace_period_end = None
        user_sub.cancel_at_period_end = False

        await self.db.commit()

        logger.info(
            f"Successfully activated/renewed {normalized_plan} plan for {user.email}. Granted {credits_to_grant} AI credits. New balance: {user.ai_credits}"
        )
        return {
            "status": "success",
            "user_email": user.email,
            "plan_id": normalized_plan,
            "credits_granted": credits_to_grant,
            "period_end": user_sub.current_period_end.isoformat(),
        }

    async def handle_subscription_payment_failure(
        self,
        provider: str,
        event_id: str,
        user_id: Optional[uuid.UUID],
        user_email: Optional[str],
        provider_sub_id: Optional[str],
        error_reason: str = "Payment declined",
        payload: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Handles payment failure without immediately destroying customer websites:
        - Marks subscription past_due.
        - Sets a 3-day grace period.
        - Preserves existing websites during grace.
        """
        # Idempotency check
        stmt = select(SubscriptionEvent).where(SubscriptionEvent.provider_event_id == event_id)
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none():
            return {"status": "already_processed"}

        sub_event = SubscriptionEvent(
            provider=provider,
            provider_event_id=event_id,
            provider_event_type="subscription.payment_failed",
            subscription_id=provider_sub_id,
            user_id=user_id,
            payload=payload,
            status="processed",
            error_message=error_reason,
        )
        self.db.add(sub_event)

        user = None
        if user_id:
            user = await self.db.get(User, user_id)
        if not user and user_email:
            u_res = await self.db.execute(select(User).where(User.email == user_email))
            user = u_res.scalar_one_or_none()

        if user:
            now = datetime.now(timezone.utc)
            grace_days = FAIR_USE_POLICY["grace_period_days"]
            user.subscription_status = "past_due"

            user_sub = await self.entitlement_service.get_or_create_user_subscription(user)
            user_sub.status = "past_due"
            user_sub.last_failed_payment_at = now
            user_sub.grace_period_end = now + timedelta(days=grace_days)
            await self.db.commit()

            logger.warning(
                f"Subscription payment failed for user {user.email}. Placed in {grace_days}-day grace period until {user_sub.grace_period_end}"
            )

        return {"status": "past_due_recorded", "event_id": event_id}

    async def cancel_subscription_at_period_end(self, user: User) -> Dict[str, Any]:
        """
        Schedules subscription cancellation at the end of the current paid billing period.
        Access is preserved until current_period_end expires.
        """
        user_sub = await self.entitlement_service.get_or_create_user_subscription(user)
        user_sub.cancel_at_period_end = True
        user_sub.canceled_at = datetime.now(timezone.utc)
        user.auto_renew = False

        # If payment provider is Stripe and subscription ID is known, set cancel_at_period_end
        if user_sub.payment_provider == "stripe" and user_sub.provider_subscription_id and settings.STRIPE_SECRET_KEY:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe.Subscription.modify(
                    user_sub.provider_subscription_id,
                    cancel_at_period_end=True,
                )
            except Exception as e_stripe:
                logger.warning(f"Could not set Stripe cancel_at_period_end: {e_stripe}")

        await self.db.commit()
        return {
            "status": "cancellation_scheduled",
            "effective_date": user_sub.current_period_end.isoformat() if user_sub.current_period_end else None,
            "message": "Your subscription will remain active until the end of your billing cycle and will not renew.",
        }

    async def reactivate_subscription(self, user: User) -> Dict[str, Any]:
        """Reactivates a subscription that was set to cancel at period end."""
        user_sub = await self.entitlement_service.get_or_create_user_subscription(user)
        user_sub.cancel_at_period_end = False
        user_sub.canceled_at = None
        user.auto_renew = True

        if user_sub.payment_provider == "stripe" and user_sub.provider_subscription_id and settings.STRIPE_SECRET_KEY:
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe.Subscription.modify(
                    user_sub.provider_subscription_id,
                    cancel_at_period_end=False,
                )
            except Exception as e_stripe:
                logger.warning(f"Could not reactivate Stripe subscription: {e_stripe}")

        await self.db.commit()
        return {
            "status": "reactivated",
            "message": "Your subscription has been reactivated and will automatically renew.",
        }

