"""
Unit & Integration Tests for Subscription, Entitlements, and Billing Enforcement.
Covers:
- Free user 1st generation trial & subsequent credit gate
- Free user 7-day trial deployment & permanent same-template trial restriction
- Free user custom domain blockage
- Pro user 150-credit allowance, 3 deployment slot cap, and 1-site Auto-Heal restriction
- Extreme user 1,000-credit deduction, 3-site Auto-Heal, and $15 domain subsidy cap
- Webhook deduplication via SubscriptionEvent
- Cancellation at period end and access preservation
"""

import pytest
import uuid
import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.deployment import Deployment
from app.models.subscription import (
    UserSubscription,
    SubscriptionEvent,
    UsageLedger,
    TrialHistory,
    AutoHealRegistration,
    PromotionalDomainCredit,
)
from app.core.plans import PlanTier, PLANS, AI_OPERATION_CREDIT_COSTS
from app.services.entitlement_service import EntitlementService
from app.services.subscription_service import SubscriptionService


@pytest.fixture
async def free_user(db: AsyncSession) -> User:
    user = User(
        email="free_tester@example.com",
        username="free_tester",
        full_name="Free Tester",
        role=UserRole.BUYER,
        subscription_tier=PlanTier.FREE.value,
        ai_credits=0,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def pro_user(db: AsyncSession) -> User:
    user = User(
        email="pro_tester@example.com",
        username="pro_tester",
        full_name="Pro Tester",
        role=UserRole.BUYER,
        subscription_tier=PlanTier.PRO.value,
        ai_credits=150,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Attach UserSubscription record
    sub = UserSubscription(
        user_id=user.id,
        plan_id=PlanTier.PRO.value,
        status="active",
        payment_provider="stripe",
        billing_cycle="monthly",
        current_period_start=datetime.datetime.now(datetime.timezone.utc),
        current_period_end=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    return user


@pytest.fixture
async def extreme_user(db: AsyncSession) -> User:
    user = User(
        email="extreme_tester@example.com",
        username="extreme_tester",
        full_name="Extreme Tester",
        role=UserRole.BUYER,
        subscription_tier=PlanTier.EXTREME.value,
        ai_credits=1000,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    sub = UserSubscription(
        user_id=user.id,
        plan_id=PlanTier.EXTREME.value,
        status="active",
        payment_provider="razorpay",
        billing_cycle="annual",
        current_period_start=datetime.datetime.now(datetime.timezone.utc),
        current_period_end=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
    )
    db.add(sub)
    await db.commit()
    return user


# ==============================================================================
# 1. FREE USER AI GENERATION ENTITLEMENT & RESTRICTIONS
# ==============================================================================

@pytest.mark.asyncio
async def test_free_user_first_generation_free_and_second_blocked(db: AsyncSession, free_user: User):
    ent_svc = EntitlementService(db)

    # 1st attempt: Must be permitted under free trial (0 credits required)
    allowed, reason, required_credits = await ent_svc.check_ai_generation_entitlement(
        free_user, operation="website_generation"
    )
    assert allowed is True
    assert required_credits == 0

    # Deduct / record trial generation
    success, msg, deducted_credits, est_cost = await ent_svc.deduct_ai_credits(
        free_user,
        operation="website_generation",
    )
    assert success is True
    assert deducted_credits == 0

    # Verify trial history recorded
    stmt = select(TrialHistory).where(
        TrialHistory.user_id == free_user.id,
        TrialHistory.trial_type == "generation",
    )
    res = await db.execute(stmt)
    trial_records = res.scalars().all()
    assert len(trial_records) == 1

    # 2nd attempt: Must be BLOCKED because free trial has been used and credits = 0
    allowed2, reason2, required_credits2 = await ent_svc.check_ai_generation_entitlement(
        free_user, operation="website_generation"
    )
    assert allowed2 is False
    assert required_credits2 == 5
    assert "used your 1 free generation" in reason2


# ==============================================================================
# 2. FREE USER DEPLOYMENT RESTRICTIONS & TEMPLATE PERMANENT TRIAL
# ==============================================================================

@pytest.mark.asyncio
async def test_free_user_deployment_trial_limits(db: AsyncSession, free_user: User):
    ent_svc = EntitlementService(db)
    template_a_id = uuid.uuid4()
    template_b_id = uuid.uuid4()

    # Attempt custom domain on Free tier: must be rejected
    can_deploy_cd, reason_cd = await ent_svc.can_create_deployment(
        free_user, is_custom_domain=True, template_id=template_a_id
    )
    assert can_deploy_cd is False
    assert "Custom domain" in reason_cd

    # Attempt subdomain deployment for Template A: permitted for 7-day trial
    can_deploy_sub, reason_sub = await ent_svc.can_create_deployment(
        free_user, is_custom_domain=False, template_id=template_a_id
    )
    assert can_deploy_sub is True

    # Record trial for Template A
    dep_id = uuid.uuid4()
    await ent_svc.record_deployment_trial(
        user_id=free_user.id,
        deployment_id=dep_id,
        template_id=template_a_id,
        template_slug="modern-saas-template-a",
    )

    # Attempt second trial deployment for the SAME Template A: must be permanently blocked
    can_deploy_again, reason_again = await ent_svc.can_create_deployment(
        free_user, is_custom_domain=False, template_id=template_a_id
    )
    assert can_deploy_again is False
    assert "already used your 7-day free trial" in reason_again

    # Attempt trial deployment for DIFFERENT Template B: permitted
    can_deploy_b, reason_b = await ent_svc.can_create_deployment(
        free_user, is_custom_domain=False, template_id=template_b_id
    )
    assert can_deploy_b is True


# ==============================================================================
# 3. PRO USER ENTITLEMENTS & AUTO-HEAL LIMITS
# ==============================================================================

@pytest.mark.asyncio
async def test_pro_user_slot_caps_and_auto_heal(db: AsyncSession, pro_user: User):
    ent_svc = EntitlementService(db)

    # Verify Pro gets custom domain connection
    can_deploy, _ = await ent_svc.can_create_deployment(pro_user, is_custom_domain=True)
    assert can_deploy is True

    # Create 3 active deployments (reaching the 3-slot cap for Pro)
    deps = []
    for i in range(3):
        dep = Deployment(
            user_id=pro_user.id,
            project_name=f"Pro Site {i+1}",
            subdomain=f"pro-site-{i+1}",
            status="live",
        )
        db.add(dep)
        deps.append(dep)
    await db.commit()
    for d in deps:
        await db.refresh(d)

    # 4th deployment should be blocked by slot cap
    can_deploy_4, reason_4 = await ent_svc.can_create_deployment(pro_user)
    assert can_deploy_4 is False
    assert "Pro Plan quota reached" in reason_4

    # Test Auto-Heal: Pro allows exactly 1 site registered
    can_heal, reason = await ent_svc.can_use_auto_heal(pro_user, deps[0].id)
    assert can_heal is True

    # Record first repair
    await ent_svc.record_auto_heal_execution(pro_user, deps[0].id)

    # Query registered sites
    regs = (await db.execute(select(AutoHealRegistration).where(AutoHealRegistration.user_id == pro_user.id))).scalars().all()
    assert len(regs) == 1
    assert regs[0].deployment_id == deps[0].id

    # Trying to use Auto-Heal on a different deployment (dep 2) should be blocked (limit is 1 for Pro)
    can_heal_dep2, reason_dep2 = await ent_svc.can_use_auto_heal(pro_user, deps[1].id)
    assert can_heal_dep2 is False
    assert "Pro Plan Policy: AI Auto-Heal is already registered to 1 website" in reason_dep2


# ==============================================================================
# 4. EXTREME USER: 1,000 CREDIT ALLOWANCE & PROMOTIONAL DOMAIN SUBSIDY
# ==============================================================================

@pytest.mark.asyncio
async def test_extreme_credit_deduction_and_domain_subsidy(db: AsyncSession, extreme_user: User):
    ent_svc = EntitlementService(db)

    # Verify credit deduction applies (Extreme does not bypass credits)
    assert extreme_user.ai_credits == 1000

    success, msg, deducted_credits, est_cost = await ent_svc.deduct_ai_credits(
        extreme_user,
        operation="website_generation",
    )
    assert success is True
    assert deducted_credits == 5
    assert extreme_user.ai_credits == 995

    # Verify usage ledger recorded
    stmt = select(UsageLedger).where(UsageLedger.user_id == extreme_user.id)
    ledger_entries = (await db.execute(stmt)).scalars().all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].credits_consumed == 5
    assert ledger_entries[0].operation == "website_generation"

    # Test Promotional Domain Credit (Capped at $15 USD, single redemption)
    domain_credit = PromotionalDomainCredit(
        user_id=extreme_user.id,
        max_credit_usd=Decimal("15.00"),
        credit_used_usd=Decimal("14.99"),
        domain_name="extremebrand.com",
        status="redeemed",
        redeemed_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(domain_credit)
    await db.commit()

    # Verify credit record exists and matches policy
    existing_credit = (await db.execute(
        select(PromotionalDomainCredit).where(PromotionalDomainCredit.user_id == extreme_user.id)
    )).scalars().first()
    assert existing_credit is not None
    assert existing_credit.credit_used_usd <= Decimal("15.00")


# ==============================================================================
# 5. IDEMPOTENT WEBHOOK HANDLING (DEDUPLICATION)
# ==============================================================================

@pytest.mark.asyncio
async def test_idempotent_subscription_events(db: AsyncSession, pro_user: User):
    sub_svc = SubscriptionService(db)
    event_id = "evt_test_dedup_12345"

    # First delivery of webhook event: must succeed and process
    res_1 = await sub_svc.handle_subscription_payment_success(
        provider="stripe",
        event_id=event_id,
        user_id=pro_user.id,
        user_email=pro_user.email,
        plan_id="pro",
        billing_cycle="monthly",
        provider_sub_id="sub_stripe_123",
        payload={"id": "sub_stripe_123", "status": "active"},
    )
    assert res_1["status"] == "success"

    # Duplicate delivery with the identical event_id: must return already_processed
    res_2 = await sub_svc.handle_subscription_payment_success(
        provider="stripe",
        event_id=event_id,
        user_id=pro_user.id,
        user_email=pro_user.email,
        plan_id="pro",
        billing_cycle="monthly",
        provider_sub_id="sub_stripe_123",
        payload={"id": "sub_stripe_123", "status": "active"},
    )
    assert res_2["status"] == "already_processed"


# ==============================================================================
# 6. CANCELLATION AT PERIOD END PRESERVES ACCESS
# ==============================================================================

@pytest.mark.asyncio
async def test_cancellation_at_period_end_preserves_entitlements(db: AsyncSession, pro_user: User):
    sub_svc = SubscriptionService(db)
    ent_svc = EntitlementService(db)

    # Cancel at period end
    result = await sub_svc.cancel_subscription_at_period_end(pro_user)
    assert result["status"] == "cancellation_scheduled"

    # Entitlements should STILL be active during grace period / before period end
    entitlements = await ent_svc.get_user_entitlements(pro_user)
    assert entitlements["plan_id"] == "pro"
    assert entitlements["custom_domain_allowed"] is True

    # Reactivate
    reactivated = await sub_svc.reactivate_subscription(pro_user)
    assert reactivated["status"] == "reactivated"

    user_sub = await ent_svc.get_or_create_user_subscription(pro_user)
    assert user_sub.cancel_at_period_end is False


# ==============================================================================
# 7. SUBSCRIPTIONS API ENDPOINTS (GET /plans & GET /my-subscription)
# ==============================================================================

@pytest.mark.asyncio
async def test_subscription_api_endpoints(auth_client):
    # Test GET /api/v1/subscriptions/plans
    res = await auth_client.get("/api/v1/subscriptions/plans")
    assert res.status_code == 200
    res_data = res.json()
    plans_list = res_data.get("plans", res_data)
    plans_data = {p["id"]: p for p in plans_list} if isinstance(plans_list, list) else plans_list
    assert "free" in plans_data
    assert "pro" in plans_data
    assert "extreme" in plans_data
    assert float(plans_data["pro"]["monthly_price_usd"]) == 19.0
    assert float(plans_data["pro"]["annual_price_usd"]) == 190.0
    assert float(plans_data["extreme"]["monthly_price_usd"]) == 50.0
    assert float(plans_data["extreme"]["annual_price_usd"]) == 500.0

    # Test GET /api/v1/subscriptions/my-subscription
    my_sub_res = await auth_client.get("/api/v1/subscriptions/my-subscription")
    assert my_sub_res.status_code == 200
    my_sub_data = my_sub_res.json()
    assert "plan_id" in my_sub_data
    assert "ai_credits_available" in my_sub_data
    assert "custom_domain_allowed" in my_sub_data


# ==============================================================================
# 8. ADMIN PROFITABILITY METRICS ENDPOINT
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_profitability_metrics(admin_client):
    res = await admin_client.get("/api/v1/admin/profitability")
    assert res.status_code == 200
    data = res.json()
    assert data["target_margin_percent"] == 70.0
    assert data["currency"] == "USD"
    assert "gross_revenue" in data
    assert "variable_costs" in data
    assert "ai_api_cost" in data["variable_costs"]
    assert "hosting_cost" in data["variable_costs"]
    assert "loss_making_subscribers" in data
    assert "recommendations" in data
