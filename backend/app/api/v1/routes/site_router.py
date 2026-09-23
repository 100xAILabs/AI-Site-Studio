"""
Workload Reverse Proxy Router — Serves isolated customer website deployments.
Strict Data Plane Isolation:
- Strictly serves static files from static/deployments/{site_id}/current/
- Implements Content-Security-Policy and isolation headers
- Real-time client & server telemetry injection for continuous monitoring
"""

import os
import asyncio
import mimetypes
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from app.services.security_scanner import security_scanner
from app.core.database import AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentLog
from sqlalchemy import select

router = APIRouter(tags=["Tenant Workload Sites"])

_STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"

_STATIC_ASSET_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif",
    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map", ".mp4"
}


async def _log_server_access(target_id: str, method: str, path: str, status_code: int, client_host: str = ""):
    """Records server-side HTTP request telemetry into the deployment logs asynchronously."""
    # Skip noisy static asset requests for 200 OK to prevent DB connection pool exhaustion
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
    - Clean URL resolution (/about -> /about.html)
    - SPA client-side routing fallback
    - Rate-limited and deduplicated browser console telemetry injection
    """
    # 0. Canonical Trailing Slash Redirect for relative asset integrity
    if not filepath and request and not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        target_url = f"{request.url.path}/"
        if request.url.query:
            target_url += f"?{request.url.query}"
        return RedirectResponse(url=target_url, status_code=308)

    clean_identifier = site_identifier.strip().lower()
    clean_site_id = site_identifier.split(".")[0].upper()

    # 1. Check DB for matching site_id, subdomain, or custom_domain
    resolved_site_id = None
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Deployment.site_id).where(
                (Deployment.site_id == clean_site_id) |
                (Deployment.subdomain == clean_identifier) |
                (Deployment.custom_domain == clean_identifier) |
                (Deployment.subdomain == f"{clean_identifier}.aisitestudio.com")
            ).limit(1)
            res = await session.execute(stmt)
            resolved_site_id = res.scalar_one_or_none()
    except Exception:
        pass

    target_id = (resolved_site_id or clean_site_id).upper()
    site_dir = _DEPLOYMENTS_ROOT / target_id / "current"

    if not site_dir.exists():
        # Check all site folders for matching subdomain
        matching_site = None
        if _DEPLOYMENTS_ROOT.exists():
            for folder in _DEPLOYMENTS_ROOT.iterdir():
                if folder.is_dir() and (folder.name.upper() == target_id or folder.name.upper() == clean_site_id):
                    matching_site = folder / "current"
                    break
        if matching_site and matching_site.exists():
            site_dir = matching_site
        else:
            raise HTTPException(status_code=404, detail=f"Tenant website deployment '{site_identifier}' not found or inactive.")

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

    # Clean URL support: if /about requested, check about.html or about/index.html or SPA fallback
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
    secure_headers["Cache-Control"] = "no-cache, no-store, must-revalidate" if target_file.suffix == ".html" else "public, max-age=300"

    # If serving HTML, inject client telemetry script and log page visit
    if target_file.suffix.lower() in (".html", ".htm") or content_type.startswith("text/html"):
        asyncio.create_task(_log_server_access(target_id, "GET", f"/{safe_path or 'index.html'}", 200, client_ip))
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

  // Rate-limiting & error deduplication state
  var eventCount = 0;
  var maxEventsPerMinute = 35;
  var resetTime = Date.now() + 60000;
  var recentErrors = {{}};

  function sendLog(level, message, meta) {{
    try {{
      var now = Date.now();
      if (now > resetTime) {{
        eventCount = 0;
        resetTime = now + 60000;
        recentErrors = {{}};
      }}
      if (eventCount >= maxEventsPerMinute) return;

      // Deduplicate identical errors within 5 seconds
      if (level === "ERROR") {{
        var errorKey = String(message).slice(0, 120);
        if (recentErrors[errorKey] && (now - recentErrors[errorKey] < 5000)) return;
        recentErrors[errorKey] = now;
      }}

      eventCount++;

      var payload = JSON.stringify({{
        level: level || "INFO",
        message: String(message),
        url: window.location.href,
        pathname: window.location.pathname,
        timestamp: new Date().toISOString(),
        meta: meta || null
      }});

      if (navigator.sendBeacon) {{
        var blob = new Blob([payload], {{ type: "application/json" }});
        navigator.sendBeacon(endpoint, blob);
      }} else {{
        fetch(endpoint, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: payload,
          keepalive: true
        }}).catch(function() {{}});
      }}
    }} catch (e) {{}}
  }}

  function formatArgs(args) {{
    return Array.prototype.slice.call(args).map(function(item) {{
      if (item === null) return "null";
      if (item === undefined) return "undefined";
      if (item instanceof Error) return (item.name || "Error") + ": " + item.message + (item.stack ? "\\n" + item.stack : "");
      if (typeof item === "object") {{
        try {{ return JSON.stringify(item); }} catch(_) {{ return String(item); }}
      }}
      return String(item);
    }}).join(" ");
  }}

  var _log = console.log, _info = console.info, _warn = console.warn, _error = console.error;

  console.log = function() {{
    _log.apply(console, arguments);
    sendLog("INFO", "[BROWSER LOG] " + formatArgs(arguments));
  }};
  console.info = function() {{
    _info.apply(console, arguments);
    sendLog("INFO", "[BROWSER INFO] " + formatArgs(arguments));
  }};
  console.warn = function() {{
    _warn.apply(console, arguments);
    sendLog("WARN", "[BROWSER WARN] " + formatArgs(arguments));
  }};
  console.error = function() {{
    _error.apply(console, arguments);
    sendLog("ERROR", "[BROWSER ERROR] " + formatArgs(arguments));
  }};

  window.addEventListener("error", function(evt) {{
    var msg = evt.message || "Script runtime error";
    var loc = (evt.filename ? evt.filename.split("/").pop() : "") + (evt.lineno ? ":" + evt.lineno : "") + (evt.colno ? ":" + evt.colno : "");
    sendLog("ERROR", "❌ [RUNTIME ERROR] " + msg + (loc ? " (" + loc + ")" : ""));
  }});

  window.addEventListener("unhandledrejection", function(evt) {{
    var reason = evt.reason;
    var msg = reason ? (reason.stack || reason.message || String(reason)) : "Promise rejected";
    sendLog("ERROR", "❌ [UNHANDLED REJECTION] " + msg);
  }});

  // Signal live website active execution
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


