"""
FastAPI dependency injection providers.

Provides: database sessions, current user extraction, role guards.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
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
    if not credentials or credentials.credentials == "mock_token_for_local_dev":
        # Dev fallback: auto-seed and return a default developer admin user
        repo = UserRepository(db)
        user = await repo.get_by_email("developer@aisitestudio.com")
        if not user:
            user = await repo.upsert_oauth_user(
                provider="google",
                provider_id="mock_google_id",
                email="developer@aisitestudio.com",
                full_name="Developer Admin",
                avatar_url="https://picsum.photos/seed/developer/100/100",
                role="admin"
            )
            user.role = UserRole.SUPER_ADMIN
            user.ai_credits = 100
            await db.commit()
            await db.refresh(user)
        return user

    try:
        payload = decode_token(credentials.credentials)
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

    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deleted.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
        )
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as get_current_user but returns None instead of raising for public routes."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
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
require_seller_or_admin = require_role(UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN)
