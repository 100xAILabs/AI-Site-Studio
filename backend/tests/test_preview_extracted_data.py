"""
Tests for live preview extracted data parsing using beautifulsoup4 (F-41).
Validates that bs4 correctly parses HTML/JSX template sections on clean install.
"""

import bs4  # Must import bs4 at collection time as mandated by F-41
import os
import tempfile
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus, TemplateFramework


@pytest.mark.asyncio
async def test_preview_extracted_data_success(client: AsyncClient, db: AsyncSession):
    """
    Creates a published template with index.html in its preview directory,
    calls GET /api/v1/preview/live/{id}/extracted-data, and asserts 200 with non-empty sections.
    """
    assert bs4 is not None

    user = User(
        email="bs4_seller_test@example.com",
        username="bs4_seller",
        full_name="BS4 Tester",
        role=UserRole.SELLER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    category = Category(name="Business Tech", slug="business-tech")
    db.add(category)
    await db.flush()

    t_id = uuid.uuid4()
    template = Template(
        id=t_id,
        title="Acme Corporate Template",
        slug=f"acme-corporate-{t_id.hex[:8]}",
        short_description="A short description for testing bs4 data extraction.",
        description="A corporate template for testing bs4 data extraction.",
        thumbnail_url="https://example.com/thumb.png",
        framework=TemplateFramework.HTML,
        price=Decimal("49.00"),
        price_currency="USD",
        status=TemplateStatus.PUBLISHED,
        is_marketplace=True,
        seller_id=user.id,
        category_id=category.id,
        download_assets={},
    )
    db.add(template)
    await db.commit()

    # Create dummy index.html in preview dir for extraction
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(t_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    html_content = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Acme Corp</title></head>
    <body>
        <header>
            <nav><a href="#hero">Home</a><a href="#services">Services</a></nav>
        </header>
        <section id="hero">
            <h1>Scale Your Business With AI</h1>
            <p>Our platform automates your entire enterprise workflow.</p>
        </section>
        <section id="services">
            <h2>Our Core Services</h2>
            <div class="card"><h3>Cloud Strategy</h3><p>Enterprise cloud transformation.</p></div>
        </section>
    </body>
    </html>"""
    (preview_dir / "index.html").write_text(html_content, encoding="utf-8")

    # Call endpoint
    res = await client.get(f"/api/v1/preview/live/{t_id}/extracted-data")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "sections" in data
    assert len(data["sections"]) > 0
    assert "hero" in data["sections"]
    assert "services" in data["sections"]
    assert data["brand"]["business_name"] == "Scale Your Business With AI"
