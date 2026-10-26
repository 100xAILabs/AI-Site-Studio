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
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, Request
from sqlalchemy import select, desc
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
    if not settings.STRIPE_HOSTING_PRICE_ID or not settings.STRIPE_SECRET_KEY:
        return {"configured": False}
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        price = stripe.Price.retrieve(settings.STRIPE_HOSTING_PRICE_ID, expand=["product"])
        recurring = price.get("recurring") or {}
        return {
            "configured": bool(price.get("active") and recurring.get("interval") == "month"),
            "amount_minor": price.get("unit_amount"),
            "currency": price.get("currency", "usd").upper(),
            "interval": recurring.get("interval"),
            "interval_count": recurring.get("interval_count", 1),
        }
    except Exception:
        return {"configured": False}


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
    profile: DomainRegistrantProfile


class DomainPurchaseRequest(DomainRegistrationQuoteRequest):
    deployment_id: uuid.UUID
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
    if not settings.STRIPE_HOSTING_PRICE_ID or not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Monthly hosting billing is not configured by the platform administrator.")
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if deployment.hosting_checkout_session_id:
            previous = stripe.checkout.Session.retrieve(deployment.hosting_checkout_session_id)
            if previous.get("status") == "open":
                return {"checkout_url": previous.url}
            if previous.get("status") == "complete":
                raise HTTPException(status_code=409, detail="Hosting payment is being processed. Refresh the deployments page shortly.")
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.STRIPE_HOSTING_PRICE_ID, "quantity": 1}],
            customer_email=current_user.email,
            client_reference_id=str(deployment.id),
            metadata={"purchase_type": "hosting_subscription", "deployment_id": str(deployment.id), "user_id": str(current_user.id)},
            subscription_data={"metadata": {"deployment_id": str(deployment.id), "user_id": str(current_user.id)}},
            success_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&hosting=active",
            cancel_url=f"{settings.FRONTEND_URL.rstrip('/')}/dashboard?tab=deployments&hosting=cancelled",
        )
        deployment.hosting_checkout_session_id = checkout.id
        await db.commit()
        return {"checkout_url": checkout.url}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not start secure hosting checkout.") from exc


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
    deployment_result = await db.execute(select(Deployment).where(
        Deployment.id == payload.deployment_id, Deployment.user_id == current_user.id
    ))
    deployment = deployment_result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    if deployment.provider != "local":
        raise HTTPException(status_code=400, detail="GoDaddy domains can only be connected to Studio-hosted deployments.")
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("your-"):
        raise HTTPException(status_code=503, detail="Secure domain checkout is not configured.")

    quote = await godaddy_domain_service.quote(payload.domain, payload.period)
    if not quote.get("available") or not quote.get("quoteToken"):
        raise HTTPException(status_code=409, detail="This domain is not available to register at the quoted price.")
    required = {item.get("agreementType") for item in quote.get("requiredAgreements", []) if item.get("agreementType")}
    if not required.issubset(set(payload.accepted_agreements)):
        raise HTTPException(status_code=400, detail="Accept each GoDaddy/registry agreement shown for this domain.")
    fees = quote.get("fees", []) or []
    if fees and payload.accepted_fees != fees:
        raise HTTPException(status_code=400, detail="Confirm the additional fees shown in the current GoDaddy quote.")
    price = quote.get("price") or {}
    currency = str(price.get("currencyCode", "")).lower()
    base_amount_minor = price.get("value")
    fees_minor = sum(int((item.get("fee") or {}).get("value", 0)) for item in (quote.get("fees") or []))
    amount_minor = base_amount_minor + fees_minor if isinstance(base_amount_minor, int) else None
    if currency not in {"usd", "eur", "gbp", "cad", "aud", "inr"} or not isinstance(amount_minor, int) or amount_minor <= 0:
        raise HTTPException(status_code=422, detail="GoDaddy returned an unsupported registration price.")
    renewal_price_minor = (quote.get("renewalPrice") or {}).get("value")
    if amount_minor != payload.quoted_total_minor or currency.upper() != payload.quoted_currency.upper() or renewal_price_minor != payload.quoted_renewal_price_minor:
        raise HTTPException(status_code=409, detail="The domain price changed since you reviewed it. Please review the updated registration and renewal quote before paying.")

    from app.core.security import encrypt_oauth_token
    from app.models.deployment import Domain
    import json
    import stripe

    existing_result = await db.execute(select(Domain).where(Domain.domain == quote["domain"].lower()))
    existing_domain = existing_result.scalar_one_or_none()
    if existing_domain:
        if existing_domain.user_id != current_user.id or existing_domain.deployment_id != deployment.id:
            raise HTTPException(status_code=409, detail="This domain already has a purchase or deployment record.")
        if existing_domain.registrar_registration_id or existing_domain.registrar_status not in {
            "pending_payment", "checkout_expired", "payment_failed"
        }:
            raise HTTPException(status_code=409, detail=f"This domain purchase is already {existing_domain.registrar_status}.")
        if existing_domain.stripe_checkout_session_id:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                old_checkout = stripe.checkout.Session.retrieve(existing_domain.stripe_checkout_session_id)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Could not check the previous domain checkout.") from exc
            if old_checkout.get("status") == "open":
                return {"domain_id": str(existing_domain.id), "checkout_url": old_checkout.url,
                        "domain": existing_domain.domain, "registration_price_minor": existing_domain.registration_price_minor,
                        "renewal_price_minor": existing_domain.renewal_price_minor, "currency": existing_domain.price_currency,
                        "period_years": existing_domain.registration_period_years, "auto_renew": existing_domain.auto_renew}
            if old_checkout.get("payment_status") == "paid":
                raise HTTPException(status_code=409, detail="Payment was received; the domain registration is being processed.")
            if old_checkout.get("status") != "expired":
                raise HTTPException(status_code=409, detail="The earlier domain checkout is still being finalized. Refresh the deployment page shortly.")
        await db.delete(existing_domain)
        await db.flush()

    domain = Domain(
        deployment_id=deployment.id,
        user_id=current_user.id,
        domain=quote["domain"].lower(),
        domain_type="purchased",
        verification_status="pending_payment",
        ssl_status="pending",
        registrar_status="pending_payment",
        registrar_data_encrypted=encrypt_oauth_token(json.dumps({
            "quote_token": quote["quoteToken"],
            "profile": payload.profile.model_dump(exclude_none=True),
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
        # GoDaddy enables auto-renew by default; disable it after registration so
        # Studio never renews a customer's domain against its own billing method.
        auto_renew=False,
    )
    db.add(domain)
    try:
        await db.flush()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout = stripe.checkout.Session.create(
            mode="payment",
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
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {
        "domain_id": str(domain.id),
        "checkout_url": checkout.url,
        "domain": domain.domain,
        "registration_price_minor": amount_minor,
        "renewal_price_minor": domain.renewal_price_minor,
        "currency": domain.price_currency,
        "period_years": payload.period,
        "auto_renew": domain.auto_renew,
        "expires_at": quote.get("expiresAt"),
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
    if payload.template_id:
        template_result = await db.execute(select(Template).where(Template.id == payload.template_id))
        template = template_result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found.")
        can_deploy = (
            (template.is_free and template.status == TemplateStatus.PUBLISHED)
            or template.seller_id == current_user.id
            or getattr(current_user.role, "value", current_user.role) == "admin"
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

    try:
        if payload.provider == "local" and settings.STRIPE_HOSTING_PRICE_ID:
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
    raise HTTPException(status_code=501, detail="Custom domains are not enabled for this hosting setup. Use the deployment provider's domain settings after the site is live.")

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
    Verifies DNS routing, SSL certificate provisioning, and HTTP accessibility for a linked custom domain.
    """
    d_res = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = d_res.scalar_one_or_none()
    if not deployment or not deployment.custom_domain:
        raise HTTPException(status_code=400, detail="No custom domain is currently linked to this deployment.")

    clean_domain = deployment.custom_domain
    backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
    test_proxy_url = f"{backend_url}/sites/{clean_domain}/"

    raise HTTPException(status_code=501, detail="Custom-domain DNS and HTTPS verification are not configured for this hosting setup.")



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
    raise HTTPException(status_code=501, detail="Custom domains are not enabled for this hosting setup. Use the deployment provider's domain settings after the site is live.")

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
    Verifies DNS CNAME / A-record configuration for a custom domain.
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

    raise HTTPException(status_code=501, detail="DNS challenge verification is not configured yet. The domain remains pending; it will not be marked live or HTTPS-enabled automatically.")


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


@router.post("/telemetry/{site_identifier}", response_model=dict, status_code=status.HTTP_200_OK)
async def record_client_telemetry(
    site_identifier: str,
    payload: ClientTelemetryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests live browser runtime console logs (console.log, console.warn, console.error,
    unhandled window errors, client boot events) from running live tenant websites.
    Publicly accessible without auth so live visitors/browsers can stream runtime telemetry.
    """
    from app.core.request_limits import enforce_user_limit
    client_ip = request.client.host if request.client else "unknown"
    await enforce_user_limit(client_ip, "deployment-telemetry", limit=60, window_seconds=60)
    clean_identifier = site_identifier.strip().lower()
    clean_site_id = site_identifier.split(".")[0].upper()

    stmt = select(Deployment).where(
        (Deployment.site_id == clean_site_id) |
        (Deployment.subdomain == clean_identifier) |
        (Deployment.custom_domain == clean_identifier) |
        (Deployment.subdomain == f"{clean_identifier}.aisitestudio.com")
    ).limit(1)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()

    if not deployment:
        stmt2 = select(Deployment).where(Deployment.site_id.ilike(clean_site_id)).limit(1)
        res2 = await db.execute(stmt2)
        deployment = res2.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail=f"Deployment '{site_identifier}' not found.")

    time_str = datetime.now().strftime("%H:%M:%S")
    clean_msg = payload.message.strip()[:4000]
    lvl = payload.level.upper() if payload.level else "INFO"
    if lvl not in ("INFO", "WARN", "ERROR", "SUCCESS"):
        lvl = "INFO"

    # Format log line with timestamp and level
    formatted_log = f"[{time_str}] [{lvl}] {clean_msg}\n"

    # This endpoint accepts anonymous browser input. Keep it informational only:
    # do not persist untrusted rows or allow clients to alter server health state.
    return {"status": "accepted", "site_id": deployment.site_id, "recorded_at": time_str}


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


