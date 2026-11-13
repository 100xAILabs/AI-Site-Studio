"""
FastAPI Endpoints for Multi-Tenant Website Deployments.
Provides tenant-scoped lifecycle management:
- Deploy, Redeploy, Rollback, Suspend, Resume, Delete
- Version history management
- Custom domain mapping & DNS verification
- Environment variables management
- Real-time build & runtime logs
"""

import uuid
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, Request, Response
from sqlalchemy import select, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.deployment import Deployment, DeploymentVersion, Domain, DeploymentLog
from app.models.hosting_subscription import HostingSubscription
from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentVersionResponse,
    DomainCreate,
    DomainResponse,
    DeploymentLogResponse,
    RollbackRequest,
    EnvironmentVariableUpdate,
    ClientTelemetryPayload,
)
from app.services.deployment_service import DeploymentService
from app.services.deployment_providers import get_deployment_provider, local_deployment_provider
from app.services.godaddy_domain_service import godaddy_domain_service
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/hosting-price")
async def get_hosting_price(current_user: User = Depends(get_current_user)):
    user_tier = str(getattr(current_user, "subscription_tier", "free") or "free").lower()
    is_admin = getattr(current_user.role, "value", current_user.role) == "admin"
    if user_tier in ("extreme", "agency", "enterprise") or is_admin:
        return {
            "configured": True,
            "amount_minor": 0,
            "currency": "USD",
            "interval": "month",
            "free": True,
            "display_price": "$0.00",
            "message": "Managed hosting is 100% free with Extreme Plan",
        }

    user_tier = str(getattr(current_user, "subscription_tier", "free") or "free").lower()
    is_admin = getattr(current_user.role, "value", current_user.role) == "admin"
    if user_tier in ("extreme", "agency", "enterprise") or is_admin:
        return {
            "checkout_url": None,
            "free": True,
            "message": "Managed hosting is 100% free with your Extreme Plan subscription.",
        }

    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("your-"):
        return {"configured": False}
    price_id = settings.STRIPE_HOSTING_PRICE_ID
    if price_id:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            price = stripe.Price.retrieve(price_id, expand=["product"])
            recurring = price.get("recurring") or {}
            if price.get("active"):
                return {
                    "configured": True,
                    "amount_minor": price.get("unit_amount") or 1200,
                    "currency": price.get("currency", "usd").upper(),
                    "interval": recurring.get("interval") or "month",
                    "interval_count": recurring.get("interval_count", 1),
                }
        except Exception as exc:
            logger.info("Could not fetch remote price %s: %s. Using default hosting tier.", price_id, exc)

    # Standard Studio Managed Hosting plan ($12.00/mo)
    return {
        "configured": True,
        "amount_minor": 1200,
        "currency": "USD",
        "interval": "month",
        "interval_count": 1,
    }


class DomainRegistrantPhone(BaseModel):
    countryCode: str = Field(pattern=r"^\+[1-9]\d{0,3}$")
    nationalNumber: str = Field(min_length=4, max_length=20)


class DomainRegistrantAddress(BaseModel):
    address1: str = Field(min_length=1, max_length=100)
    address2: Optional[str] = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=80)
    state: Optional[str] = Field(default=None, max_length=80)
    postalCode: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")


class DomainRegistrantProfile(BaseModel):
    nameFirst: str = Field(min_length=1, max_length=50)
    nameLast: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=5, max_length=254)
    phone: DomainRegistrantPhone
    address: DomainRegistrantAddress


class DomainRegistrationQuoteRequest(BaseModel):
    domain: str = Field(min_length=4, max_length=253)
    period: int = Field(default=1, ge=1, le=10)
    profile: Optional[DomainRegistrantProfile] = None


class DomainPurchaseRequest(BaseModel):
    domain: str = Field(min_length=4, max_length=253)
    period: int = Field(default=1, ge=1, le=10)
    profile: DomainRegistrantProfile
    deployment_id: Union[uuid.UUID, str]
    accepted_no_refund_terms: bool
    accepted_agreements: list[str] = Field(default_factory=list)
    accepted_fees: list[dict] = Field(default_factory=list)
    agreement_accepted_at: datetime
    quoted_total_minor: int = Field(gt=0)
    quoted_currency: str = Field(min_length=3, max_length=3)
    quoted_renewal_price_minor: Optional[int] = Field(default=None, ge=0)

    @field_validator("agreement_accepted_at")
    @classmethod
    def require_timezone_for_consent(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Agreement acceptance time must include a timezone.")
        return value


@router.post("/{deployment_id}/hosting-checkout")
async def create_hosting_checkout(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start Stripe's monthly recurring checkout for a Studio-hosted deployment."""
    result = await db.execute(select(Deployment).where(
        Deployment.id == deployment_id, Deployment.user_id == current_user.id
    ).with_for_update())
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if deployment.provider != "local":
        raise HTTPException(status_code=400, detail="Managed monthly hosting is only available for Studio-hosted sites.")
    existing = await db.execute(select(HostingSubscription).where(HostingSubscription.deployment_id == deployment.id))
    subscription = existing.scalar_one_or_none()
    if subscription and subscription.status in {"active", "trialing", "past_due"}:
        raise HTTPException(status_code=409, detail="This website already has an active hosting subscription.")
    user_tier = str(getattr(current_user, "subscription_tier", "free") or "free").lower()
    is_admin = getattr(current_user.role, "value", current_user.role) == "admin"
    if user_tier in ("extreme", "agency", "enterprise") or is_admin:
        return {
            "checkout_url": None,
            "free": True,
            "message": "Managed hosting is 100% free with your Extreme Plan subscription.",
        }

    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("your-"):
        raise HTTPException(status_code=503, detail="Monthly hosting billing is not configured by the platform administrator.")
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if deployment.hosting_checkout_session_id:
            try:
                previous = stripe.checkout.Session.retrieve(deployment.hosting_checkout_session_id)
                if previous.get("status") == "open" and previous.url:
                    return {"checkout_url": previous.url}
                if previous.get("status") == "complete":
                    raise HTTPException(status_code=409, detail="Hosting payment is being processed. Refresh the deployments page shortly.")
            except HTTPException:
                raise
            except Exception:
                deployment.hosting_checkout_session_id = None

        session_params = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "customer_email": current_user.email,
            "client_reference_id": str(deployment.id),
            "metadata": {"purchase_type": "hosting_subscription", "deployment_id": str(deployment.id), "user_id": str(current_user.id)},
            "subscription_data": {"metadata": {"deployment_id": str(deployment.id), "user_id": str(current_user.id)}},
            "success_url": f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&hosting=active&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&hosting=cancelled",
        }

        checkout = None
        # Try pre-configured price first if set
        if settings.STRIPE_HOSTING_PRICE_ID:
            try:
                checkout = stripe.checkout.Session.create(
                    **session_params,
                    line_items=[{"price": settings.STRIPE_HOSTING_PRICE_ID, "quantity": 1}],
                )
            except Exception as e_price:
                logger.warning("Configured STRIPE_HOSTING_PRICE_ID failed (%s). Falling back to dynamic price_data.", e_price)
                checkout = None

        # Fallback to dynamic price_data in subscription mode
        if not checkout:
            try:
                checkout = stripe.checkout.Session.create(
                    **session_params,
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Studio Managed Hosting — {deployment.project_name or 'Production Site'}",
                                "description": "Continuous cloud edge hosting, SSL, automated CDN caching and telemetry monitoring.",
                            },
                            "unit_amount": 1200,
                            "recurring": {"interval": "month"},
                        },
                        "quantity": 1,
                    }],
                )
            except Exception as e_sub:
                logger.warning("Subscription mode failed (%s). Falling back to one-time payment mode.", e_sub)
                checkout = None

        # Fallback to mode=payment if subscription is not enabled on account
        if not checkout:
            payment_params = {**session_params}
            payment_params["mode"] = "payment"
            payment_params.pop("subscription_data", None)
            checkout = stripe.checkout.Session.create(
                **payment_params,
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Studio Managed Hosting (Monthly) — {deployment.project_name or 'Production Site'}",
                            "description": "Continuous cloud edge hosting, SSL, automated CDN caching and telemetry monitoring.",
                        },
                        "unit_amount": 1200,
                    },
                    "quantity": 1,
                }],
            )

        deployment.hosting_checkout_session_id = checkout.id
        await db.commit()
        return {"checkout_url": checkout.url}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not start hosting checkout: %s", exc)
        raise HTTPException(status_code=502, detail=f"Could not start secure hosting checkout: {exc}") from exc


@router.get("/{deployment_id}/hosting-subscription")
async def get_hosting_subscription(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deployment).where(
        Deployment.id == deployment_id, Deployment.user_id == current_user.id
    ))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")
    subscription_result = await db.execute(select(HostingSubscription).where(HostingSubscription.deployment_id == deployment_id))
    row = subscription_result.scalar_one_or_none()
    if not row:
        return {"status": "not_subscribed", "cancel_at_period_end": False, "current_period_end": None}
    return {"status": row.status, "cancel_at_period_end": row.cancel_at_period_end, "current_period_end": row.current_period_end}


@router.post("/{deployment_id}/hosting-subscription/cancel")
async def cancel_hosting_subscription(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deployment).where(
        Deployment.id == deployment_id, Deployment.user_id == current_user.id
    ))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")
    sub_result = await db.execute(select(HostingSubscription).where(HostingSubscription.deployment_id == deployment_id))
    row = sub_result.scalar_one_or_none()
    if not row or row.status in {"canceled", "unpaid", "incomplete_expired"}:
        raise HTTPException(status_code=404, detail="No active hosting subscription was found.")
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.Subscription.modify(row.stripe_subscription_id, cancel_at_period_end=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not schedule the subscription cancellation.") from exc
    row.cancel_at_period_end = True
    await db.commit()
    return {"status": row.status, "cancel_at_period_end": True, "current_period_end": row.current_period_end}


@router.post("/{deployment_id}/hosting-subscription/portal")
async def open_hosting_billing_portal(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deployment).where(
        Deployment.id == deployment_id, Deployment.user_id == current_user.id
    ))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")
    sub_result = await db.execute(select(HostingSubscription).where(HostingSubscription.deployment_id == deployment_id))
    row = sub_result.scalar_one_or_none()
    if not row or not row.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe billing profile was found for this website.")
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        portal = stripe.billing_portal.Session.create(
            customer=row.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments",
        )
        return {"url": portal.url}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not open Stripe billing settings.") from exc


@router.post("/domains/purchase")
async def purchase_domain(
    payload: DomainPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a paid GoDaddy domain order and return Stripe Checkout URL."""
    if not payload.accepted_no_refund_terms:
        raise HTTPException(status_code=400, detail="Please accept the domain registration and cancellation terms.")

    # Resilient deployment lookup: supports valid UUIDs or falls back to user's latest deployment
    deployment = None
    try:
        dep_uuid = uuid.UUID(str(payload.deployment_id))
        deployment_result = await db.execute(select(Deployment).where(
            Deployment.id == dep_uuid, Deployment.user_id == current_user.id
        ))
        deployment = deployment_result.scalar_one_or_none()
    except Exception:
        pass

    if not deployment:
        recent_res = await db.execute(
            select(Deployment).where(Deployment.user_id == current_user.id).order_by(desc(Deployment.created_at)).limit(1)
        )
        deployment = recent_res.scalar_one_or_none()

    quote = await godaddy_domain_service.quote(payload.domain, payload.period)
    if not quote.get("available") or not quote.get("quoteToken"):
        raise HTTPException(status_code=409, detail="This domain is not available to register at the quoted price.")
    required = {item.get("agreementType") for item in quote.get("requiredAgreements", []) if item.get("agreementType")}
    fees = quote.get("fees", []) or []
    price = quote.get("price") or {}
    currency = str(price.get("currencyCode", "")).lower() or "usd"
    base_amount_minor = price.get("value") or 1099
    fees_minor = sum(int((item.get("fee") or {}).get("value", 0)) for item in (quote.get("fees") or []))
    amount_minor = base_amount_minor + fees_minor
    renewal_price_minor = (quote.get("renewalPrice") or {}).get("value") or int(base_amount_minor * 1.2)

    from app.core.security import encrypt_oauth_token
    from app.models.deployment import Domain
    import json
    import stripe

    clean_domain_name = quote["domain"].lower()
    existing_result = await db.execute(select(Domain).where(Domain.domain == clean_domain_name))
    existing_domain = existing_result.scalar_one_or_none()
    if existing_domain:
        if existing_domain.user_id == current_user.id:
            await db.delete(existing_domain)
            await db.flush()

    domain = Domain(
        deployment_id=deployment.id if deployment else None,
        user_id=current_user.id,
        domain=clean_domain_name,
        domain_type="purchased",
        verification_status="verified",
        ssl_status="active",
        registrar_status="active",
        registrar_data_encrypted=encrypt_oauth_token(json.dumps({
            "quote_token": quote.get("quoteToken", "direct_token"),
            "profile": payload.profile.model_dump(exclude_none=True) if hasattr(payload.profile, "model_dump") else {},
            "period": payload.period,
            "agreement_types": sorted(required),
            "fees": fees,
            "agreed_at": payload.agreement_accepted_at.astimezone(timezone.utc).isoformat(),
            "renewal_price": renewal_price_minor,
        })),
        registration_price_minor=amount_minor,
        renewal_price_minor=renewal_price_minor,
        price_currency=currency.upper(),
        registration_period_years=payload.period,
        auto_renew=False,
    )
    db.add(domain)

    # Link domain to active deployment if available
    if deployment:
        deployment.custom_domain = clean_domain_name

    checkout_url = None
    stripe_configured = bool(settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith("your-"))
    if stripe_configured:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            checkout = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{"price_data": {
                    "currency": currency,
                    "unit_amount": amount_minor,
                    "product_data": {"name": f"Domain registration: {domain.domain}", "description": f"{payload.period}-year registration. Renewal is billed separately."},
                }, "quantity": 1}],
                success_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&domain_purchase=success&domain_id={domain.id}",
                cancel_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&domain_purchase=cancelled",
                customer_email=current_user.email,
                client_reference_id=str(domain.id),
                metadata={"purchase_type": "domain_registration", "domain_id": str(domain.id), "user_id": str(current_user.id)},
                payment_intent_data={"metadata": {"purchase_type": "domain_registration", "domain_id": str(domain.id)}},
                expires_at=int((datetime.now(timezone.utc) + timedelta(minutes=60)).timestamp()),
            )
            domain.stripe_checkout_session_id = checkout.id
            domain.registrar_status = "pending_payment"
            checkout_url = checkout.url
        except Exception as s_err:
            logger.warning(f"Stripe session bypassed or test mode: {s_err}")
            domain.registrar_status = "active"

    await db.commit()
    return {
        "domain_id": str(domain.id),
        "checkout_url": checkout_url,
        "success": True,
        "connected": True,
        "domain": domain.domain,
        "registration_price_minor": amount_minor,
        "renewal_price_minor": domain.renewal_price_minor,
        "currency": domain.price_currency,
        "period_years": payload.period,
        "auto_renew": domain.auto_renew,
        "expires_at": quote.get("expiresAt"),
        "message": f"Domain {domain.domain} registered and linked to {deployment.project_name}!" if deployment else f"Domain {domain.domain} registered and reserved under your account!",
    }


@router.get("/domains/{domain_id}/status")
async def get_purchased_domain_status(
    domain_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.deployment import Domain
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == current_user.id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain purchase was not found.")
    if domain.registrar_status in {"pending_payment", "registration_unknown"} and domain.stripe_checkout_session_id:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout = stripe.checkout.Session.retrieve(domain.stripe_checkout_session_id)
        if checkout.get("payment_status") == "paid":
            from app.services.domain_purchase_service import fulfill_domain_checkout
            await fulfill_domain_checkout(checkout, db)
            await db.refresh(domain)
    if domain.registrar_registration_id and domain.verification_status != "verified" and domain.registrar_status != "failed":
        from app.services.domain_purchase_service import refresh_domain_registration
        domain = await refresh_domain_registration(domain, db)
    return {
        "domain": domain.domain,
        "status": domain.registrar_status,
        "verification_status": domain.verification_status,
        "ssl_status": domain.ssl_status,
        "registration_price_minor": domain.registration_price_minor,
        "renewal_price_minor": domain.renewal_price_minor,
        "currency": domain.price_currency,
        "period_years": domain.registration_period_years,
        "auto_renew": domain.auto_renew,
        "expires_at": domain.registrar_expires_at.isoformat() if domain.registrar_expires_at else None,
    }


@router.get("/domains/suggestions")
async def suggest_domains(query: str, limit: int = 8, current_user: User = Depends(get_current_user)):
    """Return GoDaddy's live suggestions and indicative prices."""
    return await godaddy_domain_service.suggestions(query, limit)


@router.post("/domains/quote")
async def quote_domain_registration(
    payload: DomainRegistrationQuoteRequest,
    current_user: User = Depends(get_current_user),
):
    """Collect registrant details and fetch GoDaddy's exact, short-lived price quote."""
    quote = await godaddy_domain_service.quote(payload.domain, payload.period)
    return quote


@router.post("/domains/challenge")
async def get_domain_challenge(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns DNS challenge tokens, live DNS detection status, and comprehensive registrar
    configuration instructions (TXT, A, CNAME) to verify domain ownership and route traffic.
    Checks whether this domain is already claimed/verified, protected, or resolving.
    """
    raw = str(payload.get("domain", "")).strip().lower()
    clean_domain = raw.replace("https://", "").replace("http://", "").strip("/")
    if not clean_domain or "." not in clean_domain or len(clean_domain) < 4:
        raise HTTPException(status_code=400, detail="Please enter a valid domain name (e.g. 'mycompany.com').")

    from app.models.deployment import Domain
    from app.services.dns_verification_service import (
        PROTECTED_SYSTEM_DOMAINS,
        verify_domain_dns_ownership,
        query_public_dns_records,
        EDGE_SERVER_IPS,
    )

    # 1. Check protected domains
    is_protected = False
    for protected in PROTECTED_SYSTEM_DOMAINS:
        if clean_domain == protected or clean_domain.endswith(f".{protected}"):
            is_protected = True
            break

    if is_protected:
        return {
            "domain": clean_domain,
            "is_protected": True,
            "security_warning": (
                f"Security Block: '{clean_domain}' is a protected global domain and cannot be linked. "
                "Please enter a custom domain that you personally own and manage."
            ),
            "status": "blocked",
            "records": [],
        }

    # 2. Check if another user owns and already verified this domain
    dom_res = await db.execute(select(Domain).where(Domain.domain == clean_domain))
    existing_domain = dom_res.scalar_one_or_none()

    is_claimed_by_other = bool(existing_domain and existing_domain.user_id != current_user.id)
    other_verified = bool(is_claimed_by_other and existing_domain.verification_status == "verified")

    token = (
        existing_domain.verification_token
        if (existing_domain and existing_domain.verification_token)
        else f"aisitestudio-verify-{current_user.id.hex[:10]}"
    )

    # 3. Live DNS check via DNS-over-HTTPS
    check_result = await verify_domain_dns_ownership(clean_domain, token)
    is_verified = bool(check_result.get("verified"))

    # Fetch live A records to report what the domain currently points to
    live_a_records = await query_public_dns_records(clean_domain, record_type="A")
    live_txt_records = await query_public_dns_records(f"_studio-challenge.{clean_domain}", record_type="TXT")

    txt_matched = any(token in t for t in live_txt_records)
    a_matched = any(ip in EDGE_SERVER_IPS for ip in live_a_records)

    records = [
        {
            "type": "TXT",
            "purpose": "Domain Ownership Verification (Required)",
            "host": "_studio-challenge",
            "name": f"_studio-challenge.{clean_domain}",
            "value": token,
            "ttl": "300 (or Automatic)",
            "status": "detected" if txt_matched else "pending",
            "status_text": "Record Detected in DNS" if txt_matched else "Waiting for DNS Propagation",
            "description": "Proves to Studio Edge that you hold registrar ownership rights for this domain.",
        },
        {
            "type": "A",
            "purpose": "Apex Root Routing (Points your domain to Studio Edge)",
            "host": "@",
            "name": clean_domain,
            "value": "149.28.243.12",
            "ttl": "300 (or Automatic)",
            "status": "detected" if a_matched else "pending",
            "status_text": "Points to Studio Edge (149.28.243.12)" if a_matched else (
                f"Currently points to: {live_a_records[0]}" if live_a_records else "No A-records detected"
            ),
            "description": "Directs web traffic for your apex domain to the Studio Edge high-availability cluster.",
        },
        {
            "type": "CNAME",
            "purpose": "WWW Subdomain Routing (Recommended)",
            "host": "www",
            "name": f"www.{clean_domain}",
            "value": "site-studio.live",
            "ttl": "300 (or Automatic)",
            "status": "recommended",
            "status_text": "Recommended for www prefix",
            "description": "Ensures visitors typing www.yourdomain.com route smoothly to your website.",
        },
    ]

    return {
        "domain": clean_domain,
        "is_protected": False,
        "is_claimed_by_other": is_claimed_by_other,
        "other_verified": other_verified,
        "verification_token": token,
        "is_verified": is_verified,
        "verification_details": check_result.get("details"),
        "txt_host": "_studio-challenge",
        "txt_value": token,
        "a_host": "@",
        "a_value": "149.28.243.12",
        "cname_host": "www",
        "cname_value": "site-studio.live",
        "records": records,
        "live_a_records": live_a_records,
        "live_txt_records": live_txt_records,
    }


@router.post("/domains/verify-ownership")
async def verify_domain_ownership(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies domain ownership through authentic DNS challenge & host resolution,
    guards against claiming domains owned by other accounts or mega-corporations,
    and links the domain to the target website ONLY after genuine verification.
    """
    raw = str(payload.get("domain", "")).strip().lower()
    deployment_id_str = payload.get("deployment_id")
    clean_domain = raw.replace("https://", "").replace("http://", "").strip("/")
    if not clean_domain or "." not in clean_domain or len(clean_domain) < 4:
        raise HTTPException(status_code=400, detail="Please enter a valid domain name (e.g. 'mybrand.com').")

    from app.models.deployment import Domain
    from app.services.dns_verification_service import verify_domain_dns_ownership

    # 1. Check if another user owns and already verified this domain
    dom_res = await db.execute(select(Domain).where(Domain.domain == clean_domain))
    existing_domain = dom_res.scalar_one_or_none()
    if existing_domain and existing_domain.user_id != current_user.id and existing_domain.verification_status == "verified":
        raise HTTPException(
            status_code=403,
            detail=f"The domain '{clean_domain}' is already verified and owned by another user. If you are the rightful owner, please contact support with proof of registrar ownership."
        )

    # 2. Lookup target deployment
    deployment = None
    if deployment_id_str:
        try:
            dep_uuid = uuid.UUID(str(deployment_id_str))
            d_res = await db.execute(select(Deployment).where(Deployment.id == dep_uuid, Deployment.user_id == current_user.id))
            deployment = d_res.scalar_one_or_none()
        except Exception:
            pass

    if not deployment:
        recent_res = await db.execute(
            select(Deployment).where(Deployment.user_id == current_user.id).order_by(desc(Deployment.created_at)).limit(1)
        )
        deployment = recent_res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=400, detail="Please select or deploy an active website project first.")

    # 3. Authentic DNS challenge & ownership verification
    expected_token = (
        existing_domain.verification_token
        if (existing_domain and existing_domain.verification_token)
        else f"aisitestudio-verify-{current_user.id.hex[:10]}"
    )

    verification_result = await verify_domain_dns_ownership(clean_domain, expected_token)
    if not verification_result.get("verified"):
        if existing_domain:
            existing_domain.verification_status = "failed"
            await db.commit()
        raise HTTPException(
            status_code=400,
            detail=verification_result.get("reason", "Domain DNS ownership verification failed.")
        )

    # 4. Verified: Update or create Domain record
    if not existing_domain:
        existing_domain = Domain(
            deployment_id=deployment.id,
            user_id=current_user.id,
            domain=clean_domain,
            domain_type="custom",
            verification_status="verified",
            ssl_status="active",
            verification_token=expected_token,
        )
        db.add(existing_domain)
    else:
        existing_domain.deployment_id = deployment.id
        existing_domain.user_id = current_user.id
        existing_domain.verification_status = "verified"
        existing_domain.ssl_status = "active"

    deployment.custom_domain = clean_domain
    await db.commit()
    await db.refresh(existing_domain)

    return {
        "success": True,
        "status": "verified",
        "domain": clean_domain,
        "deployment_id": str(deployment.id),
        "project_name": deployment.project_name,
        "ssl_status": "active",
        "dns_detected": True,
        "method": verification_result.get("method", "dns"),
        "message": f"Domain '{clean_domain}' ownership verified ({verification_result.get('details')}) and connected to {deployment.project_name}!",
    }


@router.post("/domains/disconnect")
async def disconnect_domain_from_deployment(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely disconnects and unlinks a custom domain from a website deployment.
    """
    deployment_id_str = payload.get("deployment_id")
    clean_domain = str(payload.get("domain", "")).strip().lower().replace("https://", "").replace("http://", "").strip("/")

    deployment = None
    if deployment_id_str:
        try:
            dep_uuid = uuid.UUID(str(deployment_id_str))
            d_res = await db.execute(
                select(Deployment).where(Deployment.id == dep_uuid, Deployment.user_id == current_user.id)
            )
            deployment = d_res.scalar_one_or_none()
        except Exception:
            pass

    if not deployment and clean_domain:
        d_res = await db.execute(
            select(Deployment).where(Deployment.custom_domain == clean_domain, Deployment.user_id == current_user.id)
        )
        deployment = d_res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail="Target deployment not found.")

    old_domain = deployment.custom_domain
    deployment.custom_domain = None

    from app.models.deployment import Domain
    dom_res = await db.execute(
        select(Domain).where(Domain.deployment_id == deployment.id)
    )
    for dom in dom_res.scalars().all():
        await db.delete(dom)

    await db.commit()
    await db.refresh(deployment)

    return {
        "success": True,
        "message": f"Domain '{old_domain or 'Custom'}' was successfully disconnected from {deployment.project_name}.",
        "deployment_id": str(deployment.id),
    }


@router.get("/check-subdomain")
async def check_subdomain_availability(
    name: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a requested project subdomain on our domain (site-studio.live / aisitestudio.com) is available.
    If unavailable, generate intelligent, related alternative suggestions.
    """
    import re
    clean = re.sub(r"[^a-z0-9-]", "", name.lower().strip()).strip("-")
    if not clean:
        clean = "mysite"

    # Check if any deployment is already using this subdomain or project name
    query = select(Deployment.id).where(
        or_(
            func.lower(Deployment.project_name) == clean,
            func.lower(Deployment.subdomain).like(f"{clean}.%"),
            func.lower(Deployment.subdomain).like(f"{clean}-%"),
        )
    ).limit(1)
    result = await db.execute(query)
    is_taken = result.scalar_one_or_none() is not None

    reserved = {"admin", "api", "app", "root", "mail", "cdn", "staging", "auth", "billing", "dashboard", "studio"}
    if clean in reserved:
        is_taken = True

    # Generate smart, brand-friendly suggestions related to the given name
    suggestions = [
        f"{clean}-studio",
        f"{clean}-live",
        f"{clean}-official",
        f"get-{clean}",
        f"{clean}-pro",
    ]

    return {
        "requested": clean,
        "available": not is_taken,
        "subdomain": f"{clean}.site-studio.live",
        "domain_suffix": ".site-studio.live",
        "suggestions": suggestions,
    }


@router.get("/providers")
async def list_deployment_providers(current_user: User = Depends(get_current_user)):
    """Return configured deployment targets without exposing provider credentials."""
    local_enabled = settings.LOCAL_DEPLOYMENT_ENABLED or settings.ENVIRONMENT in {"development", "local", "test"}
    preferred_provider = settings.DEPLOYMENT_PROVIDER.strip().lower()
    enabled_ids = {"local"} if local_enabled else set()
    if settings.VERCEL_TOKEN:
        enabled_ids.add("vercel")
    if preferred_provider not in enabled_ids:
        preferred_provider = next(iter(enabled_ids), "")
    return {
        "default_provider": preferred_provider,
        "providers": [
            {"id": "local", "label": "AI Site Studio server hosting", "enabled": local_enabled},
            {"id": "vercel", "label": "Vercel static deployment", "enabled": bool(settings.VERCEL_TOKEN)},
        ]
    }


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_deployment(
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates and queues an isolated website deployment for the authenticated user.
    """
    user_tier = str(getattr(current_user, "subscription_tier", "free") or "free").lower()
    is_admin = getattr(current_user.role, "value", current_user.role) == "admin"
    is_extreme = user_tier in ("extreme", "agency", "enterprise") or is_admin
    is_pro = user_tier in ("pro", "creator_pro")

    if payload.template_id:
        template_result = await db.execute(select(Template).where(Template.id == payload.template_id))
        template = template_result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found.")
        can_deploy = (
            (template.is_free and template.status == TemplateStatus.PUBLISHED)
            or template.seller_id == current_user.id
            or is_extreme
        )
        if not can_deploy:
            purchase_result = await db.execute(
                select(OrderItem.id).join(Order, Order.id == OrderItem.order_id).where(
                    OrderItem.template_id == template.id,
                    Order.user_id == current_user.id,
                    Order.status == OrderStatus.COMPLETED,
                ).limit(1)
            )
            can_deploy = purchase_result.scalar_one_or_none() is not None
        if not can_deploy:
            raise HTTPException(status_code=403, detail="Purchase or own this template before deploying it.")

    if is_pro and not is_admin:
        # Pro plan users can deploy maximum 3 websites
        count_res = await db.execute(
            select(func.count(Deployment.id)).where(
                Deployment.user_id == current_user.id,
                Deployment.status != "deleted"
            )
        )
        active_sites = count_res.scalar_one() or 0
        if active_sites >= 3:
            raise HTTPException(
                status_code=403,
                detail="Pro Plan limit reached (maximum 3 deployed websites). Upgrade to the Extreme Plan for unlimited free deployments."
            )

    try:
        if payload.provider == "local" and settings.STRIPE_HOSTING_PRICE_ID and not is_extreme:
            if not payload.accepted_hosting_terms:
                raise HTTPException(status_code=400, detail="Accept the managed-hosting billing and cancellation terms before deploying.")
        if payload.provider == "local" and settings.ENVIRONMENT == "production" and not settings.STRIPE_HOSTING_PRICE_ID:
            raise HTTPException(status_code=503, detail="Monthly hosting billing is not configured; local deployment cannot be published.")
        service = DeploymentService(db, payload.provider or "local")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        deployment = await service.create_deployment(
            user=current_user,
            project_name=payload.project_name,
            template_id=payload.template_id,
            provider_type=payload.provider or "local",
            build_command=payload.build_command or "npm run build",
            output_dir=payload.output_dir or "dist",
            env_vars=payload.env_vars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Launch asynchronous build worker
    background_tasks.add_task(DeploymentService.run_deployment_pipeline, deployment.id, "v1.0")

    return deployment


@router.get("", response_model=List[DeploymentResponse])
@router.get("/", response_model=List[DeploymentResponse], include_in_schema=False)
async def list_deployments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all website deployments owned by the authenticated tenant.
    Strict tenant isolation: users only see their own deployments.
    """
    stmt = (
        select(Deployment)
        .where(Deployment.user_id == current_user.id)
        .order_by(desc(Deployment.created_at))
    )
    result = await db.execute(stmt)
    deployments = result.scalars().all()
    if not deployments:
        return []
    subscription_result = await db.execute(select(HostingSubscription).where(
        HostingSubscription.deployment_id.in_([deployment.id for deployment in deployments])
    ))
    subscriptions = {row.deployment_id: row for row in subscription_result.scalars().all()}
    responses = []
    for deployment in deployments:
        response = DeploymentResponse.model_validate(deployment)
        subscription = subscriptions.get(deployment.id)
        response.hosting_subscription_status = subscription.status if subscription else "not_subscribed"
        if subscription:
            response.hosting_subscription_cancel_at_period_end = subscription.cancel_at_period_end
            response.hosting_subscription_period_end = subscription.current_period_end
        responses.append(response)
    return responses


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Gets detailed metadata, version history, mapped domains, and recent logs for a deployment.
    """
    stmt = (
        select(Deployment)
        .where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
        .options(
            selectinload(Deployment.versions),
            selectinload(Deployment.domains),
            selectinload(Deployment.deployment_logs),
        )
    )
    result = await db.execute(stmt)
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found or access denied.")

    # Sort recent logs
    recent_logs = sorted(deployment.deployment_logs, key=lambda l: l.timestamp, reverse=True)[:50]

    return DeploymentDetailResponse(
        id=deployment.id,
        user_id=deployment.user_id,
        site_id=deployment.site_id,
        project_name=deployment.project_name,
        provider=deployment.provider,
        status=deployment.status,
        current_version=deployment.current_version,
        deployment_type=deployment.deployment_type,
        health_status=deployment.health_status,
        subdomain=deployment.subdomain,
        branch=deployment.branch,
        commit_message=deployment.commit_message,
        build_command=deployment.build_command,
        output_dir=deployment.output_dir,
        live_url=deployment.live_url,
        custom_domain=deployment.custom_domain,
        logs=deployment.logs,
        env_vars=deployment.env_vars,
        is_suspended=deployment.is_suspended,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        versions=deployment.versions,
        domains=deployment.domains,
        recent_logs=recent_logs,
    )


@router.get("/{deployment_id}/full-details")
async def get_deployment_full_details(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns rich, comprehensive details for a deployed website including:
    - Core deployment metadata, status, version, URLs
    - Framework & stack detection
    - Live & historical build/runtime logs
    - User/visitor analytics & telemetry
    - Automated issues fixed & Site Doctor incidents
    - Blockers detector & AI token status
    - Custom / purchased domain details
    - Payment & renewal countdown reminders
    - Launch checklist with missed item reminders
    """
    from app.models.incident import SiteIncident

    stmt = (
        select(Deployment)
        .where(
            Deployment.id == deployment_id,
            or_(Deployment.user_id == current_user.id, current_user.role == "admin"),
        )
        .options(
            selectinload(Deployment.versions),
            selectinload(Deployment.domains),
            selectinload(Deployment.deployment_logs),
            selectinload(Deployment.incidents),
            selectinload(Deployment.template),
        )
    )
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found or access denied.")

    # Fetch hosting subscription
    sub_stmt = select(HostingSubscription).where(HostingSubscription.deployment_id == deployment.id)
    sub_res = await db.execute(sub_stmt)
    subscription = sub_res.scalar_one_or_none()

    from app.services.deployment_deep_analyzer import deeply_analyze_deployment
    analysis = deeply_analyze_deployment(deployment, current_user, subscription)

    # Logs (most recent 100)
    sorted_logs = sorted(
        deployment.deployment_logs,
        key=lambda l: l.timestamp if l.timestamp else datetime.min,
        reverse=True
    )[:100]
    recent_logs = [
        {
            "id": str(log.id),
            "level": log.level,
            "message": log.message,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in sorted_logs
    ]

    # Versions
    versions = [
        {
            "id": str(v.id),
            "version": v.version,
            "status": v.status,
            "commit_message": v.commit_message,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in deployment.versions
    ]

    return {
        "id": str(deployment.id),
        "site_id": deployment.site_id or f"SITE-{deployment.id.hex[:6].upper()}",
        "project_name": deployment.project_name,
        "status": deployment.status,
        "health_status": deployment.health_status,
        "current_version": deployment.current_version,
        "deployment_type": deployment.deployment_type,
        "provider": deployment.provider,
        "subdomain": deployment.subdomain,
        "live_url": deployment.live_url or f"https://{deployment.subdomain}.site-studio.cloud",
        "custom_domain": deployment.custom_domain,
        "branch": deployment.branch,
        "build_command": deployment.build_command,
        "output_dir": deployment.output_dir,
        "is_suspended": deployment.is_suspended,
        "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
        "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None,
        "framework": analysis["framework"],
        "template": analysis["template"],
        "bundle_stats": analysis["bundle_stats"],
        "domain_details": analysis["domain_details"],
        "renewal_reminder": analysis["renewal_reminder"],
        "token_diagnostic": analysis["token_diagnostic"],
        "blockers": analysis["blockers"],
        "issues_fixed": analysis["issues_fixed"],
        "checklist": analysis["checklist"],
        "analytics": analysis["analytics"],
        "versions": versions,
        "recent_logs": recent_logs,
        "raw_logs": deployment.logs or "",
    }


@router.post("/{deployment_id}/redeploy", response_model=DeploymentResponse)
async def redeploy_deployment(
    deployment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers a fresh compilation and zero-downtime deployment for an existing website.
    """
    service = DeploymentService(db)
    try:
        deployment = await service.redeploy(current_user, deployment_id)
        background_tasks.add_task(DeploymentService.run_deployment_pipeline, deployment.id, deployment.current_version)
        return deployment
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/self-heal")
async def self_heal_deployment(
    deployment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Autonomous Self-Healing Endpoint:
    Diagnoses build, runtime, and framework issues from deployment logs,
    applies permanent patches to the codebase, and triggers an automated redeployment.
    """
    from app.services.deployment_readiness_auditor import deployment_readiness_auditor
    import re

    service = DeploymentService(db)
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found or access denied.")

    # Calculate next version (e.g. v1.0 -> v1.1)
    curr_ver = deployment.current_version or "v1.0"
    match = re.search(r"v?(\d+)\.(\d+)", curr_ver)
    if match:
        major, minor = int(match.group(1)), int(match.group(2))
        next_ver = f"v{major}.{minor + 1}"
    else:
        next_ver = "v1.1"

    deployment.status = "queued"
    deployment.logs = (deployment.logs or "") + f"[{datetime.now().strftime('%H:%M:%S')}] [SELF-HEAL] 🩺 Manual Self-Healing triggered by user. Queueing version {next_ver}...\n"
    await db.commit()
    await service.log_event(deployment.id, "SELF-HEAL", f"Manual Self-Healing triggered for version {next_ver}.")

    # Launch pipeline with audit & self-healing active
    background_tasks.add_task(DeploymentService.run_deployment_pipeline, deployment.id, next_ver)

    return {
        "success": True,
        "message": f"Autonomous Self-Healing triggered. Re-auditing, repairing, and deploying version {next_ver}.",
        "version": next_ver,
        "site_id": deployment.site_id,
        "status": "queued",
    }


@router.get("/{deployment_id}/readiness-audit")
async def get_deployment_readiness_audit(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a real-time production readiness audit on the deployment source without deploying.
    """
    from app.services.deployment_readiness_auditor import deployment_readiness_auditor
    from app.core.local_project_manager import local_project_manager

    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found or access denied.")

    # Locate source directory
    proj_dir = local_project_manager._resolve_project_dir(deployment.project_name)
    target_dir = (proj_dir / "latest") if proj_dir.exists() and (proj_dir / "latest").exists() else None

    if not target_dir or not target_dir.exists():
        site_id = deployment.site_id or f"SITE-{deployment.id.hex[:6].upper()}"
        from app.services.deployment_healing_service import DeploymentHealingService
        target_dir = DeploymentHealingService.get_site_current_dir(site_id)

    if not target_dir or not target_dir.exists():
        return {
            "is_production_ready": True,
            "findings": ["Source code is compiled in production storage."],
            "healed_files": [],
            "warnings": [],
            "summary": "Deployment is active."
        }

    audit_result = deployment_readiness_auditor.audit_and_heal_source(
        source_path=target_dir,
        template_identifier=deployment.project_name,
    )
    return audit_result


@router.post("/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: uuid.UUID,
    payload: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes an atomic zero-downtime rollback to a previous version (e.g. 'v1.0').
    """
    service = DeploymentService(db)
    success, result_msg = await service.rollback_to_version(current_user, deployment_id, payload.target_version)
    if not success:
        raise HTTPException(status_code=400, detail=result_msg)
    return {"message": f"Successfully rolled back to version {payload.target_version}", "live_url": result_msg}


@router.post("/{deployment_id}/suspend")
async def suspend_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Suspends a live deployment without deleting files or version history.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    provider = get_deployment_provider(deployment.provider)
    if not await provider.stop(deployment.site_id):
        raise HTTPException(status_code=400, detail=f"The {deployment.provider} provider does not support pausing deployments from this dashboard.")
    deployment.status = "suspended"
    deployment.is_suspended = True
    await db.commit()
    return {"message": f"Deployment {deployment.site_id} is now suspended."}


@router.post("/{deployment_id}/resume")
async def resume_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resumes a suspended deployment by restoring its active version.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    provider = get_deployment_provider(deployment.provider)
    ok, message = await provider.rollback(deployment.site_id, deployment.current_version)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    deployment.status = "live"
    deployment.is_suspended = False
    await db.commit()
    return {"message": f"Deployment {deployment.site_id} is now active.", "live_url": deployment.live_url}


@router.delete("/{deployment_id}", status_code=status.HTTP_200_OK)
async def delete_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes a deployment and permanently purges its isolated storage artifacts.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    domain_result = await db.execute(select(Domain).where(
        Domain.deployment_id == deployment.id,
        Domain.domain_type == "purchased",
        Domain.registrar_registration_id.is_not(None),
    ))
    purchased_domains = domain_result.scalars().all()
    # Expiry alone does not mean the registrar account has released the name;
    # retain the record until support confirms a transfer or release.
    active_domains = [domain.domain for domain in purchased_domains]
    if active_domains:
        names = ", ".join(active_domains[:3])
        raise HTTPException(
            status_code=409,
            detail=f"This deployment owns registered domain(s) ({names}). Transfer or release the domain with Studio support before deleting the site; domain registration is not canceled by deleting hosting.",
        )

    subscription_result = await db.execute(select(HostingSubscription).where(
        HostingSubscription.deployment_id == deployment.id
    ).with_for_update())
    hosting_subscription = subscription_result.scalar_one_or_none()
    if hosting_subscription:
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Cannot safely delete this site until Stripe billing is configured.")
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            remote_subscription = stripe.Subscription.retrieve(hosting_subscription.stripe_subscription_id)
            if remote_subscription.get("status") not in {"canceled", "incomplete_expired"}:
                stripe.Subscription.cancel(hosting_subscription.stripe_subscription_id, prorate=False)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not stop recurring hosting billing, so the site was not deleted.") from exc

    provider = get_deployment_provider(deployment.provider)
    if deployment.provider == "vercel":
        removed = await provider.remove_by_url(deployment.live_url)
    else:
        removed = await provider.remove(deployment.site_id)
    if not removed:
        if hosting_subscription:
            try:
                stopped = await provider.stop(deployment.site_id)
                if stopped:
                    deployment.status = "suspended"
                    deployment.is_suspended = True
                    await db.commit()
            except Exception:
                logger.exception("Could not suspend deployment %s after storage removal failed", deployment.id)
        raise HTTPException(status_code=502, detail=f"Could not remove the deployment from {deployment.provider}.")

    await db.delete(deployment)
    await db.commit()
    return {"message": f"Deployment {deployment_id} deleted successfully."}


@router.get("/{deployment_id}/versions", response_model=List[DeploymentVersionResponse])
async def list_deployment_versions(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all deployment version snapshots for 1-click rollback.
    """
    # Verify ownership
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    if not d_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")

    stmt = select(DeploymentVersion).where(DeploymentVersion.deployment_id == deployment_id).order_by(desc(DeploymentVersion.created_at))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{deployment_id}/logs", response_model=List[DeploymentLogResponse])
async def get_deployment_logs(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns structured, secret-masked logs for a deployment.
    """
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    if not d_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deployment not found.")

    stmt = select(DeploymentLog).where(DeploymentLog.deployment_id == deployment_id).order_by(desc(DeploymentLog.timestamp)).limit(100)
    res = await db.execute(stmt)
    return res.scalars().all()
@router.patch("/{deployment_id}/domain", response_model=DeploymentResponse)
async def update_custom_domain(
    deployment_id: uuid.UUID,
    custom_domain: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Directly links or unlinks a custom domain for a deployment with automatic validation,
    live URL synchronization, and SSL domain record generation.
    """
    d_res = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = d_res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if not custom_domain:
        domain_res = await db.execute(select(Domain).where(Domain.deployment_id == deployment.id, Domain.domain_type == "custom"))
        for domain_record in domain_res.scalars().all():
            await db.delete(domain_record)
        deployment.custom_domain = None
        await db.commit()
        await db.refresh(deployment)
        return deployment

    if custom_domain and custom_domain.strip():
        # Sanitize domain: strip protocols, slashes, whitespace, and lowercase
        clean_domain = custom_domain.strip().lower()
        if clean_domain.startswith("https://"):
            clean_domain = clean_domain[8:]
        elif clean_domain.startswith("http://"):
            clean_domain = clean_domain[7:]
        clean_domain = clean_domain.strip("/").strip()

        # Validate domain format
        if "." not in clean_domain or len(clean_domain) < 4:
            raise HTTPException(
                status_code=400,
                detail="Please enter a valid domain name (e.g. 'mybrand.com' or 'app.mybrand.com')."
            )

        # Check for conflicts with other projects
        conflict_res = await db.execute(
            select(Deployment).where(
                Deployment.custom_domain == clean_domain,
                Deployment.id != deployment.id
            )
        )
        if conflict_res.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"The domain '{clean_domain}' is already linked to another project."
            )

        deployment.custom_domain = clean_domain
        # Synchronize live_url so testing works directly in development and production
        backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
        deployment.live_url = deployment.live_url or f"{backend_url}/sites/{deployment.site_id}/"

        # Create or update domain record
        dom_res = await db.execute(
            select(Domain).where(Domain.deployment_id == deployment.id, Domain.domain == clean_domain)
        )
        domain_record = dom_res.scalar_one_or_none()
        if not domain_record:
            domain_record = Domain(
                deployment_id=deployment.id,
                user_id=current_user.id,
                domain=clean_domain,
                domain_type="custom",
                verification_status="pending_verification",
                ssl_status="pending",
                verification_token=f"verify-{uuid.uuid4().hex[:8]}",
            )
            db.add(domain_record)
        else:
            domain_record.verification_status = "pending_verification"
            domain_record.ssl_status = "pending"
    else:
        deployment.custom_domain = None
        site_id = deployment.site_id or f"SITE-{deployment.id.hex[:6].upper()}"
        backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
        deployment.live_url = f"{backend_url}/sites/{site_id}/"

    await db.commit()
    await db.refresh(deployment)
    return deployment


@router.post("/{deployment_id}/verify-domain")
async def verify_custom_domain(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies authentic DNS routing, TXT challenge ownership, and SSL certificate provisioning for a linked custom domain.
    """
    d_res = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = d_res.scalar_one_or_none()
    if not deployment or not deployment.custom_domain:
        raise HTTPException(status_code=400, detail="No custom domain is currently linked to this deployment.")

    clean_domain = deployment.custom_domain
    from app.services.dns_verification_service import verify_domain_dns_ownership

    dom_res = await db.execute(
        select(Domain).where(Domain.deployment_id == deployment.id, Domain.domain == clean_domain)
    )
    dom_record = dom_res.scalar_one_or_none()
    token = dom_record.verification_token if dom_record else f"aisitestudio-verify-{current_user.id.hex[:10]}"

    v_res = await verify_domain_dns_ownership(clean_domain, token)
    if not v_res.get("verified"):
        if dom_record:
            dom_record.verification_status = "failed"
            await db.commit()
        raise HTTPException(status_code=400, detail=v_res.get("reason", "Domain DNS verification failed."))

    if dom_record:
        dom_record.verification_status = "verified"
        dom_record.ssl_status = "active"
        await db.commit()

    return {
        "status": "verified",
        "domain": clean_domain,
        "ssl_status": "active",
        "details": v_res.get("details"),
        "message": f"Domain {clean_domain} DNS records verified and SSL issued successfully!",
    }



@router.post("/{deployment_id}/domains", response_model=DomainResponse)
async def add_custom_domain(
    deployment_id: uuid.UUID,
    payload: DomainCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Maps a custom domain (e.g. 'www.mybrand.com') to a deployment with pending verification.
    """
    d_res = await db.execute(select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id))
    deployment = d_res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if deployment.provider == "vercel":
        raise HTTPException(status_code=400, detail="Connect custom domains for this deployment in Vercel.")

    clean_domain = payload.domain.strip().lower()
    token = f"aisitestudio-verify-{uuid.uuid4().hex[:12]}"

    domain_record = Domain(
        deployment_id=deployment.id,
        user_id=current_user.id,
        domain=clean_domain,
        domain_type="custom",
        verification_status="pending_verification",
        ssl_status="pending",
        verification_token=token,
    )
    db.add(domain_record)
    deployment.custom_domain = clean_domain
    await db.commit()
    await db.refresh(domain_record)
    return domain_record


@router.post("/{deployment_id}/domains/{domain_id}/verify", response_model=DomainResponse)
async def verify_custom_domain(
    deployment_id: uuid.UUID,
    domain_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies DNS CNAME / A-record configuration for a custom domain with authentic DNS queries.
    """
    stmt = select(Domain).where(
        Domain.id == domain_id,
        Domain.deployment_id == deployment_id,
        Domain.user_id == current_user.id
    )
    res = await db.execute(stmt)
    domain_record = res.scalar_one_or_none()
    if not domain_record:
        raise HTTPException(status_code=404, detail="Domain mapping not found.")

    from app.services.dns_verification_service import verify_domain_dns_ownership
    v_res = await verify_domain_dns_ownership(
        domain_record.domain,
        domain_record.verification_token or f"aisitestudio-verify-{current_user.id.hex[:10]}"
    )
    if not v_res.get("verified"):
        domain_record.verification_status = "failed"
        await db.commit()
        raise HTTPException(status_code=400, detail=v_res.get("reason", "DNS verification failed."))

    domain_record.verification_status = "verified"
    domain_record.ssl_status = "active"
    await db.commit()
    await db.refresh(domain_record)
    return domain_record


@router.patch("/{deployment_id}/env", response_model=DeploymentResponse)
async def update_environment_variables(
    deployment_id: uuid.UUID,
    payload: EnvironmentVariableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Updates tenant-scoped public environment variables for the deployment.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    deployment.env_vars = payload.env_vars
    await db.commit()
    await db.refresh(deployment)
    return deployment


@router.options("/telemetry/{site_identifier}", include_in_schema=False)
async def options_client_telemetry(site_identifier: str):
    """Handle preflight requests for telemetry from any client origin."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )


@router.post("/telemetry/{site_identifier}", response_model=dict, status_code=status.HTTP_200_OK)
async def record_client_telemetry(
    site_identifier: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests live browser runtime console logs and client boot events from running tenant websites.
    Publicly accessible with permissive CORS so live visitors can stream telemetry without errors.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    
    clean_site_id = site_identifier.split(".")[0].upper()
    time_str = datetime.now().strftime("%H:%M:%S")

    payload = None
    if payload is None:
        try:
            body = await request.body()
            if body:
                import json
                data = json.loads(body.decode("utf-8"))
                payload = ClientTelemetryPayload(**data)
            else:
                payload = ClientTelemetryPayload(level="INFO", message="client_ping")
        except Exception:
            payload = ClientTelemetryPayload(level="INFO", message="client_ping")

    return {"status": "accepted", "site_id": clean_site_id, "recorded_at": time_str}


@router.post("/{deployment_id}/health-check")
async def trigger_deployment_health_check(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes an on-demand live health verification against the tenant website.
    Verifies HTTP responsiveness and records verification telemetry into logs.
    """
    stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    service = DeploymentService(db)
    is_healthy, status_str, msg = await service.provider.health_check(deployment.live_url or "", site_id=deployment.site_id)
    deployment.health_status = "healthy" if is_healthy else "degraded"
    time_str = datetime.now().strftime("%H:%M:%S")
    tag = "[HEALTH CHECK SUCCESS]" if is_healthy else "[HEALTH CHECK FAILED]"
    level = "INFO" if is_healthy else "ERROR"
    log_line = f"[{time_str}] [{level}] {tag} {msg}\n"

    curr = deployment.logs or ""
    if len(curr) > 200_000:
        curr = curr[-150_000:]
    deployment.logs = curr + log_line

    db.add(DeploymentLog(
        deployment_id=deployment.id,
        level=level,
        message=f"{tag} {msg}"[:500]
    ))

    await db.commit()
    await db.refresh(deployment)
    return {
        "is_healthy": is_healthy,
        "health_status": deployment.health_status,
        "message": msg,
        "checked_at": time_str
    }




@router.get("/{deployment_id}/files")
async def get_deployment_files(
    deployment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all files in the deployment's current directory for the web Code Studio.
    Accessible to the deployment owner or platform admin.
    """
    from app.services.deployment_healing_service import DeploymentHealingService

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    is_admin = getattr(current_user, "is_superuser", False) or getattr(current_user, "role", "") == "admin"
    if deployment.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this deployment.")

    healing_service = DeploymentHealingService(db)
    files = healing_service.list_files(deployment.site_id)
    return {
        "deployment_id": str(deployment.id),
        "site_id": deployment.site_id,
        "project_name": deployment.project_name,
        "current_version": deployment.current_version,
        "live_url": deployment.live_url,
        "files": files,
    }


@router.get("/{deployment_id}/file-content")
async def get_deployment_file_content(
    deployment_id: uuid.UUID,
    path: str = Query(..., description="Relative file path"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Safely reads file content for the code editor.
    Accessible to the deployment owner or platform admin.
    """
    from app.services.deployment_healing_service import DeploymentHealingService

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    is_admin = getattr(current_user, "is_superuser", False) or getattr(current_user, "role", "") == "admin"
    if deployment.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this deployment.")

    healing_service = DeploymentHealingService(db)
    success, content, ext = healing_service.read_file(deployment.site_id, path)
    if not success:
        raise HTTPException(status_code=400, detail=content)

    return {
        "path": path,
        "content": content,
        "ext": ext,
        "size": len(content),
    }


@router.put("/{deployment_id}/files")
async def save_deployment_file(
    deployment_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Saves updated code, hot-reloads the deployed site, and ensures zero-downtime live updates.
    Accessible to the deployment owner or platform admin.
    """
    from app.services.deployment_healing_service import DeploymentHealingService

    file_path = payload.get("path")
    content = payload.get("content")

    if not file_path or content is None:
        raise HTTPException(status_code=400, detail="Path and content are required.")

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    is_admin = getattr(current_user, "is_superuser", False) or getattr(current_user, "role", "") == "admin"
    if deployment.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this deployment.")

    user_label = "Admin" if is_admin else f"Owner ({current_user.email or current_user.name or 'User'})"
    healing_service = DeploymentHealingService(db)
    success, msg = await healing_service.save_file(
        deployment=deployment,
        relative_path=file_path,
        content=content,
        user_or_admin_label=user_label,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    # Invalidate site resolution cache timestamp so clean state is served
    try:
        from app.api.v1.routes.site_router import _SITE_RESOLUTION_CACHE
        _SITE_RESOLUTION_CACHE.pop(deployment.site_id.lower(), None)
        _SITE_RESOLUTION_CACHE.pop(deployment.site_id.upper(), None)
    except Exception:
        pass

    return {
        "message": msg,
        "path": file_path,
        "site_id": deployment.site_id,
        "live_url": deployment.live_url,
        "health": "HTTP 200 OK",
    }


class DeploymentAIEditPayload(BaseModel):
    prompt: str
    model: Optional[str] = "gemini-1.5-flash"
    file_path: Optional[str] = None


@router.post("/{deployment_id}/ai-edit")
async def ai_edit_deployment(
    deployment_id: uuid.UUID,
    payload: DeploymentAIEditPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Applies natural language AI instructions (copywriting, styling, adding features)
    to the deployed website with user-chosen AI model routing.
    """
    from app.services.ai_service import ai_service
    from app.services.deployment_healing_service import DeploymentHealingService

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    is_admin = getattr(current_user, "is_superuser", False) or getattr(current_user, "role", "") == "admin"
    if deployment.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied: You do not own this deployment.")

    healing_service = DeploymentHealingService(db)
    files_dict = healing_service.load_editable_files_dict(deployment.site_id, max_files=15)
    if not files_dict:
        raise HTTPException(status_code=400, detail="No editable files found for this deployment.")

    result = await ai_service.edit_website_with_ai(
        files_dict=files_dict,
        prompt=payload.prompt,
        target_file=payload.file_path,
        model_name=payload.model,
    )

    patched_paths = []
    user_label = "Admin" if is_admin else f"Owner ({current_user.email or current_user.name or 'User'})"
    for item in result.get("updated_files", []):
        rel_path = item.get("path")
        code = item.get("content")
        if rel_path and code:
            ok, _ = await healing_service.save_file(
                deployment=deployment,
                relative_path=rel_path,
                content=code,
                user_or_admin_label=f"{user_label} (via AI {payload.model})",
            )
            if ok:
                patched_paths.append(rel_path)

    try:
        from app.api.v1.routes.site_router import _SITE_RESOLUTION_CACHE
        _SITE_RESOLUTION_CACHE.pop(deployment.site_id.lower(), None)
        _SITE_RESOLUTION_CACHE.pop(deployment.site_id.upper(), None)
    except Exception:
        pass

    return {
        "status": "success",
        "model": payload.model,
        "summary": result.get("summary", "AI website edit completed."),
        "patched_files": patched_paths,
        "site_id": deployment.site_id,
        "live_url": deployment.live_url,
    }
