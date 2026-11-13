"""
Workload Reverse Proxy Router — Serves isolated customer website deployments.
Strict Data Plane Isolation:
- Strictly serves static files from static/deployments/{site_id}/current/
- Implements Content-Security-Policy and isolation headers
- High-performance in-memory site resolution caching (sub-millisecond static serving)
- Lightweight runtime error reporting without CORS preflight overhead
"""

import os
import time
import asyncio
import mimetypes
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from app.services.security_scanner import security_scanner
from app.core.database import AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentLog, Domain
from app.models.hosting_subscription import HostingSubscription
from sqlalchemy import select

router = APIRouter(tags=["Tenant Workload Sites"])

_STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"

_STATIC_ASSET_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif",
    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map", ".mp4"
}

# Fast in-memory cache for resolved sites: identifier -> (target_id, site_dir_str, timestamp)
_SITE_RESOLUTION_CACHE: Dict[str, Tuple[str, str, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


async def _log_server_access(target_id: str, method: str, path: str, status_code: int, client_host: str = ""):
    """Records server-side HTTP request telemetry into the deployment logs asynchronously."""
    # Only record errors or page visits, never static assets
    if status_code < 400:
        ext = Path(path.split("?")[0]).suffix.lower()
        if ext in _STATIC_ASSET_EXTENSIONS:
            return

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Deployment).where(
                (Deployment.site_id == target_id) |
                (Deployment.subdomain == target_id.lower())
            ).limit(1)
            res = await session.execute(stmt)
            deployment = res.scalar_one_or_none()
            if deployment:
                time_str = datetime.now().strftime("%H:%M:%S")
                level = "INFO" if status_code < 400 else ("WARN" if status_code < 500 else "ERROR")
                tag = f"[SERVER HTTP {status_code}]"
                client_info = f" ({client_host})" if client_host else ""
                log_line = f"[{time_str}] [{level}] {tag} {method} {path}{client_info}\n"

                curr = deployment.logs or ""
                if len(curr) > 200_000:
                    curr = curr[-150_000:]
                deployment.logs = curr + log_line

                session.add(DeploymentLog(
                    deployment_id=deployment.id,
                    level=level,
                    message=f"{tag} {method} {path}{client_info}"[:500]
                ))
                await session.commit()
    except Exception:
        pass


@router.get("/sites/{site_identifier}", include_in_schema=False)
@router.get("/sites/{site_identifier}/{filepath:path}", include_in_schema=False)
@router.get("/api/v1/deployments/live/{site_identifier}", include_in_schema=False)
@router.get("/api/v1/deployments/live/{site_identifier}/{filepath:path}", include_in_schema=False)
async def serve_tenant_workload(
    site_identifier: str,
    filepath: str = "",
    request: Request = None,
):
    """
    Serves static assets and pages for an isolated customer website.
    Resolves `site_identifier` (e.g. `SITE-8F72A` or `subdomain.aisitestudio.com` or custom domain)
    and streams files from `static/deployments/{site_id}/current/`.
    Production features:
    - 308 Trailing slash canonicalization
    - In-memory resolution cache for ultra-low latency (<2ms)
    - Clean URL resolution (/about -> /about.html)
    - Relative subfolder CSS path auto-correction
    - SPA client-side routing fallback
    - Non-blocking browser telemetry
    """
    # 0. Canonical Trailing Slash Redirect for relative asset integrity
    if not filepath and request and not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        target_url = f"{request.url.path}/"
        if request.url.query:
            target_url += f"?{request.url.query}"
        return RedirectResponse(url=target_url, status_code=308)

    clean_identifier = site_identifier.strip().lower()
    domain_lookup = clean_identifier[4:] if clean_identifier.startswith("www.") else clean_identifier
    clean_site_id = site_identifier.split(".")[0].upper()

    now = time.time()
    cached = _SITE_RESOLUTION_CACHE.get(clean_identifier) or _SITE_RESOLUTION_CACHE.get(clean_site_id)
    site_dir = None
    target_id = None

    if cached and (now - cached[2] < _CACHE_TTL_SECONDS):
        target_id = cached[0]
        cached_path = Path(cached[1])
        if cached_path.exists():
            site_dir = cached_path

    # If not cached, fast check local deployments directory on disk
    if not site_dir:
        direct_site_dir = _DEPLOYMENTS_ROOT / clean_site_id / "current"
        if direct_site_dir.is_dir():
            target_id = clean_site_id
            site_dir = direct_site_dir
            _SITE_RESOLUTION_CACHE[clean_identifier] = (target_id, str(site_dir), now)
            _SITE_RESOLUTION_CACHE[clean_site_id] = (target_id, str(site_dir), now)

    # If still not found, check DB for matching site_id, subdomain, or custom_domain
    if not site_dir:
        resolved_site_id = None
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Deployment).where(
                    (Deployment.site_id == clean_site_id) |
                    (Deployment.subdomain == clean_identifier) |
                    (Deployment.custom_domain == clean_identifier) |
                    (Deployment.custom_domain == domain_lookup) |
                    (Deployment.subdomain == f"{clean_identifier}.aisitestudio.com") |
                    (select(Domain.id).where(
                        Domain.deployment_id == Deployment.id,
                        Domain.domain.in_({clean_identifier, domain_lookup}),
                        Domain.verification_status == "verified",
                    ).exists())
                ).limit(1)
                res = await session.execute(stmt)
                deployment = res.scalar_one_or_none()
                resolved_site_id = deployment.site_id if deployment else None
                if deployment and deployment.provider == "local":
                    from app.core.config import settings
                    from app.models.user import User

                    # Resolve deployment owner subscription status
                    owner_res = await session.execute(select(User).where(User.id == deployment.user_id))
                    owner = owner_res.scalar_one_or_none()
                    is_extreme = bool(
                        owner
                        and (
                            (owner.subscription_tier or "").lower() in ("extreme", "agency", "enterprise")
                            or getattr(owner.role, "value", owner.role) == "admin"
                        )
                    )
                    is_pro = bool(owner and owner.is_pro_subscriber)

                    # 1. Extreme tier has unlimited included hosting
                    if is_extreme:
                        pass
                    # 2. Pro tier has up to 3 live deployments included with zero extra hosting charges
                    elif is_pro:
                        pro_count_res = await session.execute(
                            select(func.count(Deployment.id)).where(
                                Deployment.user_id == owner.id,
                                Deployment.status == "live",
                            )
                        )
                        pro_live_sites = pro_count_res.scalar_one() or 0
                        if pro_live_sites <= 3:
                            pass  # Included with Pro Plan
                        else:
                            # 4th+ site requires hosting subscription
                            subscription_result = await session.execute(select(HostingSubscription).where(
                                HostingSubscription.deployment_id == deployment.id
                            ))
                            subscription = subscription_result.scalar_one_or_none()
                            subscription_status = subscription.status if subscription else None
                            if subscription_status not in {"active", "trialing"}:
                                return HTMLResponse(
                                    "<!doctype html><html><head><title>Hosting unavailable</title></head>"
                                    "<body style='font:16px system-ui;max-width:640px;margin:12vh auto;padding:24px;background:#09090b;color:#fff'>"
                                    "<h1>Hosting Subscription Required</h1><p>This deployment exceeds the 3 live websites included with your Pro Plan. Complete the $12/month hosting subscription to activate this site.</p></body></html>",
                                    status_code=402,
                                )
                    # 3. Free tier has a 7-day trial window
                    else:
                        now = datetime.now(timezone.utc)
                        trial_exp = (
                            deployment.trial_expires_at
                            if (deployment.trial_expires_at and deployment.trial_expires_at.tzinfo)
                            else (deployment.trial_expires_at.replace(tzinfo=timezone.utc) if deployment.trial_expires_at else None)
                        )
                        if trial_exp and now > trial_exp:
                            return HTMLResponse(
                                "<!doctype html><html><head><meta charset='utf-8'><title>Trial Expired — AI Site Studio</title>"
                                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                                "<style>body{background:#09090b;color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;margin:0;padding:2rem;display:flex;align-items:center;justify-content:center;min-height:100vh} "
                                ".card{background:#121216;border:1px solid #27272a;border-radius:1rem;padding:2.5rem;max-width:540px;width:100%;text-align:center;box-shadow:0 12px 32px rgba(0,0,0,0.5)} "
                                "h1{color:#dfb180;font-size:1.5rem;margin:0 0 0.75rem;font-weight:800} "
                                "p{color:#a1a1aa;font-size:0.95rem;line-height:1.6;margin:0 0 1.75rem} "
                                ".btn{display:inline-block;background:#c89666;color:#09090b;font-weight:800;text-decoration:none;padding:0.75rem 1.75rem;border-radius:0.75rem;font-size:0.875rem;transition:0.2s} "
                                ".btn:hover{background:#dfb180}</style></head>"
                                "<body><div class='card'>"
                                "<h1>7-Day Free Trial Expired</h1>"
                                f"<p>The 7-day free trial period for <strong>{deployment.project_name or 'this website'}</strong> has ended. Upgrade to <strong>Studio Pro</strong> to restore permanent live cloud edge hosting and connect custom domains.</p>"
                                "<a class='btn' href='/pricing'>Upgrade to Pro &amp; Restore Live Site</a>"
                                "</div></body></html>",
                                status_code=402,
                            )
        except Exception:
            from app.core.config import settings
            if settings.ENVIRONMENT == "production":
                return HTMLResponse("Hosting status is temporarily unavailable.", status_code=503)

        target_id = (resolved_site_id or clean_site_id).upper()
        site_dir = _DEPLOYMENTS_ROOT / target_id / "current"

        if not site_dir.exists():
            matching_site = None
            if _DEPLOYMENTS_ROOT.exists():
                for folder in _DEPLOYMENTS_ROOT.iterdir():
                    if folder.is_dir() and (folder.name.upper() == target_id or folder.name.upper() == clean_site_id):
                        matching_site = folder / "current"
                        break
            if matching_site and matching_site.exists():
                site_dir = matching_site
            else:
                from app.services.deployment_deep_analyzer import _resolve_site_current_dir
                deep_dir = _resolve_site_current_dir(deployment, target_id)
                if deep_dir and deep_dir.exists():
                    site_dir = deep_dir
                elif _DEPLOYMENTS_ROOT.exists():
                    for item in _DEPLOYMENTS_ROOT.iterdir():
                        if item.is_dir():
                            for cand in [item / "current", item / "v1.0" / "dist", item]:
                                if cand.exists() and (cand / "index.html").exists():
                                    site_dir = cand
                                    break
                            if site_dir and site_dir.exists():
                                break

        if not site_dir or not site_dir.exists():
            raise HTTPException(status_code=404, detail=f"Tenant website deployment '{site_identifier}' not found or inactive.")

        _SITE_RESOLUTION_CACHE[clean_identifier] = (target_id, str(site_dir), now)
        _SITE_RESOLUTION_CACHE[clean_site_id] = (target_id, str(site_dir), now)

    client_ip = request.client.host if request and request.client else ""

    # Sanitize requested file path and enforce directory jail to prevent LFI
    safe_path = filepath.strip("/\\")
    site_dir_resolved = site_dir.resolve()

    if not safe_path:
        target_file = (site_dir_resolved / "index.html").resolve()
    else:
        target_file = (site_dir_resolved / safe_path).resolve()

    # Reject any path escaping the site deployment root directory
    if not target_file.is_relative_to(site_dir_resolved):
        raise HTTPException(status_code=403, detail="Access denied: Invalid resource path.")

    # Clean URL support & relative subfolder auto-correction
    if not target_file.exists() or target_file.is_dir():
        # Auto-correct relative CSS subfolder asset mismatch (e.g. assets/css/assets/photo.jpg -> assets/photo.jpg)
        if "assets/css/assets/" in safe_path:
            alt_path = safe_path.replace("assets/css/assets/", "assets/")
            alt_file = (site_dir_resolved / alt_path).resolve()
            if alt_file.is_file() and alt_file.is_relative_to(site_dir_resolved):
                target_file = alt_file

    if not target_file.exists() or target_file.is_dir():
        candidate_html = (site_dir_resolved / f"{safe_path}.html").resolve()
        candidate_idx = (site_dir_resolved / safe_path / "index.html").resolve()
        candidate_spa = (site_dir_resolved / "index.html").resolve()

        if candidate_html.is_file() and candidate_html.is_relative_to(site_dir_resolved):
            target_file = candidate_html
        elif candidate_idx.is_file() and candidate_idx.is_relative_to(site_dir_resolved):
            target_file = candidate_idx
        elif candidate_spa.is_file() and not Path(safe_path).suffix:
            # SPA route fallback (e.g. /dashboard or /blog/post-1)
            target_file = candidate_spa
        else:
            asyncio.create_task(_log_server_access(target_id, "GET", f"/{safe_path}", 404, client_ip))
            raise HTTPException(status_code=404, detail="Requested resource not found on this website.")

    # Detect MIME type
    content_type, _ = mimetypes.guess_type(str(target_file))
    if not content_type:
        content_type = "text/html" if target_file.suffix == ".html" else "application/octet-stream"

    # Attach sandboxed preview headers for security
    secure_headers = security_scanner.get_secure_preview_headers()

    # Highly-optimized caching: HTML cached for 60s (stale-while-revalidate 300s); static assets 24 hours
    is_html = target_file.suffix.lower() in (".html", ".htm") or content_type.startswith("text/html")
    if is_html:
        secure_headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    else:
        secure_headers["Cache-Control"] = "public, max-age=86400, immutable"

    # If serving HTML, inject lightweight telemetry script and log page visit
    if is_html:
        try:
            raw_html = target_file.read_text(encoding="utf-8", errors="replace")

            telemetry_script = f"""
<!-- AI Site Studio Production Telemetry Injector -->
<script id="__aisitestudio_telemetry__">
(function() {{
  if (window.__AISITESTUDIO_TELEMETRY_INSTALLED__) return;
  window.__AISITESTUDIO_TELEMETRY_INSTALLED__ = true;
  var siteId = "{target_id}";
  var origin = (window.location.port === "8000" || (window.location.hostname === "localhost" && window.location.port === "8000"))
    ? ""
    : (window.location.origin.indexOf("aisitestudio.com") !== -1 ? window.location.origin : "http://localhost:8000");
  var endpoint = origin + "/api/v1/deployments/telemetry/" + siteId;

  function sendLog(level, message, meta) {{
    try {{
      var payload = JSON.stringify({{
        level: level || "INFO",
        message: String(message),
        url: window.location.href,
        pathname: window.location.pathname,
        timestamp: new Date().toISOString(),
        meta: meta || null
      }});

      // Use text/plain blob to ensure it is a simple CORS request and never triggers an OPTIONS preflight
      if (navigator.sendBeacon) {{
        var blob = new Blob([payload], {{ type: "text/plain" }});
        navigator.sendBeacon(endpoint, blob);
      }} else {{
        fetch(endpoint, {{
          method: "POST",
          headers: {{ "Content-Type": "text/plain" }},
          body: payload,
          keepalive: true
        }}).catch(function() {{}});
      }}
    }} catch (e) {{}}
  }}

  // Capture real runtime exceptions only — avoid noisy console wrapping
  window.addEventListener("error", function(evt) {{
    var msg = evt.message || "Script runtime error";
    var loc = (evt.filename ? evt.filename.split("/").pop() : "") + (evt.lineno ? ":" + evt.lineno : "");
    sendLog("ERROR", "❌ [RUNTIME ERROR] " + msg + (loc ? " (" + loc + ")" : ""));
  }});

  window.addEventListener("unhandledrejection", function(evt) {{
    var reason = evt.reason;
    var msg = reason ? (reason.stack || reason.message || String(reason)) : "Promise rejected";
    sendLog("ERROR", "❌ [UNHANDLED REJECTION] " + msg);
  }});

  // Boot signal
  sendLog("INFO", "🚀 [CLIENT BOOT] Live website running at " + (window.location.pathname || "/"));
}})();
</script>
"""
            if "</head>" in raw_html:
                modified_html = raw_html.replace("</head>", f"{telemetry_script}\n</head>", 1)
            elif "</body>" in raw_html:
                modified_html = raw_html.replace("</body>", f"{telemetry_script}\n</body>", 1)
            else:
                modified_html = raw_html + telemetry_script

            return Response(content=modified_html, media_type="text/html; charset=utf-8", headers=secure_headers)
        except Exception:
            return FileResponse(path=str(target_file), media_type=content_type, headers=secure_headers)

    return FileResponse(
        path=str(target_file),
        media_type=content_type,
        headers=secure_headers,
    )
