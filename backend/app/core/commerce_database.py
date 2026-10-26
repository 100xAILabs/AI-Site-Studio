"""Isolated database for customer accounts and generated storefront commerce."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class CommerceBase(DeclarativeBase):
    """Metadata kept completely separate from the Studio control-plane models."""


commerce_engine = None
CommerceSessionLocal = None
if settings.COMMERCE_DATABASE_URL:
    commerce_engine = create_async_engine(
        settings.COMMERCE_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=120,
    )
    CommerceSessionLocal = async_sessionmaker(
        commerce_engine, class_=AsyncSession, expire_on_commit=False,
        autocommit=False, autoflush=False,
    )


async def get_commerce_db() -> AsyncGenerator[AsyncSession, None]:
    """Fail closed when an isolated commerce database has not been configured."""
    from fastapi import HTTPException, status

    if CommerceSessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Store accounts and orders are unavailable until a separate COMMERCE_DATABASE_URL is configured.",
        )
    async with CommerceSessionLocal() as session:
        yield session


async def init_commerce_db() -> None:
    """Create commerce tables in the separately configured commerce database."""
    if commerce_engine is None:
        return
    from app.models.commerce import (CommerceCustomer, CommerceNotificationSettings, CommerceOrder,
                                     CommerceOrderItem, CommerceProduct, CommerceSession)
    del CommerceCustomer, CommerceNotificationSettings, CommerceOrder, CommerceOrderItem, CommerceProduct, CommerceSession
    async with commerce_engine.begin() as connection:
        await connection.run_sync(CommerceBase.metadata.create_all)
