import pytest
from uuid import uuid4
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.api.v1.routes.templates import download_template


def _make_template(status=TemplateStatus.PUBLISHED, is_free=False, price=Decimal("29.00")):
    return Template(
        id=uuid4(),
        title="Test Template",
        slug=f"test-template-{uuid4().hex[:8]}",
        short_description="Short desc",
        description="Full description",
        seller_id=uuid4(),
        status=status,
        is_free=is_free,
        price=price,
        thumbnail_url="https://example.com/thumb.jpg",
        category_id=uuid4(),
        download_assets={"zip": f"https://storage.example.com/{uuid4()}.zip"},
    )


@pytest.mark.asyncio
async def test_any_user_can_download_watermarked_for_evaluation():
    """All users (Free, Pro, Extreme) can download an unpurchased template with a watermark for evaluation."""
    user = User(
        id=uuid4(),
        email="evaluser@test.com",
        role=UserRole.BUYER,
        subscription_tier="free",
    )
    template = _make_template(is_free=False, price=Decimal("29.00"))

    mock_db = AsyncMock()
    mock_request = MagicMock()
    mock_request.base_url = "http://testserver"

    fake_file_id = uuid4()

    with patch("app.repositories.template_repo.TemplateRepository.get_by_id", return_value=template), \
         patch("app.repositories.template_repo.TemplateRepository.increment_downloads", return_value=None), \
         patch("app.core.storage.storage._parse_file_id", return_value=fake_file_id), \
         patch("app.api.v1.routes.templates.generate_file_signature", return_value="mock_sig"):

        purchase_result = MagicMock()
        purchase_result.first.return_value = None  # Not purchased yet

        mock_db.execute.return_value = purchase_result

        res = await download_template(
            template_id=template.id,
            request=mock_request,
            format="zip",
            license="regular",
            db=mock_db,
            current_user=user,
        )

        assert res["is_clean"] is False
        assert res["watermark_status"] == "watermarked"
        assert "mock_sig" in res["download_url"]


@pytest.mark.asyncio
async def test_unpurchased_clean_download_rejected_for_all_users():
    """Requesting clean/extended download without purchasing is rejected with 403, even for Extreme subscribers."""
    extreme_user = User(
        id=uuid4(),
        email="extreme@test.com",
        role=UserRole.BUYER,
        subscription_tier="extreme",
    )
    template = _make_template(is_free=False, price=Decimal("49.00"))

    mock_db = AsyncMock()
    mock_request = MagicMock()

    with patch("app.repositories.template_repo.TemplateRepository.get_by_id", return_value=template):
        purchase_result = MagicMock()
        purchase_result.first.return_value = None  # No purchase

        mock_db.execute.return_value = purchase_result

        with pytest.raises(HTTPException) as exc_info:
            await download_template(
                template_id=template.id,
                request=mock_request,
                format="zip",
                license="extended",
                db=mock_db,
                current_user=extreme_user,
            )

        assert exc_info.value.status_code == 403
        assert "Purchase required to download clean source code" in exc_info.value.detail


@pytest.mark.asyncio
async def test_pro_user_with_purchase_gets_clean_without_extended_fee():
    """A Pro subscriber who purchases a template gets clean, watermark-free code automatically."""
    user = User(
        id=uuid4(),
        email="pro@test.com",
        role=UserRole.BUYER,
        subscription_tier="pro",
    )
    template = _make_template(is_free=False, price=Decimal("39.00"))

    mock_db = AsyncMock()
    mock_request = MagicMock()
    mock_request.base_url = "http://testserver"

    order = Order(id=uuid4(), user_id=user.id, status=OrderStatus.COMPLETED)
    order_item = OrderItem(id=uuid4(), order_id=order.id, template_id=template.id, license_type="regular")

    fake_file_id = uuid4()

    with patch("app.repositories.template_repo.TemplateRepository.get_by_id", return_value=template), \
         patch("app.repositories.template_repo.TemplateRepository.increment_downloads", return_value=None), \
         patch("app.core.storage.storage._parse_file_id", return_value=fake_file_id), \
         patch("app.api.v1.routes.templates.generate_file_signature", return_value="pro_sig"):

        purchase_result = MagicMock()
        purchase_result.first.return_value = (order, order_item)

        mock_db.execute.return_value = purchase_result

        res = await download_template(
            template_id=template.id,
            request=mock_request,
            format="zip",
            license="regular",
            db=mock_db,
            current_user=user,
        )

        assert res["is_clean"] is True
        assert res["watermark_status"] == "clean"


@pytest.mark.asyncio
async def test_extreme_user_with_purchase_gets_clean_code():
    """An Extreme subscriber who purchases the template gets clean code without watermark removal surcharge."""
    user = User(
        id=uuid4(),
        email="extreme_owner@test.com",
        role=UserRole.BUYER,
        subscription_tier="extreme",
    )
    template = _make_template(is_free=False, price=Decimal("50.00"))

    mock_db = AsyncMock()
    mock_request = MagicMock()
    mock_request.base_url = "http://testserver"

    order = Order(id=uuid4(), user_id=user.id, status=OrderStatus.COMPLETED)
    order_item = OrderItem(id=uuid4(), order_id=order.id, template_id=template.id, license_type="regular")

    fake_file_id = uuid4()

    with patch("app.repositories.template_repo.TemplateRepository.get_by_id", return_value=template), \
         patch("app.repositories.template_repo.TemplateRepository.increment_downloads", return_value=None), \
         patch("app.core.storage.storage._parse_file_id", return_value=fake_file_id), \
         patch("app.api.v1.routes.templates.generate_file_signature", return_value="extreme_sig"):

        purchase_result = MagicMock()
        purchase_result.first.return_value = (order, order_item)

        mock_db.execute.return_value = purchase_result

        res = await download_template(
            template_id=template.id,
            request=mock_request,
            format="zip",
            license="regular",
            db=mock_db,
            current_user=user,
        )

        assert res["is_clean"] is True
        assert res["watermark_status"] == "clean"


@pytest.mark.asyncio
async def test_standard_buyer_with_purchase_gets_clean_code_no_extra_charges():
    """Any buyer who pays the base template cost receives clean code with no extra charges."""
    user = User(
        id=uuid4(),
        email="standardbuyer@test.com",
        role=UserRole.BUYER,
        subscription_tier="free",
    )
    template = _make_template(is_free=False, price=Decimal("49.00"))

    mock_db = AsyncMock()
    mock_request = MagicMock()
    mock_request.base_url = "http://testserver"

    order = Order(id=uuid4(), user_id=user.id, status=OrderStatus.COMPLETED)
    order_item = OrderItem(id=uuid4(), order_id=order.id, template_id=template.id, license_type="regular")

    fake_file_id = uuid4()

    with patch("app.repositories.template_repo.TemplateRepository.get_by_id", return_value=template), \
         patch("app.repositories.template_repo.TemplateRepository.increment_downloads", return_value=None), \
         patch("app.core.storage.storage._parse_file_id", return_value=fake_file_id), \
         patch("app.api.v1.routes.templates.generate_file_signature", return_value="buyer_sig"):

        purchase_result = MagicMock()
        purchase_result.first.return_value = (order, order_item)

        mock_db.execute.return_value = purchase_result

        res = await download_template(
            template_id=template.id,
            request=mock_request,
            format="zip",
            license="regular",
            db=mock_db,
            current_user=user,
        )

        assert res["is_clean"] is True
        assert res["watermark_status"] == "clean"
