"""Order alerts sent through server-configured email and SMS providers."""
import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(recipient: str, subject: str, body: str) -> None:
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = recipient
    if settings.SMTP_USE_TLS:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    else:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)


async def send_order_email(recipient: str, subject: str, body: str) -> bool:
    if not settings.ENABLE_EMAIL_DELIVERY:
        return False
    try:
        if settings.RESEND_API_KEY:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json={"from": settings.RESEND_FROM, "to": [recipient], "subject": subject, "text": body},
                )
                response.raise_for_status()
        elif settings.SMTP_USER and settings.SMTP_PASSWORD:
            await asyncio.to_thread(_send_smtp, recipient, subject, body)
        else:
            return False
        return True
    except Exception:
        logger.exception("Store order email delivery failed")
        return False


async def send_order_sms(recipient: str, body: str) -> bool:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={"From": settings.TWILIO_FROM_NUMBER, "To": recipient, "Body": body[:1500]},
            )
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Store order SMS delivery failed")
        return False
