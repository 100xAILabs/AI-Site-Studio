import asyncio
import os
from typing import AsyncGenerator, Optional

# Enforce test environment at the top
os.environ["ENVIRONMENT"] = "test"

import pytest

class FakeRedis:
    """In-memory Redis mock for tests."""
    def __init__(self):
        self.store = {}

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int = None) -> None:
        self.store[key] = str(value)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def incr(self, key: str) -> int:
        val = int(self.store.get(key, "0")) + 1
        self.store[key] = str(val)
        return val

global_fake_redis = FakeRedis()

async def mock_get_redis(*args, **kwargs):
    return global_fake_redis

# Override redis clients at the module level before any app/route imports
import app.core.redis
app.core.redis.get_redis = mock_get_redis
app.core.redis.get_redis_client = mock_get_redis

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.core.redis import get_redis
from app.core.security import create_access_token
from app.models.user import User, UserRole

# Use sqlite in memory for fast testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)



@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    """Create and drop all database tables per test to ensure total isolation."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def fake_redis() -> FakeRedis:
    global_fake_redis.store.clear()
    return global_fake_redis



@pytest.fixture
async def client(db: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(db: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """Fixture that returns a client authenticated as a standard buyer."""
    # Seed a standard verified user
    user = User(
        email="testbuyer@gmail.com",
        username="testbuyer",
        full_name="Test Buyer",
        role=UserRole.BUYER,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id))
    
    async def override_get_db():
        yield db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(db: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """Fixture that returns a client authenticated as a super admin."""
    # Seed a super admin user
    user = User(
        email="testadmin@aisitestudio.com",
        username="testadmin",
        full_name="Test Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id))
    
    async def override_get_db():
        yield db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seller_client(db: AsyncSession, fake_redis: FakeRedis) -> AsyncGenerator[AsyncClient, None]:
    """Fixture that returns a client authenticated as a seller."""
    user = User(
        email="testseller@gmail.com",
        username="testseller",
        full_name="Test Seller",
        role=UserRole.SELLER,
        is_active=True,
        is_email_verified=True,
        is_payout_setup_completed=False,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id))
    
    async def override_get_db():
        yield db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as ac:
        yield ac
    app.dependency_overrides.clear()


