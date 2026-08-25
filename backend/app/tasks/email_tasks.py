"""
Email communication background tasks.
"""

from app.core.celery_app import celery_app


@celery_app.task(name="app.tasks.email_tasks.send_license_delivery")
def send_license_delivery(to_email: str, license_key: str, template_name: str):
    """
    Sends license details post-payment.
    """
    print(f"📧 Sending license code {license_key} for {template_name} to {to_email}")
    return True
