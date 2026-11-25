"""
Real Payment Gateway Provisioning & Verification Service.

Handles real, strict provisioning and verification for Creator Storefront payouts:
- Razorpay Route Linked Account (POST https://api.razorpay.com/v2/accounts) auto-creation
  with fallback verification / RazorpayX Contact + Bank Fund Account when applicable.
- Stripe Connect Express account creation (stripe.Account.create) & hosted KYC onboarding
  links (stripe.AccountLink.create), plus live verification (stripe.Account.retrieve).
- Strict validation for UPI VPAs and domestic/international bank details.

Zero fake IDs or simulated connections are ever generated here.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_FAKE_TOKENS = (
    "test_creator",
    "acct_test",
    "acc_mock",
    "mock_",
    "fake",
    "dummy",
    "placeholder",
    "example",
    "creator_payout_id",
)


def is_placeholder_value(value: Optional[str]) -> bool:
    """Return True if a gateway or bank value appears to be a mock/placeholder string."""
    if not value:
        return False
    lower = str(value).strip().lower()
    return any(tok in lower for tok in _FAKE_TOKENS)


def validate_real_upi_vpa(vpa: Optional[str]) -> tuple[bool, str]:
    """Validate UPI VPA syntax and reject placeholder test handles."""
    if not vpa:
        return False, "UPI VPA is required."
    clean = str(vpa).strip().lower()
    if is_placeholder_value(clean) or clean.endswith("@test") or clean.startswith("test@"):
        return False, "Please enter a real, active UPI VPA (e.g. name@okhdfcbank)."
    if not re.match(r"^[a-z0-9._-]{2,}@[a-z0-9]{2,}$", clean):
        return False, "Invalid UPI VPA format. Expected format like name@okaxis or 9876543210@ybl."
    return True, clean


def normalize_phone_e164(phone: Optional[str], default_country: str = "IN") -> Optional[str]:
    """Normalize a phone string into E.164 format or digits acceptable by Razorpay/Stripe."""
    if not phone:
        return None
    raw = str(phone).strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10:
        return None
    if raw.startswith("+"):
        return f"+{digits}"
    if len(digits) == 10 and default_country.upper() == "IN":
        return f"+91{digits}"
    if len(digits) == 10 and default_country.upper() == "US":
        return f"+1{digits}"
    return f"+{digits}"


def validate_bank_details(
    bank_name: Optional[str],
    account_number: Optional[str],
    account_holder_name: Optional[str],
    ifsc_code: Optional[str] = None,
    iban: Optional[str] = None,
    swift_code: Optional[str] = None,
) -> tuple[bool, str]:
    """Strictly validate creator bank account details for direct settlement."""
    if not bank_name or len(bank_name.strip()) < 2:
        return False, "Bank name is required."
    if not account_holder_name or len(account_holder_name.strip()) < 2:
        return False, "Account holder legal name is required."
    if not account_number:
        return False, "Bank account number or IBAN is required."

    clean_acc = re.sub(r"\s+", "", str(account_number))
    if "*" in clean_acc or "•" in clean_acc:
        return False, "Please enter your full unmasked bank account number."
    if is_placeholder_value(clean_acc) or clean_acc in ("123456", "12345678", "00000000"):
        return False, "Please enter a valid real bank account number."
    if len(clean_acc) < 6 or len(clean_acc) > 34:
        return False, "Bank account number / IBAN must be between 6 and 34 characters."

    has_ifsc = bool(ifsc_code and len(ifsc_code.strip()) >= 4)
    has_iban = bool(iban and len(iban.strip()) >= 8)
    has_swift = bool(swift_code and len(swift_code.strip()) >= 8)
    if not (has_ifsc or has_iban or has_swift):
        return False, "Please provide a valid IFSC / Routing code, IBAN, or SWIFT/BIC code."

    if ifsc_code and re.match(r"^[A-Za-z]{4}[0-9A-Za-z]{7}$", ifsc_code.strip()):
        # Standard 11-char Indian IFSC has '0' at index 4
        if ifsc_code.strip()[4] != "0":
            return False, "Invalid Indian IFSC code format (the 5th character must be '0', e.g. HDFC0001234)."

    return True, "Valid bank details."


@dataclass
class GatewayProvisionResult:
    success: bool
    provider: str
    connected: bool = False
    account_id: Optional[str] = None
    onboarding_url: Optional[str] = None
    account_type: Optional[str] = None  # e.g. "route", "fund_account", "express", "existing"
    status_label: str = "unverified"
    error: Optional[str] = None
    technical_detail: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _razorpay_auth_headers() -> Dict[str, str]:
    token = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode("utf-8")
    ).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def is_razorpay_configured() -> bool:
    return bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and not settings.RAZORPAY_KEY_ID.startswith(("rzp_test_...", "your-"))
        and "mock" not in settings.RAZORPAY_KEY_ID.lower()
    )


def is_stripe_configured() -> bool:
    return bool(
        settings.STRIPE_SECRET_KEY
        and not settings.STRIPE_SECRET_KEY.startswith(("sk_test_...", "your-"))
        and "mock" not in settings.STRIPE_SECRET_KEY.lower()
    )


async def verify_razorpay_account_live(account_id: str) -> GatewayProvisionResult:
    """Verify an existing Razorpay Route linked account ID against the live Razorpay API."""
    if not is_razorpay_configured():
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="There is some issue connecting Razorpay right now (platform Razorpay keys are not configured). Please try again later.",
        )

    clean_id = (account_id or "").strip()
    if is_placeholder_value(clean_id) or not (clean_id.startswith("acc_") or clean_id.startswith("fa_")):
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="Invalid Razorpay Linked Account ID. Account IDs must start with 'acc_' (Route Linked Account) or 'fa_' (Fund Account). Leave the field blank to auto-generate one.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if clean_id.startswith("fa_"):
                # RazorpayX Fund Account live verification
                resp = await client.get(
                    f"https://api.razorpay.com/v1/fund_accounts/{clean_id}",
                    headers=_razorpay_auth_headers(),
                )
                data = resp.json() if resp.content else {}
                if resp.status_code in (200, 201) and data.get("id"):
                    is_active = bool(data.get("active", True))
                    return GatewayProvisionResult(
                        success=True,
                        provider="razorpay",
                        connected=is_active,
                        account_id=data.get("id", clean_id),
                        account_type="fund_account",
                        status_label="active" if is_active else "inactive",
                        metadata={
                            "contact_id": data.get("contact_id"),
                            "account_type": data.get("account_type"),
                            "active": is_active,
                        },
                    )

                err_desc = (data.get("error") or {}).get("description") or f"HTTP {resp.status_code}"
                return GatewayProvisionResult(
                    success=False,
                    provider="razorpay",
                    error="There is some issue verifying this Razorpay Fund Account right now. Please check the account ID or try again later.",
                    technical_detail=err_desc,
                )

            # Razorpay Route Linked Account live verification
            resp = await client.get(
                f"https://api.razorpay.com/v2/accounts/{clean_id}",
                headers=_razorpay_auth_headers(),
            )
            data = resp.json() if resp.content else {}
            if resp.status_code in (200, 201):
                acc_status = str(data.get("status") or "created").lower()
                return GatewayProvisionResult(
                    success=True,
                    provider="razorpay",
                    connected=acc_status not in ("suspended", "rejected"),
                    account_id=data.get("id", clean_id),
                    account_type="route",
                    status_label=acc_status,
                    metadata={"email": data.get("email"), "status": acc_status},
                )

            err_desc = (data.get("error") or {}).get("description") or f"HTTP {resp.status_code}"
            return GatewayProvisionResult(
                success=False,
                provider="razorpay",
                error="There is some issue verifying this Razorpay account right now. Please check the account ID or try again later.",
                technical_detail=err_desc,
            )
    except Exception as exc:
        logger.warning("Razorpay account verify failed: %s", exc)
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="There is some issue connecting to Razorpay right now. Please try again later.",
            technical_detail=str(exc),
        )


async def provision_razorpay_account(
    *,
    user_id: str,
    email: str,
    phone: Optional[str],
    brand_name: str,
    creator_name: Optional[str],
    business_type: str = "individual",
    pan: Optional[str] = None,
    bank_name: Optional[str] = None,
    account_number: Optional[str] = None,
    ifsc_code: Optional[str] = None,
    account_holder_name: Optional[str] = None,
    upi_vpa: Optional[str] = None,
    existing_account_id: Optional[str] = None,
) -> GatewayProvisionResult:
    """
    Automatically create (or verify) a real Razorpay account for an Extreme creator.

    Order of real provisioning attempts:
    1. If existing_account_id (acc_...) is provided, verify it directly via GET /v2/accounts/{id}.
    2. Otherwise, create a real Razorpay Route Linked Account via POST /v2/accounts (v2 composite
       with bank account or VPA settlement, falling back to standard /v2/accounts payload if composite
       fields aren't eligible).
    3. If Route v2 is unavailable on the platform key, attempt RazorpayX Contact + Bank/UPI Fund
       Account creation (POST /v1/contacts + POST /v1/fund_accounts) if credentials are enabled for payouts.
    4. Never fabricate fake acc_mock_ IDs; return an honest failure if Razorpay rejects.
    """
    if not is_razorpay_configured():
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="There is some issue connecting Razorpay right now. Platform Razorpay API keys are not active.",
        )

    if existing_account_id and existing_account_id.strip():
        return await verify_razorpay_account_live(existing_account_id)

    norm_phone = normalize_phone_e164(phone, "IN")
    if not norm_phone:
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="A valid 10-digit phone number (with country code, e.g. +919876543210) is required to automatically create your Razorpay account.",
        )

    clean_holder = (account_holder_name or creator_name or brand_name or "").strip()
    clean_acc = re.sub(r"\s+", "", str(account_number or ""))
    clean_ifsc = (ifsc_code or "").strip().upper()
    clean_vpa = (upi_vpa or "").strip().lower()

    has_bank = bool(clean_acc and clean_ifsc and "*" not in clean_acc and "•" not in clean_acc)
    has_vpa = bool(clean_vpa and "@" in clean_vpa)
    if not has_bank and not has_vpa:
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="Please provide your Bank Account Number + IFSC Code (or verified UPI ID) so we can automatically create your Razorpay payout account.",
        )

    headers = _razorpay_auth_headers()
    ref_id = f"creator_{str(user_id).replace('-', '')[:16]}"
    legal_name = (brand_name or creator_name or clean_holder or "Site Studio Creator").strip()[:100]
    b_type = (business_type or "individual").strip().lower()
    if b_type not in ("individual", "proprietorship", "partnership", "private_limited", "public_limited", "llp", "trust", "society", "ngo"):
        b_type = "individual"

    # Attempt 1: Razorpay Route v2 Linked Account (Composite API with Bank/UPI Settlement)
    composite_payload: Dict[str, Any] = {
        "type": "route",
        "tnc_accepted": True,
        "reference_id": ref_id,
        "legal_business_name": legal_name,
        "business_type": b_type,
        "email": email.strip().lower(),
        "phone": norm_phone,
        "contact_name": (creator_name or clean_holder or legal_name)[:100],
        "notes": {
            "platform": "ai_site_studio",
            "creator_user_id": str(user_id),
        },
    }
    if pan and re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan.strip().upper()):
        composite_payload["legal_info"] = {"pan": pan.strip().upper()}

    if has_bank:
        composite_payload["settlement_accounts"] = [
            {
                "method": "bank_account",
                "bank_account": {
                    "account_number": clean_acc,
                    "beneficiary_name": clean_holder[:120],
                    "code_type": "ifsc",
                    "code": clean_ifsc,
                    "currency": "INR",
                    "is_default": True,
                },
            }
        ]
    elif has_vpa:
        composite_payload["settlement_accounts"] = [
            {
                "method": "upi",
                "upi": {
                    "vpa": clean_vpa,
                    "beneficiary_name": clean_holder[:120],
                    "currency": "INR",
                    "is_default": True,
                },
            }
        ]

    route_error_detail = ""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            idem_headers = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            resp = await client.post(
                "https://api.razorpay.com/v2/accounts",
                headers=idem_headers,
                json=composite_payload,
            )
            data = resp.json() if resp.content else {}

            if resp.status_code in (200, 201) and data.get("id"):
                return GatewayProvisionResult(
                    success=True,
                    provider="razorpay",
                    connected=True,
                    account_id=data["id"],
                    account_type="route",
                    status_label=str(data.get("status") or "created"),
                    metadata={"razorpay_response_id": data["id"], "email": email},
                )

            err_obj = data.get("error") or {}
            route_error_detail = err_obj.get("description") or f"HTTP {resp.status_code}"
            logger.warning("Razorpay composite /v2/accounts failed (%s): %s", resp.status_code, route_error_detail)

            # Attempt 2: Standard /v2/accounts creation without composite settlement_accounts
            # (some Razorpay accounts accept profile creation then Route product activation separately)
            if resp.status_code == 400 and "settlement_accounts" in route_error_detail.lower():
                standard_payload = {
                    "email": email.strip().lower(),
                    "phone": norm_phone,
                    "type": "route",
                    "reference_id": f"{ref_id}_{uuid.uuid4().hex[:4]}",
                    "legal_business_name": legal_name,
                    "business_type": b_type,
                    "contact_name": (creator_name or clean_holder or legal_name)[:100],
                    "profile": {
                        "category": "ecommerce",
                        "subcategory": "software",
                    },
                }
                if "legal_info" in composite_payload:
                    standard_payload["legal_info"] = composite_payload["legal_info"]

                std_resp = await client.post(
                    "https://api.razorpay.com/v2/accounts",
                    headers=headers,
                    json=standard_payload,
                )
                std_data = std_resp.json() if std_resp.content else {}
                if std_resp.status_code in (200, 201) and std_data.get("id"):
                    return GatewayProvisionResult(
                        success=True,
                        provider="razorpay",
                        connected=True,
                        account_id=std_data["id"],
                        account_type="route",
                        status_label=str(std_data.get("status") or "created"),
                        metadata={"razorpay_response_id": std_data["id"]},
                    )
                route_error_detail = (std_data.get("error") or {}).get("description") or route_error_detail

            # Attempt 3: Check RazorpayX Contacts + Fund Account creation (for direct bank/VPA settlement)
            contact_payload = {
                "name": (creator_name or clean_holder or legal_name)[:50],
                "email": email.strip().lower(),
                "contact": re.sub(r"\D", "", norm_phone)[-10:],
                "type": "vendor",
                "reference_id": ref_id,
            }
            c_resp = await client.post(
                "https://api.razorpay.com/v1/contacts",
                headers=headers,
                json=contact_payload,
            )
            c_data = c_resp.json() if c_resp.content else {}
            if c_resp.status_code in (200, 201) and c_data.get("id"):
                contact_id = c_data["id"]
                fa_payload: Dict[str, Any] = {"contact_id": contact_id}
                if has_bank:
                    fa_payload["account_type"] = "bank_account"
                    fa_payload["bank_account"] = {
                        "name": clean_holder[:120],
                        "ifsc": clean_ifsc,
                        "account_number": clean_acc,
                    }
                else:
                    fa_payload["account_type"] = "vpa"
                    fa_payload["vpa"] = {"address": clean_vpa}

                fa_resp = await client.post(
                    "https://api.razorpay.com/v1/fund_accounts",
                    headers=headers,
                    json=fa_payload,
                )
                fa_data = fa_resp.json() if fa_resp.content else {}
                if fa_resp.status_code in (200, 201) and fa_data.get("id"):
                    return GatewayProvisionResult(
                        success=True,
                        provider="razorpay",
                        connected=True,
                        account_id=fa_data["id"],
                        account_type="fund_account",
                        status_label="active" if fa_data.get("active", True) else "pending",
                        metadata={
                            "contact_id": contact_id,
                            "fund_account_id": fa_data["id"],
                            "account_type": fa_payload["account_type"],
                        },
                    )
                fa_err = (fa_data.get("error") or {}).get("description") or f"HTTP {fa_resp.status_code}"
                route_error_detail = f"{route_error_detail} | Fund Account: {fa_err}"
            else:
                c_err = (c_data.get("error") or {}).get("description") or f"HTTP {c_resp.status_code}"
                logger.info("Razorpay contacts fallback returned (%s): %s", c_resp.status_code, c_err)

    except Exception as exc:
        logger.warning("Razorpay auto-provisioning failed: %s", exc)
        return GatewayProvisionResult(
            success=False,
            provider="razorpay",
            error="There is some issue connecting Razorpay right now. Please try again later.",
            technical_detail=str(exc),
        )

    return GatewayProvisionResult(
        success=False,
        provider="razorpay",
        error=(
            "There is some issue automatically creating or connecting your Razorpay account right now. "
            "Please verify your details or try again later."
        ),
        technical_detail=route_error_detail,
    )


async def provision_stripe_connect_account(
    *,
    user_id: str,
    email: str,
    brand_name: str,
    country: str = "US",
    existing_account_id: Optional[str] = None,
    return_url: Optional[str] = None,
    refresh_url: Optional[str] = None,
) -> GatewayProvisionResult:
    """
    Create or verify a genuine Stripe Connect Express account and generate an onboarding link.
    Never falls back to fake/test placeholder IDs.
    """
    if not is_stripe_configured():
        return GatewayProvisionResult(
            success=False,
            provider="stripe",
            error="There is some issue connecting Stripe right now (platform Stripe credentials are not configured). Please try again later.",
        )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    clean_existing = (existing_account_id or "").strip()
    if clean_existing:
        if is_placeholder_value(clean_existing) or not re.match(r"^acct_[a-zA-Z0-9]{10,40}$", clean_existing):
            return GatewayProvisionResult(
                success=False,
                provider="stripe",
                error="Invalid Stripe Connected Account ID. Please connect your real Stripe Express/Standard account or auto-create one below.",
            )
        try:
            acct = await asyncio.to_thread(stripe.Account.retrieve, clean_existing)
            charges_ok = bool(getattr(acct, "charges_enabled", False))
            payouts_ok = bool(getattr(acct, "payouts_enabled", False))
            submitted = bool(getattr(acct, "details_submitted", False))

            onboarding_url = None
            if not (submitted and (charges_ok or payouts_ok)):
                base_frontend = settings.FRONTEND_URL.rstrip("/")
                link = await asyncio.to_thread(
                    stripe.AccountLink.create,
                    account=acct.id,
                    refresh_url=refresh_url or f"{base_frontend}/creator/setup?stripe_refresh=1",
                    return_url=return_url or f"{base_frontend}/creator/setup?stripe_connected=1",
                    type="account_onboarding",
                )
                onboarding_url = link.url

            return GatewayProvisionResult(
                success=True,
                provider="stripe",
                connected=bool(submitted or charges_ok or payouts_ok),
                account_id=acct.id,
                onboarding_url=onboarding_url,
                account_type=str(getattr(acct, "type", "express")),
                status_label="active" if (charges_ok and payouts_ok) else ("onboarding_pending" if not submitted else "restricted"),
                metadata={
                    "charges_enabled": charges_ok,
                    "payouts_enabled": payouts_ok,
                    "details_submitted": submitted,
                },
            )
        except Exception as exc:
            logger.warning("Stripe account verify failed for %s: %s", clean_existing, exc)
            return GatewayProvisionResult(
                success=False,
                provider="stripe",
                error="There is some issue verifying your Stripe Connect account right now. Please try again later.",
                technical_detail=str(exc),
            )

    # Auto-create new Express connected account on Stripe
    try:
        country_code = (country or "US").strip().upper()[:2]
        if len(country_code) != 2:
            country_code = "US"

        acct = await asyncio.to_thread(
            stripe.Account.create,
            type="express",
            country=country_code,
            email=email.strip().lower(),
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="individual",
            business_profile={
                "name": (brand_name or "Site Studio Creator").strip()[:100],
            },
            metadata={
                "user_id": str(user_id),
                "platform": "ai_site_studio",
            },
        )
        base_frontend = settings.FRONTEND_URL.rstrip("/")
        link = await asyncio.to_thread(
            stripe.AccountLink.create,
            account=acct.id,
            refresh_url=refresh_url or f"{base_frontend}/creator/setup?stripe_refresh=1",
            return_url=return_url or f"{base_frontend}/creator/setup?stripe_connected=1",
            type="account_onboarding",
        )
        return GatewayProvisionResult(
            success=True,
            provider="stripe",
            connected=False,  # User must complete hosted onboarding link to submit bank & KYC
            account_id=acct.id,
            onboarding_url=link.url,
            account_type="express",
            status_label="onboarding_required",
            metadata={
                "charges_enabled": False,
                "payouts_enabled": False,
                "details_submitted": False,
            },
        )
    except Exception as exc:
        logger.warning("Stripe Express account creation failed: %s", exc)
        exc_msg = str(exc)
        if "must be activated in order to create accounts" in exc_msg.lower() or "account/onboarding" in exc_msg.lower():
            friendly_err = (
                "Stripe Connect platform activation required: Your platform Stripe account must complete activation at "
                "https://dashboard.stripe.com/account/onboarding before Express accounts can be auto-created. "
                "In the meantime, you can connect your existing Stripe account ID (acct_...), provide your real Stripe Payment Link (https://buy.stripe.com/...), "
                "or connect with Razorpay Route / Direct UPI."
            )
        else:
            friendly_err = (
                f"There is some issue connecting your Stripe account right now ({exc_msg[:120]}). Please check your details or try again later."
            )
        return GatewayProvisionResult(
            success=False,
            provider="stripe",
            error=friendly_err,
            technical_detail=exc_msg,
        )
