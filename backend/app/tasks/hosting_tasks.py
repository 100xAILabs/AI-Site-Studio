"""Scheduled actions for failed managed-hosting subscriptions."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

import stripe
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.deployment import Deployment
from app.models.hosting_subscription import HostingSubscription

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.hosting_tasks.cancel_unpaid_hosting_after_grace",
    autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5},
)
def cancel_unpaid_hosting_after_grace(subscription_row_id: str) -> None:
    """Cancel Stripe billing and suspend the site if payment is still overdue."""
    async def run_and_dispose() -> None:
        try:
            await _cancel_if_still_unpaid(subscription_row_id)
        finally:
            # Each Celery invocation owns a fresh event loop; discard asyncpg
            # connections so a later invocation never reuses loop-bound clients.
            await engine.dispose()
    asyncio.run(run_and_dispose())


async def _cancel_if_still_unpaid(subscription_row_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(HostingSubscription).where(HostingSubscription.id == uuid.UUID(subscription_row_id)).with_for_update()
        )
        row = result.scalar_one_or_none()
        if not row or row.status != "past_due" or not row.last_payment_failed_at:
            return

        failed_at = row.last_payment_failed_at
        if failed_at.tzinfo is None:
            failed_at = failed_at.replace(tzinfo=timezone.utc)
        deadline = failed_at + timedelta(days=max(0, settings.HOSTING_GRACE_PERIOD_DAYS))
        if datetime.now(timezone.utc) < deadline:
            cancel_unpaid_hosting_after_grace.apply_async(
                args=[str(row.id)], countdown=max(1, int((deadline - datetime.now(timezone.utc)).total_seconds()))
            )
            return

        subscription_id = row.stripe_subscription_id
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            remote = stripe.Subscription.retrieve(subscription_id)
            await db.refresh(row)
            if row.stripe_subscription_id != subscription_id:
                return
            remote_status = remote.get("status")
            if remote_status in {"active", "trialing"}:
                row.status = remote_status
                row.last_payment_failed_at = None
                await db.commit()
                return
            if remote_status not in {"canceled", "unpaid", "incomplete_expired"}:
                stripe.Subscription.cancel(subscription_id, prorate=False)
            await db.refresh(row)
            if row.stripe_subscription_id != subscription_id or row.status in {"active", "trialing"}:
                return
        except Exception:
            logger.exception("Could not cancel overdue hosting subscription %s", row.stripe_subscription_id)
            raise

        row.status = "canceled"
        row.cancel_at_period_end = False
        deployment_result = await db.execute(select(Deployment).where(Deployment.id == row.deployment_id))
        deployment = deployment_result.scalar_one_or_none()
        if deployment:
            from app.services.deployment_providers import get_deployment_provider
            provider = get_deployment_provider(deployment.provider)
            await provider.stop(deployment.site_id)
            deployment.status = "suspended"
            deployment.is_suspended = True
        await db.commit()
