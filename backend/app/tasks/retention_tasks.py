"""
Retention & Trash Cleanup Tasks.
Permanently removes soft-deleted templates and drafts that have exceeded the 30-day retention window.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.template import Template
from app.services.template_service import TemplateService
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


async def purge_expired_trash_async() -> int:
    """
    Finds all soft-deleted templates where deleted_at is older than 30 days
    and permanently deletes them from storage, vectors, and database.
    """
    purged_count = 0
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    async with AsyncSessionLocal() as db:
        try:
            stmt = (
                select(Template.id)
                .where(
                    Template.is_deleted.is_(True),
                    Template.deleted_at < thirty_days_ago,
                )
            )
            res = await db.execute(stmt)
            expired_ids = res.scalars().all()

            service = TemplateService(db)
            for t_id in expired_ids:
                try:
                    await service.permanent_delete_template(t_id, current_user=None)
                    purged_count += 1
                    logger.info(f"Permanently purged expired template/draft: {t_id}")
                except Exception as e:
                    logger.error(f"Failed to permanently purge template {t_id}: {e}")

            logger.info(f"Purge expired trash completed. Purged {purged_count} records.")
        except Exception as e:
            logger.error(f"Error during expired trash purge: {e}")

    return purged_count


@celery_app.task(name="app.tasks.retention_tasks.purge_expired_trash_task")
def purge_expired_trash_task() -> int:
    """Celery scheduled task wrapper for trash purge."""
    return asyncio.run(purge_expired_trash_async())


async def purge_expired_preview_sessions_async() -> int:
    """Purge preview sessions that have passed their expiration timestamp (F-30)."""
    purged = 0
    now = datetime.now(timezone.utc)
    from app.models.preview_session import PreviewSession
    from sqlalchemy import delete
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(
                delete(PreviewSession).where(PreviewSession.expires_at.isnot(None), PreviewSession.expires_at < now)
            )
            purged = res.rowcount or 0
            await db.commit()
            logger.info(f"Purged {purged} expired preview sessions.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error purging expired preview sessions: {e}")
    return purged


@celery_app.task(name="app.tasks.retention_tasks.purge_expired_preview_sessions_task")
def purge_expired_preview_sessions_task() -> int:
    return asyncio.run(purge_expired_preview_sessions_async())


async def purge_stale_telemetry_logs_async() -> int:
    """Purge tamper alerts older than 180 days (F-30)."""
    now = datetime.now(timezone.utc)
    tamper_cutoff = now - timedelta(days=180)
    from app.models.tamper_alert import TamperAlert
    from sqlalchemy import delete
    purged = 0
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(
                delete(TamperAlert).where(TamperAlert.created_at < tamper_cutoff)
            )
            purged = res.rowcount or 0
            await db.commit()
            logger.info(f"Purged {purged} stale tamper alert records.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error purging stale tamper alerts: {e}")
    return purged


@celery_app.task(name="app.tasks.retention_tasks.purge_stale_telemetry_logs_task")
def purge_stale_telemetry_logs_task() -> int:
    return asyncio.run(purge_stale_telemetry_logs_async())

