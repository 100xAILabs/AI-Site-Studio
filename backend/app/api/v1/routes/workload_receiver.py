"""
Workload Receiver Route — Edge deployment receiver for Oracle Cloud Instance 2.
Receives compiled website bundles from the Main Platform (Oracle Cloud Instance 1)
and stages them in isolated tenant workload storage on Oracle Cloud Instance 2.
"""

from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form, status
from pathlib import Path
import hmac
import re
import shutil
import stat
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
_MAX_WORKLOAD_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB per synced site artifact
_MAX_WORKLOAD_FILES = 10_000


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
    # Verify pre-shared sync secret using timing-safe comparison
    expected_secret = settings.USER_WORKLOAD_SYNC_SECRET
    if not expected_secret or not hmac.compare_digest(x_workload_secret.strip(), expected_secret.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Invalid workload synchronization secret.",
        )

    clean_site_id = site_id.strip().upper()
    if not re.match(r"^[A-Z0-9_-]{1,64}$", clean_site_id):
        raise HTTPException(status_code=400, detail="Invalid site_id format.")

    clean_version = version.strip()
    if not re.match(r"^[A-Za-z0-9._-]{1,40}$", clean_version) or ".." in clean_version:
        raise HTTPException(status_code=400, detail="Invalid deployment version identifier.")

    site_dir = (_DEPLOYMENTS_ROOT / clean_site_id).resolve()
    if not site_dir.is_relative_to(_DEPLOYMENTS_ROOT.resolve()):
        raise HTTPException(status_code=400, detail="Invalid site_id path.")
    version_dir = site_dir / clean_version / "dist"
    current_dir = site_dir / "current"

    # Read uploaded zip
    content = await artifact_zip.read()
    zip_buf = io.BytesIO(content)

    temp_stage = site_dir / f".sync-stage-{uuid.uuid4().hex}"
    temp_stage.mkdir(parents=True, exist_ok=True)
    temp_stage_resolved = temp_stage.resolve()

    try:
        total_uncompressed = 0
        with zipfile.ZipFile(zip_buf, "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > _MAX_WORKLOAD_FILES:
                raise HTTPException(status_code=400, detail="Archive contains too many entries.")

            # Safe zip extract preventing directory traversal (Zip Slip), symlinks, and sensitive files
            for member in infolist:
                raw_name = member.filename or ""
                if (
                    raw_name.startswith(("/", "\\"))
                    or ".." in raw_name.replace("\\", "/").split("/")
                    or (len(raw_name) > 1 and raw_name[1] == ":")
                ):
                    continue
                # Skip symlinks (UNIX mode S_IFLNK)
                if stat.S_ISLNK(member.external_attr >> 16):
                    continue
                parts = [p for p in raw_name.replace("\\", "/").split("/") if p]
                if any(p in {".git", ".npmrc", "node_modules", "__pycache__"} or p == ".env" or p.startswith(".env.") for p in parts):
                    continue
                if member.file_size > 1024 * 1024 and (member.compress_size == 0 or member.file_size / member.compress_size > 100.0):
                    raise HTTPException(status_code=400, detail="Archive failed compression ratio safety check.")
                total_uncompressed += max(0, int(member.file_size or 0))
                if total_uncompressed > _MAX_WORKLOAD_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=400, detail="Archive exceeds maximum uncompressed artifact size.")

                target_dest = (temp_stage_resolved / raw_name).resolve()
                if not target_dest.is_relative_to(temp_stage_resolved):
                    continue
                if member.is_dir():
                    target_dest.mkdir(parents=True, exist_ok=True)
                else:
                    target_dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src_stream, open(target_dest, "wb") as dst_stream:
                        shutil.copyfileobj(src_stream, dst_stream, length=1024 * 1024)

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
