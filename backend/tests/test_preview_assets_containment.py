import pytest
import tempfile
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_preview_assets_path_containment(client: AsyncClient):
    """F-01: Verify strict containment on /assets/{filepath:path}."""
    # 1. No referer -> 404
    resp = await client.get("/assets/index.js")
    assert resp.status_code == 404

    # 2. Invalid preview target in referer -> 400
    resp = await client.get(
        "/assets/index.js",
        headers={"referer": "http://localhost:8000/preview/live/../../etc/passwd"}
    )
    assert resp.status_code in (400, 404)

    # 3. Path traversal in filepath with .. -> 403
    resp = await client.get(
        "/assets/sub/../../secret.txt",
        headers={"referer": "http://localhost:8000/preview/live/valid-target-123"}
    )
    assert resp.status_code in (403, 404)

    # 4. Encoded path traversal (%2e%2e) -> 403
    resp = await client.get(
        "/assets/%2e%2e/secret.txt",
        headers={"referer": "http://localhost:8000/preview/live/valid-target-123"}
    )
    assert resp.status_code == 403

    # 5. Null byte injection -> 403
    resp = await client.get(
        "/assets/test%00.js",
        headers={"referer": "http://localhost:8000/preview/live/valid-target-123"}
    )
    assert resp.status_code == 403

    # 6. Valid asset served correctly from preview directory
    temp_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / "valid-test-preview"
    asset_dir = temp_dir / "dist" / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    test_file = asset_dir / "app.js"
    test_file.write_text("console.log('contained');", encoding="utf-8")

    resp = await client.get(
        "/assets/app.js",
        headers={"referer": "http://localhost:8000/preview/live/valid-test-preview"}
    )
    assert resp.status_code == 200
    assert "console.log('contained')" in resp.text
