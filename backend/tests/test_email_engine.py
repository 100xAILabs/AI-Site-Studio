"""
Unit and integration tests for Phase 5: Production Email Engine.
Tests:
- Pluggable Adapters: Resend, Brevo, SMTP, Mock
- Anti-spam honeypot & submission velocity guards
- Sliding window rate limiter
- Email engine dual dispatch (admin notification + customer auto-reply)
- API endpoints: /api/v1/email/contact, /api/v1/email/newsletter, /api/v1/email/verify-config
- Generated scaffold verification (FastAPI contact route, React Contact page, serverless contact handler)
"""

import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.email_engine import (
    email_engine,
    AntiSpamGuard,
    SubmissionRateLimiter,
    EmailMessage,
    ResendEmailAdapter,
    BrevoEmailAdapter,
    SMTPEmailAdapter,
    ConsoleMockEmailAdapter,
)
from app.services.fullstack_scaffold import fullstack_scaffold_generator


# ==============================================================================
# 1. Pluggable Email Adapters Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_console_mock_adapter():
    adapter = ConsoleMockEmailAdapter()
    msg = EmailMessage(
        to=["client@example.com"],
        subject="Test Mock Email",
        html_body="<p>Hello Mock World</p>",
        text_body="Hello Mock World",
    )
    result = await adapter.send(msg)
    assert result.success is True
    assert result.provider == "mock"
    assert result.message_id is not None
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0].subject == "Test Mock Email"


@pytest.mark.asyncio
async def test_resend_adapter_missing_key():
    adapter = ResendEmailAdapter(api_key="")
    msg = EmailMessage(to=["test@example.com"], subject="Test", html_body="<p>Test</p>")
    result = await adapter.send(msg)
    assert result.success is False
    assert result.provider == "resend"
    assert "RESEND_API_KEY is not configured" in (result.error or "")


@pytest.mark.asyncio
async def test_resend_adapter_successful_dispatch():
    mock_post_res = MagicMock()
    mock_post_res.status_code = 200
    mock_post_res.json.return_value = {"id": "re_mock_test_12345"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_post_res
        adapter = ResendEmailAdapter(api_key="re_mock_valid_key_12345")
        msg = EmailMessage(
            to=["recipient@domain.com"],
            subject="Hello from Resend",
            html_body="<p>Welcome</p>",
        )
        result = await adapter.send(msg)
        assert result.success is True
        assert result.provider == "resend"
        assert result.message_id == "re_mock_test_12345"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_brevo_adapter_successful_dispatch():
    mock_post_res = MagicMock()
    mock_post_res.status_code = 201
    mock_post_res.json.return_value = {"messageId": "brevo_mock_msg_987"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_post_res
        adapter = BrevoEmailAdapter(api_key="xkeysib-mock1234567890abcdef1234567890abcdef")
        msg = EmailMessage(
            to=["client@domain.com"],
            subject="Hello from Brevo",
            html_body="<p>Welcome</p>",
        )
        result = await adapter.send(msg)
        assert result.success is True
        assert result.provider == "brevo"
        assert result.message_id == "brevo_mock_msg_987"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_adapter_missing_creds():
    adapter = SMTPEmailAdapter(user="", password="")
    msg = EmailMessage(to=["test@example.com"], subject="Test", html_body="<p>Test</p>")
    result = await adapter.send(msg)
    assert result.success is False
    assert result.provider == "smtp"
    assert "SMTP host, username, or password is not configured" in (result.error or "")


# ==============================================================================
# 2. Anti-Spam & Rate Limiter Tests
# ==============================================================================

def test_anti_spam_honeypot_detection():
    # Honeypot filled -> spam
    valid, err = AntiSpamGuard.validate_submission(honeypot_value="http://spamsite.ru")
    assert valid is False
    assert "honeypot triggered" in (err or "").lower()

    # Honeypot empty -> pass
    valid, err = AntiSpamGuard.validate_submission(honeypot_value="")
    assert valid is True
    assert err is None


def test_anti_spam_velocity_detection():
    # Form submitted in 0.2s -> too fast for human
    valid, err = AntiSpamGuard.validate_submission(
        honeypot_value=None,
        form_loaded_at=time.time() - 0.2,
        min_seconds=1.0,
    )
    assert valid is False
    assert "too fast" in (err or "").lower()

    # Form submitted in 2.5s -> human velocity
    valid, err = AntiSpamGuard.validate_submission(
        honeypot_value=None,
        form_loaded_at=time.time() - 2.5,
        min_seconds=1.0,
    )
    assert valid is True
    assert err is None


def test_rate_limiter_window_blocking():
    limiter = SubmissionRateLimiter(max_requests=3, window_seconds=60)
    client_ip = "192.168.1.100"

    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    assert limiter.is_allowed(client_ip) is True
    # 4th request within window must be blocked
    assert limiter.is_allowed(client_ip) is False

    # Different IP is still allowed
    assert limiter.is_allowed("192.168.1.101") is True


# ==============================================================================
# 3. Email Engine Dual Dispatch Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_email_engine_dual_dispatch():
    admin_res, cust_res = await email_engine.send_contact_inquiry(
        sender_name="Alice Explorer",
        sender_email="alice@techstartup.io",
        subject="Enterprise Partnership",
        message="We are interested in licensing Site Studio templates.",
        recipient_email="founder@myagency.com",
        site_name="My Startup Agency",
    )
    assert admin_res.success is True
    assert cust_res is not None
    assert cust_res.success is True


@pytest.mark.asyncio
async def test_email_engine_newsletter_dispatch():
    result = await email_engine.send_newsletter_subscription(
        subscriber_email="subscriber@domain.com",
        site_name="Modern SaaS Demo",
    )
    assert result.success is True


# ==============================================================================
# 4. REST API Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_api_submit_contact_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "name": "Sarah Connor",
            "email": "sarah@cyberdyne.org",
            "subject": "System Upgrade Question",
            "message": "Please send us details on the fullstack generator.",
            "site_name": "Cyberdyne Systems",
            "form_loaded_at": time.time() - 2.0,
        }
        res = await ac.post("/api/v1/email/contact", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "sent"
        assert data["customer_confirmation_sent"] is True


@pytest.mark.asyncio
async def test_api_submit_contact_honeypot_rejection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "name": "Spam Bot 3000",
            "email": "bot@spamnetwork.xyz",
            "subject": "Cheap Rolex Watches",
            "message": "Click here to buy cheap watches now!",
            "website": "http://spammylink.xyz",  # Honeypot filled!
        }
        res = await ac.post("/api/v1/email/contact", json=payload)
        assert res.status_code == 400
        assert "honeypot" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_newsletter_subscription():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "email": "dev@futurebuild.io",
            "site_name": "FutureBuild",
        }
        res = await ac.post("/api/v1/email/newsletter", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "subscribed"
        assert data["email"] == "dev@futurebuild.io"


@pytest.mark.asyncio
async def test_api_verify_config():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/email/verify-config")
        assert res.status_code == 200
        data = res.json()
        assert "active_provider" in data
        assert "providers" in data
        assert "resend" in data["providers"]
        assert "brevo" in data["providers"]
        assert "smtp" in data["providers"]


# ==============================================================================
# 5. Scaffolded Code Verification Tests
# ==============================================================================

def test_fullstack_scaffold_contact_route_contains_email_engine():
    """Verify that generated fullstack FastAPI contact route includes real dispatcher, not a fake stub."""
    contact_py = fullstack_scaffold_generator._build_route_contact_py()
    assert "_dispatch_email" in contact_py
    assert "_check_rate_limit" in contact_py
    assert "website: Optional[str]" in contact_py  # Honeypot in schema
    assert "Spam bot detected" in contact_py
    assert "NOTIFICATION_EMAIL" in contact_py
    assert "Customer Auto-Reply Confirmation" in contact_py


def test_fullstack_scaffold_contact_react_page_contains_interactive_form():
    """Verify that generated React contact page contains real form state, honeypot, and api.post."""
    contact_tsx = fullstack_scaffold_generator._build_page_tsx("Contact", "My SaaS")
    assert "api.post('/api/contact'" in contact_tsx
    assert "website" in contact_tsx  # Honeypot field in state and DOM
    assert "formLoadedAt" in contact_tsx  # Velocity detection
    assert "Inquiry Dispatched!" in contact_tsx


def test_hybrid_serverless_contact_dispatcher_contains_anti_spam():
    """Verify that generated serverless contact handler includes multi-provider & honeypot."""
    files = fullstack_scaffold_generator.generate_hybrid_serverless("Test Hybrid Site")
    contact_code = files["backend/api/contact.py"]
    assert "Spam bot detected" in contact_code
    assert "_dispatch_email" in contact_code
    assert "recipient = payload.recipient_email" in contact_code
    assert "phone" in contact_code
    assert "_RATE_LIMIT_STORE" in contact_code


@pytest.mark.asyncio
async def test_motel_room_availability_inquiry_with_phone_and_custom_destination():
    """
    Test user scenario:
    A visitor requests room availability for 'Sunrise Motel'.
    The motel owner configured a specific recipient email ('reservations@sunrisemotel.com').
    The visitor provides their phone number ('+1-555-839-2001') and booking specifications.
    The email engine must deliver the inquiry directly to 'reservations@sunrisemotel.com'
    with telephone/WhatsApp callback actions and room specifications,
    while sending an instant auto-reply confirmation to the guest.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "name": "David Miller",
            "email": "david.miller@traveler.com",
            "phone": "+1-555-839-2001",
            "subject": "Room Availability for 2 Guests (Dec 1-5)",
            "message": "Hello, we are looking for a Deluxe Queen Room with ocean view from Dec 1 to Dec 5. Is there availability?",
            "site_name": "Sunrise Bay Motel",
            "recipient_email": "reservations@sunrisemotel.com",
            "metadata": {
                "check_in": "2026-12-01",
                "check_out": "2026-12-05",
                "room_type": "Deluxe Queen Suite",
                "guests": "2 Adults",
            },
            "form_loaded_at": time.time() - 2.5,
        }
        res = await ac.post("/api/v1/email/contact", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "sent"
        assert data["customer_confirmation_sent"] is True

        # Check mock sent messages to verify exact destination and content
        adapter = email_engine.get_adapter()
        assert isinstance(adapter, ConsoleMockEmailAdapter)
        matching = [m for m in adapter.sent_messages if "reservations@sunrisemotel.com" in m.to]
        assert len(matching) >= 1
        admin_email = matching[-1]
        assert "Sunrise Bay Motel" in admin_email.subject
        assert "David Miller" in admin_email.html_body
        assert "tel:+15558392001" in admin_email.html_body
        assert "wa.me/15558392001" in admin_email.html_body
        assert "Deluxe Queen Suite" in admin_email.html_body
        assert "2026-12-01" in admin_email.html_body

        # Check customer auto-reply
        cust_matching = [m for m in adapter.sent_messages if "david.miller@traveler.com" in m.to]
        assert len(cust_matching) >= 1
        cust_email = cust_matching[-1]
        assert "We received your message" in cust_email.subject
        assert "Deluxe Queen Suite" in cust_email.html_body


def test_contact_page_dynamic_phone_and_email_binding():
    """
    Test user scenario:
    When the website owner edits or changes their frontend phone number or email,
    the Contact page dynamically binds the new phone number to tel: and WhatsApp,
    and binds the new email to recipient_email in the submission payload.
    """
    contact_code = fullstack_scaffold_generator._build_page_tsx("Contact", "Sunrise Motel")
    assert "businessPhone" in contact_code
    assert "businessEmail" in contact_code
    assert "tel:${cleanPhone}" in contact_code
    assert "wa.me/${cleanWa}" in contact_code
    assert "recipient_email: businessEmail" in contact_code
    assert "Call Now" in contact_code
    assert "WhatsApp" in contact_code

