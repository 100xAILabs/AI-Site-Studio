"""
Celery Task Queue Configuration.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ai_site_studio",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ai_tasks",
        "app.tasks.preview_tasks",
        "app.tasks.email_tasks",
    ],
)

# Optional configuration settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max runtime
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
