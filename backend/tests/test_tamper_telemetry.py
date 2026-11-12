"""
Test suite for stealth tamper telemetry receiver and alert logging.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tamper_alert import TamperAlert


@pytest.mark.asyncio
async def test_receive_tamper_alert_endpoint(client: AsyncClient, db: AsyncSession):
    # 1. Post a stealth telemetry beacon payload (disguised parameter names)
    payload = {
        "tid": "saas-starter-123",
        "em": "violator@example.com",
        "lk": "LIC-STD-9988",
        "dm": "unauthorized-domain.com",
        "vt": "badge_element_deleted",
    }
    response = await client.post("/api/v1/telemetry/tamper-alert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["recorded"] is True
    assert "alert_id" in data

    # 2. Verify alert was saved in the database
    res = await db.execute(select(TamperAlert).where(TamperAlert.template_id == "saas-starter-123"))
    alert = res.scalar_one_or_none()
    assert alert is not None
    assert alert.buyer_email == "violator@example.com"
    assert alert.license_key == "LIC-STD-9988"
    assert alert.domain == "unauthorized-domain.com"
    assert alert.violation_type == "badge_element_deleted"


@pytest.mark.asyncio
async def test_admin_list_tamper_alerts(admin_client: AsyncClient, client: AsyncClient):
    # Public non-admin client cannot view security alerts
    unauth_res = await client.get("/api/v1/telemetry/tamper-alerts")
    assert unauth_res.status_code in (401, 403)

    # Admin client can view all recorded alerts
    admin_res = await admin_client.get("/api/v1/telemetry/tamper-alerts")
    assert admin_res.status_code == 200
    alerts_data = admin_res.json()
    assert "items" in alerts_data
    assert "total" in alerts_data

