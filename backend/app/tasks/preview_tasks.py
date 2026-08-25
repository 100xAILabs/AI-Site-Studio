"""
Preview rendering background tasks.
"""

import uuid
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.services.preview_service import PreviewService
import asyncio


@celery_app.task(name="app.tasks.preview_tasks.generate_screenshot_preview")
def generate_screenshot_preview(session_id: str, thumbnail_url: str, user_email: str = None):
    """
    Background job to overlay a customized watermark and save screenshot.
    """
    async def run():
        async with AsyncSessionLocal() as db:
            service = PreviewService(db)
            url = await service.generate_preview_screenshot(
                uuid.UUID(session_id),
                thumbnail_url,
                user_email
            )
            return url

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(run())
