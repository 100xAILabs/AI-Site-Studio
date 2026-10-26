"""Paid domain-registration fulfillment; safe for Stripe webhook retries."""

import json
import logging

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_oauth_token
from app.models.deployment import Deployment, Domain
from app.services.godaddy_domain_service import godaddy_domain_service

logger = logging.getLogger(__name__)


async def fulfill_domain_checkout(session: dict, db: AsyncSession) -> None:
    metadata = session.get("metadata") or {}
    if metadata.get("purchase_type") != "domain_registration":
        return
    domain_id = metadata.get("domain_id") or session.get("client_reference_id")
    if not domain_id:
        raise ValueError("Domain checkout is missing its purchase reference.")

    result = await db.execute(select(Domain).where(Domain.id == domain_id).with_for_update())
    domain = result.scalar_one_or_none()
    if not domain:
        raise ValueError("Domain purchase record does not exist.")
    if domain.registrar_registration_id or domain.registrar_status in {
        "registering", "registered", "active", "completed", "confirmed",
        "registration_failed", "refunded_registration_failed", "failed",
    }:
        return
    if session.get("payment_status") != "paid":
        return

    payment_intent = session.get("payment_intent")
    amount_paid = session.get("amount_total")
    currency_paid = str(session.get("currency") or "").upper()
    if not payment_intent or amount_paid != domain.registration_price_minor or currency_paid != domain.price_currency:
        raise ValueError("Domain payment amount or currency does not match the approved quote.")

    try:
        details = json.loads(decrypt_oauth_token(domain.registrar_data_encrypted or ""))
        # Quote again after payment: GoDaddy quote tokens expire after ten minutes.
        quote = await godaddy_domain_service.quote(
            domain.domain,
            domain.registration_period_years or 1,
        )
        latest_price = quote.get("price") or {}
        latest_fees = quote.get("fees", []) or []
        latest_renewal_price = (quote.get("renewalPrice") or {}).get("value")
        latest_total = int(latest_price.get("value", -1)) + sum(
            int((item.get("fee") or {}).get("value", 0)) for item in latest_fees
        )
        if (
            not quote.get("available")
            or latest_total != domain.registration_price_minor
            or str(latest_price.get("currencyCode", "")).upper() != domain.price_currency
            or latest_fees != details.get("fees", [])
            or latest_renewal_price != domain.renewal_price_minor
        ):
            raise ValueError("The live domain price changed after checkout; registration cannot proceed at the paid amount.")

        registration = await godaddy_domain_service.register(
            domain=domain.domain,
            period=domain.registration_period_years or 1,
            quote_token=quote["quoteToken"],
            agreement_types=details["agreement_types"],
            agreed_at=details["agreed_at"],
            fees=latest_fees,
            idempotency_key=str(domain.id),
        )

    except Exception as exc:
        logger.exception("Domain registration failed for purchase %s", domain.id)
        if isinstance(exc, HTTPException) and "uncertain" in str(exc.detail).lower():
            domain.registrar_status = "registration_unknown"
            domain.verification_status = "registration_unknown"
            await db.commit()
            try:
                from app.tasks.domain_tasks import retry_paid_domain_fulfillment
                retry_paid_domain_fulfillment.apply_async(args=[str(domain.id), 0], countdown=30)
            except Exception:
                logger.exception("Could not queue retry for uncertain GoDaddy operation %s", domain.id)
            return
        domain.registrar_status = "registration_failed"
        domain.verification_status = "failed"
        # Refund the customer if GoDaddy rejected the registration before accepting it.
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Refund.create(payment_intent=payment_intent, idempotency_key=f"domain-refund-{domain.id}")
            domain.registrar_status = "refunded_registration_failed"
        except Exception:
            logger.exception("Automatic refund failed for domain purchase %s", domain.id)
        await db.commit()
        if isinstance(exc, ValueError):
            return
        raise

    # The registrar accepted the registration request. Persist that external
    # result outside the refund handler: a database error here must never refund
    # a domain that GoDaddy may already have registered. Stripe/webhook retries
    # reuse this domain ID as GoDaddy's idempotency key.
    domain.registrar_registration_id = registration.get("registrationId")
    domain.registrar_status = (
        str(registration.get("status", "confirmed")).lower()
        if domain.registrar_registration_id
        else "registration_unknown"
    )
    domain.verification_status = "registration_processing"
    await db.commit()
    if domain.registrar_registration_id:
        try:
            from app.tasks.domain_tasks import poll_domain_registration
            poll_domain_registration.apply_async(args=[str(domain.id), 0], countdown=20)
        except Exception:
            logger.exception("Could not queue GoDaddy registration polling for %s", domain.id)


async def refresh_domain_registration(domain: Domain, db: AsyncSession) -> Domain:
    if not domain.registrar_registration_id:
        return domain
    registration = await godaddy_domain_service.registration_status(domain.registrar_registration_id)
    status = str(registration.get("status", "")).lower()
    domain.registrar_status = status or domain.registrar_status
    if status == "completed":
        details = json.loads(decrypt_oauth_token(domain.registrar_data_encrypted or ""))
        # GoDaddy v3 registers with the account profile; v1 then assigns the
        # customer-provided legal registrant contact and disables default renewals.
        await godaddy_domain_service.update_registrant(domain.domain, details["profile"])
        await godaddy_domain_service.set_auto_renew(domain.domain, False)
        await godaddy_domain_service.upsert_dns(domain.domain)
        deployment_result = await db.execute(select(Deployment).where(Deployment.id == domain.deployment_id))
        deployment = deployment_result.scalar_one_or_none()
        if deployment:
            deployment.custom_domain = domain.domain
            tls_enabled = settings.CUSTOM_DOMAIN_TLS_ENABLED
            deployment.live_url = f"{'https' if tls_enabled else 'http'}://{domain.domain}/"
        domain.verification_status = "verified"
        domain.ssl_status = "managed" if settings.CUSTOM_DOMAIN_TLS_ENABLED else "pending"
        expires_at = registration.get("expiresAt")
        if expires_at:
            from datetime import datetime
            domain.registrar_expires_at = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        domain.registrar_data_encrypted = None
    elif status == "failed":
        domain.verification_status = "failed"
        if domain.stripe_checkout_session_id:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                checkout = stripe.checkout.Session.retrieve(domain.stripe_checkout_session_id)
                payment_intent = checkout.get("payment_intent")
                if isinstance(payment_intent, dict):
                    payment_intent = payment_intent.get("id")
                if payment_intent:
                    stripe.Refund.create(
                        payment_intent=payment_intent,
                        idempotency_key=f"domain-provider-failure-refund-{domain.id}",
                    )
                    domain.registrar_status = "refunded_registration_failed"
            except Exception:
                logger.exception("Automatic refund failed for failed domain registration %s", domain.id)
    await db.commit()
    await db.refresh(domain)
    return domain
