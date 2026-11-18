"""
Security utilities: JWT creation/verification and Clerk token validation.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

import bcrypt


# ── JWT Helpers ───────────────────────────────────────────────────────────────


def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
    role: str = "buyer",
    tv: int = 0,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "role": role,
        "tv": tv,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str | Any, tv: int = 0) -> str:
    """Create a signed JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "tv": tv,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Raises:
        JWTError: if token is invalid or expired
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    try:
        passwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(passwd_bytes, hashed_bytes)
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    passwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passwd_bytes, salt)
    return hashed.decode('utf-8')


# ── OAuth Token Encryption & Key Rotation ─────────────────────────────────────
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a URL-safe 32-byte key from a secret key using PBKDF2."""
    salt = b"ai_site_studio_salt_123"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    derived = kdf.derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def encrypt_oauth_token(token: str) -> str:
    """Encrypt an OAuth token using the current SECRET_KEY."""
    if not token:
        return ""
    key = _derive_fernet_key(settings.SECRET_KEY)
    f = Fernet(key)
    encrypted = f.encrypt(token.encode("utf-8"))
    return f"v1:{encrypted.decode('utf-8')}"


def decrypt_oauth_token(encrypted_token: str) -> str:
    """Decrypt an OAuth token, checking the current SECRET_KEY and any OLD_SECRET_KEYS."""
    if not encrypted_token:
        return ""
    if not encrypted_token.startswith("v1:"):
        # Legacy/unencrypted format
        return encrypted_token

    raw_encrypted = encrypted_token[3:]
    keys_to_try = [settings.SECRET_KEY]
    if settings.OLD_SECRET_KEYS:
        keys_to_try.extend([k.strip() for k in settings.OLD_SECRET_KEYS.split(",") if k.strip()])

    for secret in keys_to_try:
        try:
            key = _derive_fernet_key(secret)
            f = Fernet(key)
            return f.decrypt(raw_encrypted.encode("utf-8")).decode("utf-8")
        except Exception:
            continue
    raise ValueError("Failed to decrypt OAuth token with any configured secret keys.")


from sqlalchemy.types import TypeDecorator, Text

class EncryptedText(TypeDecorator):
    """Transparently encrypts sensitive database text fields with Fernet (v1: prefix)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not value:
            return ""
        return encrypt_oauth_token(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not value:
            return ""
        try:
            return decrypt_oauth_token(str(value))
        except Exception:
            return value


async def authenticate_token(db, token: str, expected_type: str = "access"):
    """Unified token authentication verifying type, expiry, token_version, and user status."""
    from app.repositories.user_repo import UserRepository
    from uuid import UUID
    from jose import JWTError
    from fastapi import HTTPException, status
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{expected_type.title()} token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_uuid = UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = await UserRepository(db).get_by_id(user_uuid)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if payload.get("tv") is None or payload.get("tv") != getattr(user, "token_version", 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user


# ── HMAC URL Signing ─────────────────────────────────────────────────────────
import hmac


def generate_file_signature(file_id: str, expires: int, edition: Optional[str] = None) -> str:
    """Generate an HMAC signature for a specific file access URL, optionally binding the edition."""
    msg_str = f"{file_id}:{expires}:{edition}" if edition else f"{file_id}:{expires}"
    message = msg_str.encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


def verify_file_signature(file_id: str, expires: int, signature: str, edition: Optional[str] = None) -> bool:
    """Verify an HMAC signature for a file URL."""
    # Check expiry time (unix timestamp)
    if datetime.now(timezone.utc).timestamp() > expires:
        return False
    
    # Check with edition if provided
    if edition:
        expected_with_edition = generate_file_signature(file_id, expires, edition)
        if hmac.compare_digest(expected_with_edition, signature):
            return True
    
    expected = generate_file_signature(file_id, expires)
    return hmac.compare_digest(expected, signature)


def make_preview_token(template_id: str, clean: bool = False, ttl: int = 3600) -> str:
    """Generate an HMAC capability token for private/custom preview access."""
    exp = int(datetime.now(timezone.utc).timestamp()) + ttl
    msg = f"preview:{template_id}:{int(clean)}:{exp}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{int(clean)}.{sig}"


def check_preview_token(template_id: str, token: str) -> Optional[bool]:
    """Verify preview capability token. Returns clean flag (True/False) if valid, None if invalid or expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        exp_s, clean_s, sig = parts
        if int(exp_s) < int(datetime.now(timezone.utc).timestamp()):
            return None
        msg = f"preview:{template_id}:{clean_s}:{exp_s}"
        expected = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected, sig):
            return None
        return bool(int(clean_s))
    except Exception:
        return None



