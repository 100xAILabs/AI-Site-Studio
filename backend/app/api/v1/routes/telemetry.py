"""
Client Telemetry and Crash Reporting Routes.
Accepts client-side crash diagnostics from the React Error Boundary
for observability and debugging without blocking the user.
"""

import logging
from typing import Optional
from fastapi import APIRouter, status
from pydantic import BaseModel

logger = logging.getLogger("telemetry.crash")

router = APIRouter()


class CrashReportPayload(BaseModel):
    message: str
    stack: Optional[str] = None
    componentStack: Optional[str] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None
    timestamp: Optional[str] = None


@router.post("/crash", status_code=status.HTTP_200_OK)
async def receive_crash_report(payload: CrashReportPayload):
    """
    Ingests unhandled frontend client render errors reported by ErrorBoundary.
    """
    logger.error(
        f"[Client Crash] {payload.message} | URL: {payload.url} | "
        f"Timestamp: {payload.timestamp} | UserAgent: {payload.userAgent}"
    )
    if payload.stack:
        logger.debug(f"[Client Crash Stack] {payload.stack}")
    if payload.componentStack:
        logger.debug(f"[Client Crash Component Stack] {payload.componentStack}")

    return {"status": "recorded"}
