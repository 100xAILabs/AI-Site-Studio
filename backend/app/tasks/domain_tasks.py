"""Background polling for asynchronous registrar operations."""

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine
from app.models.deployment import Domain
from app.services.domain_purchase_service import fulfill_domain_checkout, refresh_domain_registration

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.domain_tasks.poll_domain_registration",
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
)
def poll_domain_registration(domain_id: str, attempt: int = 0) -> None:
    async def run_and_dispose() -> None:
        try:
            await _poll(uuid.UUID(domain_id), attempt)
        finally:
            await engine.dispose()
    asyncio.run(run_and_dispose())


async def _poll(domain_id: uuid.UUID, attempt: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Domain).where(Domain.id == domain_id))
        domain = result.scalar_one_or_none()
        if not domain or not domain.registrar_registration_id:
            return
        try:
            domain = await refresh_domain_registration(domain, db)
        except Exception:
            logger.exception("Registrar setup is incomplete for domain %s; scheduling another poll", domain_id)
            # Registrant, auto-renew, or DNS APIs can fail after registration has
            # completed. Keep retrying within the polling window rather than
            # relying on Celery's short automatic retry limit.
            if attempt < 60:
                poll_domain_registration.apply_async(args=[str(domain_id), attempt + 1], countdown=30)
            return
        if domain.registrar_status in {"completed", "failed", "refunded_registration_failed"}:
            return
        if attempt >= 60:
            logger.warning("Registrar operation %s is still pending after polling window", domain.registrar_registration_id)
            return
        poll_domain_registration.apply_async(args=[str(domain_id), attempt + 1], countdown=20)


@celery_app.task(
    name="app.tasks.domain_tasks.retry_paid_domain_fulfillment",
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
)
def retry_paid_domain_fulfillment(domain_id: str, attempt: int = 0) -> None:
    async def run_and_dispose() -> None:
        try:
            await _retry_fulfillment(uuid.UUID(domain_id), attempt)
        finally:
            await engine.dispose()
    asyncio.run(run_and_dispose())


async def _retry_fulfillment(domain_id: uuid.UUID, attempt: int) -> None:
    import stripe
    from app.core.config import settings

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Domain).where(Domain.id == domain_id))
        domain = result.scalar_one_or_none()
        if not domain or domain.registrar_status != "registration_unknown" or not domain.stripe_checkout_session_id:
            return
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout = stripe.checkout.Session.retrieve(domain.stripe_checkout_session_id)
        await fulfill_domain_checkout(checkout, db)
        await db.refresh(domain)
        if domain.registrar_status == "registration_unknown" and attempt < 60:
            retry_paid_domain_fulfillment.apply_async(args=[str(domain_id), attempt + 1], countdown=30)
