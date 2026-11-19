"""
Tests for Extreme Plan retailing requirements:
- Only Extreme Plan users can retail website templates.
- Only Site Studio AI-generated websites (origin 'studio' or 'custom_draft') can be retailed.
- Non-extreme users are forbidden (403).
- Manual uploads cannot be retailed (400).
- Users can only retail templates they own (403).
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_retail_enforcement_matrix(client: AsyncClient, db: AsyncSession):
    # 1. Create a category
    category = Category(
        name=f"Retail Cat {uuid.uuid4().hex[:6]}",
        slug=f"retail-cat-{uuid.uuid4().hex[:6]}",
        description="Category for testing retailing",
    )
    db.add(category)
    await db.flush()

    # 2. Create standard (free) user
    free_user = User(
        email=f"free_{uuid.uuid4().hex[:6]}@example.com",
        username=f"freeuser_{uuid.uuid4().hex[:6]}",
        hashed_password="testpasshash",
        role=UserRole.USER,
        subscription_tier="free",
        is_active=True,
    )
    db.add(free_user)

    # 3. Create extreme subscriber user
    extreme_user = User(
        email=f"extreme_{uuid.uuid4().hex[:6]}@example.com",
        username=f"extreme_{uuid.uuid4().hex[:6]}",
        hashed_password="testpasshash",
        role=UserRole.USER,
        subscription_tier="extreme",
        is_active=True,
        creator_store_slug=f"store-{uuid.uuid4().hex[:6]}",
        creator_brand_name="Extreme Studio",
    )
    db.add(extreme_user)
    await db.flush()

    # 4. Create an AI-generated template owned by extreme user
    generated_template = Template(
        title="Modern SaaS AI Generator",
        slug=f"modern-saas-{uuid.uuid4().hex[:8]}",
        short_description="A generated SaaS template for testing",
        description="Full rich description for SaaS AI Generator template testing.",
        thumbnail_url="https://example.com/thumb1.png",
        price=0,
        is_free=True,
        seller_id=extreme_user.id,
        category_id=category.id,
        status=TemplateStatus.DRAFT,
        template_origin="studio",
        tags=["studio-project", "ai-generated", "saas"],
    )
    db.add(generated_template)

    # 5. Create a manual upload template owned by extreme user
    manual_template = Template(
        title="Manual Upload ZIP",
        slug=f"manual-upload-{uuid.uuid4().hex[:8]}",
        short_description="A manual zip template for testing",
        description="Full rich description for manual zip template testing.",
        thumbnail_url="https://example.com/thumb2.png",
        price=0,
        is_free=True,
        seller_id=extreme_user.id,
        category_id=category.id,
        status=TemplateStatus.DRAFT,
        template_origin="manual_zip",
        tags=["uploaded", "zip"],
    )
    db.add(manual_template)

    # 6. Create a template owned by another user
    other_template = Template(
        title="Other User Template",
        slug=f"other-template-{uuid.uuid4().hex[:8]}",
        short_description="Other user template for testing",
        description="Full rich description for other user template testing.",
        thumbnail_url="https://example.com/thumb3.png",
        price=0,
        is_free=True,
        seller_id=free_user.id,
        category_id=category.id,
        status=TemplateStatus.DRAFT,
        template_origin="studio",
        tags=["studio-project"],
    )
    db.add(other_template)
    await db.commit()

    # Create auth headers
    free_token = create_access_token(subject=str(free_user.id), tv=free_user.token_version)
    extreme_token = create_access_token(subject=str(extreme_user.id), tv=extreme_user.token_version)
    free_headers = {"Authorization": f"Bearer {free_token}"}
    extreme_headers = {"Authorization": f"Bearer {extreme_token}"}

    # --- TEST 1: Free User attempts to retail -> 403 FORBIDDEN ---
    res_free = await client.post(
        "/api/v1/templates/retail",
        json={
            "template_id": str(generated_template.id),
            "retail_price": 49.00,
            "title": "Free User Selling Attempt",
            "category_id": str(category.id),
        },
        headers=free_headers,
    )
    assert res_free.status_code == 403
    assert "Extreme Plan" in res_free.json()["detail"]

    # --- TEST 2: Extreme User attempts to retail a manual upload -> 400 BAD REQUEST ---
    res_manual = await client.post(
        "/api/v1/templates/retail",
        json={
            "template_id": str(manual_template.id),
            "retail_price": 49.00,
            "title": "Manual Zip Selling Attempt",
            "category_id": str(category.id),
        },
        headers=extreme_headers,
    )
    assert res_manual.status_code == 400
    assert "Only AI-generated websites created via Site Studio can be retailed" in res_manual.json()["detail"]

    # --- TEST 3: Extreme User attempts to retail someone else's template -> 403 FORBIDDEN ---
    res_other = await client.post(
        "/api/v1/templates/retail",
        json={
            "template_id": str(other_template.id),
            "retail_price": 49.00,
            "title": "Hijack Attempt",
            "category_id": str(category.id),
        },
        headers=extreme_headers,
    )
    assert res_other.status_code == 403
    assert "You can only retail websites created under your own account" in res_other.json()["detail"]

    # --- TEST 4: Extreme User retails their own AI-generated website -> 200 OK ---
    res_success = await client.post(
        "/api/v1/templates/retail",
        json={
            "template_id": str(generated_template.id),
            "retail_price": 39.99,
            "title": "SaaS AI Pro Master",
            "short_description": "Clean production-ready SaaS site generated with Site Studio",
            "category_id": str(category.id),
            "tags": ["react", "saas", "tailwind"],
        },
        headers=extreme_headers,
    )
    assert res_success.status_code == 200
    data = res_success.json()
    assert data["title"] == "SaaS AI Pro Master"
    assert float(data["price"]) == 39.99
    assert data["status"] in ("submitted", "published")
    assert "retailed" in data["tags"]
    assert "extreme-creator" in data["tags"]
