"""
Watermark Service — Handles embedded (inside) multi-page template watermarks,
code-combined runtime assets, license verification, and automatic watermark removal
for Pro subscribers and Extended/Commercial license holders.
"""

import io
import re
import logging
import zipfile
from typing import Optional, Any
from app.models.user import User, UserRole
from app.models.template import Template
from app.models.order import OrderItem

logger = logging.getLogger(__name__)

WATERMARK_HEAD_START = "<!-- SITE_STUDIO_CORE_HEAD_START -->"
WATERMARK_HEAD_END = "<!-- SITE_STUDIO_CORE_HEAD_END -->"
WATERMARK_START_TAG = "<!-- SITE_STUDIO_INSIDE_WATERMARK_START -->"
WATERMARK_END_TAG = "<!-- SITE_STUDIO_INSIDE_WATERMARK_END -->"


def generate_core_css() -> str:
    """Core CSS combined with code for Standard Edition templates."""
    return """/**
 * AI Site Studio Standard Core Stylesheet
 * Required dependencies for Standard Edition templates.
 * (Automatically removed for Pro Subscribers & Extended License holders)
 */

/* 1. All-Over Diagonal Semi-Transparent Watermark Background */
.site-studio-watermark-overlay,
body::before {
  content: "" !important;
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 99990 !important;
  pointer-events: none !important;
  user-select: none !important;
  -webkit-user-select: none !important;
  background-repeat: repeat !important;
  background-size: 360px 200px !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='360' height='200' viewBox='0 0 360 200'%3E%3Cg transform='rotate(-28 180 100)'%3E%3Ctext x='180' y='92' text-anchor='middle' fill='%233730a3' fill-opacity='0.18' stroke='%23ffffff' stroke-width='0.6' stroke-opacity='0.35' font-family='system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif' font-weight='900' font-size='22' letter-spacing='3'%3EAI SITE STUDIO%3C/text%3E%3Ctext x='180' y='118' text-anchor='middle' fill='%231e293b' fill-opacity='0.16' stroke='%23ffffff' stroke-width='0.5' stroke-opacity='0.3' font-family='system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif' font-weight='700' font-size='11' letter-spacing='2'%3E%E2%80%A2 PREVIEW ONLY %E2%80%A2 STANDARD LICENSE %E2%80%A2%3C/text%3E%3C/g%3E%3C/svg%3E") !important;
  opacity: 1 !important;
}

/* 2. Sleek Floating Bottom-Right Watermark & Purchase Badge */
.site-studio-embedded-watermark {
  position: fixed !important;
  bottom: 18px !important;
  right: 18px !important;
  z-index: 999990 !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(99, 102, 241, 0.3) !important;
  border-radius: 9999px !important;
  background: rgba(15, 23, 42, 0.95) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(255, 255, 255, 0.18) !important;
  padding: 6px 14px !important;
  display: flex !important;
  align-items: center !important;
  pointer-events: auto !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.site-studio-embedded-watermark:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 14px 35px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(99, 102, 241, 0.6) !important;
}
.site-studio-watermark-inner {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
}
.site-studio-watermark-link {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  color: #f8fafc !important;
  font-size: 13px !important;
  text-decoration: none !important;
  font-weight: 600 !important;
}
.site-studio-watermark-link:hover {
  color: #38bdf8 !important;
}
.site-studio-watermark-icon {
  color: #818cf8 !important;
}
.site-studio-upgrade-pill {
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
  color: #ffffff !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  letter-spacing: 0.3px !important;
  padding: 5px 12px !important;
  border-radius: 9999px !important;
  text-decoration: none !important;
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.5) !important;
  transition: all 0.2s ease !important;
  white-space: nowrap !important;
}
.site-studio-upgrade-pill:hover {
  background: linear-gradient(135deg, #4338ca, #6d28d9) !important;
  transform: scale(1.03) !important;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.7) !important;
  color: #ffffff !important;
}
@media (max-width: 640px) {
  .site-studio-embedded-watermark {
    bottom: 10px !important;
    right: 10px !important;
    padding: 5px 10px !important;
  }
  .site-studio-upgrade-pill {
    padding: 3px 8px !important;
    font-size: 10px !important;
  }
}
"""


def generate_runtime_js(title: str = "Website Template") -> str:
    """
    Core Runtime JavaScript combined with code for Standard Edition templates.
    Monitors license integrity, required files, and components.
    """
    safe_title = title.replace('"', '\\"')
    return f"""/**
 * AI Site Studio Runtime & License Integrity Guard
 * Standard Edition — Combined code and multi-page attribution.
 * (Automatically removed for Pro Subscribers & Extended License holders)
 */
(function () {{
  "use strict";

  var TEMPLATE_TITLE = "{safe_title}";
  var INTEGRITY_FAILED = false;
  var ALERT_DISPATCHED = false;

  function _sendTamperBeacon(violation) {{
    if (ALERT_DISPATCHED) return;
    ALERT_DISPATCHED = true;
    try {{
      var isLocal = window.location.hostname === "localhost" ||
                    window.location.hostname === "127.0.0.1" ||
                    window.location.protocol === "file:";
      var base = isLocal ? "http://localhost:8000" : "https://ai-site-studio.onrender.com";
      var payload = JSON.stringify({{
        tid: TEMPLATE_TITLE,
        vt: violation || "tamper_detected",
        dm: (window.location && (window.location.host || window.location.hostname)) || "local",
        dt: "Standard Edition license integrity violation"
      }});
      var dest = base + "/api/v1/telemetry/tamper-alert";
      if (navigator.sendBeacon) {{
        navigator.sendBeacon(dest, payload);
      }} else if (window.fetch) {{
        window.fetch(dest, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: payload,
          keepalive: true
        }}).catch(function () {{}});
      }} else {{
        var x = new XMLHttpRequest();
        x.open("POST", dest, true);
        x.setRequestHeader("Content-Type", "application/json");
        x.send(payload);
      }}
    }} catch (e) {{}}
  }}

  function triggerIntegrityError(reason) {{
    if (INTEGRITY_FAILED) return;
    INTEGRITY_FAILED = true;

    console.error("[Site Studio Integrity Error] " + reason);
    console.warn(
      "[Site Studio] This Standard Edition template requires intact attribution files. " +
      "If you wish to remove the watermark without integrity errors, upgrade to a Pro Subscription or Extended License at http://localhost:5173/pricing"
    );

    _sendTamperBeacon(reason);

    if (document.getElementById("site-studio-integrity-overlay")) return;

    var overlay = document.createElement("div");
    overlay.id = "site-studio-integrity-overlay";
    overlay.style.position = "fixed";
    overlay.style.inset = "0";
    overlay.style.backgroundColor = "rgba(11, 15, 25, 0.92)";
    overlay.style.zIndex = "9999999";
    overlay.style.display = "flex";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    overlay.style.padding = "20px";
    overlay.style.backdropFilter = "blur(10px)";
    overlay.style.webkitBackdropFilter = "blur(10px)";
    overlay.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    overlay.innerHTML = [
      '<div style="max-width: 520px; width: 100%; padding: 32px; background: #111827; border: 1px solid #ef4444; border-radius: 18px; color: #f9fafb; text-align: center; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);">',
      '  <div style="width: 52px; height: 52px; margin: 0 auto 16px; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px;">⚠️</div>',
      '  <h2 style="font-size: 20px; font-weight: 800; color: #ffffff; margin-bottom: 8px;">Template Integrity &amp; License Error</h2>',
      '  <p style="font-size: 13px; color: #9ca3af; line-height: 1.6; margin-bottom: 16px;">',
      '    A required Standard Edition code file or attribution component was altered or deleted:<br>',
      '    <strong style="color: #f87171;">' + reason + '</strong>',
      '  </p>',
      '  <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid #1f2937; border-radius: 10px; padding: 12px; margin-bottom: 20px; font-size: 12px; color: #d1d5db; text-align: left;">',
      '    <strong>Why am I seeing this?</strong><br>',
      '    Standard Edition templates are combined with Site Studio runtime files and attribution. Modifying or deleting these files breaks template integrity.',
      '  </div>',
      '  <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">',
      '    <a href="watermark-license.html" style="padding: 10px 20px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; text-decoration: none; border-radius: 10px; font-size: 13px; font-weight: 700;">View License &amp; Upgrade</a>',
      '    <button onclick="location.reload()" style="padding: 10px 20px; background: #1f2937; color: #e5e7eb; border: 1px solid #374151; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;">Restore &amp; Reload</button>',
      '  </div>',
      '</div>'
    ].join("");

    if (document.body) {{
      document.body.appendChild(overlay);
    }} else {{
      document.addEventListener("DOMContentLoaded", function () {{
        document.body.appendChild(overlay);
      }});
    }}
  }}

  function checkIntegrity() {{
    var badge = document.getElementById("site-studio-watermark-badge");
    if (!badge) {{
      triggerIntegrityError("Missing required attribution component (#site-studio-watermark-badge)");
      return;
    }}
    var style = window.getComputedStyle(badge);
    if (style.display === "none" || style.visibility === "hidden" || parseFloat(style.opacity || "1") < 0.1) {{
      triggerIntegrityError("Attribution component cannot be hidden or disabled in Standard Edition");
      return;
    }}
    var overlay = document.getElementById("site-studio-watermark-overlay");
    if (!overlay) {{
      triggerIntegrityError("Missing required background watermark (#site-studio-watermark-overlay)");
      return;
    }}
    var oStyle = window.getComputedStyle(overlay);
    if (oStyle.display === "none" || oStyle.visibility === "hidden" || parseFloat(oStyle.opacity || "1") < 0.1) {{
      triggerIntegrityError("Background watermark overlay cannot be hidden or disabled in Standard Edition");
      return;
    }}
    if (window.location && window.location.protocol && window.location.protocol.indexOf("http") === 0) {{
      try {{
        var xhr = new XMLHttpRequest();
        xhr.open("HEAD", "watermark-license.html", true);
        xhr.onreadystatechange = function () {{
          if (xhr.readyState === 4 && (xhr.status === 404 || xhr.status === 410)) {{
            triggerIntegrityError("Missing required license documentation (watermark-license.html)");
          }}
        }};
        xhr.send();
      }} catch (err) {{}}
    }}
  }}

  // DOM mutation guard: catch removal or tampering of attribution badge
  if (typeof MutationObserver !== "undefined") {{
    var observer = new MutationObserver(function () {{
      checkIntegrity();
    }});
    if (document.documentElement) {{
      observer.observe(document.documentElement, {{ childList: true, subtree: true, attributes: true }});
    }}
  }}

  // Periodic heartbeat verification
  setInterval(checkIntegrity, 3500);

  // Initial check on load
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", checkIntegrity);
  }} else {{
    checkIntegrity();
  }}

  // Global runtime exposure
  window.SiteStudioRuntime = {{
    title: TEMPLATE_TITLE,
    edition: "standard-watermarked",
    version: "2.4.0",
    verifyIntegrity: checkIntegrity
  }};
}})();
"""


def generate_embedded_watermark_html(title: str = "Website Template", relative_prefix: str = "") -> str:
    """Generate the inside watermark badge injected into the body of HTML pages."""
    lic_href = f"{relative_prefix}watermark-license.html"
    return f"""{WATERMARK_START_TAG}
<div class="site-studio-watermark-overlay" id="site-studio-watermark-overlay" aria-hidden="true"></div>
<div class="site-studio-embedded-watermark" id="site-studio-watermark-badge">
  <div class="site-studio-watermark-inner">
    <a href="{lic_href}" class="site-studio-watermark-link" title="Standard Edition Watermarked Template">
      <svg class="site-studio-watermark-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
      </svg>
      <span>Created with <strong>AI Site Studio</strong></span>
    </a>
    <a href="{lic_href}" class="site-studio-upgrade-pill" title="Buy Official License to Remove All Watermarks">
      ⚡ Buy License &bull; Remove Watermark
    </a>
  </div>
</div>
{WATERMARK_END_TAG}"""


def apply_inside_watermark(
    html_content: str,
    title: str = "Website Template",
    is_watermarked: bool = True,
    relative_prefix: str = "",
) -> str:
    """
    Inject or update inside watermark into an HTML page across all pages.
    - Adds head links for core CSS and runtime JS.
    - Adds inside badge before </body>.
    If is_watermarked is False, strips all watermarks and links cleanly.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    # If should not be watermarked, strip it
    if not is_watermarked:
        return strip_inside_watermark(html_content)

    output_html = html_content

    # 1. Inject Head combined code dependencies (CSS & Runtime JS)
    css_path = f"{relative_prefix}assets/css/site-studio-core.css"
    js_path = f"{relative_prefix}assets/js/site-studio-runtime.js"
    head_snippet = f"""{WATERMARK_HEAD_START}
  <link rel="stylesheet" href="{css_path}">
  <script src="{js_path}" defer></script>
{WATERMARK_HEAD_END}"""

    if WATERMARK_HEAD_START not in output_html:
        if "</head>" in output_html:
            output_html = output_html.replace("</head>", f"{head_snippet}\n</head>", 1)
        elif "<head>" in output_html:
            output_html = output_html.replace("<head>", f"<head>\n{head_snippet}", 1)

    # 2. Inject Body inside watermark badge
    if WATERMARK_START_TAG not in output_html:
        watermark_snippet = generate_embedded_watermark_html(title, relative_prefix=relative_prefix)
        if "</body>" in output_html:
            output_html = output_html.replace("</body>", f"\n{watermark_snippet}\n</body>", 1)
        elif "</html>" in output_html:
            output_html = output_html.replace("</html>", f"\n{watermark_snippet}\n</html>", 1)
        else:
            output_html = f"{output_html}\n{watermark_snippet}"

    return output_html


def strip_inside_watermark(html_content: str) -> str:
    """
    Completely remove all inside watermarks, runtime scripts, styles, and tags
    from an HTML page, returning 100% clean, pristine white-label source code.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    cleaned = html_content

    # 1. Strip marked head dependencies
    head_pattern = re.compile(
        rf"{re.escape(WATERMARK_HEAD_START)}[\s\S]*?{re.escape(WATERMARK_HEAD_END)}",
        re.MULTILINE
    )
    cleaned = head_pattern.sub("", cleaned)

    # 2. Strip marked watermark body blocks
    body_pattern = re.compile(
        rf"{re.escape(WATERMARK_START_TAG)}[\s\S]*?{re.escape(WATERMARK_END_TAG)}",
        re.MULTILINE
    )
    cleaned = body_pattern.sub("", cleaned)

    # 3. Fallback: strip any manual references to site-studio-core.css or site-studio-runtime.js
    cleaned = re.sub(
        r'<link[^>]*href=["\'][^"\']*site-studio-core\.css["\'][^>]*>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'<script[^>]*src=["\'][^"\']*site-studio-runtime\.js["\'][^>]*>\s*</script>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'<script[^>]*src=["\'][^"\']*site-studio-runtime\.js["\'][^>]*/>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'<style[^>]*id=["\']site-studio-watermark-styles["\'][^>]*>[\s\S]*?</style>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'<div[^>]*class=["\'][^"\']*site-studio-watermark-overlay[^"\']*["\'][^>]*>[\s\S]*?</div>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r'<div[^>]*class=["\'][^"\']*site-studio-embedded-watermark[^"\']*["\'][^>]*>[\s\S]*?</div>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )

    return cleaned


def generate_license_warning_text(
    title: str = "Website Template",
    buyer_name: str = "Valued Customer",
    template_id: str = "",
) -> str:
    """
    Generates plain-text legal warning notice and code modification rules packaged into downloads.
    """
    return f"""================================================================================
          AI SITE STUDIO — STANDARD EDITION LICENSE & CODE USAGE RULES
================================================================================
Template: {title}
License:  Standard Regular License (Evaluation / Single End-Product)
Issued:   AI Site Studio Platform Licensing

IMPORTANT LEGAL NOTICE:
Please read these terms carefully before editing, running, or deploying this code.
This template package is subject to strict licensing, copyright, and telemetry guards.

1. WATERMARK & ATTRIBUTION INTEGRITY (MANDATORY REQUIREMENT)
--------------------------------------------------------------------------------
• All multi-page embedded watermarks (diagonal semi-transparent "AI SITE STUDIO"
  background pattern) and floating attribution badges (#site-studio-watermark-badge)
  MUST remain visible and unaltered on every HTML page.
• You may NOT hide, obscure, or alter watermark elements using CSS
  (e.g., `display: none`, `opacity: 0`, `visibility: hidden`, or zero font-size).
• The included `watermark-license.html` file and core runtime dependencies
  (`assets/css/site-studio-core.css`, `assets/js/site-studio-runtime.js`) MUST
  remain inside the project root and subdirectories.

2. PERMITTED VS. PROHIBITED CODE MODIFICATIONS
--------------------------------------------------------------------------------
[✓] ALLOWED MODIFICATIONS:
  • Customizing website content, text, headings, and descriptions for your company.
  • Swapping out images, icons, logos, and graphic assets.
  • Adjusting color palettes, typography, and page section layouts.
  • Wiring contact forms, lead capture forms, and backend APIs.
  • Hosting and deploying the site on your personal domain WITH watermarks intact.

[✗] STRICTLY PROHIBITED (LICENSE VIOLATIONS):
  • Removing or modifying the watermark overlay, corner badge, or runtime scripts.
  • Deleting `watermark-license.html` to disguise the template's standard origin.
  • Reselling, re-distributing, sharing, or sub-licensing the source code on other
    marketplaces, GitHub public repos, or file sharing sites.
  • Delivering watermarked Standard templates to clients as custom 100% original work.

3. AUTOMATED TAMPER TELEMETRY & LEGAL ENFORCEMENT
--------------------------------------------------------------------------------
• This template package includes automated client-side and backend runtime integrity
  checks that verify license compliance.
• If attribution badges, watermarks, or license files are altered or deleted, the
  runtime guard immediately blocks the display with a License Integrity Error and
  dispatches a security alert to our platform telemetry receiver.
• Intentional copyright infringement or license stripping will result in immediate
  revocation of all usage rights, DMCA takedown notices, and legal action.

4. NEED 100% WHITE-LABEL (ZERO WATERMARK)?
--------------------------------------------------------------------------------
If you need pristine, unwatermarked source code for commercial client delivery,
agency handoffs, or resale:
  • Upgrade to an active PRO SUBSCRIPTION ($29/month) for unlimited clean downloads.
  • Or purchase an EXTENDED COMMERCIAL LICENSE for this specific template.
  Visit: http://localhost:5173/pricing
================================================================================
"""


def generate_watermark_license_page(title: str = "Website Template", genre: str = "General", author: str = "AI Site Studio", template_id: str = "", api_base_url: str = "") -> str:
    """
    Generates the standalone watermark-license.html page packaged inside normal templates.
    """
    try:
        from app.core.config import settings
        frontend_base = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    except Exception:
        frontend_base = ""

    if not frontend_base:
        frontend_base = "http://localhost:5173"

    marketplace_path = f"/marketplace/{template_id}" if template_id else "/marketplace"
    marketplace_url = f"{frontend_base}{marketplace_path}"
    pricing_url = f"{frontend_base}/pricing"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>License &amp; Watermark Notice — {title}</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #111827;
      --border: #1f2937;
      --text: #f9fafb;
      --text-muted: #9ca3af;
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --accent: #8b5cf6;
      --gold: #f59e0b;
      --gold-bg: rgba(245, 158, 11, 0.1);
      --gold-border: rgba(245, 158, 11, 0.3);
      --emerald: #10b981;
      --emerald-bg: rgba(16, 185, 129, 0.1);
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 40px 20px;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
    }}
    .license-container {{
      max-width: 780px;
      width: 100%;
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 40px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    }}
    .license-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border);
      padding-bottom: 24px;
      margin-bottom: 28px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand-title {{
      font-size: 20px;
      font-weight: 800;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-icon {{
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--primary), var(--accent));
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
    }}
    .badge-status {{
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      color: var(--gold);
      font-size: 12px;
      font-weight: 700;
      padding: 6px 14px;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    h1 {{
      font-size: 28px;
      font-weight: 800;
      margin-bottom: 12px;
      color: #ffffff;
    }}
    .meta-subtitle {{
      color: var(--text-muted);
      font-size: 15px;
      margin-bottom: 28px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 30px;
    }}
    .meta-item strong {{
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 4px;
    }}
    .meta-item span {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
    }}
    .info-card {{
      background: rgba(245, 158, 11, 0.05);
      border: 1px solid var(--gold-border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 28px;
    }}
    .info-card h3 {{
      font-size: 16px;
      color: var(--gold);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .info-card p {{
      font-size: 14px;
      color: #d1d5db;
      line-height: 1.6;
    }}
    .tier-comparison {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }}
    .tier-box {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 22px;
      background: rgba(255, 255, 255, 0.02);
    }}
    .tier-box.active {{
      border-color: var(--gold-border);
      background: rgba(245, 158, 11, 0.03);
    }}
    .tier-box.pro {{
      border-color: rgba(99, 102, 241, 0.4);
      background: rgba(99, 102, 241, 0.05);
      position: relative;
    }}
    .tier-box.pro::before {{
      content: "RECOMMENDED FOR RESALE & CLIENTS";
      position: absolute;
      top: -10px;
      left: 16px;
      background: var(--primary);
      color: white;
      font-size: 9px;
      font-weight: 800;
      padding: 2px 8px;
      border-radius: 9999px;
      letter-spacing: 0.5px;
    }}
    .tier-title {{
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #ffffff;
    }}
    .tier-desc {{
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 14px;
    }}
    .tier-list {{
      list-style: none;
      font-size: 13px;
      color: #e5e7eb;
    }}
    .tier-list li {{
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .tier-list li.check {{
      color: #10b981;
    }}
    .tier-list li.cross {{
      color: #ef4444;
    }}
    .action-row {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 22px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s ease;
      cursor: pointer;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--primary), var(--accent));
      color: #ffffff;
      border: none;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
    }}
    .btn-primary:hover {{
      opacity: 0.95;
      transform: translateY(-1px);
    }}
    .btn-secondary {{
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.05);
    }}
    .footer-note {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 28px;
      text-align: center;
      border-top: 1px solid var(--border);
      padding-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="license-container">
    <div class="license-header">
      <div class="brand-title">
        <div class="brand-icon">S</div>
        <span>AI Site Studio</span>
      </div>
      <div class="badge-status">
        Standard Edition (Watermarked)
      </div>
    </div>

    <h1>{title}</h1>
    <p class="meta-subtitle">Official Template License, Usage Terms &amp; Watermark Notice</p>

    <div class="meta-grid">
      <div class="meta-item">
        <strong>Template Name</strong>
        <span>{title}</span>
      </div>
      <div class="meta-item">
        <strong>Category / Genre</strong>
        <span>{genre}</span>
      </div>
      <div class="meta-item">
        <strong>Template Creator</strong>
        <span>{author}</span>
      </div>
      <div class="meta-item">
        <strong>Current License</strong>
        <span>Regular / Standard (Watermarked)</span>
      </div>
    </div>

    <div class="info-card">
      <h3>⚠️ Notice: Standard Edition Watermarks Active</h3>
      <p>
        This template is currently running under the <strong>Standard Edition</strong> with active multi-page watermarks:
        an all-over semi-transparent background watermark pattern (<code>AI SITE STUDIO</code>) and a floating attribution badge.
        The template code is protected by runtime integrity checks (<code>assets/js/site-studio-runtime.js</code>).
      </p>
    </div>

    <div class="tier-comparison">
      <div class="tier-box active">
        <h4 class="tier-title">Standard Edition (Current)</h4>
        <p class="tier-desc">Combined code with embedded Site Studio background watermark &amp; attribution.</p>
        <ul class="tier-list">
          <li class="cross">✕ All-over semi-transparent background watermark on all pages</li>
          <li class="cross">✕ Floating attribution badge and license runtime guard</li>
          <li class="cross">✕ Cannot resell or deliver as original work to clients</li>
          <li class="check">✓ Full source code access for evaluation</li>
          <li class="check">✓ Responsive mobile reflow</li>
        </ul>
      </div>

      <div class="tier-box pro">
        <h4 class="tier-title">Pro &amp; Extended Commercial License</h4>
        <p class="tier-desc">Automatic watermark removal &amp; full white-label commercial rights.</p>
        <ul class="tier-list">
          <li class="check">✓ <strong>ZERO WATERMARK</strong> (100% White-Label)</li>
          <li class="check">✓ Background watermark pattern completely removed</li>
          <li class="check">✓ All runtime guards and dependencies stripped cleanly</li>
          <li class="check">✓ Full commercial rights to deploy, resell, and deliver to clients</li>
        </ul>
      </div>
    </div>

    <div class="action-row">
      <a href="{marketplace_url}" id="buy-license-btn" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="background: linear-gradient(135deg, #4f46e5, #7c3aed); box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);">
        ⚡ Buy Official Commercial License &amp; Remove All Watermarks
      </a>
      <a href="{pricing_url}" id="pro-sub-btn" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="border-color: rgba(99, 102, 241, 0.5); color: #818cf8;">
        ✦ Pro Subscription ($29/mo) — Unlimited Clean Downloads
      </a>
      <a href="index.html" class="btn btn-secondary">
        Return to Home Page (index.html)
      </a>
    </div>

    <div class="footer-note">
      When you download this template as an active <strong>Pro Creator / Agency Subscriber</strong> or with an <strong>Extended Commercial License</strong>, our platform automatically strips all watermarks and runtime guards, delivering pristine, white-label production files with zero dependencies.
    </div>
  </div>

  <script>
    (function () {{
      try {{
        var buyBtn = document.getElementById("buy-license-btn");
        var proBtn = document.getElementById("pro-sub-btn");
        var isLocal = window.location.hostname === "localhost" ||
                      window.location.hostname === "127.0.0.1" ||
                      window.location.protocol === "file:";
        if (isLocal) {{
          var base = "http://localhost:5173";
          if (buyBtn) buyBtn.href = base + "{marketplace_path}";
          if (proBtn) proBtn.href = base + "/pricing";
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>"""


def generate_commercial_license_page(title: str = "Website Template", buyer_name: str = "Commercial Licensee", license_key: str = "EXT-COMMERCIAL") -> str:
    """
    Generates the COMMERCIAL-LICENSE.html certificate included in clean, unwatermarked templates.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Commercial License Certificate — {title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0b0f19;
      color: #f9fafb;
      padding: 40px 20px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }}
    .cert-card {{
      max-width: 720px;
      width: 100%;
      background: #111827;
      border: 1px solid rgba(16, 185, 129, 0.4);
      border-radius: 20px;
      padding: 40px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }}
    .cert-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1f2937;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .cert-badge {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #10b981;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    h1 {{
      font-size: 26px;
      color: #ffffff;
      margin-bottom: 8px;
    }}
    p {{
      color: #9ca3af;
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 16px;
    }}
    .cert-box {{
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 20px;
      margin: 24px 0;
    }}
    .cert-row {{
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 14px;
    }}
    .cert-row:last-child {{
      border-bottom: none;
    }}
    .cert-label {{
      color: #9ca3af;
    }}
    .cert-val {{
      color: #ffffff;
      font-weight: 600;
    }}
    .cert-rights {{
      list-style: none;
      padding: 0;
      margin: 20px 0;
      color: #e5e7eb;
      font-size: 14px;
    }}
    .cert-rights li {{
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .cert-rights li::before {{
      content: "✓";
      color: #10b981;
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <div class="cert-card">
    <div class="cert-header">
      <div style="font-weight: 800; font-size: 18px; color: #fff;">AI Site Studio</div>
      <div class="cert-badge">✦ White-Label Commercial License</div>
    </div>
    <h1>Certificate of Commercial License &amp; Zero-Watermark Rights</h1>
    <p>This document verifies that this template source code has been delivered in pristine, white-label format with zero watermarks or platform attribution.</p>
    
    <div class="cert-box">
      <div class="cert-row">
        <span class="cert-label">Licensed Product:</span>
        <span class="cert-val">{title}</span>
      </div>
      <div class="cert-row">
        <span class="cert-label">Licensee / Author:</span>
        <span class="cert-val">{buyer_name}</span>
      </div>
      <div class="cert-row">
        <span class="cert-label">License Reference:</span>
        <span class="cert-val">{license_key}</span>
      </div>
      <div class="cert-row">
        <span class="cert-label">Watermark Status:</span>
        <span class="cert-val" style="color: #10b981;">REMOVED &bull; 100% White-Label</span>
      </div>
    </div>

    <ul class="cert-rights">
      <li>Zero watermarks, runtime guards, or external attributions in source files</li>
      <li>Authorized for commercial client projects, production hosting, and SaaS</li>
      <li>Full rights to customize, brand, and sell websites derived from this source</li>
      <li>Lifetime validity under the AI Site Studio Commercial License</li>
    </ul>

    <p style="text-align: center; margin-top: 24px;">
      <a href="index.html" style="color: #6366f1; text-decoration: none; font-weight: 700;">Open Homepage (index.html) &rarr;</a>
    </p>
  </div>
</body>
</html>"""


def user_qualifies_for_clean_template(
    user: Optional[User],
    template: Optional[Template] = None,
    order_item: Optional[OrderItem] = None,
    license_type: Optional[str] = None
) -> bool:
    """
    Determine if a user or transaction qualifies for the zero-watermark clean template.
    Returns True for:
      1. Admins and Super Admins
      2. Users with an active Pro or Agency subscription tier
      3. Orders purchased with Extended, Commercial, or Pro licenses
      4. Template creators who have a Pro subscription
    """
    CLEAN_LICENSES = ("extended", "commercial", "agency", "unlimited", "pro", "full_access", "full-access", "full", "white_label", "whitelabel")
    if not user:
        if license_type and str(license_type).lower() in CLEAN_LICENSES:
            return True
        return False

    # 1. Admin bypass
    role_val = str(getattr(user, "role", "")).lower()
    if "admin" in role_val:
        return True

    # 2. Template Creator bypass
    if template and str(getattr(template, "seller_id", "")) == str(user.id):
        return True

    # 3. Truly free templates
    if template and getattr(template, "is_free", False) and getattr(template, "price", 0) == 0:
        return True

    # 4. Check explicit clean license
    if license_type and str(license_type).lower() in CLEAN_LICENSES:
        return True

    # 5. Check if user is attempting to get an unpurchased paid template clean:
    # Even Extreme and Pro subscribers must pay the base template fee to get clean code!
    if template and not getattr(template, "is_free", False) and getattr(template, "price", 0) > 0 and not order_item:
        return False

    # 6. Pro / Extreme subscribers qualify for clean code on purchased templates without paying extended fee
    sub_tier = str(getattr(user, "subscription_tier", "") or "").lower()
    if sub_tier in ("pro", "extreme", "agency", "creator_pro", "enterprise"):
        return True

    # 7. Any user who purchased the template (order_item is present) receives 100% clean source code (no extra charges)
    if order_item:
        return True

    return False


STEALTH_JS_START = "/* @perf-observer-start */"
STEALTH_JS_END = "/* @perf-observer-end */"
STEALTH_PY_START = "# --- Sys Metrics Collector (Start) ---"
STEALTH_PY_END = "# --- Sys Metrics Collector (End) ---"
STEALTH_NODE_START = "/* @sys-worker-metric-start */"
STEALTH_NODE_END = "/* @sys-worker-metric-end */"


def generate_stealth_telemetry_js(
    template_id: str,
    buyer_email: str = "unknown",
    license_key: str = "STD-LICENSE",
    api_base_url: Optional[str] = None,
) -> str:
    """
    Generates compact, disguised client-side JavaScript telemetry.
    The telemetry endpoint (/api/v1/telemetry/tamper-alert) is encoded as character codes
    so simple search/grep tools cannot find it.
    Silently checks if the watermark badge (#site-studio-watermark-badge) or required elements
    have been stripped or hidden via CSS, and beacons an alert back to the platform.
    """
    base_url = (api_base_url or "").rstrip("/")
    if not base_url:
        import os
        from app.core.config import settings
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        if render_url:
            base_url = render_url
        elif str(getattr(settings, "ENVIRONMENT", "")).lower() in ("production", "prod") or os.getenv("RENDER"):
            base_url = "https://ai-site-studio.onrender.com"
        else:
            base_url = "http://localhost:8000"

    safe_tid = template_id.replace('"', '\\"')
    safe_email = buyer_email.replace('"', '\\"')
    safe_key = license_key.replace('"', '\\"')
    safe_base = base_url.replace('"', '\\"')

    return f"""{STEALTH_JS_START}
/* Layout & Viewport Core Metrics v1.3.2 */
(function () {{
  if (typeof window === "undefined" || typeof document === "undefined") return;
  var _p = [47,97,112,105,47,118,49,47,116,101,108,101,109,101,116,114,121,47,116,97,109,112,101,114,45,97,108,101,114,116];
  var _ep = String.fromCharCode.apply(null, _p);
  var _dest = "{safe_base}" + _ep;
  var _payload = {{
    tid: "{safe_tid}",
    em: "{safe_email}",
    lk: "{safe_key}",
    dm: (window.location && (window.location.host || window.location.hostname)) || "local",
    vt: "watermark_removed"
  }};
  var _reported = false;

  function _sendBeacon(violation) {{
    if (_reported) return;
    _reported = true;
    _payload.vt = violation || "badge_removed";
    try {{
      var dataStr = JSON.stringify(_payload);
      if (navigator.sendBeacon) {{
        navigator.sendBeacon(_dest, dataStr);
      }} else if (window.fetch) {{
        window.fetch(_dest, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: dataStr,
          keepalive: true
        }}).catch(function () {{}});
      }} else {{
        var x = new XMLHttpRequest();
        x.open("POST", _dest, true);
        x.setRequestHeader("Content-Type", "application/json");
        x.send(dataStr);
      }}
    }} catch (e) {{}}
  }}

  function _verifyWatermark() {{
    try {{
      var b = document.getElementById("site-studio-watermark-badge");
      if (!b) {{
        _sendBeacon("badge_element_deleted");
        return;
      }}
      var cs = window.getComputedStyle ? window.getComputedStyle(b) : null;
      if (cs) {{
        if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity || "1") < 0.1) {{
          _sendBeacon("badge_hidden_by_css");
          return;
        }}
        if (parseInt(cs.fontSize || "12", 10) < 2 || parseInt(cs.lineHeight || "12", 10) < 2) {{
          _sendBeacon("badge_collapsed_size");
          return;
        }}
      }}
      if (window.location && window.location.protocol && window.location.protocol.indexOf("http") === 0) {{
        try {{
          var xhr = new XMLHttpRequest();
          xhr.open("HEAD", "watermark-license.html", true);
          xhr.onreadystatechange = function () {{
            if (xhr.readyState === 4 && (xhr.status === 404 || xhr.status === 410)) {{
              _sendBeacon("license_file_missing");
            }}
          }};
          xhr.send();
        }} catch (e) {{}}
      }}
    }} catch (err) {{}}
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", function () {{
      setTimeout(_verifyWatermark, 2500);
    }});
  }} else {{
    setTimeout(_verifyWatermark, 2500);
  }}

  if (typeof MutationObserver !== "undefined") {{
    try {{
      var mo = new MutationObserver(function () {{
        _verifyWatermark();
      }});
      if (document.documentElement) {{
        mo.observe(document.documentElement, {{ childList: true, subtree: true, attributes: true }});
      }}
    }} catch (e) {{}}
  }}
  setInterval(_verifyWatermark, 12000);
}})();
{STEALTH_JS_END}"""


def generate_stealth_backend_python_hook(
    template_id: str,
    buyer_email: str = "unknown",
    license_key: str = "STD-LICENSE",
    api_base_url: Optional[str] = None,
) -> str:
    """
    Generates a stealth backend runtime telemetry hook for Python templates (FastAPI/Django).
    Silently checks if watermark or license documentation files exist in the project root.
    If missing, fires a background HTTP alert to the platform telemetry receiver.
    """
    base_url = (api_base_url or "").rstrip("/")
    if not base_url:
        import os
        from app.core.config import settings
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        if render_url:
            base_url = render_url
        elif str(getattr(settings, "ENVIRONMENT", "")).lower() in ("production", "prod") or os.getenv("RENDER"):
            base_url = "https://ai-site-studio.onrender.com"
        else:
            base_url = "http://localhost:8000"

    safe_tid = template_id.replace('"', '\\"')
    safe_email = buyer_email.replace('"', '\\"')
    safe_key = license_key.replace('"', '\\"')
    safe_base = base_url.replace('"', '\\"')

    return f"""{STEALTH_PY_START}
# System Health & Telemetry Worker v1.0.4
def _sys_telemetry_check():
    import os, threading, urllib.request, json
    def _worker():
        try:
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            p_parents = [curr_dir, os.path.dirname(curr_dir), os.path.dirname(os.path.dirname(curr_dir))]
            lic_files = ["watermark-license.html", "LICENSE-STANDARD-WATERMARKED.html", "license-notice.html"]
            found = any(os.path.exists(os.path.join(p, lf)) for p in p_parents for lf in lic_files)
            if not found:
                ep = bytes.fromhex("2f6170692f76312f74656c656d657472792f74616d7065722d616c657274").decode()
                url = "{safe_base}" + ep
                data = json.dumps({{
                    "tid": "{safe_tid}",
                    "em": "{safe_email}",
                    "lk": "{safe_key}",
                    "vt": "backend_license_file_missing",
                    "dm": "backend-process"
                }}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={{"Content-Type": "application/json"}})
                urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

try:
    _sys_telemetry_check()
except Exception:
    pass
{STEALTH_PY_END}"""


def generate_stealth_backend_node_hook(
    template_id: str,
    buyer_email: str = "unknown",
    license_key: str = "STD-LICENSE",
    api_base_url: Optional[str] = None,
) -> str:
    """
    Generates a stealth backend runtime telemetry hook for Node.js / Express / NestJS templates.
    Silently checks if watermark or license documentation files exist in the project root or parent dirs.
    If missing, fires a background HTTP alert to the platform telemetry receiver.
    """
    base_url = (api_base_url or "").rstrip("/")
    if not base_url:
        import os
        from app.core.config import settings
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        if render_url:
            base_url = render_url
        elif str(getattr(settings, "ENVIRONMENT", "")).lower() in ("production", "prod") or os.getenv("RENDER"):
            base_url = "https://ai-site-studio.onrender.com"
        else:
            base_url = "http://localhost:8000"

    safe_tid = template_id.replace('"', '\\"')
    safe_email = buyer_email.replace('"', '\\"')
    safe_key = license_key.replace('"', '\\"')
    safe_base = base_url.replace('"', '\\"')

    return f"""{STEALTH_NODE_START}
// System Health & Telemetry Worker v1.0.4
(function _sysTelemetryCheck() {{
  try {{
    const fs = require("fs");
    const path = require("path");
    const http = require("http");
    const https = require("https");
    const currDir = __dirname;
    const searchDirs = [currDir, path.resolve(currDir, ".."), path.resolve(currDir, "../..")];
    const licFiles = ["watermark-license.html", "LICENSE-STANDARD-WATERMARKED.html", "license-notice.html"];
    let found = false;
    for (const d of searchDirs) {{
      for (const f of licFiles) {{
        try {{
          if (fs.existsSync(path.join(d, f))) {{
            found = true;
            break;
          }}
        }} catch (_) {{}}
      }}
      if (found) break;
    }}
    if (!found) {{
      const postData = JSON.stringify({{
        tid: "{safe_tid}",
        em: "{safe_email}",
        lk: "{safe_key}",
        vt: "backend_license_file_missing",
        dm: "node-backend"
      }});
      const targetUrl = new URL("{safe_base}/api/v1/telemetry/tamper-alert");
      const client = targetUrl.protocol === "https:" ? https : http;
      const req = client.request(targetUrl, {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData)
        }},
        timeout: 4000
      }});
      req.on("error", function () {{}});
      req.write(postData);
      req.end();
    }}
  }} catch (_) {{}}
}})();
{STEALTH_NODE_END}"""


def strip_stealth_telemetry(content: str) -> str:
    """Safely strips any injected stealth telemetry blocks from JS, Node, or Python code."""
    pattern_js = re.escape(STEALTH_JS_START) + r"[\s\S]*?" + re.escape(STEALTH_JS_END)
    content = re.sub(pattern_js, "", content)
    pattern_py = re.escape(STEALTH_PY_START) + r"[\s\S]*?" + re.escape(STEALTH_PY_END)
    content = re.sub(pattern_py, "", content)
    pattern_node = re.escape(STEALTH_NODE_START) + r"[\s\S]*?" + re.escape(STEALTH_NODE_END)
    content = re.sub(pattern_node, "", content)
    return content.strip()


def process_zip_package(
    zip_bytes: bytes,
    is_clean: bool,
    title: str = "Website Template",
    buyer_name: str = "Valued Customer",
    buyer_email: str = "customer@example.com",
    template_id: str = "template-id",
    license_key: str = "LIC-COMMERCIAL",
    api_base_url: Optional[str] = None,
) -> bytes:
    """
    Process an in-memory ZIP package across ALL kinds of templates:
    - Pure HTML/CSS/JS (single and multi-page)
    - Full-stack projects with frontend (HTML/React/Next/Vue/Vite/Nuxt/Svelte) and backend (FastAPI/Django/Express/NestJS)
    - User-uploaded templates and Studio-generated templates alike.
    
    If is_clean (Pro / Extended):
      Strips all inside watermarks, head links, and runtime JS from all HTML files,
      removes watermark-license.html, assets/js/site-studio-runtime.js, and assets/css/site-studio-core.css,
      strips stealth telemetry from all JS/TS and backend files, and adds COMMERCIAL-LICENSE.html.
    If not is_clean (Standard Edition):
      Ensures inside watermark, background diagonal watermark, head links, and runtime JS are applied
      across ALL HTML files with relative paths, ensures site-studio-runtime.js and
      site-studio-core.css are present in both root and frontend folders, embeds stealth tamper beaconing
      into primary client JS and backend files (both Python and Node.js), and ensures watermark-license.html is present.
    """
    if not zip_bytes:
        return zip_bytes

    try:
        input_zip = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    except Exception as e:
        logger.warning("Could not open zip bytes for watermark processing: %s", e)
        return zip_bytes

    existing_names = [info.filename for info in input_zip.infolist()]

    primary_js_candidate = None
    primary_backend_py = None
    primary_backend_node = None

    if not is_clean:
        # 1. Identify primary client JS / TS / React entrypoint
        for cand in [
            "assets/js/index.js",
            "assets/js/main.js",
            "assets/js/app.js",
            "js/main.js",
            "js/index.js",
            "js/app.js",
            "static/js/main.js",
            "main.js",
            "index.js",
            "frontend/src/main.tsx",
            "frontend/src/main.jsx",
            "frontend/src/App.tsx",
            "frontend/src/App.jsx",
            "client/src/main.tsx",
            "client/src/main.jsx",
            "client/src/App.tsx",
            "client/src/App.jsx",
            "src/main.tsx",
            "src/main.jsx",
            "src/App.tsx",
            "src/App.jsx",
            "src/index.tsx",
            "src/index.js",
            "frontend/assets/js/main.js",
            "frontend/assets/js/index.js",
        ]:
            if cand in existing_names:
                primary_js_candidate = cand
                break

        if not primary_js_candidate:
            for name in existing_names:
                lower = name.lower()
                if (lower.endswith((".js", ".jsx", ".ts", ".tsx"))
                    and "runtime" not in lower
                    and "node_modules" not in lower
                    and "dist/" not in lower
                    and "build/" not in lower
                    and not lower.startswith("backend/")
                    and not lower.startswith("server/")):
                    primary_js_candidate = name
                    break

        # 2. Identify primary backend Python entrypoint
        for cand in [
            "backend/app/main.py",
            "backend/main.py",
            "backend/server.py",
            "backend/app.py",
            "server/main.py",
            "server/app.py",
            "server/server.py",
            "app/main.py",
            "api/main.py",
            "api/index.py",
            "main.py",
            "server.py",
            "app.py",
        ]:
            if cand in existing_names:
                primary_backend_py = cand
                break

        # 3. Identify primary backend Node.js / Express entrypoint
        for cand in [
            "backend/server.js",
            "backend/app.js",
            "backend/index.js",
            "backend/src/server.ts",
            "backend/src/main.ts",
            "backend/src/app.ts",
            "backend/src/index.ts",
            "server/server.js",
            "server/app.js",
            "server/index.js",
            "server/src/server.ts",
            "server/src/index.ts",
            "api/server.js",
            "api/index.js",
        ]:
            if cand in existing_names:
                primary_backend_node = cand
                break

    output_buffer = io.BytesIO()
    with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as output_zip:
        for item in input_zip.infolist():
            content = input_zip.read(item.filename)

            # Skip watermark & runtime files if clean Pro/Extended download
            if is_clean and (
                item.filename.endswith("watermark-license.html")
                or item.filename.endswith("license-notice.html")
                or item.filename.endswith("site-studio-runtime.js")
                or item.filename.endswith("site-studio-core.css")
            ):
                continue

            # 1. HTML files: Strip or inject inside watermark badge
            if item.filename.lower().endswith((".html", ".htm")):
                try:
                    html_text = content.decode("utf-8", errors="replace")
                    if is_clean:
                        modified_html = strip_inside_watermark(html_text)
                    else:
                        if not item.filename.endswith(("watermark-license.html", "COMMERCIAL-LICENSE.html")):
                            # Determine folder depth to compute relative prefix (e.g. "frontend/index.html" -> "../")
                            norm_path = item.filename.replace("\\", "/").lstrip("/")
                            parts = norm_path.split("/")[:-1]
                            rel_prefix = "../" * len(parts) if parts else ""
                            modified_html = apply_inside_watermark(
                                html_text,
                                title=title,
                                is_watermarked=True,
                                relative_prefix=rel_prefix,
                            )
                        else:
                            modified_html = html_text
                    content = modified_html.encode("utf-8")
                except Exception as decode_err:
                    logger.debug("Skipping html transform for %s: %s", item.filename, decode_err)

            # 2. JavaScript / TypeScript files
            elif item.filename.lower().endswith((".js", ".jsx", ".ts", ".tsx")):
                try:
                    js_text = content.decode("utf-8", errors="replace")
                    if is_clean:
                        cleaned_js = strip_stealth_telemetry(js_text)
                        content = cleaned_js.encode("utf-8")
                    elif item.filename == primary_js_candidate:
                        if STEALTH_JS_START not in js_text:
                            stealth_js = generate_stealth_telemetry_js(
                                template_id=template_id,
                                buyer_email=buyer_email,
                                license_key=license_key,
                                api_base_url=api_base_url,
                            )
                            weaved_js = js_text + "\n\n" + stealth_js + "\n"
                            content = weaved_js.encode("utf-8")
                    elif item.filename == primary_backend_node:
                        if STEALTH_NODE_START not in js_text:
                            stealth_node = generate_stealth_backend_node_hook(
                                template_id=template_id,
                                buyer_email=buyer_email,
                                license_key=license_key,
                                api_base_url=api_base_url,
                            )
                            weaved_node = js_text + "\n\n" + stealth_node + "\n"
                            content = weaved_node.encode("utf-8")
                except Exception as decode_err:
                    logger.debug("Skipping JS telemetry transform for %s: %s", item.filename, decode_err)

            # 3. Python backend files
            elif item.filename.lower().endswith(".py"):
                try:
                    py_text = content.decode("utf-8", errors="replace")
                    if is_clean:
                        cleaned_py = strip_stealth_telemetry(py_text)
                        content = cleaned_py.encode("utf-8")
                    elif item.filename == primary_backend_py:
                        if STEALTH_PY_START not in py_text:
                            stealth_py = generate_stealth_backend_python_hook(
                                template_id=template_id,
                                buyer_email=buyer_email,
                                license_key=license_key,
                                api_base_url=api_base_url,
                            )
                            weaved_py = py_text + "\n\n" + stealth_py + "\n"
                            content = weaved_py.encode("utf-8")
                except Exception as decode_err:
                    logger.debug("Skipping Python telemetry transform for %s: %s", item.filename, decode_err)

            output_zip.writestr(item, content)

        # Pro / Extended: Add commercial certificate
        if is_clean:
            comm_cert = generate_commercial_license_page(title=title, buyer_name=buyer_name, license_key=license_key)
            output_zip.writestr("COMMERCIAL-LICENSE.html", comm_cert)
        else:
            # Standard Edition: Ensure runtime JS, core CSS, and watermark license page are embedded
            has_frontend_dir = any(name.startswith("frontend/") for name in existing_names)
            has_client_dir = any(name.startswith("client/") for name in existing_names)
            has_backend_dir = any(name.startswith("backend/") for name in existing_names)
            has_server_dir = any(name.startswith("server/") for name in existing_names)

            stealth_code = generate_stealth_telemetry_js(
                template_id=template_id,
                buyer_email=buyer_email,
                license_key=license_key,
                api_base_url=api_base_url,
            )
            runtime_code = generate_runtime_js(title=title)
            runtime_combined = runtime_code + "\n\n" + stealth_code + "\n"
            core_css = generate_core_css()
            watermark_page = generate_watermark_license_page(
                title=title,
                author=buyer_name,
                template_id=template_id,
                api_base_url=api_base_url,
            )
            warning_notice = generate_license_warning_text(
                title=title,
                buyer_name=buyer_name,
                template_id=template_id,
            )

            # Write to root
            if "LICENSE_WARNING_AND_RULES.txt" not in existing_names:
                output_zip.writestr("LICENSE_WARNING_AND_RULES.txt", warning_notice)
            if "assets/js/site-studio-runtime.js" not in existing_names:
                output_zip.writestr("assets/js/site-studio-runtime.js", runtime_combined)
            if "assets/css/site-studio-core.css" not in existing_names:
                output_zip.writestr("assets/css/site-studio-core.css", core_css)
            if "watermark-license.html" not in existing_names:
                output_zip.writestr("watermark-license.html", watermark_page)

            # If full-stack frontend directory exists, also provide assets inside frontend/
            if has_frontend_dir:
                if "frontend/LICENSE_WARNING_AND_RULES.txt" not in existing_names:
                    output_zip.writestr("frontend/LICENSE_WARNING_AND_RULES.txt", warning_notice)
                if "frontend/assets/js/site-studio-runtime.js" not in existing_names:
                    output_zip.writestr("frontend/assets/js/site-studio-runtime.js", runtime_combined)
                if "frontend/assets/css/site-studio-core.css" not in existing_names:
                    output_zip.writestr("frontend/assets/css/site-studio-core.css", core_css)
                if "frontend/watermark-license.html" not in existing_names:
                    output_zip.writestr("frontend/watermark-license.html", watermark_page)

            # If full-stack client directory exists, also provide assets inside client/
            if has_client_dir:
                if "client/assets/js/site-studio-runtime.js" not in existing_names:
                    output_zip.writestr("client/assets/js/site-studio-runtime.js", runtime_combined)
                if "client/assets/css/site-studio-core.css" not in existing_names:
                    output_zip.writestr("client/assets/css/site-studio-core.css", core_css)
                if "client/watermark-license.html" not in existing_names:
                    output_zip.writestr("client/watermark-license.html", watermark_page)

            # If backend directories exist, also place watermark-license.html inside them so backend guard finds it
            if has_backend_dir and "backend/watermark-license.html" not in existing_names:
                output_zip.writestr("backend/watermark-license.html", watermark_page)
            if has_server_dir and "server/watermark-license.html" not in existing_names:
                output_zip.writestr("server/watermark-license.html", watermark_page)

    return output_buffer.getvalue()
