"""Tests for domain auto-renewal authority, registrar sync, and automated debit collection."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, Domain
from app.models.subscription import SubscriptionEvent, UsageLedger
from app.models.user import User, UserRole
from app.services.domain_renewal_service import domain_renewal_service


@pytest.fixture
async def free_user(db: AsyncSession) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"domain_user_{uid}@example.com",
        username=f"domain_user_{uid}",
        full_name="Domain Renewal Tester",
        role=UserRole.BUYER,
        subscription_tier="free",
        ai_credits=0,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_domain_auto_renew_toggle_authority(db: AsyncSession, free_user: User):
    """Test user granting and revoking auto-renewal & debit authority."""
    domain_name = f"autorenew-test-{uuid.uuid4().hex[:6]}.com"
    domain = Domain(
        user_id=free_user.id,
        domain=domain_name,
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=False,
        registrar_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        renewal_price_minor=1299,
        price_currency="USD",
    )
    db.add(domain)
    await db.commit()

    # 1. Grant Authority (Enable Auto-Renew)
    grant_res = await domain_renewal_service.toggle_auto_renew(
        user=free_user,
        domain_name=domain_name,
        enabled=True,
        db=db,
    )
    assert grant_res["success"] is True
    assert grant_res["auto_renew"] is True
    assert "enabled" in grant_res["message"]

    # Verify DB state
    await db.refresh(domain)
    assert domain.auto_renew is True

    # 2. Revoke Authority (Disable Auto-Renew)
    revoke_res = await domain_renewal_service.toggle_auto_renew(
        user=free_user,
        domain_name=domain_name,
        enabled=False,
        db=db,
    )
    assert revoke_res["success"] is True
    assert revoke_res["auto_renew"] is False
    assert "disabled" in revoke_res["message"]

    await db.refresh(domain)
    assert domain.auto_renew is False


@pytest.mark.asyncio
async def test_domain_auto_renewal_blocked_without_authority(db: AsyncSession, free_user: User):
    """Domains without customer authority must NOT be auto-renewed or debited."""
    domain_name = f"no-auth-{uuid.uuid4().hex[:6]}.com"
    original_expiry = datetime.now(timezone.utc) + timedelta(days=15)
    domain = Domain(
        user_id=free_user.id,
        domain=domain_name,
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=False,  # No authority granted
        registrar_expires_at=original_expiry,
        renewal_price_minor=1299,
        price_currency="USD",
    )
    db.add(domain)
    await db.commit()

    # Execute renewal without force
    res = await domain_renewal_service.execute_domain_renewal(
        domain=domain,
        user=free_user,
        db=db,
        force=False,
    )
    assert res["success"] is False
    assert "not granted auto-renewal authority" in res["error"]

    # Expiry date should NOT change
    await db.refresh(domain)
    dom_exp = domain.registrar_expires_at.replace(tzinfo=timezone.utc) if domain.registrar_expires_at.tzinfo is None else domain.registrar_expires_at
    assert abs((dom_exp - original_expiry).total_seconds()) < 2


@pytest.mark.asyncio
async def test_domain_auto_renewal_execution_with_authority(db: AsyncSession, free_user: User):
    """Domains with customer authority automatically debit fee and extend expiration by 1 year."""
    domain_name = f"authorized-renew-{uuid.uuid4().hex[:6]}.com"
    initial_expiry = datetime.now(timezone.utc) + timedelta(days=5)
    domain = Domain(
        user_id=free_user.id,
        domain=domain_name,
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=True,  # Authority granted!
        registrar_expires_at=initial_expiry,
        renewal_price_minor=1299,
        price_currency="USD",
    )
    db.add(domain)
    await db.commit()

    # Execute renewal
    res = await domain_renewal_service.execute_domain_renewal(
        domain=domain,
        user=free_user,
        db=db,
        force=False,
    )
    assert res["success"] is True
    assert res["amount_debited"] == 12.99
    assert res["currency"] == "USD"
    assert "renewed for 1 year" in res["message"]

    # Verify expiration extended by 365 days
    await db.refresh(domain)
    dom_exp = domain.registrar_expires_at.replace(tzinfo=timezone.utc) if domain.registrar_expires_at.tzinfo is None else domain.registrar_expires_at
    assert dom_exp > initial_expiry + timedelta(days=360)

    # Verify audit event in subscription_events
    ev_stmt = select(SubscriptionEvent).where(
        SubscriptionEvent.user_id == free_user.id,
        SubscriptionEvent.provider_event_type == "domain.auto_renew.collected_and_renewed",
    )
    ev_res = await db.execute(ev_stmt)
    event = ev_res.scalar_one_or_none()
    assert event is not None
    assert event.payload["domain"] == domain_name


@pytest.mark.asyncio
async def test_domain_batch_auto_renewal_scanner(db: AsyncSession, free_user: User):
    """Batch scanner finds domains expiring within 30 days and auto-renews only authorized ones."""
    domain_due = Domain(
        user_id=free_user.id,
        domain=f"due-batch-{uuid.uuid4().hex[:6]}.com",
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=True,  # Authorized!
        registrar_expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        renewal_price_minor=1099,
        price_currency="USD",
    )
    domain_not_due = Domain(
        user_id=free_user.id,
        domain=f"far-batch-{uuid.uuid4().hex[:6]}.com",
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=True,
        registrar_expires_at=datetime.now(timezone.utc) + timedelta(days=200),  # Not due
        renewal_price_minor=1099,
        price_currency="USD",
    )
    domain_unauthorized = Domain(
        user_id=free_user.id,
        domain=f"unauth-batch-{uuid.uuid4().hex[:6]}.com",
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        auto_renew=False,  # Due but not authorized!
        registrar_expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        renewal_price_minor=1099,
        price_currency="USD",
    )
    db.add_all([domain_due, domain_not_due, domain_unauthorized])
    await db.commit()

    # Run batch renewal scanner
    results = await domain_renewal_service.process_due_renewals(db)
    processed_domains = [r["domain"] for r in results]

    # Only domain_due should have been renewed
    assert domain_due.domain in processed_domains
    assert domain_not_due.domain not in processed_domains
    assert domain_unauthorized.domain not in processed_domains


@pytest.mark.asyncio
async def test_extreme_domain_purchase_credit_decimal_initialization(db: AsyncSession, free_user: User):
    """Test that PromotionalDomainCredit can be initialized with Decimal values without NameError."""
    from app.models.subscription import PromotionalDomainCredit

    promo_credit_applied_minor = 1299
    promo_rec = PromotionalDomainCredit(
        user_id=free_user.id,
        max_credit_usd=Decimal("15.00"),
        credit_used_usd=Decimal(promo_credit_applied_minor) / Decimal(100),
        domain_name="extreme-perk-test.com",
        status="redeemed",
        redeemed_at=datetime.now(timezone.utc),
    )
    db.add(promo_rec)
    await db.commit()
    await db.refresh(promo_rec)

    assert promo_rec.max_credit_usd == Decimal("15.00")
    assert promo_rec.credit_used_usd == Decimal("12.99")
    assert promo_rec.domain_name == "extreme-perk-test.com"

