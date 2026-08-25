import pytest
import time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.core.security import create_access_token, generate_file_signature
from app.core.redis import get_redis


@pytest.mark.asyncio
async def test_unauthenticated_requests_fail(client: AsyncClient):
    """Assert unauthenticated requests receive 401."""
    # Test GET profile /me
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401

    # Test file upload
    res = await client.post("/api/v1/files/upload")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_role_authorization_guards(client: AsyncClient, db: AsyncSession):
    """Verify that role based access controls are enforced."""
    # Seed a standard buyer user
    user = User(
        email="buyer1@gmail.com",
        username="buyer1",
        full_name="Buyer One",
        role=UserRole.BUYER,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id))
    client.headers["Authorization"] = f"Bearer {token}"

    # Try accessing seller/admin only route
    res = await client.post("/api/v1/templates/analyze-git", json={"git_url": "https://github.com/test/repo"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_otp_rate_limiting_and_attempts(client: AsyncClient, db: AsyncSession, fake_redis):
    """Verify OTP rate limits (429) and attempt bounds (invalidation)."""
    # 1. Register a user (triggers OTP generation)
    reg_payload = {
        "email": "anotherbuyer@gmail.com",
        "password": "StrongPassword123!",
        "role": "buyer"
    }
    res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200
    
    # 2. Try triggering OTP generation again immediately (should return 429)
    res2 = await client.post("/api/v1/auth/resend-otp", json={"email": "anotherbuyer@gmail.com"})
    assert res2.status_code == 429
    assert "Too many OTP requests" in res2.json()["detail"]

    # 3. Verify OTP: try 3 failed attempts
    verify_payload = {
        "email": "anotherbuyer@gmail.com",
        "otp": "111111"  # incorrect
    }
    
    # Attempt 1
    res_v1 = await client.post("/api/v1/auth/verify-otp", json=verify_payload)
    assert res_v1.status_code == 400
    
    # Attempt 2
    res_v2 = await client.post("/api/v1/auth/verify-otp", json=verify_payload)
    assert res_v2.status_code == 400

    # Attempt 3
    res_v3 = await client.post("/api/v1/auth/verify-otp", json=verify_payload)
    assert res_v3.status_code == 400

    # Attempt 4 (should state that maximum attempts are exceeded / OTP is invalidated)
    res_v4 = await client.post("/api/v1/auth/verify-otp", json=verify_payload)
    assert res_v4.status_code == 400
    assert "attempts exceeded" in res_v4.json()["detail"] or "expired" in res_v4.json()["detail"]


@pytest.mark.asyncio
async def test_file_upload_format_validation(auth_client: AsyncClient):
    """Verify uploads only accept allowed formats and validate using Pillow."""
    # Try uploading plain text as image
    files = {"file": ("test.png", b"not an image", "image/png")}
    res = await auth_client.post("/api/v1/files/upload", files=files)
    assert res.status_code == 400
    assert "not a valid image" in res.json()["detail"]


@pytest.mark.asyncio
async def test_signed_urls_file_download(auth_client: AsyncClient, client: AsyncClient, db: AsyncSession):
    """Assert file access requires valid JWT or valid signed URL."""
    from app.core.storage import storage
    from app.core.security import generate_file_signature
    import time
    
    zip_data = b"PK\x03\x04mock_zip_content"
    url = await storage.upload_file(
        db=db,
        file_content=zip_data,
        folder="uploads",
        original_filename="template.zip",
        content_type="application/zip",
    )
    file_id = url.split("/files/")[1]
    
    expires = int(time.time()) + 300
    signature = generate_file_signature(file_id, expires)
    signed_url = f"/api/v1/files/{file_id}?expires={expires}&signature={signature}"

    # 2. Try fetching file without auth and without signature (should fail)
    res_no_auth = await client.get(f"/api/v1/files/{file_id}")
    assert res_no_auth.status_code == 401

    # 3. Try fetching file with valid signature (should succeed)
    res_signed = await client.get(signed_url)
    assert res_signed.status_code == 200

    # 4. Try fetching file with expired/invalid signature (should fail)
    bad_signature_url = f"/api/v1/files/{file_id}?expires={int(time.time()) - 100}&signature=invalid"
    res_bad_sig = await client.get(bad_signature_url)
    assert res_bad_sig.status_code == 401


@pytest.mark.asyncio
async def test_zip_file_download_requires_signature(auth_client: AsyncClient, db: AsyncSession):
    """Assert that retrieving a ZIP file requires a valid signature and rejects regular authenticated users."""
    # 1. Store a mock ZIP file in storage
    from app.core.storage import storage
    zip_data = b"PK\x03\x04mock_zip_content"
    url = await storage.upload_file(
        db=db,
        file_content=zip_data,
        folder="uploads",
        original_filename="template.zip",
        content_type="application/zip",
    )
    file_id = url.split("/files/")[1]

    # 2. Try fetching the ZIP file with an authenticated user (but no signature) -> should be rejected (403)
    res_auth_no_sig = await auth_client.get(f"/api/v1/files/{file_id}")
    assert res_auth_no_sig.status_code == 403

    # 3. Try fetching with a valid signature -> should succeed (200)
    import time
    expires = int(time.time()) + 3600
    signature = generate_file_signature(file_id, expires)
    res_signed = await auth_client.get(f"/api/v1/files/{file_id}?expires={expires}&signature={signature}")
    assert res_signed.status_code == 200
    assert res_signed.content == zip_data


@pytest.mark.asyncio
async def test_company_email_seller_auto_assignment(client: AsyncClient, db: AsyncSession):
    """Verify that registering with a company email (e.g. name@company.com) auto-assigns seller role."""
    reg_payload = {
        "email": "alex@company.com",
        "password": "StrongPassword123!",
        "role": "buyer"  # Even if buyer is requested, company email should auto-switch to seller
    }
    res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "otp_required"

    # Check created user in DB
    from app.repositories.user_repo import UserRepository
    repo = UserRepository(db)
    user = await repo.get_by_email("alex@company.com")
    assert user is not None
    assert user.role == UserRole.SELLER


