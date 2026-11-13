import pytest
import asyncio
from app.services.dns_verification_service import verify_domain_dns_ownership, PROTECTED_SYSTEM_DOMAINS


@pytest.mark.asyncio
async def test_protected_domain_rejection():
    # Attempting to claim google.com, www.google.com, apple.com must be immediately blocked
    for domain in ["google.com", "www.google.com", "apple.com", "microsoft.com", "site-studio.live"]:
        res = await verify_domain_dns_ownership(domain, expected_token="aisitestudio-verify-fake123")
        assert res["verified"] is False
        assert "Security Block" in res["reason"]


@pytest.mark.asyncio
async def test_unowned_domain_no_txt_token():
    # Attempting to claim an arbitrary real domain without proper TXT challenge record must fail
    res = await verify_domain_dns_ownership("example.com", expected_token="aisitestudio-verify-unmatched-token")
    assert res["verified"] is False
    assert "Ownership verification failed" in res["reason"]


@pytest.mark.asyncio
async def test_purchased_domain_inherent_ownership_verification(auth_client, db):
    # Tests that a domain purchased by the user on the platform is inherently verified
    from app.models.deployment import Domain, Deployment
    import uuid

    # Get the authenticated user from the client fixture
    res_user = await auth_client.get("/api/v1/auth/me")
    assert res_user.status_code == 200
    user_id = uuid.UUID(res_user.json()["id"])

    # Create deployment
    dep = Deployment(
        user_id=user_id,
        project_name="Platform Domain Test Project",
        subdomain=f"platform-test-{uuid.uuid4().hex[:6]}",
        status="live",
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)

    # Create purchased domain for this user
    domain_name = f"platform-owned-{uuid.uuid4().hex[:6]}.com"
    domain = Domain(
        user_id=user_id,
        domain=domain_name,
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
    )
    db.add(domain)
    await db.commit()

    # Call verify-ownership endpoint
    verify_resp = await auth_client.post(
        "/api/v1/deployments/domains/verify-ownership",
        json={"domain": domain_name, "deployment_id": str(dep.id)}
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["success"] is True
    assert data["status"] == "verified"
    assert data["method"] == "platform_purchase"


