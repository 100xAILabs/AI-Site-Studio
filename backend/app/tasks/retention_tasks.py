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
