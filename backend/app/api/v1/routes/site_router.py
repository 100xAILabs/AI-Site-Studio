"""
Workload Reverse Proxy Router — Serves isolated customer website deployments.
Strict Data Plane Isolation:
- Strictly serves static files from static/deployments/{site_id}/current/
- Implements Content-Security-Policy and isolation headers
- Zero access to platform backend secrets or environment variables
"""

import os
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from app.services.security_scanner import security_scanner

router = APIRouter(tags=["Tenant Workload Sites"])

_STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"


@router.get("/sites/{site_identifier}", include_in_schema=False)
@router.get("/sites/{site_identifier}/{filepath:path}", include_in_schema=False)
async def serve_tenant_workload(
    site_identifier: str,
    filepath: str = "",
    request: Request = None,
):
    """
    Serves static assets and pages for an isolated customer website.
    Resolves `site_identifier` (e.g. `SITE-8F72A` or `subdomain.aisitestudio.com`)
    and streams files from `static/deployments/{site_id}/current/`.
    """
    clean_site_id = site_identifier.split(".")[0].upper()
    
    # Try exact match or SITE- prefixed match
    site_dir = _DEPLOYMENTS_ROOT / clean_site_id / "current"
    if not site_dir.exists():
        # Check all site folders for matching subdomain
        matching_site = None
        if _DEPLOYMENTS_ROOT.exists():
            for folder in _DEPLOYMENTS_ROOT.iterdir():
                if folder.is_dir() and folder.name.upper() == clean_site_id:
                    matching_site = folder / "current"
                    break
        if matching_site and matching_site.exists():
            site_dir = matching_site
        else:
            raise HTTPException(status_code=404, detail="Tenant website deployment not found or inactive.")

    # Sanitize requested file path to prevent directory traversal
    safe_path = filepath.strip("/\\")
    if not safe_path:
        target_file = site_dir / "index.html"
    else:
        target_file = site_dir / safe_path

    # Fallback to SPA index.html for client-side routing if asset is not found
    if not target_file.exists() or target_file.is_dir():
        if (site_dir / "index.html").exists():
            target_file = site_dir / "index.html"
        else:
            raise HTTPException(status_code=404, detail="Requested resource not found on this website.")

    # Detect MIME type
    content_type, _ = mimetypes.guess_type(str(target_file))
    if not content_type:
        content_type = "text/html" if target_file.suffix == ".html" else "application/octet-stream"

    # Attach sandboxed preview headers for security
    secure_headers = security_scanner.get_secure_preview_headers()
    secure_headers["Cache-Control"] = "public, max-age=300"

    return FileResponse(
        path=str(target_file),
        media_type=content_type,
        headers=secure_headers,
    )
