"""
Unit tests for Dual-Server Workload Node Receiver and Remote Artifact Synchronization.
Verifies secure isolation between Platform Control Plane (Oracle Instance 1)
and User Workload Edge Server (Oracle Instance 2).
"""

import io
import zipfile
import pytest
from pathlib import Path
from httpx import AsyncClient
from app.core.config import settings
from app.services.deployment_providers.local_provider import local_deployment_provider


def _create_sample_zip() -> bytes:
    """Create a minimal valid website zip artifact."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", "<!DOCTYPE html><html><body><h1>Tenant Site</h1></body></html>")
        zf.writestr("style.css", "body { background: #000; color: #fff; }")
        # Attempted zip slip entry
        zf.writestr("../malicious.txt", "should be skipped")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_workload_receiver_unauthorized(client: AsyncClient):
    """Requests with missing or invalid secret must be blocked with HTTP 403."""
    zip_bytes = _create_sample_zip()
    files = {"artifact_zip": ("site.zip", zip_bytes, "application/zip")}
    data = {"site_id": "SITE-UNAUTH-101", "version": "v1.0"}

    # No header
    res = await client.post("/api/v1/workload/sync-artifact", data=data, files=files)
    assert res.status_code == 422 or res.status_code == 403

    # Invalid header
    files = {"artifact_zip": ("site.zip", zip_bytes, "application/zip")}
    res_bad = await client.post(
        "/api/v1/workload/sync-artifact",
        data=data,
        files=files,
        headers={"X-Workload-Secret": "wrong-secret-token"},
    )
    assert res_bad.status_code == 403
    assert "Unauthorized" in res_bad.json()["detail"]


@pytest.mark.asyncio
async def test_workload_receiver_authorized_sync(client: AsyncClient, monkeypatch):
    """Valid secret and artifact must extract safely and stage live deployment."""
    test_secret = "test-oracle-workload-secret-xyz"
    monkeypatch.setattr(settings, "USER_WORKLOAD_SYNC_SECRET", test_secret)

    site_id = "SITE-ORACLE-WORKLOAD-777"
    zip_bytes = _create_sample_zip()
    files = {"artifact_zip": ("site.zip", zip_bytes, "application/zip")}
    data = {"site_id": site_id, "version": "v1.0"}
    headers = {"X-Workload-Secret": test_secret}

    res = await client.post(
        "/api/v1/workload/sync-artifact",
        data=data,
        files=files,
        headers=headers,
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "synced"
    assert res_data["site_id"] == site_id

    # Verify filesystem deployment on the receiver node
    from app.api.v1.routes.workload_receiver import _DEPLOYMENTS_ROOT
    staged_index = _DEPLOYMENTS_ROOT / site_id / "current" / "index.html"
    assert staged_index.exists()
    assert "Tenant Site" in staged_index.read_text(encoding="utf-8")

    # Clean up test artifacts
    import shutil
    shutil.rmtree(_DEPLOYMENTS_ROOT / site_id, ignore_errors=True)


@pytest.mark.asyncio
async def test_local_provider_remote_workload_sync_dispatch(tmp_path, monkeypatch):
    """Tests the sender method on the local deployment provider."""
    # Create mock artifact directory
    test_artifact = tmp_path / "dist"
    test_artifact.mkdir()
    (test_artifact / "index.html").write_text("<h1>Deployed Site</h1>", encoding="utf-8")

    monkeypatch.setattr(settings, "USER_WORKLOAD_MODE", "remote_oracle")
    monkeypatch.setattr(settings, "USER_WORKLOAD_SERVER_URL", "https://sites.aisitestudio.com")
    monkeypatch.setattr(settings, "USER_WORKLOAD_SYNC_SECRET", "super-secret")

    # Mock httpx.AsyncClient.post to return 200
    from unittest.mock import AsyncMock, patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "synced"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        success = await local_deployment_provider._sync_to_remote_workload_node(
            str(test_artifact), "SITE-MOCK-999", "v1.0"
        )
        assert success is True
        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        assert "X-Workload-Secret" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Workload-Secret"] == "super-secret"
