"""
AI Site Studio — Email System REST Endpoints
Handles contact inquiries, newsletter signups, diagnostic verification, and transactional dispatch.
Includes:
- Anti-spam honeypot & velocity validation
- Rate-limiting guard per IP
- Dual notification (Admin inquiry alert + Customer confirmation email)
- Clean error and success reporting according to actual provider status
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, status, Depends
from app.schemas.email import (
    ContactSubmissionRequest,
    ContactSubmissionResponse,
    NewsletterSubscriptionRequest,
    NewsletterSubscriptionResponse,
    GenericEmailSendRequest,
    EmailConfigVerifyResponse,
)
from app.services.email_engine import (
    email_engine,
    AntiSpamGuard,
    global_contact_rate_limiter,
    EmailMessage,
)
from app.core.config import settings

logger = logging.getLogger("app.api.v1.routes.email")

router = APIRouter(tags=["Email & Contact System"])


def _get_client_ip(request: Request) -> str:
    """Extracts client IP considering standard reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


@router.post(
    "/contact",
    response_model=ContactSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Contact Inquiry",
    description="Submits a contact form inquiry with spam protection, rate limiting, and dual email notification.",
)
async def submit_contact_form(payload: ContactSubmissionRequest, request: Request):
    client_ip = _get_client_ip(request)

    # 1. Anti-Spam Honeypot & Velocity Check
    is_valid, spam_error = AntiSpamGuard.validate_submission(
        honeypot_value=payload.website,
        form_loaded_at=payload.form_loaded_at,
        min_seconds=1.0,
    )
    if not is_valid:
        logger.warning(f"Contact form rejected from IP {client_ip}: {spam_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=spam_error,
        )

    # 2. Sliding Window Rate Limiting
    if not global_contact_rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for contact form from IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many contact submissions. Please wait a minute before submitting again.",
        )

    # 3. Dispatch Emails via Email Engine
    admin_res, cust_res = await email_engine.send_contact_inquiry(
        sender_name=payload.name,
        sender_email=payload.email,
        subject=payload.subject or "Website Inquiry",
        message=payload.message,
        sender_phone=payload.phone,
        recipient_email=payload.recipient_email,
        site_name=payload.site_name or "AI Site Studio Website",
        metadata=payload.metadata,
    )

    if not admin_res.success:
        logger.error(f"Failed to deliver contact inquiry: {admin_res.error}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email dispatch failed through provider '{admin_res.provider}': {admin_res.error}",
        )

    return ContactSubmissionResponse(
        success=True,
        status="sent",
        message="Thank you! Your message has been sent successfully. A confirmation has been emailed to you.",
        provider=admin_res.provider,
        message_id=admin_res.message_id,
        customer_confirmation_sent=bool(cust_res and cust_res.success),
    )


@router.post(
    "/newsletter",
    response_model=NewsletterSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Subscribe to Newsletter",
    description="Subscribes an email to the newsletter and sends a confirmation email.",
)
async def subscribe_newsletter(payload: NewsletterSubscriptionRequest, request: Request):
    client_ip = _get_client_ip(request)

    # 1. Anti-Spam Check
    is_valid, spam_error = AntiSpamGuard.validate_submission(
        honeypot_value=payload.website,
        form_loaded_at=payload.form_loaded_at,
        min_seconds=1.0,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=spam_error,
        )

    # 2. Rate Limiting
    if not global_contact_rate_limiter.is_allowed(f"newsletter:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many subscription attempts. Please wait a moment.",
        )

    # 3. Send Newsletter Confirmation
    res = await email_engine.send_newsletter_subscription(
        subscriber_email=payload.email,
        site_name=payload.site_name or "AI Site Studio",
    )

    return NewsletterSubscriptionResponse(
        success=True,
        status="subscribed",
        message="You have been successfully subscribed to our newsletter updates.",
        email=payload.email,
        provider=res.provider,
    )


@router.get(
    "/verify-config",
    response_model=EmailConfigVerifyResponse,
    summary="Verify Email Provider Configuration",
    description="Checks which email providers (Resend, Brevo, SMTP) are configured and ready.",
)
async def verify_email_config():
    adapter = email_engine.get_adapter()
    active_details = adapter.verify_config()
    active_name = active_details.get("provider", "mock")

    # Audit each known provider
    resend_configured = bool(settings.RESEND_API_KEY and settings.RESEND_API_KEY.startswith("re_"))
    brevo_configured = bool(getattr(settings, "BREVO_API_KEY", None) and len(settings.BREVO_API_KEY) > 10)
    smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD and settings.SMTP_HOST)

    return EmailConfigVerifyResponse(
        active_provider=active_name,
        ready=active_name != "mock" or active_details.get("configured", False),
        providers={
            "resend": {
                "configured": resend_configured,
                "from": settings.RESEND_FROM,
            },
            "brevo": {
                "configured": brevo_configured,
                "from": getattr(settings, "SMTP_FROM", "noreply@aisitestudio.com"),
            },
            "smtp": {
                "configured": smtp_configured,
                "host": settings.SMTP_HOST,
                "port": settings.SMTP_PORT,
                "user": settings.SMTP_USER[:3] + "***" if settings.SMTP_USER else "",
                "use_tls": settings.SMTP_USE_TLS,
            },
            "mock": {
                "configured": True,
                "description": "Safe local/test fallback adapter",
            },
        },
    )


@router.post(
    "/send",
    summary="Send Generic Transactional Email",
    description="Sends a transactional email via the active email provider.",
)
async def send_transactional_email(payload: GenericEmailSendRequest):
    adapter = email_engine.get_adapter()
    msg = EmailMessage(
        to=list(payload.to),
        subject=payload.subject,
        html_body=payload.html_body,
        text_body=payload.text_body,
        from_email=payload.from_email,
        reply_to=payload.reply_to,
    )
    result = await adapter.send(msg)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email dispatch failed: {result.error}",
        )
    return {
        "success": True,
        "provider": result.provider,
        "message_id": result.message_id,
        "timestamp": result.timestamp,
    }
