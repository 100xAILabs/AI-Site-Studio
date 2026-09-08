"""
Auth routes — OAuth with Google and Facebook.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth, OAuthError

from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserResponse, PayoutSetupRequest

router = APIRouter()

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


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
import datetime

import asyncio
import smtplib
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

def send_smtp_email_sync(to_email: str, subject: str, body: str):
    # 1. Skip if test environment or email delivery explicitly disabled
    is_test_env = (
        getattr(settings, "ENVIRONMENT", "").lower() in ("test", "testing")
        or os.getenv("ENVIRONMENT", "").lower() in ("test", "testing")
        or not getattr(settings, "ENABLE_EMAIL_DELIVERY", True)
    )
    if is_test_env:
        print(f"\n[TEST SIMULATION] Real SMTP skipped for {to_email} (Test/Disabled Mode). Subject: {subject}\n")
        return

    # 2. Skip placeholder / dummy domains to prevent delivery delay & bounce notices from mail providers
    if is_dummy_or_test_email(to_email):
        print(f"\n[SIMULATION] Email to placeholder domain ({to_email}) skipped to prevent delivery bounce. Subject: {subject}\n")
        return

    # 3. Check credentials
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"\n[SIMULATION] SMTP credentials not configured. Email to {to_email} not sent. Content: {body}\n")
        return

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
        print(f"\n[EMAIL SENT] OTP successfully sent to {to_email}\n")
    except Exception as e:
        print(f"\n[EMAIL ERROR] Failed to send email via SMTP to {to_email}: {e}\n")

async def send_otp_email(to_email: str, otp: str):
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
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, send_smtp_email_sync, to_email, subject, body)
    except Exception as e:
        print(f"Error sending email in executor: {e}")

import hashlib
from app.core.redis import get_redis

_active_background_tasks = set()

async def generate_otp(email: str, purpose: str) -> str:
    email_key = email.lower().strip()
    redis_client = await get_redis()
    
    # 1. Rate limiting: Check if an OTP was generated within the last 60 seconds
    rate_key = f"otp:rate:{purpose}:{email_key}"
    if await redis_client.get(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait 60 seconds before trying again."
        )

    # 2. Generate random 6-digit code
    otp = f"{random.randint(100000, 999999)}"
    hashed_otp = hashlib.sha256(otp.encode("utf-8")).hexdigest()

    # 3. Store hashed OTP with 5 minute expiration, and verification attempts counter (max 3)
    db_key = f"otp:code:{purpose}:{email_key}"
    await redis_client.set(db_key, hashed_otp, ex=300)
    
    attempts_key = f"otp:attempts:{purpose}:{email_key}"
    await redis_client.set(attempts_key, "0", ex=300)

    # Set rate limiter for 60 seconds
    await redis_client.set(rate_key, "1", ex=60)
    
    # Store strong reference to background task to prevent garbage collection
    task = asyncio.create_task(send_otp_email(email, otp))
    _active_background_tasks.add(task)
    task.add_done_callback(_active_background_tasks.discard)
    
    return otp


oauth = OAuth()
if settings.GOOGLE_CLIENT_ID:
    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        client_kwargs={'scope': 'openid email profile'},
    )

if settings.FACEBOOK_CLIENT_ID:
    oauth.register(
        name='facebook',
        api_base_url='https://graph.facebook.com/v19.0/',
        access_token_url='https://graph.facebook.com/v19.0/oauth/access_token',
        authorize_url='https://www.facebook.com/v19.0/dialog/oauth',
        client_id=settings.FACEBOOK_CLIENT_ID,
        client_secret=settings.FACEBOOK_CLIENT_SECRET,
        client_kwargs={'scope': 'email public_profile'},
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
    token: Optional[str] = None
):
    """Redirects to the OAuth provider."""
    # github is allowed only when 'token' param is present (connect-to-existing-user flow)
    # It should NOT be a standalone login method — the sign-in page only shows Google.
    if provider not in ["google", "github"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
    if provider == "github" and not token:
        raise HTTPException(status_code=403, detail="GitHub OAuth is only available for connecting to an existing account. Please sign in with Google first.")
    
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth is not configured")
        
    redirect_uri = request.url_for('auth_callback', provider=provider)
    
    request.session['auth_role'] = role
    if redirect:
        request.session['auth_redirect'] = redirect
        
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                request.session['auth_current_user_id'] = user_id
        except Exception:
            pass
            
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def auth_callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Handles OAuth callback and creates/updates the user."""
    if provider not in ["google", "github"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
        
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=500, detail=f"{provider} OAuth is not configured")
    try:
        if "development" in settings.ENVIRONMENT.lower():
            # Avoid mismatching_state errors in local development due to localhost/127.0.0.1 session cookie mismatches
            token = await client.authorize_access_token(request, check_state=False)
        else:
            token = await client.authorize_access_token(request)

    except OAuthError as error:

        import traceback
        print("OAuthError occurred during token exchange:")
        print(f"Error: {error.error}")
        print(f"Description: {getattr(error, 'description', 'No description')}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"OAuth error: {error.error}")
        
    if provider == "google":
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await client.parse_id_token(request, token)
        email = user_info.get("email")
        provider_id = user_info.get("sub")
        full_name = user_info.get("name")
        avatar_url = user_info.get("picture")
    elif provider == "facebook":
        resp = await client.get('me?fields=id,name,email,picture')
        user_info = resp.json()
        email = user_info.get("email")
        provider_id = user_info.get("id")
        full_name = user_info.get("name")
        avatar_url = user_info.get("picture", {}).get("data", {}).get("url")
        if not email:
            # Facebook might not return an email if the user didn't allow it, but we need it.
            email = f"{provider_id}@facebook.placeholder.com"
    elif provider == "github":
        access_token_val = token.get("access_token")
        resp = await client.get('user', token=token)
        user_info = resp.json()
        email_resp = await client.get('user/emails', token=token)
        emails = email_resp.json()
        email = None
        if isinstance(emails, list):
            for em in emails:
                if em.get("primary") and em.get("verified"):
                    email = em.get("email")
                    break
            if not email and len(emails) > 0:
                email = emails[0].get("email")
        if not email:
            email = user_info.get("email") or f"{user_info.get('login')}@github.placeholder.com"
            
        provider_id = str(user_info.get("id"))
        full_name = user_info.get("name") or user_info.get("login")
        avatar_url = user_info.get("avatar_url")

    if not email or not provider_id:
        raise HTTPException(status_code=400, detail="Could not retrieve email or ID from provider")

    current_user_id = request.session.pop('auth_current_user_id', None)
    
    repo = UserRepository(db)
    if current_user_id:
        from uuid import UUID
        user = await repo.get_by_id(UUID(current_user_id))
        if not user:
            raise HTTPException(status_code=404, detail="Logged in user not found")
        
        # Link GitHub details
        if provider == "github":
            user.github_id = provider_id
            user.github_access_token = access_token_val
        elif provider == "google":
            user.google_id = provider_id
        elif provider == "facebook":
            user.facebook_id = provider_id
            
        from app.models.user import UserRole
        if is_company_email(email):
            user.role = UserRole.SELLER

        await db.flush()
        await db.refresh(user)
    else:
        role_str = request.session.get('auth_role', 'buyer')
        if is_company_email(email):
            role_str = "seller"

        print(f"\n[OAUTH AUTH] Provider: {provider.upper()} | Email: {email} | Company Email: {is_company_email(email)} | Assigned Role: {role_str}\n", flush=True)

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

    access_token = create_access_token(subject=str(user.id))
    
    redirect_path = request.session.pop('auth_redirect', None)
    # If this was a GitHub connect operation, send the user back to the upload tab
    if not redirect_path and current_user_id and provider == "github":
        redirect_path = "/dashboard?tab=seller-upload"
    elif not redirect_path:
        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        redirect_path = "/dashboard" if user_role_str.lower() == "seller" else "/"

    from urllib.parse import quote_plus
    redirect_url = f"{settings.FRONTEND_URL}/?token={access_token}&redirect={quote_plus(redirect_path)}"
    return RedirectResponse(url=redirect_url)


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
        
    # Auto-assign seller role if email is a company email (e.g. name@company.com)
    if is_company_email(email):
        role = "seller"

    print(f"\n[USER REGISTER] Email: {email} | Company Email: {is_company_email(email)} | Final Role: {role}\n", flush=True)

    if role.lower() == "seller" and not is_company_email(email):
        raise HTTPException(
            status_code=400,
            detail="Sellers must register with a company email address (not public domains like Gmail)."
        )
        
    if role.lower() == "buyer" and not email.lower().endswith("@gmail.com"):
        raise HTTPException(
            status_code=400,
            detail="Buyers must register with a Gmail address (ending in @gmail.com)."
        )
        
    if not is_strong_password(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )
        
    repo = UserRepository(db)
    existing = await repo.get_by_email(email)
    if existing:
        if existing.is_email_verified:
            # Determine HOW this account was originally created
            if existing.google_id and not existing.hashed_password:
                signup_method = "google"
                detail = "An account with this email already exists. It was created using Google Sign-In. Please click 'Continue with Google' to sign in."
            elif existing.facebook_id and not existing.hashed_password:
                signup_method = "facebook"
                detail = "An account with this email already exists. It was created using Facebook. Please sign in with Facebook."
            elif existing.hashed_password:
                signup_method = "email"
                detail = "An account with this email already exists. Please sign in with your email and password."
            else:
                signup_method = "oauth"
                detail = "An account with this email already exists. Please sign in using the method you originally used."
            raise HTTPException(
                status_code=409,
                detail=detail,
                headers={"X-Signup-Method": signup_method}
            )
        else:
            await generate_otp(email, "verify_email")
            return {
                "status": "otp_required",
                "email": email,
                "message": "This email has already registered but is not verified. A new OTP has been sent."
            }
        
    from app.core.security import hash_password
    from app.models.user import UserRole
    base_username = email.split("@")[0]
    unique_username = await repo.get_unique_username(base_username)
    user = User(
        email=email,
        username=unique_username,
        hashed_password=hash_password(password),
        role=UserRole.SELLER if role.lower() == "seller" else UserRole.BUYER,
        is_email_verified=False
    )
    db.add(user)
    await db.flush()
    await db.commit()
    
    await generate_otp(email, "verify_email")
    return {
        "status": "otp_required",
        "email": email,
        "message": "Registration successful! An OTP has been sent to your email."
    }


@router.post("/login")
async def login_email(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")

        repo = UserRepository(db)
        user = await repo.get_by_email(email)
        if not user or not user.hashed_password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        from app.core.security import verify_password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        if not user.is_email_verified:
            await generate_otp(user.email, "verify_email")
            return {
                "status": "otp_required",
                "email": user.email,
                "message": "Your email is not verified yet. An OTP has been sent to your email."
            }
            
        if is_company_email(user.email) and user.role.value.lower() == "buyer":
            from app.models.user import UserRole
            user.role = UserRole.SELLER
            await db.flush()
            await db.commit()
            await db.refresh(user)

        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        print(f"\n[USER LOGIN] Email: {user.email} | Active Role: {user_role_str}\n", flush=True)

        from app.services.location_service import update_user_location
        try:
            await update_user_location(user, db, request=request)
        except Exception as err:
            print(f"Location update notice on login: {err}")

        access_token = create_access_token(subject=str(user.id))
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        try:
            with open("login_error.log", "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        print(f"[LOGIN ERROR] {tb}", flush=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/verify-otp")
async def verify_otp(
    request: Request,
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

    # Check verification attempts limit
    attempts_str = await redis_client.get(attempts_key) or "0"
    attempts = int(attempts_str)
    if attempts >= 3:
        await redis_client.delete(db_key)
        await redis_client.delete(attempts_key)
        raise HTTPException(status_code=400, detail="Max verification attempts exceeded. Please request a new OTP.")

    # Compare hashed code
    provided_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
    if stored_hash != provided_hash:
        # Increment attempt counter
        await redis_client.incr(attempts_key)
        raise HTTPException(status_code=400, detail="Invalid OTP code.")
        
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    user.is_email_verified = True
    if is_company_email(user.email) and user.role.value.lower() == "buyer":
        from app.models.user import UserRole
        user.role = UserRole.SELLER
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
        print(f"Location update notice on OTP verify: {err}")
    
    access_token = create_access_token(subject=str(user.id))
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
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email is already verified. Please sign in.")
        
    await generate_otp(email, "verify_email")
    return {"message": "A new OTP has been sent."}


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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address."
        )
    
    if not user.hashed_password:
        # This user signed up via OAuth only — can't reset a password they never set
        raise HTTPException(
            status_code=400,
            detail="This account was created using social login (Google). Please sign in with Google instead."
        )
    
    await generate_otp(email, "reset_password")
    return {"message": "A password reset code has been sent to your email."}


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
        
    attempts_str = await redis_client.get(attempts_key) or "0"
    attempts = int(attempts_str)
    if attempts >= 3:
        await redis_client.delete(db_key)
        await redis_client.delete(attempts_key)
        raise HTTPException(status_code=400, detail="Max reset attempts exceeded. Please request a new code.")

    provided_hash = hashlib.sha256(otp.encode("utf-8")).hexdigest()
    if stored_hash != provided_hash:
        await redis_client.incr(attempts_key)
        raise HTTPException(status_code=400, detail="Invalid reset code.")
    
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
    
    from app.core.security import hash_password
    user.hashed_password = hash_password(new_password)
    user.is_email_verified = True  # Implicitly verify email since they proved ownership via OTP
    await db.flush()
    await db.commit()
    await db.refresh(user)
    
    # Clean up OTP keys in redis
    await redis_client.delete(db_key)
    await redis_client.delete(attempts_key)
    
    return {"message": "Password has been reset successfully. You can now sign in with your new password."}


@router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    from app.models.user import UserRole
    user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if is_company_email(current_user.email) and user_role_val.lower() == "buyer":
        current_user.role = UserRole.SELLER
        await db.flush()
        await db.commit()
        await db.refresh(current_user)
        user_role_val = "seller"

    # Auto-detect location & currency if missing
    if not current_user.country or not current_user.currency or not current_user.country_code:
        from app.services.location_service import update_user_location
        try:
            await update_user_location(current_user, db, request=request)
        except Exception as err:
            print(f"Location detection notice in /me: {err}")

    print(f"\n[PROFILE FETCH] User: {current_user.email} | Role: {user_role_val.upper()} | Location: {current_user.country} ({current_user.currency})\n", flush=True)
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
async def update_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """Update the currently authenticated user's profile."""
    data = await request.json()
    
    from app.models.user import UserRole
    if "role" in data and data["role"] == "seller":
        current_user.role = UserRole.SELLER
    elif is_company_email(current_user.email) and current_user.role == UserRole.BUYER:
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
    current_user.payout_bank_name = data.payout_bank_name
    current_user.payout_account_number = data.payout_account_number
    current_user.payout_ifsc_code = data.payout_ifsc_code
    current_user.payout_account_holder_name = data.payout_account_holder_name
    current_user.is_payout_setup_completed = True
    
    await db.flush()
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)

