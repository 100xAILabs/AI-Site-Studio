"""
AI Site Studio — Production Email Engine
Multi-provider email system supporting Resend, Brevo, SMTP, and Mock delivery.
Features:
- Interchangeable provider adapters (Resend, Brevo, SMTP, Mock)
- Anti-spam honeypot detection & bot velocity mitigation
- Sliding window submission rate limiting
- Modern, responsive HTML email templates for inquiries, confirmations, and newsletters
- Dual-dispatch: Admin inquiry notification + Customer auto-reply confirmation
- Delivery logging and error handling without sensitive payload leakage
"""

import os
import time
import uuid
import smtplib
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, Field, EmailStr
import httpx

logger = logging.getLogger("app.services.email_engine")


# ==============================================================================
# 1. Models & Data Structures
# ==============================================================================

class EmailMessage(BaseModel):
    to: List[str]
    subject: str
    html_body: str
    text_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None


class EmailSendResult(BaseModel):
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


# ==============================================================================
# 2. Anti-Spam & Rate Limiter Guards
# ==============================================================================

class AntiSpamGuard:
    """
    Guards incoming contact & newsletter forms against automated bot floods.
    - Honeypot validation (hidden fields that bots fill out, but humans cannot see)
    - Submission velocity check (requires minimum human reaction time, e.g. 1.0s)
    """

    @staticmethod
    def validate_submission(
        honeypot_value: Optional[str] = None,
        form_loaded_at: Optional[float] = None,
        min_seconds: float = 1.0,
    ) -> Tuple[bool, Optional[str]]:
        # 1. Honeypot check: must be strictly empty
        if honeypot_value and honeypot_value.strip():
            logger.warning("Spam detected: honeypot field was filled.")
            return False, "Bot activity detected (honeypot triggered)."

        # 2. Velocity check: form submitted abnormally fast (< min_seconds)
        if form_loaded_at is not None and form_loaded_at > 0:
            elapsed = time.time() - form_loaded_at
            if elapsed < min_seconds:
                logger.warning(f"Spam detected: form submitted in {elapsed:.2f}s (< {min_seconds}s).")
                return False, "Submission was too fast. Please take your time to fill out the form."

        return True, None


class SubmissionRateLimiter:
    """
    Sliding window in-memory rate limiter per IP or sender identifier.
    Default: max 5 submissions per 60 seconds.
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        timestamps = self._history.get(identifier, [])

        # Prune expired timestamps
        cutoff = now - self.window_seconds
        timestamps = [ts for ts in timestamps if ts > cutoff]

        if len(timestamps) >= self.max_requests:
            self._history[identifier] = timestamps
            return False

        timestamps.append(now)
        self._history[identifier] = timestamps
        return True

    def reset(self):
        self._history.clear()


# Global in-memory rate limiter for public contact endpoints
global_contact_rate_limiter = SubmissionRateLimiter(max_requests=5, window_seconds=60)


# ==============================================================================
# 3. HTML Email Templates
# ==============================================================================

def render_admin_inquiry_html(
    site_name: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    message: str,
) -> str:
    """Generates clean, responsive HTML notification email for the website owner."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>New Inquiry from {sender_name}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0c10; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e5e5f7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b0c10; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 600px; background-color: #12131a; border: 1px solid #232533; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
          <!-- Header -->
          <tr>
            <td style="padding: 28px 32px; background: linear-gradient(135deg, #1b1c28 0%, #151620 100%); border-bottom: 1px solid #232533;">
              <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #c89666; font-weight: 700; display: block; margin-bottom: 6px;">New Website Inquiry</span>
              <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{site_name}</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <table role="presentation" width="100%" style="margin-bottom: 24px; background: #0c0d14; border: 1px solid #1f212e; border-radius: 8px; padding: 16px;">
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #8e90a5; width: 80px;">From:</td>
                  <td style="padding: 6px 0; font-size: 13px; color: #ffffff; font-weight: 600;">{sender_name}</td>
                </tr>
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #8e90a5;">Email:</td>
                  <td style="padding: 6px 0; font-size: 13px; color: #c89666; font-weight: 600;">
                    <a href="mailto:{sender_email}" style="color: #c89666; text-decoration: none;">{sender_email}</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #8e90a5;">Subject:</td>
                  <td style="padding: 6px 0; font-size: 13px; color: #ffffff;">{subject}</td>
                </tr>
              </table>

              <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #8e90a5; margin-bottom: 8px;">Message Content:</div>
              <div style="background-color: #0c0d14; border-left: 3px solid #c89666; border-radius: 4px; padding: 16px; font-size: 14px; line-height: 1.6; color: #d0d2e0; white-space: pre-wrap;">{message}</div>

              <div style="margin-top: 32px; text-align: center;">
                <a href="mailto:{sender_email}?subject=Re: {subject}" style="display: inline-block; padding: 12px 24px; background-color: #c89666; color: #0b0c10; font-size: 13px; font-weight: 700; text-decoration: none; border-radius: 8px;">
                  Reply to {sender_name}
                </a>
              </div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0c0d14; border-top: 1px solid #1f212e; text-align: center; font-size: 12px; color: #626477;">
              Sent via AI Site Studio Production Email Engine &bull; Automated notification
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_customer_confirmation_html(
    site_name: str,
    sender_name: str,
    subject: str,
) -> str:
    """Generates auto-reply confirmation email to reassure the customer their message was received."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>We Received Your Message — {site_name}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0c10; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e5e5f7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b0c10; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 560px; background-color: #12131a; border: 1px solid #232533; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
          <tr>
            <td style="padding: 28px 32px; background: linear-gradient(135deg, #1b1c28 0%, #151620 100%); border-bottom: 1px solid #232533;">
              <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #10b981; font-weight: 700; display: block; margin-bottom: 6px;">Confirmation Received</span>
              <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff;">{site_name}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 32px;">
              <p style="font-size: 15px; line-height: 1.5; color: #ffffff; margin-top: 0;">Hello <strong>{sender_name}</strong>,</p>
              <p style="font-size: 14px; line-height: 1.6; color: #a4a7be;">
                Thank you for reaching out to us regarding <em>"{subject}"</em>. We have received your inquiry and our team is already reviewing your details.
              </p>
              <div style="background-color: #0c0d14; border: 1px solid #1f212e; border-radius: 8px; padding: 18px; margin: 24px 0; text-align: center;">
                <p style="margin: 0; font-size: 13px; color: #10b981; font-weight: 600;">
                  &#10003; Your message has been logged in our priority queue.
                </p>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #767990;">
                  A representative will follow up with you within 24 business hours.
                </p>
              </div>
              <p style="font-size: 13px; line-height: 1.6; color: #767990; margin-bottom: 0;">
                If your inquiry is urgent, please feel free to reply directly to this message.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 32px; background-color: #0c0d14; border-top: 1px solid #1f212e; text-align: center; font-size: 12px; color: #626477;">
              &copy; {site_name}. All rights reserved.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_newsletter_welcome_html(
    site_name: str,
    subscriber_email: str,
) -> str:
    """Generates welcoming newsletter confirmation email."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to {site_name}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0c10; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #e5e5f7;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b0c10; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 560px; background-color: #12131a; border: 1px solid #232533; border-radius: 12px; overflow: hidden;">
          <tr>
            <td style="padding: 32px; text-align: center;">
              <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #c89666; font-weight: 700;">Newsletter Confirmation</span>
              <h1 style="margin: 8px 0 16px 0; font-size: 24px; color: #ffffff;">You're on the list!</h1>
              <p style="font-size: 14px; line-height: 1.6; color: #a4a7be; margin: 0 0 24px 0;">
                Thanks for subscribing to <strong>{site_name}</strong> with <em>{subscriber_email}</em>. You'll receive our newest product releases, case studies, and insights directly in your inbox.
              </p>
              <div style="background-color: #0c0d14; border-radius: 8px; padding: 14px; font-size: 12px; color: #767990; margin-bottom: 24px;">
                Zero spam. You can unsubscribe at any time with one click.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ==============================================================================
# 4. Email Provider Adapters
# ==============================================================================

class BaseEmailAdapter(ABC):
    """Abstract interface for pluggable email transport adapters."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailSendResult:
        """Dispatches an email message asynchronously."""
        pass

    @abstractmethod
    def verify_config(self) -> Dict[str, Any]:
        """Validates configuration parameters and returns health status."""
        pass


class ResendEmailAdapter(BaseEmailAdapter):
    """Adapter for Resend API (https://resend.com)."""

    def __init__(self, api_key: str, default_from: Optional[str] = None):
        self.api_key = api_key.strip() if api_key else ""
        self.default_from = default_from or "Site Studio <onboarding@resend.dev>"

    def verify_config(self) -> Dict[str, Any]:
        has_key = bool(self.api_key and self.api_key.startswith("re_"))
        return {
            "provider": "resend",
            "configured": has_key,
            "default_from": self.default_from,
            "status": "ready" if has_key else "missing_or_invalid_api_key",
        }

    async def send(self, message: EmailMessage) -> EmailSendResult:
        if not self.api_key:
            return EmailSendResult(
                success=False,
                provider="resend",
                error="RESEND_API_KEY is not configured.",
            )

        sender = message.from_email or self.default_from
        payload = {
            "from": sender,
            "to": message.to,
            "subject": message.subject,
            "html": message.html_body,
        }
        if message.text_body:
            payload["text"] = message.text_body
        if message.reply_to:
            payload["reply_to"] = message.reply_to

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post("https://api.resend.com/emails", json=payload, headers=headers)
                if res.status_code in (200, 201):
                    data = res.json()
                    msg_id = data.get("id", str(uuid.uuid4()))
                    logger.info(f"Resend dispatched email {msg_id} to {len(message.to)} recipient(s)")
                    return EmailSendResult(success=True, provider="resend", message_id=msg_id)
                else:
                    err_msg = f"Resend API error {res.status_code}: {res.text}"
                    logger.error(err_msg)
                    return EmailSendResult(success=False, provider="resend", error=err_msg)
        except Exception as exc:
            err_msg = f"Network or transport exception sending via Resend: {str(exc)}"
            logger.error(err_msg)
            return EmailSendResult(success=False, provider="resend", error=err_msg)


class BrevoEmailAdapter(BaseEmailAdapter):
    """Adapter for Brevo / Sendinblue API (https://brevo.com)."""

    def __init__(self, api_key: str, default_from: Optional[str] = None):
        self.api_key = api_key.strip() if api_key else ""
        self.default_from = default_from or "noreply@aisitestudio.com"

    def verify_config(self) -> Dict[str, Any]:
        has_key = bool(self.api_key and len(self.api_key) > 10)
        return {
            "provider": "brevo",
            "configured": has_key,
            "default_from": self.default_from,
            "status": "ready" if has_key else "missing_api_key",
        }

    async def send(self, message: EmailMessage) -> EmailSendResult:
        if not self.api_key:
            return EmailSendResult(
                success=False,
                provider="brevo",
                error="BREVO_API_KEY is not configured.",
            )

        sender_email = message.from_email or self.default_from
        sender_name = "Site Studio"
        if "<" in sender_email and ">" in sender_email:
            parts = sender_email.split("<")
            sender_name = parts[0].strip()
            sender_email = parts[1].replace(">", "").strip()

        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject,
            "htmlContent": message.html_body,
        }
        if message.text_body:
            payload["textContent"] = message.text_body
        if message.reply_to:
            payload["replyTo"] = {"email": message.reply_to}

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
                if res.status_code in (200, 201):
                    data = res.json()
                    msg_id = data.get("messageId", str(uuid.uuid4()))
                    logger.info(f"Brevo dispatched email {msg_id} to {len(message.to)} recipient(s)")
                    return EmailSendResult(success=True, provider="brevo", message_id=msg_id)
                else:
                    err_msg = f"Brevo API error {res.status_code}: {res.text}"
                    logger.error(err_msg)
                    return EmailSendResult(success=False, provider="brevo", error=err_msg)
        except Exception as exc:
            err_msg = f"Network or transport exception sending via Brevo: {str(exc)}"
            logger.error(err_msg)
            return EmailSendResult(success=False, provider="brevo", error=err_msg)


class SMTPEmailAdapter(BaseEmailAdapter):
    """Adapter for standard SMTP transport (Gmail, AWS SES, Postmark, Mailgun, SendGrid)."""

    def __init__(
        self,
        host: str = "smtp.gmail.com",
        port: int = 587,
        user: str = "",
        password: str = "",
        use_tls: bool = True,
        from_email: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email or user or "noreply@aisitestudio.com"

    def verify_config(self) -> Dict[str, Any]:
        has_creds = bool(self.host and self.user and self.password)
        return {
            "provider": "smtp",
            "configured": has_creds,
            "host": self.host,
            "port": self.port,
            "user": self.user[:3] + "***" if self.user else "",
            "use_tls": self.use_tls,
            "status": "ready" if has_creds else "missing_smtp_credentials",
        }

    def _send_sync(self, message: EmailMessage) -> str:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = message.from_email or self.from_email
        msg["To"] = ", ".join(message.to)
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        if message.text_body:
            msg.attach(MIMEText(message.text_body, "plain", "utf-8"))
        msg.attach(MIMEText(message.html_body, "html", "utf-8"))

        if self.use_tls:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(msg["From"], message.to, msg.as_string())
        else:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as server:
                server.login(self.user, self.password)
                server.sendmail(msg["From"], message.to, msg.as_string())

        return f"smtp-{uuid.uuid4()}"

    async def send(self, message: EmailMessage) -> EmailSendResult:
        if not (self.host and self.user and self.password):
            return EmailSendResult(
                success=False,
                provider="smtp",
                error="SMTP host, username, or password is not configured.",
            )

        try:
            msg_id = await asyncio.to_thread(self._send_sync, message)
            logger.info(f"SMTP sent email {msg_id} to {len(message.to)} recipient(s)")
            return EmailSendResult(success=True, provider="smtp", message_id=msg_id)
        except smtplib.SMTPException as exc:
            err_msg = f"SMTP protocol error: {str(exc)}"
            logger.error(err_msg)
            return EmailSendResult(success=False, provider="smtp", error=err_msg)
        except Exception as exc:
            err_msg = f"Unexpected SMTP error: {str(exc)}"
            logger.error(err_msg)
            return EmailSendResult(success=False, provider="smtp", error=err_msg)


class ConsoleMockEmailAdapter(BaseEmailAdapter):
    """Safe mock adapter for local testing and zero-credential development."""

    def __init__(self):
        self.sent_messages: List[EmailMessage] = []

    def verify_config(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "configured": True,
            "status": "ready (mock delivery for development/tests)",
        }

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent_messages.append(message)
        masked_recipients = [f"{r[:2]}***@{r.split('@')[-1]}" if "@" in r else "hidden" for r in message.to]
        msg_id = f"mock-{uuid.uuid4()}"
        logger.info(f"📧 [MOCK EMAIL DISPATCH] {msg_id} | Subject: '{message.subject}' | To: {masked_recipients}")
        return EmailSendResult(success=True, provider="mock", message_id=msg_id)


# ==============================================================================
# 5. Production Email Engine Orchestrator
# ==============================================================================

class EmailEngine:
    """
    Unified manager and dynamic resolver for email delivery.
    Resolves the best available adapter based on configured environment variables:
    1. Resend (if RESEND_API_KEY present)
    2. Brevo (if BREVO_API_KEY present)
    3. SMTP (if SMTP_USER and SMTP_PASSWORD present)
    4. Mock (fallback for unit tests / dev environments)
    """

    def __init__(self):
        self._mock_adapter = ConsoleMockEmailAdapter()

    def get_adapter(
        self,
        provider_preference: Optional[str] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> BaseEmailAdapter:
        env = custom_env or os.environ

        pref = (provider_preference or "").lower().strip()

        # Check explicit preference or autodetect
        if pref == "resend" or (not pref and env.get("RESEND_API_KEY")):
            key = env.get("RESEND_API_KEY", "")
            from_addr = env.get("RESEND_FROM") or env.get("FROM_EMAIL")
            if key:
                return ResendEmailAdapter(api_key=key, default_from=from_addr)

        if pref == "brevo" or (not pref and env.get("BREVO_API_KEY")):
            key = env.get("BREVO_API_KEY", "")
            from_addr = env.get("BREVO_FROM") or env.get("FROM_EMAIL")
            if key:
                return BrevoEmailAdapter(api_key=key, default_from=from_addr)

        if pref == "smtp" or (not pref and env.get("SMTP_USER") and env.get("SMTP_PASSWORD")):
            return SMTPEmailAdapter(
                host=env.get("SMTP_HOST", "smtp.gmail.com"),
                port=int(env.get("SMTP_PORT", 587)),
                user=env.get("SMTP_USER", ""),
                password=env.get("SMTP_PASSWORD", ""),
                use_tls=env.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
                from_email=env.get("SMTP_FROM") or env.get("FROM_EMAIL"),
            )

        # Fallback to safe Mock
        return self._mock_adapter

    async def send_contact_inquiry(
        self,
        sender_name: str,
        sender_email: str,
        subject: str,
        message: str,
        recipient_email: Optional[str] = None,
        site_name: str = "Website",
        custom_env: Optional[Dict[str, str]] = None,
    ) -> Tuple[EmailSendResult, Optional[EmailSendResult]]:
        """
        Dispatches dual email:
        1. Admin Inquiry Notification -> NOTIFICATION_EMAIL / recipient_email
        2. Customer Auto-Reply Confirmation -> sender_email
        """
        env = custom_env or os.environ
        admin_to = recipient_email or env.get("NOTIFICATION_EMAIL") or env.get("SMTP_USER") or "admin@example.com"
        adapter = self.get_adapter(custom_env=env)

        # 1. Admin Email
        admin_html = render_admin_inquiry_html(
            site_name=site_name,
            sender_name=sender_name,
            sender_email=sender_email,
            subject=subject,
            message=message,
        )
        admin_msg = EmailMessage(
            to=[admin_to],
            subject=f"[{site_name}] New Inquiry: {subject}",
            html_body=admin_html,
            text_body=f"New inquiry from {sender_name} ({sender_email}):\n\n{message}",
            reply_to=sender_email,
        )
        admin_result = await adapter.send(admin_msg)

        # 2. Customer Confirmation Email
        customer_html = render_customer_confirmation_html(
            site_name=site_name,
            sender_name=sender_name,
            subject=subject,
        )
        customer_msg = EmailMessage(
            to=[sender_email],
            subject=f"We received your message — {site_name}",
            html_body=customer_html,
            text_body=f"Hello {sender_name},\n\nWe received your message regarding '{subject}'. Our team will respond shortly.",
        )
        customer_result = await adapter.send(customer_msg)

        return admin_result, customer_result

    async def send_newsletter_subscription(
        self,
        subscriber_email: str,
        site_name: str = "Website",
        custom_env: Optional[Dict[str, str]] = None,
    ) -> EmailSendResult:
        """Sends welcoming confirmation email to new newsletter subscriber."""
        env = custom_env or os.environ
        adapter = self.get_adapter(custom_env=env)

        html = render_newsletter_welcome_html(site_name=site_name, subscriber_email=subscriber_email)
        msg = EmailMessage(
            to=[subscriber_email],
            subject=f"Welcome to {site_name} Newsletter!",
            html_body=html,
            text_body=f"Welcome to {site_name}! Thanks for subscribing with {subscriber_email}.",
        )
        return await adapter.send(msg)


# Global singleton instance
email_engine = EmailEngine()
