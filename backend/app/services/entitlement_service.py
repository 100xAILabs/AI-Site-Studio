"""
Central Subscription Entitlement Service.

The single authoritative backend source of truth for:
- User plan entitlements & limits (Free, Pro, Extreme)
- AI credit validation, reservation, deduction, and usage ledgering
- Deployment slot quotas, included vs paid hosting allowances
- 7-day trial policy enforcement & permanent per-template trial history
- Persistent Auto-Heal site registrations and period repair quotas
- Custom domain connection permissions
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple, List

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import (
    PLANS,
    get_plan_config,
    normalize_plan_id,
    get_operation_cost,
    ESTIMATED_PROVIDER_COSTS,
    FAIR_USE_POLICY,
)
from app.models.user import User
from app.models.deployment import Deployment
from app.models.hosting_subscription import HostingSubscription
from app.models.template import Template
from app.models.subscription import (
    UserSubscription,
    UsageLedger,
    TrialHistory,
    AutoHealRegistration,
    PromotionalDomainCredit,
)


class EntitlementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # -----------------------------------------------------------------------
    # PRIMARY USER SUBSCRIPTION & PLAN SUMMARY
    # -----------------------------------------------------------------------

    async def get_or_create_user_subscription(self, user: User) -> UserSubscription:
        """Retrieves or lazily provisions the primary UserSubscription for an account."""
        stmt = select(UserSubscription).where(UserSubscription.user_id == user.id)
        res = await self.db.execute(stmt)
        sub = res.scalar_one_or_none()

        tier_on_user = normalize_plan_id(getattr(user, "subscription_tier", "free") or "free")
        now = datetime.now(timezone.utc)

        if not sub:
            sub = UserSubscription(
                user_id=user.id,
                plan_id=tier_on_user,
                billing_cycle="monthly",
                payment_provider="manual",
                status="active",
                start_date=now,
                current_period_start=now,
                current_period_end=user.subscription_expires_at or (now + timedelta(days=30)),
                next_billing_date=user.subscription_expires_at,
                cancel_at_period_end=not getattr(user, "auto_renew", True),
                is_trial=(tier_on_user == "free"),
            )
            self.db.add(sub)
            await self.db.flush()
        else:
            # Sync user tier with primary record if updated elsewhere
            if sub.plan_id != tier_on_user and getattr(user, "subscription_tier", None):
                sub.plan_id = tier_on_user

        return sub

    async def get_user_entitlements(self, user: User) -> Dict[str, Any]:
        """
        Calculates and returns complete, authoritative entitlement details for a user.
        Queried by protected API routes and frontend billing dashboards.
        """
        sub = await self.get_or_create_user_subscription(user)
        plan_id = normalize_plan_id(sub.plan_id)
        plan_cfg = get_plan_config(plan_id)
        now = datetime.now(timezone.utc)

        # Check subscription status and grace period
        status = sub.status
        is_past_due = status == "past_due"
        in_grace_period = False
        if is_past_due and sub.grace_period_end:
            grace_end = sub.grace_period_end if sub.grace_period_end.tzinfo else sub.grace_period_end.replace(tzinfo=timezone.utc)
            in_grace_period = now <= grace_end

        # AI Credits
        available_credits = user.ai_credits if user.ai_credits is not None else (10 if plan_id == "free" else 0)
        
        # Period start for usage queries
        period_start = sub.current_period_start or (now - timedelta(days=30))
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)

        # Calculate consumed credits in current billing period
        usage_stmt = select(func.coalesce(func.sum(UsageLedger.credits_consumed), 0)).where(
            UsageLedger.user_id == user.id,
            UsageLedger.created_at >= period_start,
        )
        usage_res = await self.db.execute(usage_stmt)
        credits_consumed_period = int(usage_res.scalar() or 0)

        # Active Deployments Count
        dep_stmt = select(func.count(Deployment.id)).where(
            Deployment.user_id == user.id,
            Deployment.status != "stopped",
        )
        dep_res = await self.db.execute(dep_stmt)
        active_deployment_count = int(dep_res.scalar() or 0)

        # Active Live Hosted Websites Count
        live_stmt = select(func.count(Deployment.id)).where(
            Deployment.user_id == user.id,
            Deployment.status == "live",
        )
        live_res = await self.db.execute(live_stmt)
        active_live_hosted_count = int(live_res.scalar() or 0)

        # Additional Paid Hosting Add-ons Count
        addon_stmt = select(func.count(HostingSubscription.id)).where(
            HostingSubscription.user_id == user.id,
            HostingSubscription.status.in_(["active", "trialing"]),
        )
        addon_res = await self.db.execute(addon_stmt)
        paid_hosting_addon_count = int(addon_res.scalar() or 0)

        # Total hosted website capacity = included capacity + paid add-ons
        included_hosting = plan_cfg["included_hosted_websites"]
        total_hosting_capacity = included_hosting + paid_hosting_addon_count

        # Auto-Heal registered sites count
        heal_stmt = select(func.count(AutoHealRegistration.id)).where(
            AutoHealRegistration.user_id == user.id,
            AutoHealRegistration.active.is_(True),
        )
        heal_res = await self.db.execute(heal_stmt)
        active_auto_heal_count = int(heal_res.scalar() or 0)

        # Free generation trial status
        build_stmt = select(func.count(TrialHistory.id)).where(
            TrialHistory.user_id == user.id,
            TrialHistory.trial_type == "generation",
        )
        b_res = await self.db.execute(build_stmt)
        free_generations_used = int(b_res.scalar() or 0)

        return {
            "plan_id": plan_id,
            "plan_name": plan_cfg["name"],
            "plan_badge": plan_cfg["badge"],
            "subscription_status": status,
            "is_past_due": is_past_due,
            "in_grace_period": in_grace_period,
            "billing_cycle": sub.billing_cycle,
            "payment_provider": sub.payment_provider,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "next_billing_date": sub.next_billing_date.isoformat() if sub.next_billing_date else None,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "canceled_at": sub.canceled_at.isoformat() if sub.canceled_at else None,
            # AI Credits
            "ai_credits_available": available_credits,
            "ai_credits_consumed_period": credits_consumed_period,
            "included_monthly_credits": plan_cfg["included_ai_credits"],
            "free_generations_used": free_generations_used,
            "free_generations_allowance": plan_cfg["free_generation_allowance"],
            # Deployments & Hosting
            "active_deployments": active_deployment_count,
            "max_deployment_slots": plan_cfg["max_deployment_slots"],
            "active_live_hosted_websites": active_live_hosted_count,
            "included_hosted_websites": included_hosting,
            "paid_hosting_addons": paid_hosting_addon_count,
            "total_hosting_capacity": total_hosting_capacity,
            "can_create_deployment_slot": active_deployment_count < plan_cfg["max_deployment_slots"],
            "can_host_more_free": active_live_hosted_count < included_hosting,
            # Custom Domains
            "custom_domain_allowed": plan_cfg["custom_domain_allowed"],
            "custom_domain_allowance": plan_cfg["custom_domain_allowance"],
            # Auto-Heal
            "auto_heal_allowed": plan_cfg["auto_heal_allowed"],
            "auto_heal_sites_limit": plan_cfg["auto_heal_sites_limit"],
            "auto_heal_registered_count": active_auto_heal_count,
            "auto_heal_repairs_per_period_limit": plan_cfg["auto_heal_repairs_per_period"],
            # Retention & Tools
            "deployment_versions_limit": plan_cfg["deployment_versions_limit"],
            "backup_retention_days": plan_cfg["backup_retention_days"],
            "token_discount_percent": plan_cfg["token_discount_percent"],
            "support_tier": plan_cfg["support_tier"],
        }

    # -----------------------------------------------------------------------
    # AI CREDIT CHECKING, RESERVATION, DEDUCTION & USAGE AUDIT
    # -----------------------------------------------------------------------

    async def check_ai_generation_entitlement(
        self, user: User, operation: str
    ) -> Tuple[bool, str, int]:
        """
        Evaluates whether a user can perform an AI operation.
        Returns: (allowed: bool, reason: str, required_credits: int)
        """
        sub = await self.get_or_create_user_subscription(user)
        plan_id = normalize_plan_id(sub.plan_id)
        cost = get_operation_cost(operation)
        available = user.ai_credits if user.ai_credits is not None else 0

        # Admin bypass
        is_admin = getattr(user.role, "value", user.role) == "admin"
        if is_admin:
            return True, "Admin entitlement granted.", cost

        if plan_id == "free":
            # Free tier: 1st website generation is free
            if operation in ("website_generation", "website_planning", "multipage_generation"):
                stmt = select(func.count(TrialHistory.id)).where(
                    TrialHistory.user_id == user.id,
                    TrialHistory.trial_type == "generation",
                )
                res = await self.db.execute(stmt)
                count = res.scalar() or 0
                if count < 1:
                    return True, "Initial free generation trial.", 0

            # Subsequent operations require purchased credits
            if available < cost:
                return (
                    False,
                    f"You have used your 1 free generation. This operation requires {cost} AI credits, but you have {available}. Please purchase credits or upgrade to Pro (150 credits/mo) or Extreme (1,000 credits/mo).",
                    cost,
                )
            return True, "Credits available.", cost

        elif plan_id == "pro":
            if available < cost:
                return (
                    False,
                    f"Your Pro monthly credits are depleted (available: {available}, required: {cost}). Please top up credits or wait for your next billing renewal.",
                    cost,
                )
            return True, "Pro credits available.", cost

        elif plan_id == "extreme":
            # Extreme tier MUST deduct from its 1,000 monthly credits!
            if available < cost:
                return (
                    False,
                    f"Your Extreme monthly credits are depleted (available: {available}, required: {cost}). Please top up discounted credits or wait for renewal.",
                    cost,
                )
            return True, "Extreme credits available.", cost

        return False, "Unrecognized plan entitlement.", cost

    async def deduct_ai_credits(
        self,
        user: User,
        operation: str,
        deployment_id: Optional[uuid.UUID] = None,
        project_id: Optional[str] = None,
        provider: str = "gemini",
        model_name: Optional[str] = None,
        credits_override: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[bool, str, int, Decimal]:
        """
        Deducts credits, writes to the immutable usage_ledger, and estimates provider costs.
        Returns: (success: bool, message: str, deducted_credits: int, estimated_cost: Decimal)
        """
        is_admin = getattr(user.role, "value", user.role) == "admin"
        sub = await self.get_or_create_user_subscription(user)
        plan_id = normalize_plan_id(sub.plan_id)
        cost = credits_override if credits_override is not None else get_operation_cost(operation)

        # Check if this is the free user's 1st website generation
        if not is_admin and plan_id == "free" and operation in ("website_generation", "website_planning", "multipage_generation"):
            stmt = select(func.count(TrialHistory.id)).where(
                TrialHistory.user_id == user.id,
                TrialHistory.trial_type == "generation",
            )
            res = await self.db.execute(stmt)
            if (res.scalar() or 0) < 1:
                # Record the 1st generation trial
                trial_rec = TrialHistory(
                    user_id=user.id,
                    trial_type="generation",
                    started_at=datetime.now(timezone.utc),
                    is_active=True,
                )
                self.db.add(trial_rec)
                cost = 0

        current_credits = user.ai_credits if user.ai_credits is not None else 0
        if not is_admin and cost > 0 and current_credits < cost:
            return False, f"Insufficient AI credits (have {current_credits}, need {cost}).", 0, Decimal("0.000000")

        # Deduct credits
        if not is_admin and cost > 0:
            user.ai_credits = max(0, current_credits - cost)
            self.db.add(user)

        # Calculate estimated provider cost
        unit_cost = ESTIMATED_PROVIDER_COSTS.get("gemini_flash_operation", Decimal("0.0015"))
        if model_name:
            clean_m = model_name.lower()
            if "gpt-4o-mini" in clean_m:
                unit_cost = ESTIMATED_PROVIDER_COSTS.get("openai_gpt4o_mini_operation", Decimal("0.0020"))
            elif "gpt-4o" in clean_m:
                unit_cost = ESTIMATED_PROVIDER_COSTS.get("openai_gpt4o_operation", Decimal("0.0250"))
            elif "claude" in clean_m or "sonnet" in clean_m:
                unit_cost = ESTIMATED_PROVIDER_COSTS.get("claude_sonnet_operation", Decimal("0.0200"))
            elif "flux" in clean_m or "dall-e" in clean_m or operation == "image_generation":
                unit_cost = ESTIMATED_PROVIDER_COSTS.get("flux_image_operation", Decimal("0.0350"))

        # Write to UsageLedger
        ledger_entry = UsageLedger(
            user_id=user.id,
            deployment_id=deployment_id,
            project_id=project_id,
            operation=operation,
            quantity=1.0,
            credits_consumed=cost,
            estimated_provider_cost=unit_cost,
            currency="USD",
            provider=provider,
            model_name=model_name or "gemini-1.5-flash",
            extra_metadata=metadata or {},
        )
        self.db.add(ledger_entry)
        await self.db.flush()

        return True, "Credits deducted successfully.", cost, unit_cost

    # -----------------------------------------------------------------------
    # DEPLOYMENT & HOSTING ENTITLEMENT ENFORCEMENT
    # -----------------------------------------------------------------------

    async def can_create_deployment(
        self,
        user: User,
        template_id: Optional[uuid.UUID] = None,
        template_slug: Optional[str] = None,
        is_custom_domain: bool = False,
    ) -> Tuple[bool, str]:
        """
        Validates deployment creation permissions before launching builds.
        Enforces:
        - Free: 1 trial deployment for 7 days. Permanent 1-trial-per-template history. Subdomain only.
        - Pro: max 3 deployment slots. 1 included hosted website. Custom domain for included site.
        - Extreme: fair-use slots. 3 included hosted websites. Custom domain for 3 included sites.
        """
        is_admin = getattr(user.role, "value", user.role) == "admin"
        if is_admin:
            return True, "Admin deployment approved."

        sub = await self.get_or_create_user_subscription(user)
        plan_id = normalize_plan_id(sub.plan_id)
        plan_cfg = get_plan_config(plan_id)

        # 1. Custom Domain Restriction
        if is_custom_domain and not plan_cfg["custom_domain_allowed"]:
            return (
                False,
                "Custom domain connection is not supported on the Free Starter tier. Upgrade to Pro (1 website) or Extreme (3 websites) to connect custom domains.",
            )

        # 2. Free Tier Specific Restrictions
        if plan_id == "free":
            # Enforce permanent 1-trial-per-template rule
            if template_id or template_slug:
                t_stmt = select(TrialHistory).where(
                    TrialHistory.user_id == user.id,
                    TrialHistory.trial_type == "deployment",
                    or_(
                        TrialHistory.template_id == template_id if template_id else False,
                        TrialHistory.template_slug == template_slug if template_slug else False,
                    ),
                )
                t_res = await self.db.execute(t_stmt)
                if t_res.scalar_one_or_none():
                    return (
                        False,
                        "Free Trial Policy: You have already used your 7-day free trial for this template. Free accounts may not trial the same template again. You can trial a different template or upgrade to Pro to unlock 3 permanent deployments.",
                    )

            # Check active trial deployment count (Free allows max 1 active trial deployment)
            active_dep_stmt = select(func.count(Deployment.id)).where(
                Deployment.user_id == user.id,
                Deployment.status.in_(["building", "live", "created", "queued"]),
            )
            active_res = await self.db.execute(active_dep_stmt)
            if (active_res.scalar() or 0) >= 1:
                return (
                    False,
                    "Free tier allows exactly 1 active trial deployment (7 days). Please upgrade to Pro for 3 active deployment slots or suspend your existing deployment.",
                )

            return True, "Eligible for 7-day free trial deployment."

        # 3. Pro Tier Restrictions
        elif plan_id == "pro":
            # Check deployment slots (max 3)
            active_dep_stmt = select(func.count(Deployment.id)).where(
                Deployment.user_id == user.id,
                Deployment.status.in_(["building", "live", "created", "queued"]),
            )
            active_res = await self.db.execute(active_dep_stmt)
            active_count = active_res.scalar() or 0
            if active_count >= plan_cfg["max_deployment_slots"]:
                return (
                    False,
                    f"Pro Plan quota reached: You have {active_count} of {plan_cfg['max_deployment_slots']} active deployment slots in use. Upgrade to Extreme for unlimited project slots or remove an unused deployment.",
                )

            return True, "Pro deployment slot available."

        # 4. Extreme Tier Restrictions
        elif plan_id == "extreme":
            # Check fair-use deployment updates frequency
            hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_builds_stmt = select(func.count(UsageLedger.id)).where(
                UsageLedger.user_id == user.id,
                UsageLedger.operation == "deployment_build",
                UsageLedger.created_at >= hour_ago,
            )
            r_res = await self.db.execute(recent_builds_stmt)
            if (r_res.scalar() or 0) > FAIR_USE_POLICY["max_deployment_updates_per_hour"]:
                return (
                    False,
                    "Fair-Use Protection: You have reached the hourly deployment rate limit (15 builds/hour). Please wait a few minutes before launching another build.",
                )

            return True, "Extreme deployment slot available."

        return False, "Unrecognized plan."

    async def record_deployment_trial(
        self,
        user_id: uuid.UUID,
        deployment_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
        template_slug: Optional[str] = None,
        trial_days: int = 7,
    ) -> TrialHistory:
        """Permanently records that a user started a 7-day trial for this template."""
        now = datetime.now(timezone.utc)
        record = TrialHistory(
            user_id=user_id,
            deployment_id=deployment_id,
            template_id=template_id,
            template_slug=template_slug,
            trial_type="deployment",
            started_at=now,
            expires_at=now + timedelta(days=trial_days),
            is_active=True,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    # -----------------------------------------------------------------------
    # AUTO-HEAL REGISTRATION & INCIDENT PERMISSIONS
    # -----------------------------------------------------------------------

    async def can_use_auto_heal(
        self, user: User, deployment_id: uuid.UUID
    ) -> Tuple[bool, str]:
        """
        Enforces Auto-Heal entitlements:
        - Free: disabled.
        - Pro: 1 explicitly registered site (persistent).
        - Extreme: up to 3 registered sites.
        - Periodic repair quotas (10/mo Pro, 30/mo Extreme).
        """
        is_admin = getattr(user.role, "value", user.role) == "admin"
        if is_admin:
            return True, "Admin Auto-Heal approved."

        sub = await self.get_or_create_user_subscription(user)
        plan_id = normalize_plan_id(sub.plan_id)
        plan_cfg = get_plan_config(plan_id)

        if not plan_cfg["auto_heal_allowed"]:
            return (
                False,
                "AI Auto-Heal is disabled on the Free Starter tier. Upgrade to Studio Pro (1 registered website) or Extreme (up to 3 websites) to enable autonomous healing.",
            )

        now = datetime.now(timezone.utc)
        period_start = sub.current_period_start or (now - timedelta(days=30))
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)

        # Check existing registration for this deployment
        reg_stmt = select(AutoHealRegistration).where(
            AutoHealRegistration.user_id == user.id,
            AutoHealRegistration.deployment_id == deployment_id,
            AutoHealRegistration.active.is_(True),
        )
        res = await self.db.execute(reg_stmt)
        existing_reg = res.scalar_one_or_none()

        if not existing_reg:
            # Need to register this site: check site limit
            count_stmt = select(func.count(AutoHealRegistration.id)).where(
                AutoHealRegistration.user_id == user.id,
                AutoHealRegistration.active.is_(True),
            )
            c_res = await self.db.execute(count_stmt)
            active_registered = c_res.scalar() or 0

            max_allowed = plan_cfg["auto_heal_sites_limit"]
            if active_registered >= max_allowed:
                if plan_id == "pro":
                    return (
                        False,
                        "Pro Plan Policy: AI Auto-Heal is already registered to 1 website. Pro accounts may register exactly 1 website. Upgrade to Extreme to protect up to 3 websites.",
                    )
                else:
                    return (
                        False,
                        f"Extreme Plan Policy: You have reached your allowance of {max_allowed} registered Auto-Heal websites.",
                    )

            # Register site now
            dep_res = await self.db.execute(select(Deployment.site_id).where(Deployment.id == deployment_id))
            site_id = dep_res.scalar_one_or_none() or "SITE"

            new_reg = AutoHealRegistration(
                user_id=user.id,
                deployment_id=deployment_id,
                site_id=site_id,
                active=True,
                repair_count_current_period=0,
                period_start=period_start,
                period_end=sub.current_period_end,
            )
            self.db.add(new_reg)
            await self.db.flush()
            existing_reg = new_reg

        # Check per-period repair limit
        period_limit = plan_cfg["auto_heal_repairs_per_period"]
        if existing_reg.repair_count_current_period >= period_limit:
            return (
                False,
                f"Auto-Heal Quota: You have reached the maximum allowance of {period_limit} autonomous repairs for this billing cycle.",
            )

        return True, "Auto-Heal entitlement verified."

    async def record_auto_heal_execution(
        self, user: User, deployment_id: uuid.UUID
    ) -> None:
        """Increments repair count and records usage cost."""
        now = datetime.now(timezone.utc)
        reg_stmt = select(AutoHealRegistration).where(
            AutoHealRegistration.user_id == user.id,
            AutoHealRegistration.deployment_id == deployment_id,
            AutoHealRegistration.active.is_(True),
        )
        res = await self.db.execute(reg_stmt)
        reg = res.scalar_one_or_none()
        if reg:
            reg.repair_count_current_period += 1
            reg.last_healed_at = now
            self.db.add(reg)

        # Record in UsageLedger
        cost = ESTIMATED_PROVIDER_COSTS.get("auto_heal_avg_cost", Decimal("0.0150"))
        ledger_entry = UsageLedger(
            user_id=user.id,
            deployment_id=deployment_id,
            operation="auto_heal",
            quantity=1.0,
            credits_consumed=get_operation_cost("auto_heal"),
            estimated_provider_cost=cost,
            currency="USD",
            provider="gemini",
            model_name="gemini-1.5-flash",
            extra_metadata={"autonomous": True},
        )
        self.db.add(ledger_entry)
        await self.db.flush()

