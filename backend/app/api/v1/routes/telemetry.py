"""
Client Telemetry and Crash Reporting Routes.
Accepts client-side crash diagnostics from the React Error Boundary
for observability and debugging without blocking the user.
"""

import logging
from typing import Optional
from fastapi import APIRouter, status, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("telemetry.crash")

router = APIRouter()


class CrashReportPayload(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    stack: Optional[str] = Field(default=None, max_length=4000)
    componentStack: Optional[str] = Field(default=None, max_length=2000)
    url: Optional[str] = Field(default=None, max_length=2048)
    userAgent: Optional[str] = Field(default=None, max_length=512)
    timestamp: Optional[str] = Field(default=None, max_length=64)


@router.post("/crash", status_code=status.HTTP_200_OK)
async def receive_crash_report(payload: CrashReportPayload, request: Request):
    """
    Ingests unhandled frontend client render errors reported by ErrorBoundary.
    """
    from app.core.request_limits import enforce_user_limit
    client_ip = request.client.host if request.client else "unknown"
    await enforce_user_limit(client_ip, "client-crash", limit=20, window_seconds=60)
    logger.error(
        "[Client Crash] %s | URL: %s | Timestamp: %s | UserAgent: %s",
        payload.message, payload.url, payload.timestamp, payload.userAgent,
    )
    if payload.stack:
        logger.debug(f"[Client Crash Stack] {payload.stack}")
    if payload.componentStack:
        logger.debug(f"[Client Crash Component Stack] {payload.componentStack}")

    return {"status": "recorded"}
