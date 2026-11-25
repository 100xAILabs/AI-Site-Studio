"""
Workload Reverse Proxy Router — Serves isolated customer website deployments.
Strict Data Plane Isolation:
- Strictly serves static files from static/deployments/{site_id}/current/
- Implements Content-Security-Policy and isolation headers
- High-performance in-memory site resolution caching (sub-millisecond static serving)
- Lightweight runtime error reporting without CORS preflight overhead
"""

import os
import html
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
from sqlalchemy import select, func

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


def invalidate_site_cache(
    site_id: str | None = None,
    subdomain: str | None = None,
    domain: str | None = None,
) -> None:
    """Clear cached resolution entries whenever site files, status, or domains change."""
    candidates = []
    for raw in (site_id, subdomain, domain):
        if raw:
            clean = str(raw).strip().lower()
            candidates.extend([clean, clean.upper(), clean.split(".")[0], clean.split(".")[0].upper()])
            if clean.startswith("www."):
                candidates.append(clean[4:])
    for key in candidates:
        _SITE_RESOLUTION_CACHE.pop(key, None)


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
    branding_meta = None

    if cached and (now - cached[2] < _CACHE_TTL_SECONDS):
        trial_exp_ts = cached[3] if len(cached) > 3 else None
        branding_meta = cached[4] if len(cached) > 4 else None
        if trial_exp_ts and now > trial_exp_ts:
            return HTMLResponse(
                "<!doctype html><html><head><meta charset='utf-8'><title>Trial Expired — AI Site Studio</title>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<style>body{background:#09090b;color:#f4f4f5;font-family:sans-serif;margin:0;padding:2rem;display:flex;align-items:center;justify-content:center;min-height:100vh} "
                ".card{background:#121216;border:1px solid #27272a;border-radius:1rem;padding:2.5rem;max-width:540px;width:100%;text-align:center} "
                "h1{color:#dfb180;font-size:1.5rem;margin:0 0 0.75rem} .btn{display:inline-block;background:#c89666;color:#09090b;font-weight:800;text-decoration:none;padding:0.75rem 1.75rem;border-radius:0.75rem;font-size:0.875rem}</style></head>"
                "<body><div class='card'><h1>7-Day Free Trial Expired</h1><p>Upgrade to Studio Pro to restore permanent live cloud edge hosting.</p><a class='btn' href='/pricing'>Upgrade to Pro</a></div></body></html>",
                status_code=402,
            )
        target_id = cached[0]
        cached_path = Path(cached[1])
        if cached_path.exists():
            site_dir = cached_path

    # If still not found or not cached, check DB for matching site_id, subdomain, or verified custom_domain
    if not site_dir:
        resolved_site_id = None
        trial_exp_timestamp = None
        deployment = None
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Deployment).where(
                    (Deployment.site_id == clean_site_id) |
                    (Deployment.subdomain == clean_identifier) |
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
                        now_utc = datetime.now(timezone.utc)
                        trial_exp = (
                            deployment.trial_expires_at
                            if (deployment.trial_expires_at and deployment.trial_expires_at.tzinfo)
                            else (deployment.trial_expires_at.replace(tzinfo=timezone.utc) if deployment.trial_expires_at else None)
                        )
                        if trial_exp:
                            trial_exp_timestamp = trial_exp.timestamp()
                        if trial_exp and now_utc > trial_exp:
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
                                f"<p>The 7-day free trial period for <strong>{html.escape(str(deployment.project_name or 'this website'))}</strong> has ended. Upgrade to <strong>Studio Pro</strong> to restore permanent live cloud edge hosting and connect custom domains.</p>"
                                "<a class='btn' href='/pricing'>Upgrade to Pro &amp; Restore Live Site</a>"
                                "</div></body></html>",
                                status_code=402,
                            )
        except Exception:
            from app.core.config import settings
            if settings.ENVIRONMENT == "production":
                return HTMLResponse("Hosting status is temporarily unavailable.", status_code=503)

        if not deployment:
            raise HTTPException(status_code=404, detail=f"Tenant website deployment '{site_identifier}' not found or inactive.")

        target_id = (resolved_site_id or clean_site_id).upper()
        site_dir = _DEPLOYMENTS_ROOT / target_id / "current"

        if not site_dir.exists():
            from app.services.deployment_deep_analyzer import _resolve_site_current_dir
            deep_dir = _resolve_site_current_dir(deployment, target_id)
            if deep_dir and deep_dir.exists():
                site_dir = deep_dir

        if not site_dir or not site_dir.exists():
            raise HTTPException(status_code=404, detail=f"Tenant website deployment '{site_identifier}' not found or inactive.")

        branding_meta = (deployment.extra_metadata or {}).get("creator_branding") or (deployment.env_vars or {}).get("__creator_branding__")
        if not branding_meta and deployment.template_id:
            try:
                from app.models.template import Template
                from app.models.user import User
                async with AsyncSessionLocal() as s2:
                    t_res = await s2.execute(select(Template).where(Template.id == deployment.template_id))
                    t_obj = t_res.scalar_one_or_none()
                    if t_obj and t_obj.seller_id:
                        s_res = await s2.execute(select(User).where(User.id == t_obj.seller_id))
                        seller_u = s_res.scalar_one_or_none()
                        if seller_u:
                            branding_meta = {
                                "creator_id": str(seller_u.id),
                                "brand_name": seller_u.creator_brand_name or seller_u.full_name or seller_u.username or "Studio Creator",
                                "creator_slug": seller_u.creator_store_slug or "",
                                "logo_url": seller_u.creator_logo_url or seller_u.avatar_url or "",
                                "support_email": seller_u.creator_support_email or seller_u.email or "",
                                "storefront_url": f"/creator/{seller_u.creator_store_slug}" if seller_u.creator_store_slug else None,
                                "badge_text": f"Deployed by {seller_u.creator_brand_name or seller_u.full_name or 'Creator'}",
                            }
            except Exception:
                pass

        _SITE_RESOLUTION_CACHE[clean_identifier] = (target_id, str(site_dir), now, trial_exp_timestamp, branding_meta)
        _SITE_RESOLUTION_CACHE[clean_site_id] = (target_id, str(site_dir), now, trial_exp_timestamp, branding_meta)

    client_ip = request.client.host if request and request.client else ""

    # Sanitize requested file path and enforce directory jail to prevent LFI
    safe_path = filepath.strip("/\\")
    path_segments = [seg for seg in safe_path.replace("\\", "/").split("/") if seg]
    if any(seg != ".well-known" and seg.startswith(".") for seg in path_segments):
        raise HTTPException(status_code=403, detail="Access denied: Restricted configuration path.")

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

            if branding_meta:
                import html as html_lib
                import re as re_lib
                b_name = html_lib.escape(str(branding_meta.get("brand_name") or "Creator"), quote=True)
                raw_slug = re_lib.sub(r"[^a-zA-Z0-9_-]", "", str(branding_meta.get("creator_slug") or ""))
                b_slug = html_lib.escape(raw_slug, quote=True)
                raw_logo = str(branding_meta.get("logo_url") or "").strip()
                safe_logo = ""
                if raw_logo and (
                    raw_logo.startswith("https://")
                    or raw_logo.startswith("http://")
                    or (raw_logo.startswith("/") and not raw_logo.startswith("//"))
                ):
                    safe_logo = html_lib.escape(raw_logo, quote=True)
                b_storefront = f"/creator/{b_slug}" if b_slug else "/"
                if safe_logo:
                    logo_icon_html = f'<img src="{safe_logo}" alt="{b_name}" class="creator-badge-logo" onerror="this.style.display=\'none\'" />'
                else:
                    logo_icon_html = '✦'
                creator_badge = f"""
<!-- Creator Deployment Branding Engine -->
<aside id="__creator_deployment_badge__" class="creator-deployment-badge" aria-label="Creator Branding Badge">
  <a href="{b_storefront}" target="_blank" rel="noopener noreferrer" class="creator-badge-link" title="Crafted &amp; Deployed by {b_name}">
    <span class="creator-badge-icon">
      {logo_icon_html}
    </span>
    <span class="creator-badge-text">Deployed by <strong>{b_name}</strong></span>
    <span class="creator-badge-arrow">↗</span>
  </a>
</aside>
<style id="__creator_deployment_badge_style__">
  .creator-deployment-badge {{
    position: fixed !important;
    bottom: 18px !important;
    right: 18px !important;
    z-index: 2147483647 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    pointer-events: auto !important;
  }}
  .creator-badge-link {{
    display: inline-flex !important;
    align-items: center !important;
    gap: 7px !important;
    padding: 7px 14px 7px 10px !important;
    border-radius: 9999px !important;
    background: rgba(18, 22, 32, 0.94) !important;
    color: #f4f4f5 !important;
    border: 1px solid rgba(223, 177, 128, 0.45) !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6), 0 0 12px rgba(223, 177, 128, 0.15) !important;
    text-decoration: none !important;
    font-size: 12px !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
  }}
  .creator-badge-link:hover {{
    transform: translateY(-2px) !important;
    border-color: #dfb180 !important;
    background: rgba(26, 32, 48, 0.98) !important;
    box-shadow: 0 14px 30px rgba(0, 0, 0, 0.75), 0 0 18px rgba(223, 177, 128, 0.3) !important;
    color: #ffffff !important;
  }}
  .creator-badge-icon {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 20px !important;
    height: 20px !important;
    border-radius: 50% !important;
    background: rgba(223, 177, 128, 0.2) !important;
    color: #dfb180 !important;
    font-size: 11px !important;
    overflow: hidden !important;
    flex-shrink: 0 !important;
  }}
  .creator-badge-logo {{
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
  }}
  .creator-badge-text {{
    color: #e4e4e7 !important;
    font-size: 12px !important;
    letter-spacing: -0.01em !important;
  }}
  .creator-badge-text strong {{
    color: #dfb180 !important;
    font-weight: 700 !important;
  }}
  .creator-badge-arrow {{
    color: #a1a1aa !important;
    font-size: 11px !important;
    margin-left: 2px !important;
  }}
</style>
"""
                if "</body>" in modified_html:
                    modified_html = modified_html.replace("</body>", f"{creator_badge}\n</body>", 1)
                else:
                    modified_html += f"\n{creator_badge}"

            return Response(content=modified_html, media_type="text/html; charset=utf-8", headers=secure_headers)
        except Exception:
            return FileResponse(path=str(target_file), media_type=content_type, headers=secure_headers)

    return FileResponse(
        path=str(target_file),
        media_type=content_type,
        headers=secure_headers,
    )
