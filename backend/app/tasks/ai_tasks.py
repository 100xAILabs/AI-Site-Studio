"""
AI-related background jobs.
"""

from app.core.celery_app import celery_app
from app.services.ai_service import ai_service
import asyncio


@celery_app.task(name="app.tasks.ai_tasks.generate_bulk_content")
def generate_bulk_content(business_name: str, industry: str):
    """
    Simulated background task to generate high-fidelity business contents.
    In production, this would call OpenAI and update a database session session.
    """
    loop = asyncio.get_event_loop()
    coro = ai_service.generate_business_content(business_name, industry, "business")
    result = loop.run_until_complete(coro)
    return result
