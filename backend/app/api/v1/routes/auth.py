"""
Auth routes — OAuth with Google and GitHub.
"""

from typing import Optional
import secrets
import time
import logging
import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth, OAuthError

from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, create_refresh_token, authenticate_token
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserResponse, PayoutSetupRequest
from app.services.gateway_provisioning import (
    is_placeholder_value,
    validate_bank_details,
    validate_real_upi_vpa,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory fallback for OAuth authorization codes if Redis is temporarily unreachable
_oauth_codes: dict[str, tuple[str, float]] = {}

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str
    creator_slug: Optional[str] = None


def is_company_email(email: str) -> bool:
    if "@" not in email:
        return False
    domain = email.split("@")[-1].lower()
    public_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
        "aol.com", "zoho.com", "protonmail.com", "proton.me", "mail.com",
        "yandex.com", "gmx.com", "live.com", "msn.com"
    }
    return domain not in public_domains

def is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(not c.isalnum() for c in password):
        return False
    return True

import random

import os
import asyncio
import smtplib
from email.mime.text import MIMEText
DUMMY_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "dummy.com",
    "company.com", "sample.com", "invalid", "localhost", "mailinator.com"
}

def is_dummy_or_test_email(email: str) -> bool:
    if not email or "@" not in email:
        return True
    domain = email.split("@")[-1].lower().strip()
    return (
        domain in DUMMY_EMAIL_DOMAINS
        or domain.endswith(".example")
        or domain.endswith(".test")
        or domain.endswith(".invalid")
        or domain.endswith(".local")
    )

def send_smtp_email_sync(to_email: str, subject: str, body: str) -> bool:
    # 1. Skip if test environment or email delivery explicitly disabled
    is_test_env = (
        getattr(settings, "ENVIRONMENT", "").lower() in ("test", "testing")
        or os.getenv("ENVIRONMENT", "").lower() in ("test", "testing")
        or not getattr(settings, "ENABLE_EMAIL_DELIVERY", True)
    )
    if is_test_env:
        print(f"\n[TEST SIMULATION] Real SMTP skipped for {to_email} (Test/Disabled Mode). Subject: {subject}\n")
        return False

    # 2. Skip placeholder / dummy domains to prevent delivery delay & bounce notices from mail providers
    if is_dummy_or_test_email(to_email):
        print(f"\n[SIMULATION] Email to placeholder domain ({to_email}) skipped to prevent delivery bounce. Subject: {subject}\n")
        return False

    # 3. Check credentials
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"\n[EMAIL NOT SENT] SMTP credentials are not configured; verification email was not delivered to {to_email}.\n")
        return False

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email

    try:
        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to_email], msg.as_string())
        logger.info("[EMAIL SENT] OTP successfully sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("[EMAIL ERROR] Failed to send email via SMTP to %s: %s", to_email, e)
        return False

async def send_otp_email(to_email: str, otp: str) -> bool:
    if not to_email or "@" not in to_email or is_dummy_or_test_email(to_email):
        logger.info("[SIMULATION/SKIP] Email to %s skipped.", to_email)
        return False

    subject = f"Your OTP Verification Code - Site Studio"
    body = f"""
    <html>
      <body style="font-family: sans-serif; line-height: 1.5; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
          <h2 style="color: #6366f1;">Verify Your Email Address</h2>
          <p>Thank you for using Site Studio. Please use the following One-Time Passcode (OTP) to complete your verification. This code is valid for 5 minutes:</p>
          <div style="font-size: 24px; font-weight: bold; color: #4f46e5; letter-spacing: 2px; text-align: center; margin: 30px 0; padding: 15px; background-color: #f5f3ff; border-radius: 6px;">
            {otp}
          </div>
          <p style="font-size: 12px; color: #777;">If you did not request this code, you can safely ignore this email.</p>
        </div>
      </body>
    </html>
    """

    # 1. If BREVO_API_KEY is configured, send via Brevo REST API (HTTPS port 443 — free 300 emails/day to ANY email worldwide)
    if getattr(settings, "BREVO_API_KEY", ""):
        try:
            import httpx
            sender_email = settings.SMTP_FROM or settings.SMTP_USER or "navinbharath917@gmail.com"
            headers = {
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "sender": {"name": "Site Studio", "email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": body,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.brevo.com/v3/smtp/email", headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    logger.info("[EMAIL SENT] OTP successfully sent via Brevo API to %s", to_email)
                    return True
                else:
                    logger.warning("[EMAIL ERROR] Brevo API error (%s): %s", resp.status_code, resp.text)
        except Exception as err:
            logger.error("[EMAIL ERROR] Brevo API exception: %s", err)

    # 2. If RESEND_API_KEY is configured, send via Resend REST API (HTTPS port 443 — never blocked on Render)
    if getattr(settings, "RESEND_API_KEY", ""):
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": settings.RESEND_FROM or "Site Studio <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": body,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://api.resend.com/emails", headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    logger.info("[EMAIL SENT] OTP successfully sent via Resend API to %s", to_email)
                    return True
                else:
                    logger.warning("[EMAIL ERROR] Resend API error (%s): %s", resp.status_code, resp.text)
        except Exception as err:
            logger.error("[EMAIL ERROR] Resend API exception: %s", err)

    # 3. Fallback to standard SMTP
    try:
        loop = asyncio.get_running_loop()
        sent = await loop.run_in_executor(None, send_smtp_email_sync, to_email, subject, body)
        return bool(sent)
    except Exception as e:
        logger.error("Error sending email in executor: %s", e)
        return False

import hashlib
from app.core.redis import get_redis

_active_background_tasks = set()
_login_attempts: dict[str, list[float]] = {}

async def enforce_login_rate_limit(request: Request, email: str) -> None:
    """Limit password guessing per client and account; Redis is shared across workers."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"auth:login:{client_ip}:{email.strip().lower()[:254]}"
    redis_client = await get_redis()
    if redis_client:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 900)
        if count > 10:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again later.")
        return

    now = time.monotonic()
    attempts = [stamp for stamp in _login_attempts.get(key, []) if now - stamp < 900]
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again later.")
    attempts.append(now)
    _login_attempts[key] = attempts
    if len(_login_attempts) > 10000:
        _login_attempts.clear()

async def generate_otp(email: str, purpose: str) -> tuple[str, bool]:
    email_key = email.lower().strip()
    redis_client = await get_redis()
    
    # 1a. Daily send cap: max 10 OTP requests per email per 24 hours to prevent quota exhaustion
    daily_key = f"otp:daily:{purpose}:{email_key}"
    daily_count = await redis_client.incr(daily_key)
    if daily_count == 1:
        await redis_client.expire(daily_key, 86400)
    elif daily_count > 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily OTP limit exceeded for this email address. Please try again tomorrow."
        )

    # 1b. Rate limiting: Check if an OTP was generated within the last 60 seconds
    rate_key = f"otp:rate:{purpose}:{email_key}"
    if await redis_client.get(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait 60 seconds before trying again."
        )

    # 2. Generate random 6-digit code
    otp = f"{secrets.randbelow(900000) + 100000}"
    hashed_otp = hashlib.sha256(otp.encode("utf-8")).hexdigest()

    # 3. Store hashed OTP with 5 minute expiration, and verification attempts counter (max 3)
    db_key = f"otp:code:{purpose}:{email_key}"
    await redis_client.set(db_key, hashed_otp, ex=300)
    
    attempts_key = f"otp:attempts:{purpose}:{email_key}"
    await redis_client.set(attempts_key, "0", ex=300)

    # Set rate limiter for 60 seconds
    await redis_client.set(rate_key, "1", ex=60)
    
    # Dispatch email and wait for delivery result
    sent = await send_otp_email(email, otp)
    logger.info("OTP dispatched for %s (purpose=%s, delivered=%s)", email, purpose, sent)
    
    return otp, sent


oauth = OAuth()
if settings.GOOGLE_CLIENT_ID:
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        client_kwargs={'scope': 'openid email profile'},
    )

if settings.GITHUB_CLIENT_ID:
    oauth.register(
        name='github',
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={
            'scope': 'read:user user:email',
            'headers': {'User-Agent': 'AI-Site-Studio'}
        },
    )


@router.get("/{provider}/login")
async def login(
    provider: str,
    request: Request,
    role: str = "buyer",
    redirect: Optional[str] = None,
    origin: Optional[str] = None,
):
    """Redirects to the OAuth provider."""
    # github is allowed only when 'auth_current_user_id' is already in session (connect-to-existing-user flow)
    # It should NOT be a standalone login method — the sign-in page only shows Google.
    if provider not in ["google", "github"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
    if provider == "github":
        if not request.session.get("auth_current_user_id"):
            raise HTTPException(
                status_code=403,
                detail="GitHub OAuth is only available for connecting to an existing account. Please sign in with Google first."
            )
    
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth is not configured")
        
    redirect_uri = request.url_for('auth_callback', provider=provider)
    
    request.session['auth_role'] = role
    if redirect and redirect.startswith('/') and not redirect.startswith('//') and '://' not in redirect:
        request.session['auth_redirect'] = redirect
        
    candidate_origin = origin or request.headers.get("referer")
    if candidate_origin:
        try:
            from urllib.parse import urlparse
            cand_p = urlparse(candidate_origin)
            cand_origin = f"{cand_p.scheme}://{cand_p.netloc}".rstrip("/")
            if any(cand_origin == allowed.rstrip("/") for allowed in settings.ALLOWED_ORIGINS_LIST):
                request.session['auth_frontend_url'] = cand_origin
        except Exception:
            pass
            
    return await client.authorize_redirect(request, redirect_uri)


@router.post("/github/connect-start")
async def github_connect_start(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Initiates GitHub OAuth account connection by setting session context.
    Prevents CSRF and token leakage in URL.
    """
    request.session["auth_current_user_id"] = str(current_user.id)
    return {"url": "/api/v1/auth/github/login"}


@router.get("/{provider}/callback")
async def auth_callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Handles OAuth callback and creates/updates the user."""
    if provider not in ["google", "github"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
        
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth is not configured")
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as error:
        logger.warning("OAuth token exchange failed for provider %s (%s)", provider, type(error).__name__)
        raise HTTPException(status_code=400, detail=f"OAuth error: {error.error}")
        
    if provider == "google":
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await client.parse_id_token(request, token)
        if not user_info.get("email_verified"):
            raise HTTPException(status_code=400, detail="Google account email is not verified.")
        email = user_info.get("email")
        provider_id = user_info.get("sub")
        full_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "github":
        access_token_val = token.get("access_token")
        resp = await client.get('user', token=token)
        user_info = resp.json()
        email_resp = await client.get('user/emails', token=token)
        emails = email_resp.json()
        email = None
        if isinstance(emails, list):
            for em in emails:
                if em.get("verified") and (em.get("primary") or not email):
                    email = em.get("email")
                    if em.get("primary"):
                        break
        # Reject unverified emails: only accept emails verified by GitHub
        if not email:
            raise HTTPException(
                status_code=400,
                detail="GitHub account has no verified email address. Please verify your email on GitHub before signing in."
            )
            
        provider_id = str(user_info.get("id"))
        full_name = user_info.get("name") or user_info.get("login")
        avatar_url = user_info.get("avatar_url")

    if not email or not provider_id:
        raise HTTPException(status_code=400, detail="Could not retrieve email or ID from provider")

    current_user_id = request.session.pop('auth_current_user_id', None)
    if provider == "github" and not current_user_id:
        raise HTTPException(status_code=403, detail="GitHub OAuth is only available for connecting to an existing account.")

    repo = UserRepository(db)
    if current_user_id:
        from uuid import UUID
        user = await repo.get_by_id(UUID(current_user_id))
        if not user:
            raise HTTPException(status_code=404, detail="Logged in user not found")
        
        # Link GitHub details
        if provider == "github":
            existing_gh_user = await repo.get_by_github_id(provider_id)
            if existing_gh_user and existing_gh_user.id != user.id:
                raise HTTPException(status_code=409, detail="This GitHub account is already linked to another user.")
            user.github_id = provider_id
            user.github_access_token = access_token_val
        elif provider == "google":
            user.google_id = provider_id
            
        await db.flush()
        await db.refresh(user)
    else:
        role_str = request.session.get('auth_role', 'buyer')
        masked_em = f"{email[:2]}***@{email.split('@')[-1]}" if "@" in email else "user"
        logger.info("[OAUTH AUTH] Provider: %s | User: %s | Requested Role: %s", provider.upper(), masked_em, role_str)

        user = await repo.upsert_oauth_user(
            provider=provider,
            provider_id=provider_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            role=role_str
        )

        
        if provider == "github" and access_token_val:
            user.github_access_token = access_token_val
            await db.flush()
            await db.refresh(user)

    from app.services.location_service import update_user_location
    try:
        await update_user_location(user, db, request=request)
    except Exception as err:
        print(f"Location update notice on OAuth callback: {err}")

    redirect_path = request.session.pop('auth_redirect', None)
    # If this was a GitHub connect operation, send the user back to the upload tab
    if not redirect_path and current_user_id and provider == "github":
        redirect_path = "/dashboard?tab=seller-upload"
    elif not redirect_path:
        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        redirect_path = "/dashboard" if user_role_str.lower() == "seller" else "/"

    from urllib.parse import quote_plus
    from app.core.redis import get_redis
    frontend_base = request.session.pop('auth_frontend_url', None) or settings.FRONTEND_URL
    code = secrets.token_urlsafe(32)
    redis_client = await get_redis()
    if redis_client:
        await redis_client.set(f"oauth_code:{code}", str(user.id), ex=60)
    else:
        _oauth_codes[code] = (str(user.id), time.time() + 60.0)
    request.session["oauth_code"] = code
    redirect_url = f"{str(frontend_base).rstrip('/')}/auth/complete?code={code}&redirect={quote_plus(redirect_path)}"
    return RedirectResponse(url=redirect_url)


class OAuthExchangeRequest(BaseModel):
    code: str


@router.post("/exchange")
async def exchange_oauth_code(
    request_data: OAuthExchangeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange single-use OAuth authorization code for session JWT.
    Enforces browser session binding and immediately burns code to prevent replay/brute-force.
    """
    code = request_data.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")

    from app.core.redis import get_redis
    redis_client = await get_redis()
    stored_user_id = None
    if redis_client:
        stored_user_id = await redis_client.get(f"oauth_code:{code}")
        await redis_client.delete(f"oauth_code:{code}")
    else:
        entry = _oauth_codes.pop(code, None)
        if entry and entry[1] > time.time():
            stored_user_id = entry[0]

    session_code = request.session.pop("oauth_code", None)
    if not stored_user_id or session_code != code:
        raise HTTPException(status_code=400, detail="Invalid authorization code or session expired")

    from uuid import UUID
    try:
        user_uuid = UUID(str(stored_user_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user reference in authorization code")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_uuid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account not found or deactivated")

    user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    tv = getattr(user, "token_version", 0)
    access_token = create_access_token(subject=str(user.id), role=user_role_str, tv=tv)
    refresh_token = create_refresh_token(subject=str(user.id), tv=tv)

    is_secure = (request.url.scheme == "https" or settings.ENVIRONMENT == "production")
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=30 * 86400,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user_role_str,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
        },
    }


@router.post("/refresh")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using httpOnly refresh cookie.
    Validates token version against user model to respect global revocation.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            refresh_token = auth_hdr[7:].strip()

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    from app.core.security import authenticate_token
    user = await authenticate_token(db, refresh_token, expected_type="refresh")

    user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    tv = getattr(user, "token_version", 0)
    new_access_token = create_access_token(subject=str(user.id), role=user_role_str, tv=tv)
    new_refresh_token = create_refresh_token(subject=str(user.id), tv=tv)

    is_secure = (request.url.scheme == "https" or settings.ENVIRONMENT == "production")
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=30 * 86400,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(response: Response):
    """Clear session refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke all active sessions and refresh tokens across all devices
    by incrementing user's token version in PostgreSQL.
    """
    current_user.token_version = (getattr(current_user, "token_version", 0) or 0) + 1
    await db.flush()
    await db.commit()
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "All sessions revoked successfully"}


class ConnectGithubRequest(BaseModel):
    token: str


@router.post("/connect-github")
async def connect_github(
    request_data: ConnectGithubRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect a GitHub Personal Access Token to the logged-in user account.
    Validates the token against GitHub API and stores it.
    """
    token = request_data.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token cannot be empty")
        
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}"
    }
    
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.github.com/user", headers=headers, timeout=10.0)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid GitHub token or expired permissions.")
            
            user_data = resp.json()
            github_id = str(user_data.get("id"))
            github_username = user_data.get("login")

            repo = UserRepository(db)
            existing_user = await repo.get_by_github_id(github_id)
            if existing_user and existing_user.id != current_user.id:
                raise HTTPException(status_code=409, detail="This GitHub account is already linked to another user.")
            
            # Save the token and username to the user profile
            current_user.github_id = github_id
            current_user.github_access_token = token
            if not current_user.username:
                current_user.username = github_username
                
            await db.flush()
            await db.refresh(current_user)
            
            return {
                "success": True,
                "message": "GitHub account connected successfully!",
                "github_username": github_username,
            }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error connecting to GitHub: {str(e)}")


@router.post("/disconnect-github")
async def disconnect_github(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disconnect/Unlink GitHub account from the logged-in user.
    """
    current_user.github_id = None
    current_user.github_access_token = None
    await db.flush()
    await db.refresh(current_user)
    return {"success": True, "message": "GitHub account disconnected successfully!"}


@router.post("/register")
async def register(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with email and password."""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "buyer")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
        
    role = "seller" if str(role).lower() == "seller" else "buyer"
    print(f"\n[USER REGISTER] Email: {email} | Role: {role}\n", flush=True)
        
    if not is_strong_password(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )
        
    repo = UserRepository(db)
    existing = await repo.get_by_email(email)
    if existing:
        if existing.google_id:
            raise HTTPException(
                status_code=409,
                detail="This email is already registered using Google Sign-In. You cannot create a manual password account with this email. Please sign in using 'Continue with Google'."
            )
        existing_role_str = existing.role.value if hasattr(existing.role, "value") else str(existing.role)
        if existing.is_email_verified:
            raise HTTPException(
                status_code=409,
                detail=f"An account with this email already exists. Please sign in instead."
            )
        sent = False
        try:
            _, sent = await generate_otp(email, "verify_email")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
            sent = False
        return {
            "status": "otp_required",
            "email": email,
            "sent": sent,
            "message": "OTP verification code sent to your email." if sent else "Could not deliver email. Please check that your email address is correct."
        }
        
    from app.core.security import hash_password
    from app.models.user import UserRole
    base_username = email.split("@")[0]
    unique_username = await repo.get_unique_username(base_username)
    # Auto-upgrade role to SELLER when registering with a corporate/business email domain
    effective_role = role
    if effective_role != "seller" and is_company_email(email):
        effective_role = "seller"

    creator_slug = data.get("creator_slug") or data.get("creator")
    extra_meta = {}
    if creator_slug:
        c_slug = str(creator_slug).strip().lower()
        c_stmt = select(User).where(func.lower(User.creator_store_slug) == c_slug)
        c_res = await db.execute(c_stmt)
        c_obj = c_res.scalar_one_or_none()
        if c_obj:
            extra_meta = {
                "client_of_creator_id": str(c_obj.id),
                "client_of_creator_slug": c_obj.creator_store_slug,
                "client_of_brand": c_obj.creator_brand_name or c_obj.username,
            }

    user = User(
        email=email,
        username=unique_username,
        hashed_password=hash_password(password),
        role=UserRole.SELLER if effective_role == "seller" else UserRole.BUYER,
        is_email_verified=False,
        client_of_creator_id=c_obj.id if c_obj else None,
        client_of_creator_slug=c_obj.creator_store_slug if c_obj else None,
        client_of_brand=(c_obj.creator_brand_name or c_obj.username) if c_obj else None,
        extra_metadata=extra_meta if extra_meta else None
    )
    db.add(user)
    await db.flush()
    await db.commit()
    
    sent = False
    try:
        _, sent = await generate_otp(email, "verify_email")
    except HTTPException as exc:
        if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        sent = False
    return {
        "status": "otp_required",
        "email": email,
        "sent": sent,
        "message": "OTP verification code sent to your email." if sent else "Could not deliver email. Please check that your email address is correct."
    }


@router.post("/login")
async def login_email(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        requested_role = data.get("role")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")

        if not isinstance(email, str) or not isinstance(password, str) or len(email) > 254 or len(password) > 1024:
            raise HTTPException(status_code=400, detail="Invalid sign-in request")
        await enforce_login_rate_limit(request, email)

        repo = UserRepository(db)
        user = await repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Security check: If the account was registered via Google Sign-In, block manual password login
        if user.google_id:
            raise HTTPException(
                status_code=400,
                detail="This account was registered using Google Sign-In. For security reasons, manual password login is disabled for this account. Please sign in using 'Continue with Google'."
            )

        if not user.hashed_password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        from app.core.security import verify_password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
            
        if not user.is_email_verified:
            sent = False
            try:
                _, sent = await generate_otp(user.email, "verify_email")
            except HTTPException as exc:
                if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                    raise
                sent = False
            return {
                "status": "otp_required",
                "email": user.email,
                "sent": sent,
                "message": "Your email is not verified yet. An OTP has been sent to your email." if sent else "Could not deliver email. Please check that your email address is correct."
            }

        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        print(f"\n[USER LOGIN] Email: {user.email} | Active Role: {user_role_str}\n", flush=True)

        from app.services.location_service import update_user_location
        try:
            await update_user_location(user, db, request=request)
        except Exception as err:
            print(f"Location update notice on login: {err}")

        # Attribute user to creator if logging in via creator's portal
        creator_param = data.get("creator_slug") or data.get("creator")
        if creator_param and not user.client_of_creator_id:
            try:
                c_slug = str(creator_param).strip().lower()
                c_stmt = select(User).where(func.lower(User.creator_store_slug) == c_slug)
                c_res = await db.execute(c_stmt)
                c_obj = c_res.scalar_one_or_none()
                if c_obj and c_obj.id != user.id:
                    user.client_of_creator_id = c_obj.id
                    user.client_of_creator_slug = c_obj.creator_store_slug
                    user.client_of_brand = c_obj.creator_brand_name or c_obj.username
                    meta = dict(user.extra_metadata or {})
                    meta["client_of_creator_id"] = str(c_obj.id)
                    meta["client_of_creator_slug"] = c_obj.creator_store_slug
                    meta["client_of_brand"] = c_obj.creator_brand_name or c_obj.username
                    user.extra_metadata = meta
                    await db.commit()
            except Exception as e_meta:
                print(f"Creator client linking notice on login: {e_meta}")

        user_role_for_token = user.role.value if hasattr(user.role, "value") else str(user.role)
        tv = getattr(user, "token_version", 0)
        access_token = create_access_token(subject=str(user.id), role=user_role_for_token, tv=tv)
        refresh_token = create_refresh_token(subject=str(user.id), tv=tv)

        is_secure = (request.url.scheme == "https" or settings.ENVIRONMENT == "production")
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            path="/api/v1/auth",
            max_age=30 * 86400,
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected email login failure")
        raise HTTPException(status_code=500, detail="Unable to sign in right now.") from exc


@router.post("/verify-otp")
async def verify_otp(
    request: Request,
    response: Response,
    request_data: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    email = request_data.email.strip().lower()
    otp = request_data.otp.strip()
    
    redis_client = await get_redis()
    db_key = f"otp:code:verify_email:{email}"
    attempts_key = f"otp:attempts:verify_email:{email}"

    # Get hashed OTP from Redis
    stored_hash = await redis_client.get(db_key)
    if not stored_hash:
        raise HTTPException(status_code=400, detail="OTP expired or no active request found.")

    # Atomic attempt counter increment to prevent parallel brute-force race conditions
    current_attempts = await redis_client.incr(attempts_key)
    if current_attempts > 3:
        await redis_client.delete(db_key)
        await redis_client.delete(attempts_key)
        raise HTTPException(status_code=400, detail="Max verification attempts exceeded. Please request a new OTP.")

    # Constant-time comparison of hashed code
    provided_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(stored_hash, provided_hash):
        raise HTTPException(status_code=400, detail="Invalid OTP code.")
    
    # Successful verification clears OTP keys
    await redis_client.delete(db_key)
    await redis_client.delete(attempts_key)
        
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    user.is_email_verified = True

    # Link user to creator if verifying OTP from a creator portal
    creator_param = request_data.creator_slug
    if creator_param and not user.client_of_creator_id:
        try:
            c_slug = str(creator_param).strip().lower()
            c_stmt = select(User).where(func.lower(User.creator_store_slug) == c_slug)
            c_res = await db.execute(c_stmt)
            c_obj = c_res.scalar_one_or_none()
            if c_obj and c_obj.id != user.id:
                user.client_of_creator_id = c_obj.id
                user.client_of_creator_slug = c_obj.creator_store_slug
                user.client_of_brand = c_obj.creator_brand_name or c_obj.username
                meta = dict(user.extra_metadata or {})
                meta["client_of_creator_id"] = str(c_obj.id)
                meta["client_of_creator_slug"] = c_obj.creator_store_slug
                meta["client_of_brand"] = c_obj.creator_brand_name or c_obj.username
                user.extra_metadata = meta
        except Exception as e_c:
            logger.info("Creator attribution notice on OTP verify: %s", e_c)

    await db.flush()
    await db.commit()
    await db.refresh(user)
    
    # Delete OTP records on success
    await redis_client.delete(db_key)
    await redis_client.delete(attempts_key)

    from app.services.location_service import update_user_location
    try:
        await update_user_location(user, db, request=request)
    except Exception as err:
        logger.info("Location update notice on OTP verify: %s", err)
    
    user_role_for_token = user.role.value if hasattr(user.role, "value") else str(user.role)
    tv = getattr(user, "token_version", 0)
    access_token = create_access_token(subject=str(user.id), role=user_role_for_token, tv=tv)
    refresh_token = create_refresh_token(subject=str(user.id), tv=tv)

    is_secure = (request.url.scheme == "https" or settings.ENVIRONMENT == "production")
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=30 * 86400,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Email verified successfully!"
    }


class ResendOTPRequest(BaseModel):
    email: str


@router.post("/resend-otp")
async def resend_otp(
    request_data: ResendOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    email = request_data.email.strip().lower()
    
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    sent = False
    if user and not user.is_email_verified:
        try:
            _, sent = await generate_otp(email, "verify_email")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
            raise HTTPException(
                status_code=429,
                detail="Too many OTP requests. Please wait 60 seconds before trying again."
            )
    return {
        "status": "otp_required",
        "email": email,
        "sent": sent,
        "message": "A new verification code has been sent." if sent else "Could not deliver verification email. Please check that your email address is correct."
    }


class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/forgot-password")
async def forgot_password(
    request_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a password reset OTP to the user's email."""
    email = request_data.email.strip().lower()
    
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user and user.google_id and not user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="This account was registered using Google Sign-In and does not use a password. Please sign in using 'Continue with Google'."
        )
    sent = False
    if user and user.hashed_password:
        try:
            _, sent = await generate_otp(email, "reset_password")
        except HTTPException as exc:
            if exc.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                raise
            sent = False
    return {
        "status": "otp_required",
        "email": email,
        "sent": sent,
        "message": "A password reset code has been sent to your email." if sent else "Could not deliver reset email. Please check that your email address is correct."
    }


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


@router.post("/reset-password")
async def reset_password(
    request_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset user's password using OTP verification."""
    email = request_data.email.strip().lower()
    otp = request_data.otp.strip()
    new_password = request_data.new_password
    
    redis_client = await get_redis()
    db_key = f"otp:code:reset_password:{email}"
    attempts_key = f"otp:attempts:reset_password:{email}"

    # Verify OTP
    stored_hash = await redis_client.get(db_key)
    if not stored_hash:
        raise HTTPException(status_code=400, detail="OTP expired or no active reset request found.")
        
    # Atomic increment to prevent parallel brute-force race conditions
    current_attempts = await redis_client.incr(attempts_key)
    if current_attempts > 3:
        await redis_client.delete(db_key)
        await redis_client.delete(attempts_key)
        raise HTTPException(status_code=400, detail="Max reset attempts exceeded. Please request a new code.")

    provided_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(stored_hash, provided_hash):
        raise HTTPException(status_code=400, detail="Invalid reset code.")
    
    await redis_client.delete(db_key)
    await redis_client.delete(attempts_key)
    
    # Validate new password strength
    if not is_strong_password(new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )
    
    # Find user and update password
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.google_id and not user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="This account was registered using Google Sign-In and cannot have a manual password set. Please sign in with Google."
        )
    
    from app.core.security import hash_password
    user.hashed_password = hash_password(new_password)
    user.is_email_verified = True  # Implicitly verify email since they proved ownership via OTP
    user.token_version = (getattr(user, "token_version", 0) or 0) + 1
    await db.flush()
    await db.commit()
    await db.refresh(user)
    
    # Clean up OTP keys in redis
    await redis_client.delete(db_key)
    await redis_client.delete(attempts_key)

    # Invalidate all prior active JWT sessions across devices for this account
    try:
        from datetime import timezone
        revocation_ts = int(datetime.now(timezone.utc).timestamp())
        await redis_client.set(f"auth:revoked_before:{user.id}", str(revocation_ts), ex=30 * 86400)
    except Exception as e_rev:
        logger.warning(f"Failed to record token revocation in Redis: {e_rev}")
    
    return {"message": "Password has been reset successfully. You can now sign in with your new password."}


@router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    from datetime import datetime, timezone
    from app.models.user import UserRole
    user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Subscription expiration check:
    # When credits run out or subscription plan is finished, unused tokens MUST NOT be preserved or shown.
    # When plan finishes, tier becomes free, status becomes expired, and ai_credits = 0.
    now_utc = datetime.now(timezone.utc)
    tier = (current_user.subscription_tier or "free").lower()
    user_updated = False

    if tier != "free" and current_user.subscription_expires_at:
        expires = (
            current_user.subscription_expires_at
            if current_user.subscription_expires_at.tzinfo
            else current_user.subscription_expires_at.replace(tzinfo=timezone.utc)
        )
        if expires < now_utc:
            current_user.subscription_tier = "free"
            current_user.subscription_status = "expired"
            current_user.ai_credits = 0
            user_updated = True
    elif tier == "free" and getattr(current_user, "subscription_status", "") in ("expired", "canceled"):
        if (current_user.ai_credits or 0) > 0:
            current_user.ai_credits = 0
            user_updated = True

    if user_updated:
        try:
            from app.services.entitlement_service import EntitlementService
            ent_svc = EntitlementService(db)
            sub = await ent_svc.get_or_create_user_subscription(current_user)
            sub.plan_id = "free"
            sub.status = "expired"
            db.add(sub)
        except Exception as e_sub:
            logger.warning(f"Failed to sync subscription record in /me: {e_sub}")
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

    # Auto-detect location & currency if missing
    if not current_user.country or not current_user.currency or not current_user.country_code:
        from app.services.location_service import update_user_location
        try:
            await update_user_location(current_user, db, request=request)
        except Exception as err:
            print(f"Location detection notice in /me: {err}")

    masked_user_em = f"{current_user.email[:2]}***@{current_user.email.split('@')[-1]}" if "@" in current_user.email else "user"
    logger.info("[PROFILE FETCH] User: %s | Role: %s | Location: %s (%s)", masked_user_em, user_role_val.upper(), current_user.country, current_user.currency)
    return UserResponse.model_validate(current_user)


@router.post("/detect-location", response_model=UserResponse)
async def detect_and_update_location(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Explicitly trigger location & currency detection based on client IP."""
    from app.services.location_service import update_user_location
    await update_user_location(current_user, db, request=request, force=True)
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Update the currently authenticated user's profile."""
    data = await request.json()
    
    from app.models.user import UserRole
    if "role" in data and str(data["role"]).lower() == "seller" and current_user.role == UserRole.BUYER:
        current_user.role = UserRole.SELLER

    if "full_name" in data:
        current_user.full_name = data["full_name"]
    if "username" in data:
        current_user.username = data["username"]
    if "bio" in data:
        current_user.bio = data["bio"]
    if "avatar_url" in data:
        current_user.avatar_url = data["avatar_url"]
    if "country" in data:
        current_user.country = data["country"]
    if "country_code" in data:
        current_user.country_code = data["country_code"]
    if "city" in data:
        current_user.city = data["city"]
    if "currency" in data:
        current_user.currency = data["currency"]

    # ── Payout Settings Updates ──────────────────────────────────────────────
    strict_mode = settings.ENVIRONMENT != "test"
    payout_keys_updated = any(k.startswith("payout_") for k in data)
    if payout_keys_updated and strict_mode:
        for field_name in (
            "payout_bank_name",
            "payout_account_number",
            "payout_ifsc_code",
            "payout_account_holder_name",
            "payout_razorpay_vpa",
            "payout_upi_id",
            "payout_stripe_email",
            "payout_paypal_email",
        ):
            val = data.get(field_name)
            if val and is_placeholder_value(str(val)):
                raise HTTPException(
                    status_code=400,
                    detail=f"Placeholder or demo values are not permitted for {field_name}. Please enter real details."
                )

    if "payout_method" in data and data["payout_method"]:
        current_user.payout_method = str(data["payout_method"]).lower().strip()
    if "payout_bank_name" in data:
        current_user.payout_bank_name = str(data["payout_bank_name"]).strip() if data["payout_bank_name"] else None
    if "payout_account_number" in data:
        current_user.payout_account_number = str(data["payout_account_number"]).strip() if data["payout_account_number"] else None
    if "payout_ifsc_code" in data:
        current_user.payout_ifsc_code = str(data["payout_ifsc_code"]).strip() if data["payout_ifsc_code"] else None
    if "payout_account_holder_name" in data:
        current_user.payout_account_holder_name = str(data["payout_account_holder_name"]).strip() if data["payout_account_holder_name"] else None
    if "payout_razorpay_vpa" in data:
        current_user.payout_razorpay_vpa = str(data["payout_razorpay_vpa"]).strip() if data["payout_razorpay_vpa"] else None
    if "payout_upi_id" in data:
        # payout_upi_id is an alias — save to the same razorpay_vpa column
        new_vpa = str(data["payout_upi_id"]).strip() if data["payout_upi_id"] else None
        if new_vpa:
            current_user.payout_razorpay_vpa = new_vpa
    if "payout_stripe_email" in data:
        current_user.payout_stripe_email = str(data["payout_stripe_email"]).strip() if data["payout_stripe_email"] else None
    if "payout_paypal_email" in data:
        current_user.payout_paypal_email = str(data["payout_paypal_email"]).strip() if data["payout_paypal_email"] else None

    # Sync UPI VPA into creator_payout_details so the storefront picks it up correctly
    if payout_keys_updated and current_user.payout_razorpay_vpa:
        _existing_pd = dict(getattr(current_user, "creator_payout_details", None) or {})
        _existing_pd["upi_id"] = current_user.payout_razorpay_vpa
        _existing_pd["razorpay_vpa"] = current_user.payout_razorpay_vpa
        _enabled = list(_existing_pd.get("enabled_methods") or [])
        if "upi" not in _enabled:
            _enabled.append("upi")
            _existing_pd["enabled_methods"] = _enabled
        current_user.creator_payout_details = _existing_pd

    # Track if payout setup has been configured with genuine verified details
    if payout_keys_updated:
        if not strict_mode:
            current_user.is_payout_setup_completed = True
        else:
            if (
                current_user.payout_bank_name
                or current_user.payout_account_number
                or current_user.payout_ifsc_code
                or current_user.payout_account_holder_name
            ):
                ok_bank, bank_err = validate_bank_details(
                    bank_name=current_user.payout_bank_name,
                    account_holder_name=current_user.payout_account_holder_name,
                    account_number=current_user.payout_account_number,
                    ifsc_or_routing=current_user.payout_ifsc_code,
                    country=current_user.country or "IN",
                )
                if not ok_bank:
                    raise HTTPException(status_code=400, detail=bank_err)

            if current_user.payout_razorpay_vpa:
                ok_upi, upi_err = validate_real_upi_vpa(current_user.payout_razorpay_vpa)
                if not ok_upi:
                    raise HTTPException(status_code=400, detail=upi_err)

            payout_details = getattr(current_user, "creator_payout_details", None) or {}
            has_stripe = bool(
                current_user.stripe_connect_id
                and not is_placeholder_value(current_user.stripe_connect_id)
                and payout_details.get("stripe_charges_enabled")
            )
            has_razorpay = bool(
                (payout_details.get("razorpay_account_id") and not is_placeholder_value(payout_details.get("razorpay_account_id")))
                or (payout_details.get("razorpay_fund_account_id") and not is_placeholder_value(payout_details.get("razorpay_fund_account_id")))
            )
            has_bank = bool(
                current_user.payout_bank_name
                and current_user.payout_account_holder_name
                and current_user.payout_account_number
                and current_user.payout_ifsc_code
            )
            has_upi = bool(current_user.payout_razorpay_vpa)
            primary_method = (current_user.payout_method or "").lower()
            if primary_method == "stripe":
                current_user.is_payout_setup_completed = has_stripe
            elif primary_method == "razorpay":
                current_user.is_payout_setup_completed = has_razorpay
            else:
                current_user.is_payout_setup_completed = bool(has_stripe or has_razorpay or has_bank or has_upi)
        
    if "full_name" in data or "avatar_url" in data:
        from app.models.template import Template
        from sqlalchemy import update
        update_vals = {}
        if "full_name" in data:
            update_vals["developer_name"] = data["full_name"]
        if "avatar_url" in data:
            update_vals["developer_avatar"] = data["avatar_url"]
        if update_vals:
            await db.execute(
                update(Template)
                .where(Template.seller_id == current_user.id)
                .values(**update_vals)
            )
        
    await db.flush()
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.put("/payout-account", response_model=UserResponse)
async def update_payout_account(
    data: PayoutSetupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Setup or update the seller's payout bank account details."""
    if settings.ENVIRONMENT != "test":
        ok_bank, bank_err = validate_bank_details(
            bank_name=data.payout_bank_name,
            account_holder_name=data.payout_account_holder_name,
            account_number=data.payout_account_number,
            ifsc_or_routing=data.payout_ifsc_code,
            country=current_user.country or "IN",
        )
        if not ok_bank:
            raise HTTPException(status_code=400, detail=bank_err)

    current_user.payout_bank_name = data.payout_bank_name
    current_user.payout_account_number = data.payout_account_number
    current_user.payout_ifsc_code = data.payout_ifsc_code
    current_user.payout_account_holder_name = data.payout_account_holder_name
    current_user.is_payout_setup_completed = True
    
    await db.flush()
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get("/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Self-service personal data export endpoint (GDPR Art. 20 / India DPDP Act 2023 Sec. 12).
    Returns machine-readable JSON containing all personal profile data, order history, and activity records.
    """
    from app.models.order import Order
    from app.models.download import Download
    from sqlalchemy.orm import selectinload

    order_stmt = select(Order).options(selectinload(Order.items)).where(Order.user_id == current_user.id)
    order_res = await db.execute(order_stmt)
    orders = order_res.scalars().all()

    dl_stmt = select(Download).where(Download.user_id == current_user.id)
    dl_res = await db.execute(dl_stmt)
    downloads = dl_res.scalars().all()

    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "id": str(current_user.id),
            "email": current_user.email,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "avatar_url": current_user.avatar_url,
            "bio": current_user.bio,
            "country": current_user.country,
            "currency": current_user.currency,
            "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            "ai_credits": current_user.ai_credits,
            "subscription_tier": current_user.subscription_tier,
            "created_at": current_user.created_at.isoformat() if hasattr(current_user, "created_at") and current_user.created_at else None,
        },
        "orders": [
            {
                "order_number": o.order_number,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "total": float(o.total),
                "currency": getattr(o, "currency", "USD"),
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": [
                    {
                        "template_id": str(item.template_id),
                        "price": float(item.price),
                        "license_type": getattr(item, "license_type", "regular"),
                    }
                    for item in o.items
                ],
            }
            for o in orders
        ],
        "downloads_count": len(downloads),
        "compliance_notice": "Data export prepared in compliance with GDPR Art. 20 and DPDP Act 2023.",
    }


@router.delete("/me")
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Self-service account deletion and personal data anonymization (GDPR Art. 17 / DPDP Act 2023 Sec. 12).
    Anonymizes identifying personal information while preserving financial/order records for statutory compliance.
    """
    user_id_str = str(current_user.id)
    anonymized_tag = uuid.uuid4().hex[:12]

    # Anonymize personal profile data
    current_user.email = f"anonymized_{anonymized_tag}@privacy.local"
    current_user.username = f"deleted_user_{anonymized_tag[:8]}"
    current_user.full_name = "Deleted User"
    current_user.avatar_url = None
    current_user.bio = None
    current_user.detected_ip = None
    current_user.hashed_password = None
    current_user.github_access_token = None
    current_user.google_id = None
    current_user.github_id = None
    current_user.facebook_id = None
    current_user.payout_account_number = None
    current_user.payout_bank_name = None
    current_user.payout_ifsc_code = None
    current_user.payout_account_holder_name = None
    current_user.is_payout_setup_completed = False
    current_user.is_active = False

    await db.flush()
    await db.commit()

    # Invalidate all active tokens immediately in Redis
    try:
        redis_client = await get_redis()
        revocation_ts = int(datetime.now(timezone.utc).timestamp())
        await redis_client.set(f"auth:revoked_before:{user_id_str}", str(revocation_ts), ex=30 * 86400)
    except Exception as e_rev:
        logger.warning(f"Failed to record token revocation on account deletion: {e_rev}")

    return {
        "status": "success",
        "message": "Your personal data has been permanently anonymized and your account has been closed.",
    }


