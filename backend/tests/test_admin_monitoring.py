"""
Tests for Admin Payments & User Usage Telemetry monitoring routes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


@pytest.mark.asyncio
async def test_admin_payments_monitoring_auth(client: AsyncClient, admin_client: AsyncClient):
    # Non-admin user cannot view payments
    unauth_res = await client.get("/api/v1/admin/payments")
    assert unauth_res.status_code in (401, 403)

    # Admin client successfully retrieves payments feed
    admin_res = await admin_client.get("/api/v1/admin/payments")
    assert admin_res.status_code == 200
    data = admin_res.json()
    assert "summary" in data
    assert "payments" in data
    assert "total_revenue_usd" in data["summary"]
    assert "total_revenue_inr" in data["summary"]
    assert "total_transactions" in data["summary"]


@pytest.mark.asyncio
async def test_admin_users_usage_monitoring(client: AsyncClient, admin_client: AsyncClient):
    # Non-admin user blocked
    unauth_res = await client.get("/api/v1/admin/users/usage")
    assert unauth_res.status_code in (401, 403)

    # Admin user can monitor platform usage
    admin_res = await admin_client.get("/api/v1/admin/users/usage")
    assert admin_res.status_code == 200
    users_usage = admin_res.json()
    assert isinstance(users_usage, list)

    if len(users_usage) > 0:
        u = users_usage[0]
        assert "subscription_tier" in u
        assert "ai_credits" in u
        assert "total_orders" in u
        assert "total_downloads" in u
        assert "clean_downloads" in u
        assert "watermarked_downloads" in u
        assert "deployments_count" in u
        assert "tamper_alerts_count" in u


@pytest.mark.asyncio
async def test_admin_user_usage_details(admin_client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    res_user = await db.execute(select(User).where(User.email == "testadmin@aisitestudio.com"))
    admin_user = res_user.scalar_one()

    # Get details for admin user itself
    res = await admin_client.get(f"/api/v1/admin/users/{admin_user.id}/usage-details")
    assert res.status_code == 200
    data = res.json()
    assert "user" in data
    assert "orders" in data
    assert "downloads" in data
    assert "deployments" in data
    assert "tamper_alerts" in data
    assert data["user"]["id"] == str(admin_user.id)
