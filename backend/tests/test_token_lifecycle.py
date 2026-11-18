"""
Tests for JWT and session token lifecycle hardening (F-21).
Enforces query-parameter rejection, refresh-token separation, token versioning (logout-all / password reset),
OAuth code exchange with session binding, and zero tokens in URLs.
"""

import uuid
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User, UserRole
from tests.conftest import FakeRedis


@pytest.mark.asyncio
async def test_query_token_ignored(client: AsyncClient, db: AsyncSession):
    """
    Query parameter ?token= must never authenticate a caller.
    Calling /api/v1/files/<id>?token=<valid_token> returns 401 or 404, never authorized 200.
    """
    user = User(
        email="query_token_victim@example.com",
        username="query_victim",
        full_name="Query Victim",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id), role="buyer", tv=user.token_version)
    fake_file_id = str(uuid.uuid4())

    # Passing token via query parameter should be ignored
    res = await client.get(f"/api/v1/files/{fake_file_id}?token={token}")
    assert res.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access(client: AsyncClient, db: AsyncSession):
    """A refresh token passed as Bearer on protected endpoints (like /api/v1/auth/me) must return 401."""
    user = User(
        email="refresh_as_access@example.com",
        username="ref_acc_user",
        full_name="Refresh User",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    ref_token = create_refresh_token(subject=str(user.id), tv=user.token_version)

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ref_token}"})
    assert res.status_code == 401
    assert "token required" in res.json()["detail"].lower() or "session revoked" in res.json()["detail"].lower() or "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_password_reset_revokes(client: AsyncClient, db: AsyncSession, fake_redis: FakeRedis):
    """
    Resetting password increments token_version and immediately revokes all prior tokens.
    """
    import hashlib
    user = User(
        email="reset_revocation_test@example.com",
        username="reset_user",
        full_name="Reset User",
        role=UserRole.BUYER,
        hashed_password=hash_password("OldP@ssword123!"),
        is_active=True,
        is_email_verified=True,
        token_version=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    old_token = create_access_token(subject=str(user.id), role="buyer", tv=0)

    # Verify old token works before reset
    res_before = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert res_before.status_code == 200

    # Seed reset OTP in fake_redis
    otp_code = "123456"
    otp_hash = hashlib.sha256(otp_code.encode("utf-8")).hexdigest()
    await fake_redis.set(f"otp:code:reset_password:{user.email}", otp_hash)

    # Perform password reset
    reset_res = await client.post("/api/v1/auth/reset-password", json={
        "email": user.email,
        "otp": otp_code,
        "new_password": "NewStrongP@ssword456!",
    })
    assert reset_res.status_code == 200

    # Old token MUST now be revoked and return 401
    res_after = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert res_after.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes(client: AsyncClient, db: AsyncSession):
    """POST /auth/logout-all increments token_version, revoking all active sessions."""
    user = User(
        email="logout_all_test@example.com",
        username="logout_user",
        full_name="Logout User",
        role=UserRole.BUYER,
        is_active=True,
        token_version=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id), role="buyer", tv=0)

    # Valid before logout-all
    res1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200

    # Call logout-all
    logout_res = await client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Old token must now be revoked
    res2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_exchange_requires_session_binding(client: AsyncClient, db: AsyncSession, fake_redis: FakeRedis):
    """
    Exchange requires the one-time code to match the session cookie that originated it.
    A fresh client without the matching session gets 400, and the code is immediately burned.
    """
    code = "test_code_abc_123"
    await fake_redis.set(f"oauth_code:{code}", str(uuid.uuid4()))

    # Request from fresh client (no session)
    res = await client.post("/api/v1/auth/exchange", json={"code": code})
    assert res.status_code == 400

    # The code must remain unusable afterwards
    val = await fake_redis.get(f"oauth_code:{code}")
    assert val is None


@pytest.mark.asyncio
async def test_oauth_callback_has_no_token_in_url(client: AsyncClient, db: AsyncSession, monkeypatch):
    """
    OAuth callback must redirect to frontend with code= and NEVER with token= in the URL.
    """
    from app.api.v1.routes.auth import oauth

    user = User(
        email="oauth_url_leak_test@example.com",
        username="oauth_user_clean",
        full_name="Clean OAuth User",
        role=UserRole.BUYER,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    class MockOAuthClient:
        async def authorize_access_token(self, request):
            return {"access_token": "mock_google_access_token"}

        async def parse_id_token(self, request, token):
            return {
                "sub": "google_123456",
                "email": user.email,
                "email_verified": True,
                "name": "Clean OAuth User",
                "picture": "https://example.com/avatar.jpg",
            }

    monkeypatch.setattr(oauth, "create_client", lambda provider: MockOAuthClient())

    res = await client.get("/api/v1/auth/google/callback", follow_redirects=False)
    assert res.status_code in (302, 307)
    loc = res.headers.get("location", "")

    # MUST contain code=
    assert "code=" in loc
    # MUST NOT contain token=
    assert "token=" not in loc


@pytest.mark.asyncio
async def test_github_login_rejects_token_param(client: AsyncClient):
    """GET /api/v1/auth/github/login?token=x without session returns 403."""
    res = await client.get("/api/v1/auth/github/login?token=some_forged_jwt")
    assert res.status_code == 403
