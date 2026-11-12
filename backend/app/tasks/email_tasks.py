"""
Email communication background tasks.
Sends real license delivery emails via SMTP using configured settings.
Gracefully falls back to console logging when SMTP is unconfigured (local dev).
"""

import smtplib
import email.mime.text
import email.mime.multipart
import datetime

from app.core.celery_app import celery_app
from app.core.config import settings


@celery_app.task(name="app.tasks.email_tasks.send_license_delivery", bind=True, max_retries=3)
def send_license_delivery(self, to_email: str, license_key: str, template_name: str):
    """
    Sends license details post-payment via SMTP.
    Falls back to log-only mode when SMTP credentials are not configured.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # Graceful fallback for local development — no SMTP configured
        print(f"📧 [EMAIL STUB] License {license_key} for '{template_name}' → {to_email}")
        return True

    subject = f"Your License Key for {template_name} — AI Site Studio"
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #0f0f13; color: #e5e5f7; padding: 32px;">
        <div style="max-width: 560px; margin: auto; background: #1a1a2e; border-radius: 12px; padding: 32px; border: 1px solid #2d2d5b;">
          <h2 style="color: #a78bfa; margin-top: 0;">Your Purchase is Ready!</h2>
          <p>Thank you for your purchase on <strong>AI Site Studio</strong>.</p>
          <p style="font-size: 15px;">Here is your license key for <strong>{template_name}</strong>:</p>
          <div style="background: #0d0d1a; border: 1px solid #3b3b7c; border-radius: 8px; padding: 16px; text-align: center; margin: 24px 0;">
            <span style="font-size: 22px; font-family: monospace; color: #c4b5fd; letter-spacing: 2px;">{license_key}</span>
          </div>
          <p style="color: #9ca3af; font-size: 13px;">
            This is a single-use license key tied to your account. Keep it safe — you can always find your licenses in your Dashboard.
          </p>
          <hr style="border-color: #2d2d5b; margin: 24px 0;" />
          <p style="font-size: 12px; color: #6b7280; text-align: center;">
            AI Site Studio &copy; {datetime.datetime.now().year}
          </p>
        </div>
      </body>
    </html>
    """

    try:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [to_email], msg.as_string())

        print(f"📧 [EMAIL SENT] License {license_key} delivered to {to_email}")
        return True

    except smtplib.SMTPException as exc:
        print(f"[EMAIL ERROR] Failed to send license email to {to_email}: {exc}")
        # Retry up to 3 times with exponential backoff (60s, 120s, 240s)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        print(f"[EMAIL ERROR] Unexpected error sending email to {to_email}: {exc}")
        return False


@celery_app.task(name="app.tasks.email_tasks.send_tamper_alert_notification", bind=True, max_retries=3)
def send_tamper_alert_notification(
    self,
    template_id: str,
    template_title: str,
    buyer_email: str,
    license_key: str,
    violation_type: str,
    domain: str,
    ip_address: str,
):
    """
    Alerts platform admins whenever a Standard Edition buyer tampers with or removes
    embedded watermarks, license guards, or required license attribution files.
    """
    admin_email = settings.SMTP_FROM or settings.SMTP_USER or "admin@aisitestudio.com"
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(
            f"🚨 [TAMPER ALERT STUB] Template '{template_id}' ({template_title}) tampered by {buyer_email} on domain {domain} (Violation: {violation_type})"
        )
        return True

    subject = f"🚨 [SECURITY ALERT] License Violation Detected — {template_title or template_id}"
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 32px;">
        <div style="max-width: 600px; margin: auto; background: #1e293b; border-radius: 12px; padding: 32px; border: 1px solid #ef4444;">
          <h2 style="color: #ef4444; margin-top: 0;">🚨 Template Tamper &amp; License Alert</h2>
          <p>Stealth license telemetry has detected unauthorized tampering or removal of the embedded watermark / license files on a downloaded template.</p>
          
          <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: #0f172a; border-radius: 8px; overflow: hidden;">
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Template</td>
              <td style="padding: 10px 14px; color: #f8fafc; font-weight: bold;">{template_title or template_id} ({template_id})</td>
            </tr>
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Buyer Email</td>
              <td style="padding: 10px 14px; color: #38bdf8; font-weight: bold;">{buyer_email or "Unknown"}</td>
            </tr>
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">License Key</td>
              <td style="padding: 10px 14px; color: #c084fc; font-family: monospace;">{license_key or "N/A"}</td>
            </tr>
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Violation Detected</td>
              <td style="padding: 10px 14px; color: #f87171; font-weight: bold;">{violation_type}</td>
            </tr>
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Hosting Domain / Origin</td>
              <td style="padding: 10px 14px; color: #facc15; font-family: monospace;">{domain or "N/A"}</td>
            </tr>
            <tr style="border-bottom: 1px solid #334155;">
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Client IP</td>
              <td style="padding: 10px 14px; color: #cbd5e1; font-family: monospace;">{ip_address or "N/A"}</td>
            </tr>
            <tr>
              <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">Timestamp</td>
              <td style="padding: 10px 14px; color: #cbd5e1;">{ts}</td>
            </tr>
          </table>

          <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 14px; font-size: 13px; color: #fca5a5;">
            <strong>Action Required:</strong> Review this buyer's account on the Admin Dashboard. Standard Edition licenses require embedded watermarks to remain intact unless upgraded to an Extended License or active Pro subscription.
          </div>

          <hr style="border-color: #334155; margin: 24px 0;" />
          <p style="font-size: 12px; color: #64748b; text-align: center;">
            AI Site Studio Automated Security Telemetry &copy; {datetime.datetime.now().year}
          </p>
        </div>
      </body>
    </html>
    """

    try:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = admin_email
        msg.attach(email.mime.text.MIMEText(html_body, "html", "utf-8"))

        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [admin_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, [admin_email], msg.as_string())

        print(f"🚨 [TAMPER ALERT EMAIL SENT] Alert delivered to {admin_email}")
        return True
    except smtplib.SMTPException as exc:
        print(f"[TAMPER ALERT ERROR] Failed to send email to {admin_email}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        print(f"[TAMPER ALERT ERROR] Unexpected error sending email to {admin_email}: {exc}")
        return False
