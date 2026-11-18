"""
Unit tests for template marketplace routes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.category import Category
from app.models.template import Template


@pytest.mark.asyncio
async def test_read_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_templates_empty(client: AsyncClient):
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_payout_setup_update(seller_client: AsyncClient):
    # 1. Update payout account details
    payload = {
        "payout_bank_name": "Chase Bank",
        "payout_account_number": "1234567890",
        "payout_ifsc_code": "CHAS0001234",
        "payout_account_holder_name": "Test Seller",
    }
    response = await seller_client.put("/api/v1/auth/payout-account", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["payout_bank_name"] == "Chase Bank"
    assert "7890" in data["payout_account_number"]
    assert data["payout_ifsc_code"] == "CHAS0001234"
    assert data["payout_account_holder_name"] == "Test Seller"
    assert data["is_payout_setup_completed"] is True


@pytest.mark.asyncio
async def test_admin_create_template(admin_client: AsyncClient, db: AsyncSession):
    # Seed a Category first so the request payload is valid
    category = Category(name="Portfolio", slug="portfolio")
    db.add(category)
    await db.flush()
    await db.commit()
    await db.refresh(category)

    # 1. Admin creates marketplace template
    payload = {
        "title": "Creative Portfolio Template",
        "slug": "creative-portfolio-template",
        "short_description": "Modern portfolio layout.",
        "thumbnail_url": "https://example.com/thumb.png",
        "description": "A beautiful modern website layout.",
        "price": 19.99,
        "category_id": str(category.id),
        "features": ["Responsive", "Framer motion animations"],
        "figma_link": "https://figma.com/file/123",
        "is_published": False,
    }
    response = await admin_client.post("/api/v1/templates", json=payload)
    assert response.status_code == 201
    assert response.json()["title"] == "Creative Portfolio Template"


@pytest.mark.asyncio
async def test_redis_caching_and_invalidation(client: AsyncClient, db: AsyncSession):
    """Verify Redis cache set, get, invalidation, and deterministic keys."""
    from app.core.redis import CacheKeys, cache_get, cache_set, cache_delete

    # 1. Test set and get
    test_key = "test:unit:cache_key"
    payload = {"status": "ok", "items": [1, 2, 3], "value": 42.5}
    await cache_set(test_key, payload, ttl=60)
    cached = await cache_get(test_key)
    assert cached is not None
    assert cached["status"] == "ok"
    assert cached["items"] == [1, 2, 3]

    # 2. Test deletion
    await cache_delete(test_key)
    assert await cache_get(test_key) is None

    # 3. Test CacheKeys determinism
    key1 = CacheKeys.search("landing page", "category:tech")
    key2 = CacheKeys.search("landing page", "category:tech")
    assert key1 == key2
    assert key1.startswith("search:")

    # 4. Test categories list caching
    res = await client.get("/api/v1/categories")
    assert res.status_code == 200
    # Second call should also succeed (cached)
    res2 = await client.get("/api/v1/categories")
    assert res2.status_code == 200


@pytest.mark.asyncio
async def test_storage_service_cloud_and_local_modes(db: AsyncSession):
    """Verify StorageService properties and default local PostgreSQL fallback."""
    from app.core.storage import storage

    # Default in test environment should be postgres fallback
    assert storage.bucket_name == "ai-site-studio"
    assert storage.public_url.endswith("/files")

    # Upload and verify retrieval via local DB fallback
    dummy_data = b"<!DOCTYPE html><html><body>Test</body></html>"
    file_url = await storage.upload_file(
        db=db,
        file_content=dummy_data,
        folder="test",
        original_filename="index.html",
        content_type="text/html",
    )
    assert file_url is not None
    assert "/files/" in file_url

    file_id = storage._parse_file_id(file_url)
    assert file_id is not None

    retrieved = await storage.get_file(db, file_id)
    assert retrieved is not None
    content, content_type, filename = retrieved
    assert content == dummy_data
    assert content_type == "text/html"
    assert filename == "index.html"

    # Clean up
    deleted = await storage.delete_file(db, file_url)
    assert deleted is True


@pytest.mark.asyncio
async def test_soft_delete_template_to_trash(admin_client: AsyncClient, client: AsyncClient, db: AsyncSession):
    """Verify that deleting a template soft-deletes it and excludes it from public catalog."""
    from app.models.category import Category
    from app.models.template import Template, TemplateStatus
    from sqlalchemy import select

    cat = Category(name="Agency", slug="agency-soft-del")
    db.add(cat)
    await db.flush()
    await db.commit()

    tmpl_payload = {
        "title": "Agency Soft Delete Test",
        "slug": "agency-soft-delete-test",
        "short_description": "Soft delete test description",
        "thumbnail_url": "https://example.com/agency.png",
        "description": "Full description",
        "price": 29.99,
        "category_id": str(cat.id),
        "is_published": True,
    }
    create_res = await admin_client.post("/api/v1/templates", json=tmpl_payload)
    assert create_res.status_code == 201
    tmpl_id = create_res.json()["id"]

    # Verify visible before delete
    get_res = await client.get("/api/v1/templates/agency-soft-delete-test")
    assert get_res.status_code == 200

    # Delete template
    del_res = await admin_client.delete(f"/api/v1/templates/{tmpl_id}")
    assert del_res.status_code == 204

    # Verify no longer visible in public endpoints
    get_res2 = await client.get("/api/v1/templates/agency-soft-delete-test")
    assert get_res2.status_code == 404

    # Verify record still exists in DB with is_deleted=True
    import uuid
    stmt = select(Template).where(Template.id == uuid.UUID(str(tmpl_id)))
    db_res = await db.execute(stmt)
    db_tmpl = db_res.scalar_one_or_none()
    assert db_tmpl is not None
    assert db_tmpl.is_deleted is True
    assert db_tmpl.deleted_at is not None


@pytest.mark.asyncio
async def test_user_trash_and_restore_lifecycle(seller_client: AsyncClient, auth_client: AsyncClient, admin_client: AsyncClient, db: AsyncSession):
    """Verify 7-day user trash recovery window, ownership check, and admin permanent delete."""
    import uuid
    from app.models.category import Category
    from app.models.template import Template, TemplateStatus, TemplateFramework, TemplateLicense
    from app.models.user import User
    from sqlalchemy import select

    cat = Category(name="Tech", slug="tech-trash-test")
    db.add(cat)
    await db.flush()
    await db.commit()

    # Get seller user from DB
    seller_user = (await db.execute(select(User).where(User.email == "testseller@gmail.com"))).scalar_one()

    # Seed template owned by seller
    tmpl = Template(
        title="Seller Trash Project",
        slug="seller-trash-project",
        short_description="Project for trash test",
        thumbnail_url="https://example.com/p.png",
        description="Full details",
        price=10.0,
        category_id=cat.id,
        seller_id=seller_user.id,
        framework=TemplateFramework.HTML,
        license_type=TemplateLicense.REGULAR,
        status=TemplateStatus.DRAFT,
        template_origin="studio",
        is_marketplace=False,
    )
    db.add(tmpl)
    await db.flush()
    await db.commit()
    await db.refresh(tmpl)
    tmpl_id = str(tmpl.id)

    # 1. Seller deletes their own template
    del_res = await seller_client.delete(f"/api/v1/templates/{tmpl_id}")
    assert del_res.status_code == 204

    # 2. Seller checks their trash
    trash_res = await seller_client.get("/api/v1/templates/trash")
    assert trash_res.status_code == 200
    trash_items = trash_res.json()
    assert any(item["id"] == tmpl_id for item in trash_items)
    item_in_trash = next(item for item in trash_items if item["id"] == tmpl_id)
    assert item_in_trash["days_left"] >= 6

    # 3. Another user cannot restore seller's trash
    unauth_restore = await auth_client.post(f"/api/v1/templates/{tmpl_id}/restore")
    assert unauth_restore.status_code == 403

    # 4. Admin checks admin trash (30-day window)
    admin_trash_res = await admin_client.get("/api/v1/admin/templates/trash")
    assert admin_trash_res.status_code == 200
    admin_trash_items = admin_trash_res.json()
    assert any(item["id"] == tmpl_id for item in admin_trash_items)

    # 5. Seller restores their template within 7 days
    restore_res = await seller_client.post(f"/api/v1/templates/{tmpl_id}/restore")
    assert restore_res.status_code == 200
    assert restore_res.json()["status"] == "success"

    # Verify it is no longer in trash
    trash_res2 = await seller_client.get("/api/v1/templates/trash")
    assert not any(item["id"] == tmpl_id for item in trash_res2.json())

    # 6. Delete again and permanently delete as admin
    await seller_client.delete(f"/api/v1/templates/{tmpl_id}")
    perm_del_res = await admin_client.delete(f"/api/v1/admin/templates/{tmpl_id}/permanent")
    assert perm_del_res.status_code == 200

    # Verify completely purged from DB
    stmt = select(Template).where(Template.id == uuid.UUID(tmpl_id))
    db_res = await db.execute(stmt)
    assert db_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_purge_custom_drafts_is_scoped(seller_client: AsyncClient, auth_client: AsyncClient, db: AsyncSession):
    """Verify that purge-custom-drafts only affects the calling user's drafts, not other users."""
    import uuid
    from app.models.category import Category
    from app.models.template import Template, TemplateStatus, TemplateFramework, TemplateLicense
    from app.models.user import User
    from sqlalchemy import select

    cat = Category(name="DraftsCat", slug="drafts-cat")
    db.add(cat)
    await db.flush()
    await db.commit()

    seller_user = (await db.execute(select(User).where(User.email == "testseller@gmail.com"))).scalar_one()

    # Create draft for seller
    d1 = Template(
        title="Customized Seller Draft 1",
        slug="seller-draft-1-custom-123",
        short_description="draft",
        thumbnail_url="https://example.com/d1.png",
        description="draft desc",
        price=0.0,
        category_id=cat.id,
        seller_id=seller_user.id,
        framework=TemplateFramework.HTML,
        license_type=TemplateLicense.REGULAR,
        status=TemplateStatus.DRAFT,
        template_origin="custom_draft",
        is_marketplace=False,
    )
    db.add(d1)
    await db.flush()
    await db.commit()
    await db.refresh(d1)
    d1_id = d1.id

    # Other user calls purge-custom-drafts
    purge_res = await auth_client.post("/api/v1/templates/purge-custom-drafts")
    assert purge_res.status_code == 200

    # Seller draft 1 must NOT be touched because it belongs to seller
    stmt = select(Template).where(Template.id == d1_id)
    d1_db = (await db.execute(stmt)).scalar_one_or_none()
    assert d1_db is not None
    assert d1_db.is_deleted is False

    # Now seller calls purge-custom-drafts
    seller_purge = await seller_client.post("/api/v1/templates/purge-custom-drafts")
    assert seller_purge.status_code == 200
    assert seller_purge.json()["deleted_count"] >= 1

    # Verify seller draft 1 is now soft-deleted
    await db.refresh(d1_db)
    assert d1_db.is_deleted is True





