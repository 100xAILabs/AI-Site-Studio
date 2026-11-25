import os
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import AI_OPERATION_CREDIT_COSTS
from app.core.security import create_access_token
from app.models.category import Category
from app.models.deployment import Deployment
from app.models.license import License, LicenseType
from app.models.order import Order, OrderItem, OrderStatus
from app.models.template import Template, TemplateFramework, TemplateStatus
from app.models.user import User, UserRole
from app.schemas.deployment import DeploymentResponse
from app.services.deployment_healing_service import DeploymentHealingService
from app.services.dns_verification_service import PROTECTED_SYSTEM_DOMAINS
from app.services.entitlement_service import EntitlementService
from tests.conftest import TestingSessionLocal


async def _seed_user(
    db: AsyncSession,
    email: str,
    username: str,
    *,
    tier: str = "free",
    credits: int = 10,
    role: UserRole = UserRole.BUYER,
) -> User:
    user = User(
        email=email,
        username=username,
        full_name=username.title(),
        role=role,
        subscription_tier=tier,
        ai_credits=credits,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    tok = create_access_token(
        subject=str(user.id),
        role=getattr(user.role, "value", str(user.role)),
        tv=getattr(user, "token_version", 0),
    )
    return {"Authorization": f"Bearer {tok}"}


async def _seed_template_and_license(
    db: AsyncSession,
    owner: User,
    *,
    slug_suffix: str,
    license_key: str,
) -> tuple[Template, License]:
    category = Category(
        name=f"Category-{slug_suffix}",
        slug=f"cat-{slug_suffix}",
        is_active=True,
    )
    db.add(category)
    await db.flush()

    tmpl = Template(
        title=f"Template {slug_suffix}",
        slug=f"template-{slug_suffix}",
        short_description="Test template",
        description="Test template description",
        price=Decimal("29.00"),
        thumbnail_url="https://example.com/thumb.png",
        category_id=category.id,
        framework=TemplateFramework.HTML,
        status=TemplateStatus.PUBLISHED,
        seller_id=owner.id,
        is_marketplace=True,
        template_origin="marketplace",
    )
    db.add(tmpl)
    await db.flush()

    order = Order(
        user_id=owner.id,
        order_number=f"ASS-ORD-{slug_suffix[:8].upper()}",
        status=OrderStatus.COMPLETED,
        subtotal=Decimal("29.00"),
        total=Decimal("29.00"),
        extra_metadata={"buyer_email": owner.email},
    )
    db.add(order)
    await db.flush()

    item = OrderItem(
        order_id=order.id,
        template_id=tmpl.id,
        quantity=1,
        price=Decimal("29.00"),
        license_type="regular",
    )
    db.add(item)

    lic = License(
        user_id=owner.id,
        template_id=tmpl.id,
        order_id=order.id,
        license_key=license_key,
        license_type=LicenseType.REGULAR,
        is_active=True,
        notes=f"Project token {license_key} for {tmpl.id}",
    )
    db.add(lic)
    await db.commit()
    await db.refresh(tmpl)
    await db.refresh(lic)
    return tmpl, lic


@pytest.mark.asyncio
async def test_cross_tenant_deployment_key_hijack_blocked(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Attacker cannot claim another user's license using prefix or exact key probes."""
    from app.services.deployment_service import DeploymentService

    monkeypatch.setattr(DeploymentService, "run_deployment_pipeline", AsyncMock())

    victim = await _seed_user(db, "victim@example.com", "victimuser")
    attacker = await _seed_user(db, "attacker@example.com", "attackeruser", credits=50)

    tmpl, lic = await _seed_template_and_license(
        db,
        victim,
        slug_suffix=uuid.uuid4().hex[:8],
        license_key="site-victim-secret-key01",
    )

    # Probe both import-by-key and activate-key as attacker
    for probe_key in ("LIC-", "site-", lic.license_key):
        resp_import = await client.post(
            "/api/v1/deployments/import-by-key",
            json={"key": probe_key, "project_name": "HijackAttempt"},
            headers=_auth_headers(attacker),
        )
        assert resp_import.status_code in (403, 404)

        resp_activate = await client.post(
            "/api/v1/licenses/activate-key",
            json={"key": probe_key},
            headers=_auth_headers(attacker),
        )
        assert resp_activate.status_code in (403, 404)

    # Even sending victim's exact license_id / template_id as attacker must fail
    resp_id_probe = await client.post(
        "/api/v1/licenses/activate-key",
        json={"license_id": str(lic.id), "template_id": str(tmpl.id)},
        headers=_auth_headers(attacker),
    )
    assert resp_id_probe.status_code in (403, 404)

    res_deps = await db.execute(select(Deployment).where(Deployment.user_id == attacker.id))
    assert res_deps.scalars().all() == []

    # Legitimate owner can activate their own license via license_id
    resp_owner = await client.post(
        "/api/v1/licenses/activate-key",
        json={"license_id": str(lic.id)},
        headers=_auth_headers(victim),
    )
    assert resp_owner.status_code == 200
    assert resp_owner.json()["template_id"] == str(tmpl.id)


@pytest.mark.asyncio
async def test_paid_topup_tokens_preserved_for_free_user(db: AsyncSession):
    """Standalone paid token pack credits must survive Free-tier entitlement checks."""
    user = await _seed_user(
        db,
        "tokenbuyer@example.com",
        "tokenbuyer",
        tier="free",
        credits=60,
    )

    topup_order = Order(
        user_id=user.id,
        order_number="ASS-TOPUP-0001",
        status=OrderStatus.COMPLETED,
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
        notes="AI Compute Top-Up: 50 credits",
        extra_metadata={
            "type": "ai_credits",
            "pack_id": "tokens_50",
            "credits_to_add": 50,
            "credits_credited": True,
        },
    )
    db.add(topup_order)
    await db.commit()

    ent = EntitlementService(db)
    summary = await ent.get_user_entitlements(user)
    await db.refresh(user)

    assert summary["available_credits"] == 60
    assert summary["ai_credits_available"] == 60
    assert user.ai_credits == 60

    # Without a paid top-up order, stale inflated free credits remain capped at 10
    free_unpaid = await _seed_user(
        db,
        "unpaidcap@example.com",
        "unpaidcap",
        tier="free",
        credits=60,
    )
    summary_unpaid = await ent.get_user_entitlements(free_unpaid)
    await db.refresh(free_unpaid)
    assert summary_unpaid["available_credits"] == 10
    assert summary_unpaid["ai_credits_available"] == 10
    assert free_unpaid.ai_credits == 10


@pytest.mark.asyncio
async def test_token_funded_deployment_without_subscription(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Free-tier user with paid tokens can deploy without a subscription using Studio tokens."""
    from app.services.deployment_service import DeploymentService

    monkeypatch.setattr(DeploymentService, "run_deployment_pipeline", AsyncMock())

    deploy_cost = AI_OPERATION_CREDIT_COSTS["site_deployment"]
    assert deploy_cost == 10

    buyer = await _seed_user(
        db,
        "tokendeploy@example.com",
        "tokendeploy",
        tier="free",
        credits=25,
    )
    tmpl, _ = await _seed_template_and_license(
        db,
        buyer,
        slug_suffix=uuid.uuid4().hex[:8],
        license_key="site-token-deploy-key01",
    )

    topup_order = Order(
        user_id=buyer.id,
        order_number="ASS-TOKDEP-001",
        status=OrderStatus.COMPLETED,
        subtotal=Decimal("10.00"),
        total=Decimal("10.00"),
        extra_metadata={"type": "ai_credits", "pack_id": "tokens_50", "credits_to_add": 50},
    )
    db.add(topup_order)

    # Seed one active prior custom deployment so Free-tier 1-site cap blocks non-token deploys
    prior_dep = Deployment(
        user_id=buyer.id,
        template_id=None,
        site_id="SITE-PRIOR01",
        project_name="First Free Site",
        subdomain="first-free-site-01",
        status="live",
    )
    db.add(prior_dep)
    await db.commit()

    ent = EntitlementService(db)
    blocked, _ = await ent.can_create_deployment(buyer, template_id=None, use_tokens=False)
    assert blocked is False

    allowed, _ = await ent.can_create_deployment(buyer, template_id=None, use_tokens=True)
    assert allowed is True

    resp = await client.post(
        "/api/v1/deployments",
        json={
            "project_name": "Second Token Site",
            "provider": "local",
            "template_id": str(tmpl.id),
            "accepted_hosting_terms": True,
            "use_tokens": True,
        },
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201, resp.text
    await db.refresh(buyer)
    assert buyer.ai_credits == 25 - deploy_cost


@pytest.mark.asyncio
async def test_site_router_blocks_dotfiles_and_escapes_creator_badge(
    client: AsyncClient,
    db: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """site_router must block .env dotfiles with 403 and sanitize creator badge XSS."""
    from app.api.v1.routes import site_router

    monkeypatch.setattr(site_router, "_DEPLOYMENTS_ROOT", tmp_path)
    monkeypatch.setattr(site_router, "AsyncSessionLocal", TestingSessionLocal)
    site_router.invalidate_site_cache(site_id="SITE-XSS01", subdomain="testxss")

    site_dir = tmp_path / "SITE-XSS01" / "current"
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text("<html><body><p>Clean Site</p></body></html>", encoding="utf-8")
    (site_dir / ".env").write_text("STRIPE_SECRET_KEY=sk_live_donotexpose", encoding="utf-8")

    owner = await _seed_user(db, "xssowner@example.com", "xssowner")
    dep = Deployment(
        user_id=owner.id,
        site_id="SITE-XSS01",
        project_name="XSS Test Site",
        subdomain="testxss",
        status="live",
        is_suspended=False,
        extra_metadata={
            "creator_branding": {
                "brand_name": 'Evil <script>alert(1)</script>',
                "creator_slug": 'bad" onclick="alert(1)',
                "logo_url": "javascript:alert(1)",
            }
        },
    )
    db.add(dep)
    await db.commit()

    try:
        env_resp = await client.get("/sites/testxss/.env")
        assert env_resp.status_code == 403
        assert "sk_live_donotexpose" not in env_resp.text

        html_resp = await client.get("/sites/testxss/")
        assert html_resp.status_code == 200
        assert "<script>alert(1)</script>" not in html_resp.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_resp.text
        assert 'src="javascript:' not in html_resp.text
        assert 'onclick="' not in html_resp.text
    finally:
        site_router.invalidate_site_cache(site_id="SITE-XSS01", subdomain="testxss")


def test_healing_service_blocks_env_and_sibling_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """read_file must reject .env files and sibling-directory prefix collisions."""
    from app.services import deployment_healing_service as dhs

    monkeypatch.setattr(dhs, "_DEPLOYMENTS_ROOT", tmp_path)
    site_current = tmp_path / "SITE-HEAL01" / "current"
    site_current.mkdir(parents=True, exist_ok=True)
    (site_current / ".env").write_text("SECRET=123", encoding="utf-8")
    (site_current / "index.html").write_text("<h1>OK</h1>", encoding="utf-8")

    sibling_secret = tmp_path / "SITE-HEAL01" / "current_secret"
    sibling_secret.mkdir(parents=True, exist_ok=True)
    (sibling_secret / "leak.txt").write_text("TOP_SECRET", encoding="utf-8")

    svc = DeploymentHealingService(None)  # type: ignore[arg-type]

    ok_env, _, _ = svc.read_file("SITE-HEAL01", ".env")
    assert ok_env is False

    ok_sibling, _, _ = svc.read_file("SITE-HEAL01", "../current_secret/leak.txt")
    assert ok_sibling is False

    ok_index, content, _ = svc.read_file("SITE-HEAL01", "index.html")
    assert ok_index is True
    assert "<h1>OK</h1>" in content


def test_deployment_response_masks_sensitive_env_vars():
    """DeploymentResponse must mask secrets/keys/URLs while keeping public env vars intact."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    resp = DeploymentResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "project_name": "Masked Site",
            "provider": "local",
            "status": "live",
            "current_version": "v1.0",
            "subdomain": "masked-site-01",
            "env_vars": {
                "STRIPE_SECRET_KEY": "sk_live_supersecret",
                "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
                "NEXT_PUBLIC_SITE_NAME": "Site Studio",
            },
            "is_suspended": False,
            "created_at": now,
            "updated_at": now,
        }
    )

    assert resp.env_vars is not None
    assert resp.env_vars["STRIPE_SECRET_KEY"] == "********"
    assert resp.env_vars["DATABASE_URL"] == "********"
    assert resp.env_vars["NEXT_PUBLIC_SITE_NAME"] == "Site Studio"


@pytest.mark.asyncio
async def test_add_custom_domain_guards_free_tier_and_protected_domains(
    client: AsyncClient,
    db: AsyncSession,
):
    """add_custom_domain must reject Free users and protected platform domains."""
    free_user = await _seed_user(db, "freedomain@example.com", "freedomain", tier="free")
    pro_user = await _seed_user(db, "prodomain@example.com", "prodomain", tier="pro")

    free_dep = Deployment(
        user_id=free_user.id,
        site_id="SITE-DOMFREE",
        project_name="Free Domain Site",
        subdomain="free-dom-01",
        status="live",
    )
    pro_dep = Deployment(
        user_id=pro_user.id,
        site_id="SITE-DOMPRO",
        project_name="Pro Domain Site",
        subdomain="pro-dom-01",
        status="live",
    )
    db.add_all([free_dep, pro_dep])
    await db.commit()
    await db.refresh(free_dep)
    await db.refresh(pro_dep)

    resp_free = await client.post(
        f"/api/v1/deployments/{free_dep.id}/domains",
        json={"domain": "custom-free-test.example.com"},
        headers=_auth_headers(free_user),
    )
    assert resp_free.status_code == 403

    protected = next(iter(PROTECTED_SYSTEM_DOMAINS))
    resp_protected = await client.post(
        f"/api/v1/deployments/{pro_dep.id}/domains",
        json={"domain": protected},
        headers=_auth_headers(pro_user),
    )
    assert resp_protected.status_code == 403

    resp_ok = await client.post(
        f"/api/v1/deployments/{pro_dep.id}/domains",
        json={"domain": "valid-pro-brand.example.com"},
        headers=_auth_headers(pro_user),
    )
    assert resp_ok.status_code in (200, 201), resp_ok.text
    assert resp_ok.json()["domain"] == "valid-pro-brand.example.com"


def test_validate_secrets_rejects_default_workload_secret_in_production_oracle(
    monkeypatch: pytest.MonkeyPatch,
):
    """Production + remote_oracle mode must reject weak default USER_WORKLOAD_SYNC_SECRET."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "a-strong-non-default-jwt-secret-value-1234567890")
    monkeypatch.setattr(settings, "USER_WORKLOAD_MODE", "remote_oracle")
    monkeypatch.setattr(settings, "USER_WORKLOAD_SYNC_SECRET", "oracle-workload-sync-secret-change-in-production")

    with pytest.raises(ValueError, match="USER_WORKLOAD_SYNC_SECRET"):
        settings.validate_secrets()

    monkeypatch.setattr(settings, "USER_WORKLOAD_SYNC_SECRET", "too-short")
    with pytest.raises(ValueError, match="USER_WORKLOAD_SYNC_SECRET"):
        settings.validate_secrets()
