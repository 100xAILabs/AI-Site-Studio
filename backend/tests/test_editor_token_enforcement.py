import pytest
import uuid
from decimal import Decimal
from httpx import AsyncClient
from app.models.user import User
from app.models.category import Category
from app.models.template import Template, TemplateStatus, TemplateFramework

@pytest.mark.asyncio
async def test_token_deduction_and_depletion(client: AsyncClient, db):
    # 0. Create category
    cat = Category(name="Test Category", slug=f"cat-{uuid.uuid4().hex[:6]}")
    db.add(cat)
    await db.commit()
    await db.refresh(cat)

    # 1. Create a buyer user with 1 token
    test_buyer = User(
        email=f"buyer_token_test_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="fakehash",
        role="buyer",
        is_active=True,
        ai_credits=1
    )
    db.add(test_buyer)
    await db.commit()
    await db.refresh(test_buyer)

    from app.core.security import create_access_token
    token = create_access_token(subject=str(test_buyer.id), role=test_buyer.role)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a test draft template owned by the buyer
    test_template = Template(
        title="Token Test Draft",
        slug=f"token-test-draft-{uuid.uuid4().hex[:6]}",
        short_description="Test short desc",
        description="Test full desc",
        framework=TemplateFramework.REACT,
        status=TemplateStatus.DRAFT,
        category_id=cat.id,
        seller_id=test_buyer.id,
        is_marketplace=False,
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00")
    )
    db.add(test_template)
    await db.commit()
    await db.refresh(test_template)

    # 3. First operation (costs 1 token) should succeed or check tokens
    from app.api.v1.routes.preview import check_and_deduct_tokens
    remaining = await check_and_deduct_tokens(test_buyer, db, cost=1, operation_name="test_op")
    assert remaining == 0
    assert test_buyer.ai_credits == 0

    # 4. Second operation when user has 0 tokens should raise 402 HTTPException
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await check_and_deduct_tokens(test_buyer, db, cost=1, operation_name="test_op")
    assert exc_info.value.status_code == 402
    assert "Insufficient AI tokens" in exc_info.value.detail
