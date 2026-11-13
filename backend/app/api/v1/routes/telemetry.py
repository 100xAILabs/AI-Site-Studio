"""
Client Telemetry and Crash Reporting Routes.
Accepts client-side crash diagnostics from the React Error Boundary
and stealth tamper alerts from watermarked template runtime guards.
"""

import datetime
import json
import logging
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.tamper_alert import TamperAlert
from app.models.template import Template
from app.models.user import User

logger = logging.getLogger("telemetry")

router = APIRouter()


class CrashReportPayload(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    stack: Optional[str] = Field(default=None, max_length=4000)
    componentStack: Optional[str] = Field(default=None, max_length=2000)
    url: Optional[str] = Field(default=None, max_length=2048)
    userAgent: Optional[str] = Field(default=None, max_length=512)
    timestamp: Optional[str] = Field(default=None, max_length=64)


class TamperAlertPayload(BaseModel):
    template_id: Optional[str] = None
    tid: Optional[str] = None
    buyer_email: Optional[str] = None
    em: Optional[str] = None
    license_key: Optional[str] = None
    lk: Optional[str] = None
    domain: Optional[str] = None
    dm: Optional[str] = None
    origin: Optional[str] = None
    violation_type: Optional[str] = None
    vt: Optional[str] = None
    details: Optional[str] = None
    dt: Optional[str] = None


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


@router.options("/tamper-alert")
async def options_tamper_alert():
    """Permissive CORS preflight handler so live visitors on any external domain can report telemetry."""
    return Response(
        status_code=status.HTTP_200_OK,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        },
    )


@router.post("/tamper-alert", status_code=status.HTTP_200_OK)
async def receive_tamper_alert(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Silent receiver for stealth tamper telemetry beacons.
    Triggered when a Standard Edition buyer modifies or strips embedded watermarks,
    license badges, or required attribution files.
    Permissive CORS allows beacons from arbitrary client domains, local files, or subdomains.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    response.headers["Access-Control-Allow-Headers"] = "*"
    # Accept JSON body or raw bytes/form data (e.g. navigator.sendBeacon)
    payload_data: dict[str, Any] = {}
    try:
        raw_body = await request.body()
        if raw_body:
            try:
                payload_data = json.loads(raw_body.decode("utf-8", errors="ignore"))
            except Exception:
                # Might be form-urlencoded or query params
                payload_data = dict(request.query_params)
        else:
            payload_data = dict(request.query_params)
    except Exception:
        payload_data = dict(request.query_params)

    # Normalize compact or disguised payload field names
    template_id = str(
        payload_data.get("template_id")
        or payload_data.get("tid")
        or payload_data.get("t")
        or "unknown-template"
    ).strip()
    buyer_email = (
        payload_data.get("buyer_email")
        or payload_data.get("em")
        or payload_data.get("u")
        or None
    )
    license_key = (
        payload_data.get("license_key")
        or payload_data.get("lk")
        or payload_data.get("k")
        or None
    )
    domain = (
        payload_data.get("domain")
        or payload_data.get("dm")
        or payload_data.get("origin")
        or request.headers.get("origin")
        or request.headers.get("referer")
        or "unknown-domain"
    )
    violation_type = str(
        payload_data.get("violation_type")
        or payload_data.get("vt")
        or payload_data.get("v")
        or "watermark_removed"
    ).strip()
    details = (
        payload_data.get("details")
        or payload_data.get("dt")
        or payload_data.get("msg")
        or None
    )

    client_ip = request.client.host if request.client else "unknown"
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")[:500]

    # Look up template title if available
    template_title = None
    try:
        stmt = select(Template.title).where(
            (Template.id == template_id) | (Template.slug == template_id)
        )
        t_res = await db.execute(stmt)
        template_title = t_res.scalar_one_or_none()
    except Exception:
        pass

    # Save to tamper_alerts table
    alert = TamperAlert(
        template_id=template_id,
        template_title=template_title,
        buyer_email=buyer_email,
        license_key=license_key,
        domain=domain[:255] if domain else None,
        violation_type=violation_type[:100],
        ip_address=client_ip[:100] if client_ip else None,
        user_agent=user_agent,
        details=str(details) if details else None,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    logger.warning(
        "🚨 [TAMPER ALERT DETECTED] Template '%s' (%s) | Buyer: %s | Domain: %s | Violation: %s | IP: %s",
        template_id,
        template_title or "No Title",
        buyer_email,
        domain,
        violation_type,
        client_ip,
    )

    # Dispatch email alert to admin via background task or Celery
    def _dispatch_email():
        from app.tasks.email_tasks import send_tamper_alert_notification
        try:
            send_tamper_alert_notification.delay(
                template_id=template_id,
                template_title=template_title or template_id,
                buyer_email=buyer_email or "Unknown Buyer",
                license_key=license_key or "N/A",
                violation_type=violation_type,
                domain=domain,
                ip_address=client_ip,
            )
        except Exception:
            # Fallback to direct synchronous execution in thread if Celery broker is offline
            try:
                send_tamper_alert_notification(
                    None,
                    template_id=template_id,
                    template_title=template_title or template_id,
                    buyer_email=buyer_email or "Unknown Buyer",
                    license_key=license_key or "N/A",
                    violation_type=violation_type,
                    domain=domain,
                    ip_address=client_ip,
                )
            except Exception as e_send:
                logger.error(f"Failed to dispatch tamper email alert: {e_send}")

    background_tasks.add_task(_dispatch_email)

    return {
        "status": "ok",
        "recorded": True,
        "alert_id": str(alert.id),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@router.get("/tamper-alerts")
async def list_tamper_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    template_id: Optional[str] = Query(None),
    violation_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    [Admin] Lists all stealth tamper telemetry alerts recorded across all templates.
    """
    stmt = select(TamperAlert).order_by(desc(TamperAlert.created_at))
    if template_id:
        stmt = stmt.where(TamperAlert.template_id == template_id)
    if violation_type:
        stmt = stmt.where(TamperAlert.violation_type == violation_type)
    stmt = stmt.offset(skip).limit(limit)

    res = await db.execute(stmt)
    alerts = res.scalars().all()

    return {
        "total": len(alerts),
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": str(a.id),
                "template_id": a.template_id,
                "template_title": a.template_title,
                "buyer_email": a.buyer_email,
                "license_key": a.license_key,
                "domain": a.domain,
                "violation_type": a.violation_type,
                "ip_address": a.ip_address,
                "user_agent": a.user_agent,
                "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }
