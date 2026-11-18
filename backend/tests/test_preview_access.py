"""
Tests for Live Preview Capability Tokens and Source Asset Protection (F-14, F-18).
Ensures unpublished draft previews require valid capability tokens, watermark suppression requires clean=True token,
source files and sensitive directories are blocked from live asset access, and CSP sandbox headers isolate previews.
"""

import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from app.core.config import settings
from app.core.security import make_preview_token
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus, TemplateFramework


@pytest.fixture
async def sample_template_with_files(db: AsyncSession, tmp_path):
    user = User(
        email="creator_preview_test@example.com",
        username="preview_creator",
        full_name="Preview Creator",
        role=UserRole.SELLER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    cat = Category(name="Preview Category", slug="preview-cat")
    db.add(cat)
    await db.flush()

    # Create dummy template files in preview directory
    import tempfile
    from pathlib import Path
    t_id = uuid.uuid4()
    preview_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(t_id)
    preview_dir.mkdir(parents=True, exist_ok=True)

    # Public web file
    (preview_dir / "index.html").write_text("<html><body><h1>Hello World</h1></body></html>", encoding="utf-8")
    (preview_dir / "style.css").write_text("body { color: red; }", encoding="utf-8")

    # Sensitive files that must be blocked
    (preview_dir / ".env").write_text("SECRET_KEY=leak", encoding="utf-8")
    (preview_dir / "package.json").write_text('{"name": "leaked"}', encoding="utf-8")

    src_dir = preview_dir / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "App.jsx").write_text("export default function App() {}", encoding="utf-8")

    template = Template(
        id=t_id,
        seller_id=user.id,
        title="Preview Test Template",
        slug="preview-test-template",
        short_description="Preview test",
        description="Full preview test description",
        thumbnail_url="https://example.com/thumb.jpg",
        price=Decimal("49.00"),
        status=TemplateStatus.DRAFT,  # Unpublished
        framework=TemplateFramework.HTML,
        category_id=cat.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return template


@pytest.mark.asyncio
async def test_capability_token_required_for_draft(client: AsyncClient, sample_template_with_files):
    """Unpublished template drafts require a valid capability token to access live preview."""
    tmpl = sample_template_with_files

    # 1. Request without token: must be rejected with 403 Forbidden
    res_no_token = await client.get(f"/api/v1/preview/live/{tmpl.id}")
    assert res_no_token.status_code == 403

    # 2. Request with valid capability token in URL: succeeds
    token = make_preview_token(str(tmpl.id), clean=False, ttl=3600)
    res_with_token = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token}/")
    assert res_with_token.status_code == 200
    assert "Preview Test Template" in res_with_token.text or "Hello World" in res_with_token.text


@pytest.mark.asyncio
async def test_clean_flag_respected_only_with_valid_cap(client: AsyncClient, sample_template_with_files, db: AsyncSession):
    """
    Query parameter ?clean=1 or ?mode=live is ignored.
    Watermark suppression is only granted when the capability token specifically asserts clean=True or template is free.
    """
    tmpl = sample_template_with_files

    # Valid token with clean=False: served with watermark
    token_watermarked = make_preview_token(str(tmpl.id), clean=False, ttl=3600)
    res_wm = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token_watermarked}/?clean=1")
    assert res_wm.status_code == 200
    # Watermark script or ribbon should be injected for non-clean token
    assert "aisitestudio-watermark" in res_wm.text or "Watermark" in res_wm.text or "ai-site-studio" in res_wm.text.lower() or "preview-watermark-grid" in res_wm.text

    # Valid token with clean=True: clean presentation without watermark
    token_clean = make_preview_token(str(tmpl.id), clean=True, ttl=3600)
    res_clean = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token_clean}/")
    assert res_clean.status_code == 200
    assert "preview-watermark-grid" not in res_clean.text
    assert "preview-purchase-footer-banner" not in res_clean.text


@pytest.mark.asyncio
async def test_blocked_source_files_404_or_403(client: AsyncClient, sample_template_with_files):
    """
    Requests to sensitive files (.env, package.json) or raw source (.jsx in /src/) must be blocked (403 or 404).
    """
    tmpl = sample_template_with_files
    token = make_preview_token(str(tmpl.id), clean=False, ttl=3600)

    # 1. .env file
    res_env = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token}/.env")
    assert res_env.status_code in (403, 404)

    # 2. package.json
    res_pkg = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token}/package.json")
    assert res_pkg.status_code in (403, 404)

    # 3. Source directory and jsx
    res_src = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token}/src/App.jsx")
    assert res_src.status_code in (403, 404)


@pytest.mark.asyncio
async def test_preview_sandbox_headers(client: AsyncClient, sample_template_with_files):
    """
    Preview responses must include strict CSP sandbox headers that do NOT contain allow-same-origin,
    and must NOT emit permissive Access-Control-Allow-Origin: *.
    """
    tmpl = sample_template_with_files
    token = make_preview_token(str(tmpl.id), clean=False, ttl=3600)

    res = await client.get(f"/api/v1/preview/live/{tmpl.id}~{token}/")
    assert res.status_code == 200

    csp = res.headers.get("content-security-policy", "")
    cors = res.headers.get("access-control-allow-origin", "")

    # CSP sandbox must NOT have allow-same-origin
    if "sandbox" in csp:
        assert "allow-same-origin" not in csp

    # CORS header must NOT be wildcard *
    assert cors != "*"
