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
    assert data["payout_account_number"] == "1234567890"
    assert data["payout_ifsc_code"] == "CHAS0001234"
    assert data["payout_account_holder_name"] == "Test Seller"
    assert data["is_payout_setup_completed"] is True


@pytest.mark.asyncio
async def test_seller_create_template_without_payout(seller_client: AsyncClient, db: AsyncSession):
    # Seed a Category first so the request payload is valid
    category = Category(name="Portfolio", slug="portfolio")
    db.add(category)
    await db.flush()
    await db.commit()
    await db.refresh(category)

    # 1. Try to upload/create template without payout setup (should succeed now)
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
    response = await seller_client.post("/api/v1/templates", json=payload)
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


