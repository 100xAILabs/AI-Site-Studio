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

    from app.core.security import authenticate_token
    user = await authenticate_token(db, credentials.credentials, "access")
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
    """Allows Admin and active Extreme plan creators only (no standalone seller role)."""
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if is_admin:
        return current_user
    if current_user.can_retail_templates or current_user.is_extreme_subscriber:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Template retailing is an exclusive privilege for Extreme Plan subscribers.",
    )
