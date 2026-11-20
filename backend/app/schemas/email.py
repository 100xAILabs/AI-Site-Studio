"""
Pydantic schemas for Email & Contact System.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class ContactSubmissionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Name of sender")
    email: EmailStr = Field(..., description="Email address of sender")
    phone: Optional[str] = Field(None, max_length=40, description="Phone number of sender for callback or WhatsApp")
    subject: Optional[str] = Field("Website Inquiry", max_length=200, description="Subject of inquiry")
    message: str = Field(..., min_length=5, max_length=5000, description="Message body")
    site_name: Optional[str] = Field("AI Site Studio Website", description="Source website name")
    recipient_email: Optional[EmailStr] = Field(None, description="Optional custom recipient/owner email")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom enquiry attributes e.g. room availability, dates, guests")
    # Anti-spam protections
    website: Optional[str] = Field(None, description="Honeypot field — MUST BE EMPTY")
    form_loaded_at: Optional[float] = Field(None, description="Timestamp when user loaded form (velocity check)")


class NewsletterSubscriptionRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to subscribe")
    site_name: Optional[str] = Field("AI Site Studio Website", description="Source website name")
    # Anti-spam protections
    website: Optional[str] = Field(None, description="Honeypot field — MUST BE EMPTY")
    form_loaded_at: Optional[float] = Field(None, description="Timestamp when user loaded form")


class GenericEmailSendRequest(BaseModel):
    to: List[EmailStr] = Field(..., description="Recipient email address(es)")
    subject: str = Field(..., min_length=1, max_length=255)
    html_body: str = Field(..., min_length=1)
    text_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[EmailStr] = None


class ContactSubmissionResponse(BaseModel):
    success: bool
    status: str
    message: str
    provider: str
    message_id: Optional[str] = None
    customer_confirmation_sent: bool = False


class NewsletterSubscriptionResponse(BaseModel):
    success: bool
    status: str
    message: str
    email: str
    provider: str


class EmailConfigVerifyResponse(BaseModel):
    active_provider: str
    providers: Dict[str, Any]
    ready: bool
