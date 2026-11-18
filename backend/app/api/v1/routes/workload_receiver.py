"""
Workload Receiver Route — Edge deployment receiver for Oracle Cloud Instance 2.
Receives compiled website bundles from the Main Platform (Oracle Cloud Instance 1)
and stages them in isolated tenant workload storage on Oracle Cloud Instance 2.
"""

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form, status
from pathlib import Path
import shutil
import zipfile
import io
import uuid
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workload", tags=["Workload Node Receiver"])

_STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"
_DEPLOYMENTS_ROOT.mkdir(parents=True, exist_ok=True)


@router.post("/sync-artifact")
async def sync_deployment_artifact(
    site_id: str = Form(...),
    version: str = Form("v1.0"),
    artifact_zip: UploadFile = File(...),
    x_workload_secret: str = Header(..., alias="X-Workload-Secret"),
):
    """
    Ingest compiled tenant website bundle from Oracle Instance 1 (Control Plane)
    onto Oracle Instance 2 (User Workload Server).
    """
    # Verify pre-shared sync secret
    expected_secret = settings.USER_WORKLOAD_SYNC_SECRET
    if not expected_secret or x_workload_secret.strip() != expected_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Invalid workload synchronization secret.",
        )

    clean_site_id = site_id.strip().upper()
    site_dir = _DEPLOYMENTS_ROOT / clean_site_id
    version_dir = site_dir / version / "dist"
    current_dir = site_dir / "current"

    # Read uploaded zip
    content = await artifact_zip.read()
    zip_buf = io.BytesIO(content)

    temp_stage = site_dir / f".sync-stage-{uuid.uuid4().hex}"
    temp_stage.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_buf, "r") as zf:
            # Safe zip extract preventing directory traversal (Zip Slip)
            for member in zf.infolist():
                if member.filename.startswith(("/", "\\")) or ".." in member.filename:
                    continue
                zf.extract(member, temp_stage)

        # Stage to version_dir
        version_dir.parent.mkdir(parents=True, exist_ok=True)
        if version_dir.exists():
            shutil.rmtree(version_dir, ignore_errors=True)
        shutil.copytree(temp_stage, version_dir)

        # Atomic switch current
        current_stage = site_dir / f".current-stage-{uuid.uuid4().hex}"
        shutil.copytree(version_dir, current_stage)

        # Replace current_dir
        if current_dir.exists():
            old_backup = site_dir / f".old-current-{uuid.uuid4().hex}"
            current_dir.rename(old_backup)
            current_stage.rename(current_dir)
            shutil.rmtree(old_backup, ignore_errors=True)
        else:
            current_stage.rename(current_dir)

        # Invalidate in-memory site resolution cache if site_router is loaded
        try:
            from app.api.v1.routes.site_router import _SITE_RESOLUTION_CACHE
            _SITE_RESOLUTION_CACHE.pop(clean_site_id.lower(), None)
            _SITE_RESOLUTION_CACHE.pop(clean_site_id, None)
        except Exception:
            pass

        logger.info(f"[Workload Node] Successfully staged remote site {clean_site_id} ({version})")

        return {
            "status": "synced",
            "site_id": clean_site_id,
            "version": version,
            "live_url": f"/sites/{clean_site_id}/",
        }
    except Exception as e:
        logger.exception(f"[Workload Node] Failed to extract and stage artifact for {clean_site_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stage workload artifact: {str(e)}",
        )
    finally:
        shutil.rmtree(temp_stage, ignore_errors=True)
