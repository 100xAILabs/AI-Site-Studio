"""
FastAPI dependency injection providers.

Provides: database sessions, current user extraction, role guards.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current authenticated user from JWT.

    Raises:
        401 if token is missing or invalid
        404 if user not found in database
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token format.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check session revocation (e.g. after password reset or global logout)
    try:
        from app.core.redis import get_redis_client
        redis_c = await get_redis_client()
        if redis_c:
            revoked_before = await redis_c.get(f"auth:revoked_before:{user_id}")
            if revoked_before:
                iat_val = payload.get("iat")
                if isinstance(iat_val, (int, float)) and iat_val < int(revoked_before):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session has been revoked. Please sign in again.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
    except HTTPException:
        raise
    except Exception:
        pass

    repo = UserRepository(db)
    user = await repo.get_by_id(user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deleted.",
        )
    # Authentication is a read-only lookup. End its transaction before a request
    # performs long-running AI generation so its pooled DB connection is released.
    await db.commit()
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
        )
    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as get_current_user but returns None instead of raising for public routes."""
    if credentials:
        try:
            return await get_current_user(credentials=credentials, db=db)
        except HTTPException:
            pass

    return None


def require_role(*roles: UserRole):
    """Dependency factory that guards routes by role."""

    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to roles: {[r.value for r in roles]}",
            )
        return current_user

    return _check_role


# Convenience role guards
require_admin = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
require_super_admin = require_role(UserRole.SUPER_ADMIN)


async def require_creator_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces active Extreme Plan subscription or Admin privilege for creator studio publishing."""
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if is_admin:
        return current_user
    if current_user.can_retail_templates or current_user.is_extreme_subscriber:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Selling website templates is an exclusive privilege of the Extreme Plan ($50/mo). Please upgrade to access Creator Studio publishing.",
    )


async def require_seller_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allows Admin, existing Sellers, and active Extreme plan creators."""
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if is_admin:
        return current_user
    if current_user.role == UserRole.SELLER or current_user.can_retail_templates or current_user.is_extreme_subscriber:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Creator Studio privileges require an active Extreme Plan subscription.",
    )
