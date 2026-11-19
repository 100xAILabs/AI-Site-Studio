"""
Tests for Tier 3 Hardening & Privacy Compliance (F-25, F-26, F-28, F-29, F-30, F-36, F-37, F-40).
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.core.config import settings
from app.models.user import User, UserRole
from app.models.template import Template, TemplateStatus, TemplateFramework
from app.models.category import Category
from app.models.preview_session import PreviewSession
from app.core.logging_filter import PIIRedactionFilter
from app.api.v1.routes.payment import sanitize_gateway_payload
from app.services.location_service import detect_location


@pytest.mark.asyncio
async def test_health_and_healthz_probes(client: AsyncClient):
    """Test /healthz liveness and /health readiness probes including X-Request-ID header (F-40)."""
    # 1. /healthz must always succeed with 200
    res_z = await client.get("/healthz")
    assert res_z.status_code == 200
    assert res_z.json()["status"] == "ok"
    assert "x-request-id" in res_z.headers

    # 2. /health must check database and return status
    res_h = await client.get("/health")
    assert res_h.status_code == 200
    data = res_h.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "x-request-id" in res_h.headers


def test_pii_redaction_filter():
    """Verify logging filter scrubs email addresses, tokens, and license keys (F-28)."""
    filter_ = PIIRedactionFilter()

    # Email redaction
    record_email = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="User john.doe@example.com logged in from account", args=(), exc_info=None
    )
    filter_.filter(record_email)
    assert "john.doe@example.com" not in record_email.msg
    assert "[REDACTED_EMAIL]" in record_email.msg

    # License key redaction
    record_lic = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Generated license AS-ABCD-1234-EFGH-5678 for order", args=(), exc_info=None
    )
    filter_.filter(record_lic)
    assert "AS-ABCD-1234-EFGH-5678" not in record_lic.msg
    assert "[REDACTED_KEY]" in record_lic.msg


@pytest.mark.asyncio
async def test_location_service_zero_network():
    """Verify location service derives country from edge headers without external HTTP queries (F-26)."""
    class DummyRequest:
        headers = {
            "cf-ipcountry": "GB",
            "cf-ipcity": "London",
        }

    loc = await detect_location(request=DummyRequest())
    assert loc["country_code"] == "GB"
    assert loc["country"] == "United Kingdom"
    assert loc["currency"] == "GBP"
    assert loc["detected_ip"] is None


def test_payment_payload_data_minimization():
    """Verify sensitive customer and billing data is stripped from webhook payloads (F-25)."""
    raw_payload = {
        "id": "evt_test123",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc",
                "object": "checkout.session",
                "amount": 4900,
                "currency": "usd",
                "customer_details": {
                    "email": "victim@example.com",
                    "phone": "+1234567890",
                    "card": {"last4": "4242", "brand": "visa"}
                },
                "billing_details": {
                    "address": {"city": "New York", "line1": "123 Street"}
                },
                "notes": {
                    "private_info": "secret note"
                }
            }
        }
    }

    sanitized = sanitize_gateway_payload(raw_payload)
    assert sanitized["id"] == "evt_test123"
    assert sanitized["data"]["object"]["id"] == "cs_test_abc"
    assert sanitized["data"]["object"]["amount"] == 4900
    assert sanitized["data"]["object"]["currency"] == "usd"
    assert "customer_details" not in sanitized["data"]["object"]
    assert "billing_details" not in sanitized["data"]["object"]
    assert "notes" not in sanitized["data"]["object"]


@pytest.mark.asyncio
async def test_preview_session_expiry_410(client: AsyncClient, db: AsyncSession):
    """Expired preview sessions must return 410 Gone (F-30)."""
    cat = Category(name="Test Cat Expiry", slug=f"cat-expiry-{uuid.uuid4().hex[:6]}")
    db.add(cat)
    await db.flush()

    template = Template(
        id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        title="Expiry Test Template",
        slug=f"expiry-test-{uuid.uuid4().hex[:6]}",
        short_description="Test short",
        description="Test description",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("29.00"),
        status=TemplateStatus.PUBLISHED,
        framework=TemplateFramework.HTML,
        category_id=cat.id,
    )
    db.add(template)
    await db.flush()

    # Expired session (expires_at 1 hour in the past)
    expired_sess = PreviewSession(
        id=uuid.uuid4(),
        template_id=template.id,
        user_email="buyer@example.com",
        business_data={"business_name": "Old Business"},
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(expired_sess)
    await db.commit()

    res = await client.get(f"/api/v1/preview/{expired_sess.id}")
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_account_anonymization_and_export(client: AsyncClient, db: AsyncSession):
    """Test GDPR / DPDP self-service account export and anonymization (F-29)."""
    from app.core.security import create_access_token

    u_id = uuid.uuid4()
    test_user = User(
        id=u_id,
        email=f"anonymize_me_{u_id.hex[:6]}@example.com",
        username=f"anon_user_{u_id.hex[:6]}",
        full_name="Target For Anonymization",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(test_user)
    await db.commit()
    await db.refresh(test_user)

    token = create_access_token(subject=str(test_user.id), role=test_user.role.value, tv=test_user.token_version)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Export personal data
    res_export = await client.get("/api/v1/auth/me/export", headers=headers)
    assert res_export.status_code == 200
    export_json = res_export.json()
    assert export_json["profile"]["id"] == str(test_user.id)
    assert "GDPR" in export_json["compliance_notice"]

    # 2. Anonymize personal account
    res_del = await client.delete("/api/v1/auth/me", headers=headers)
    assert res_del.status_code == 200

    await db.refresh(test_user)
    assert test_user.is_active is False
    assert "@deleted.invalid" in test_user.email or "anonymized_" in test_user.email
    assert test_user.full_name == "Deleted User"
