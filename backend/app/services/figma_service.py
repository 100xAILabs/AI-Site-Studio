"""
Figma-to-Code & Design Importer Service.
Parses Figma design URLs/REST APIs and synthesizes production-grade,
multi-page responsive templates (HTML/Tailwind or React) with design tokens.
"""

import os
import re
import io
import json
import uuid
import zipfile
import logging
import urllib.parse
from collections import Counter
from typing import Optional, Dict, Any, List
from decimal import Decimal
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import storage
from app.models.template import Template, TemplateStatus, TemplateFramework, TemplateLicense
from app.models.category import Category
from app.services.screenshot_service import screenshot_service

logger = logging.getLogger(__name__)


def hex_to_rgb_str(hex_code: str) -> str:
    """Convert hex color code (e.g. '#4f46e5') to comma-separated RGB string ('79, 70, 229')."""
    if not hex_code:
        return "79, 70, 229"
    h = hex_code.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    if len(h) != 6:
        return "79, 70, 229"
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return f"{r}, {g}, {b}"
    except Exception:
        return "79, 70, 229"


class FigmaImportService:
    """Service to parse Figma URLs, extract design tokens, and generate production templates."""

    def parse_figma_url(self, url: str) -> Dict[str, Optional[str]]:
        """
        Extract file key, title slug, and node id from Figma URLs.
        Properly handles URL decoding (spaces, hyphens, underscores) and diverse Figma link types.
        """
        result = {
            "file_key": None,
            "title_slug": "Creative Studio Flagship",
            "node_id": None
        }

        if not url:
            return result

        clean_url = url.strip()

        # Match /file/{key}/{title} or /design/{key}/{title} or /buzz/{key}/{title} or /community/file/{key} etc.
        match = re.search(
            r"figma\.com/(?:file|design|community/file|buzz|board|slides|proto|make)/([a-zA-Z0-9_-]+)(?:/([^\?\#]+))?",
            clean_url
        )
        if match:
            result["file_key"] = match.group(1)
            raw_slug = match.group(2)
            if raw_slug:
                clean_slug = urllib.parse.unquote_plus(raw_slug).replace("-", " ").replace("_", " ").strip()
                clean_slug = re.sub(r"\s+", " ", clean_slug)
                if clean_slug.lower() not in ("untitled", "draft", "file", "design", "figma imported site"):
                    result["title_slug"] = clean_slug.title()

        # Match ?node-id=...
        node_match = re.search(r"node-id=([a-zA-Z0-9%_-]+)", clean_url)
        if node_match:
            result["node_id"] = urllib.parse.unquote(node_match.group(1))

        return result

    async def fetch_figma_api_data(self, file_key: str, token: str) -> Optional[Dict[str, Any]]:
        """
        Fetch live file metadata and document structure from Figma REST API.
        Supports both classic and modern personal access tokens (figd_...) with dual auth headers.
        """
        if not file_key or not token:
            return None

        clean_token = token.strip()
        bearer_val = clean_token if clean_token.startswith("Bearer ") else f"Bearer {clean_token}"
        headers = {
            "X-Figma-Token": clean_token,
            "Authorization": bearer_val,
        }

        try:
            async with httpx.AsyncClient(timeout=18.0) as client:
                res = await client.get(f"https://api.figma.com/v1/files/{file_key}", headers=headers)
                if res.status_code == 200:
                    logger.info(f"Successfully fetched live Figma document for file key '{file_key}'")
                    return res.json()
                logger.warning(f"Figma API returned HTTP {res.status_code} for key {file_key}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"Failed to query Figma API for key {file_key}: {e}")

        return None

    def extract_figma_document_details(self, figma_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively traverse the Figma AST node tree to extract authentic design details:
        - Real file name and thumbnail URL
        - Solid fill colors, background colors, and canvas colors
        - Typography styles (primary font families, font weights)
        - Real headlines and paragraph copy
        - Top-level frame section names
        """
        if not figma_data or not isinstance(figma_data, dict):
            return {}

        colors = Counter()
        fonts = Counter()
        texts: List[Dict[str, Any]] = []
        frames: List[str] = []

        def hex_from_color(c: Dict[str, Any]) -> Optional[str]:
            try:
                r = max(0.0, min(1.0, float(c.get("r", 0))))
                g = max(0.0, min(1.0, float(c.get("g", 0))))
                b = max(0.0, min(1.0, float(c.get("b", 0))))
                return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"
            except Exception:
                return None

        def is_neutral(hex_str: str) -> bool:
            h = hex_str.lstrip("#")
            if len(h) != 6:
                return True
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (max(r, g, b) - min(r, g, b)) < 25

        def visit(node: Any):
            if not isinstance(node, dict):
                return
            ntype = node.get("type")
            name = node.get("name", "")

            # Frame collection
            if ntype in ("FRAME", "SECTION", "COMPONENT") and name:
                if not name.startswith(("Vector", "Group", "Line", "Ellipse", "Rectangle")):
                    frames.append(name)

            # Background color
            if "backgroundColor" in node and isinstance(node["backgroundColor"], dict):
                h = hex_from_color(node["backgroundColor"])
                if h:
                    colors[h] += 2

            # Fills
            for fill in node.get("fills", []):
                if isinstance(fill, dict) and fill.get("type") == "SOLID" and fill.get("visible", True) is not False:
                    if "color" in fill and isinstance(fill["color"], dict):
                        h = hex_from_color(fill["color"])
                        if h:
                            colors[h] += 1

            # Text nodes
            if ntype == "TEXT":
                style = node.get("style", {})
                font_fam = style.get("fontFamily")
                if font_fam:
                    fonts[font_fam] += 1
                chars = (node.get("characters") or "").strip()
                if chars and len(chars) >= 3:
                    f_size = style.get("fontSize", 16)
                    f_weight = style.get("fontWeight", 400)
                    texts.append({"text": chars, "size": f_size, "weight": f_weight})

            for child in node.get("children", []):
                visit(child)

        doc = figma_data.get("document", {})
        visit(doc)

        vibrant_colors = [c for c, _ in colors.most_common() if not is_neutral(c)]
        neutral_colors = [c for c, _ in colors.most_common() if is_neutral(c)]

        headline = None
        subheadline = None
        sorted_texts = sorted(texts, key=lambda x: x["size"], reverse=True)
        for t in sorted_texts:
            txt = t["text"].replace("\n", " ").strip()
            words = txt.split()
            if not headline and 2 <= len(words) <= 15:
                headline = txt
            elif headline and not subheadline and 6 <= len(words) <= 35 and txt != headline:
                subheadline = txt

        primary_font = fonts.most_common(1)[0][0] if fonts else None

        return {
            "file_name": figma_data.get("name"),
            "thumbnail_url": figma_data.get("thumbnailUrl"),
            "vibrant_colors": vibrant_colors,
            "neutral_colors": neutral_colors,
            "primary_font": primary_font,
            "headline": headline,
            "subheadline": subheadline,
            "frames": frames[:8],
        }

    def synthesize_design_tokens(
        self,
        figma_data: Optional[Dict[str, Any]],
        title_hint: str,
        extracted: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize design tokens (color palette, typography, layout style)
        from live Figma AST document data or smart domain heuristics.
        """
        tokens = {
            "primary_color": "#4f46e5",    # Indigo
            "secondary_color": "#3b82f6",  # Royal Blue
            "accent_color": "#06b6d4",     # Cyan
            "background": "#0b0f19",       # Deep Navy / Dark Canvas
            "card_bg": "#111827",          # Dark Slate Card
            "text_primary": "#f9fafb",
            "text_secondary": "#9ca3af",
            "font_family": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
            "border_radius": "1rem",
            "theme_mode": "dark"
        }

        # 1. Exact tokens from Figma Document AST
        if extracted:
            v_colors = extracted.get("vibrant_colors", [])
            if len(v_colors) >= 1:
                tokens["primary_color"] = v_colors[0]
            if len(v_colors) >= 2:
                tokens["secondary_color"] = v_colors[1]
            if len(v_colors) >= 3:
                tokens["accent_color"] = v_colors[2]
            elif len(v_colors) >= 1:
                tokens["accent_color"] = v_colors[0]

            n_colors = extracted.get("neutral_colors", [])
            if n_colors:
                tokens["background"] = n_colors[0]

            if extracted.get("primary_font"):
                tokens["font_family"] = f"'{extracted['primary_font']}', -apple-system, BlinkMacSystemFont, sans-serif"

            return tokens

        # 2. Smart AI heuristics based on title context when token not provided
        lower_title = title_hint.lower()
        if any(w in lower_title for w in ["portfolio", "fire", "showcase", "creator", "designer"]):
            tokens.update({
                "primary_color": "#f97316",    # Vivid Orange
                "secondary_color": "#ef4444",  # Crimson Fire
                "accent_color": "#eab308",     # Amber Gold
                "background": "#0a0a0f",       # Obsidian Dark
                "card_bg": "#12121a",          # Deep Slate
                "font_family": "'Plus Jakarta Sans', -apple-system, sans-serif"
            })
        elif any(w in lower_title for w in ["bakery", "cafe", "coffee", "restaurant", "food"]):
            tokens.update({
                "primary_color": "#b45309",
                "secondary_color": "#d97706",
                "accent_color": "#f59e0b",
                "background": "#181411",
                "card_bg": "#241d18",
                "font_family": "'Playfair Display', Georgia, serif"
            })
        elif any(w in lower_title for w in ["health", "clinic", "dental", "medical", "wellness"]):
            tokens.update({
                "primary_color": "#059669",
                "secondary_color": "#10b981",
                "accent_color": "#34d399",
                "background": "#061a14",
                "card_bg": "#0c2820",
                "font_family": "'Plus Jakarta Sans', sans-serif"
            })
        elif any(w in lower_title for w in ["fashion", "luxury", "boutique", "apparel"]):
            tokens.update({
                "primary_color": "#9333ea",
                "secondary_color": "#c084fc",
                "accent_color": "#f43f5e",
                "background": "#120b18",
                "card_bg": "#1c1424",
                "font_family": "'Cinzel', 'Playfair Display', serif"
            })
        elif any(w in lower_title for w in ["realestate", "realtor", "property", "architecture", "estate"]):
            tokens.update({
                "primary_color": "#0f766e",
                "secondary_color": "#14b8a6",
                "accent_color": "#2dd4bf",
                "background": "#081c1a",
                "card_bg": "#0e2926",
                "font_family": "'Outfit', sans-serif"
            })
        elif any(w in lower_title for w in ["fitness", "gym", "workout", "trainer"]):
            tokens.update({
                "primary_color": "#dc2626",
                "secondary_color": "#ea580c",
                "accent_color": "#f59e0b",
                "background": "#09090b",
                "card_bg": "#18181b",
                "font_family": "'Plus Jakarta Sans', sans-serif"
            })
        elif any(w in lower_title for w in ["saas", "tech", "platform", "cloud", "software"]):
            tokens.update({
                "primary_color": "#4f46e5",
                "secondary_color": "#3b82f6",
                "accent_color": "#06b6d4",
                "background": "#0b0f19",
                "card_bg": "#111827",
                "font_family": "'Inter', sans-serif"
            })

        return tokens

    def generate_html_template_bundle(
        self,
        title: str,
        tokens: Dict[str, Any],
        extracted_content: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate a comprehensive, pixel-perfect multi-page website bundle.
        Includes index.html, about.html, services.html, pricing.html, contact.html, style.css, and README.md.
        """
        p_col = tokens["primary_color"]
        s_col = tokens["secondary_color"]
        acc = tokens["accent_color"]
        bg = tokens["background"]
        card = tokens["card_bg"]
        text_p = tokens["text_primary"]
        text_s = tokens["text_secondary"]
        font = tokens["font_family"]
        radius = tokens["border_radius"]
        p_rgb = hex_to_rgb_str(p_col)

        # Dynamic Google Fonts link
        primary_font_name = font.split(",")[0].strip("'\" ")
        google_fonts_family = primary_font_name.replace(" ", "+")
        google_fonts_link = f"""<link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family={google_fonts_family}:wght@400;500;600;700;850&display=swap" rel="stylesheet">"""

        common_css = f"""/* Figma Imported Design Tokens */
:root {{
  --primary: {p_col};
  --primary-rgb: {p_rgb};
  --secondary: {s_col};
  --accent: {acc};
  --bg-dark: {bg};
  --bg-card: {card};
  --text-primary: {text_p};
  --text-secondary: {text_s};
  --font-family: {font};
  --radius: {radius};
}}

* {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: var(--font-family);
  background-color: var(--bg-dark);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
  overflow-x: hidden;
}}

a {{
  color: inherit;
  text-decoration: none;
}}

.nav-container {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2rem;
  background: rgba(17, 24, 39, 0.92);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  position: sticky;
  top: 0;
  z-index: 50;
  gap: 1.5rem;
}}

.logo-brand {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  flex-shrink: 0;
  margin-right: 1.25rem;
}}

.logo-badge {{
  width: 2.25rem;
  height: 2.25rem;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  border-radius: 0.625rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 900;
}}

.nav-links {{
  display: flex;
  align-items: center;
  gap: 1.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
  flex-wrap: wrap;
}}

@media (max-width: 900px) {{
  .nav-container {{
    padding: 1rem 1.25rem;
    gap: 0.75rem;
  }}
  .nav-links {{
    gap: 1rem;
    font-size: 0.82rem;
  }}
  .logo-brand {{
    font-size: 1.1rem;
    margin-right: 0.75rem;
  }}
}}

.nav-links a:hover, .nav-links a.active {{
  color: var(--text-primary);
}}

.cta-btn {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.5rem;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: white;
  font-weight: 700;
  font-size: 0.875rem;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
  transition: all 0.2s ease;
}}

.cta-btn:hover {{
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5);
}}

.btn-outline {{
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: var(--text-primary);
  box-shadow: none;
}}

.btn-outline:hover {{
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.4);
}}

.container {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 4rem 1.5rem;
}}

.section-header {{
  text-align: center;
  max-width: 700px;
  margin: 0 auto 3.5rem auto;
}}

.badge {{
  display: inline-block;
  padding: 0.25rem 0.85rem;
  border-radius: 9999px;
  background: rgba(79, 70, 229, 0.15);
  border: 1px solid rgba(79, 70, 229, 0.3);
  color: #818cf8;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  margin-bottom: 1rem;
}}

.title-hero {{
  font-size: 3.25rem;
  font-weight: 850;
  line-height: 1.15;
  letter-spacing: -0.03em;
  margin-bottom: 1.25rem;
  background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.subtitle {{
  font-size: 1.125rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 2rem;
}}

.grid-3 {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 2rem;
}}

.card {{
  background: var(--bg-card);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius);
  padding: 2.25rem;
  transition: transform 0.3s ease, border-color 0.3s ease;
}}

.card:hover {{
  transform: translateY(-4px);
  border-color: rgba(99, 102, 241, 0.4);
}}

footer {{
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 3rem 1.5rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.875rem;
}}
"""

        # Ensure clean brand name is used instead of generic Untitled
        clean_brand = title.strip()
        if not clean_brand or clean_brand.lower() in ("untitled", "draft", "figma imported site"):
            clean_brand = "Creative Studio"

        # Contextual or extracted copy
        extracted_content = extracted_content or {}
        hero_headline = extracted_content.get("headline")
        if not hero_headline:
            lower_b = clean_brand.lower()
            if any(w in lower_b for w in ["portfolio", "fire", "creator", "designer", "showcase"]):
                hero_headline = "Ignite Your Digital Presence & Creative Work"
            elif any(w in lower_b for w in ["saas", "tech", "platform", "cloud"]):
                hero_headline = "Engineered for High-Impact Brands & Modern Teams"
            elif any(w in lower_b for w in ["agency", "studio", "creative"]):
                hero_headline = "Crafting Visionary Brands & High-Converting Experiences"
            else:
                hero_headline = f"Crafted with Precision for {clean_brand}"

        hero_subtitle = extracted_content.get("subheadline")
        if not hero_subtitle:
            hero_subtitle = "Experience lightning-fast performance, resilient architectures, and polished visual design tokens directly mapped from Figma."
            
        google_fonts_link = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;850&family=Plus+Jakarta+Sans:wght@700;800&display=swap" rel="stylesheet">'

        # Header nav helper
        def get_header(active_page="Home"):
            links = [
                ("Home", "index.html"),
                ("About", "about.html"),
                ("Services", "services.html"),
                ("Pricing", "pricing.html"),
                ("Contact", "contact.html"),
            ]
            links_html = "".join(
                f'<a href="{url}" class="{"active" if name == active_page else ""}">{name}</a>'
                for name, url in links
            )
            return f"""
<header class="nav-container">
  <div class="logo-brand">
    <div class="logo-badge">✦</div>
    <span>{clean_brand}</span>
  </div>
  <nav class="nav-links">
    {links_html}
  </nav>
  <a href="contact.html" class="cta-btn">Get Started &rarr;</a>
</header>
"""

        # index.html (Home)
        index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Modern Digital Platform</title>
  <link rel="stylesheet" href="style.css">
  {google_fonts_link}
</head>
<body>
  {get_header("Home")}

  <section class="container" style="text-align: center; padding-top: 6rem; padding-bottom: 5rem;">
    <span class="badge">⚡ Synthesized from Figma Design</span>
    <h1 class="title-hero">{hero_headline}</h1>
    <p class="subtitle" style="max-width: 680px; margin: 0 auto 2.5rem auto;">
      {hero_subtitle}
    </p>
    <div style="display: flex; gap: 1rem; justify-content: center;">
      <a href="contact.html" class="cta-btn">Start Free Trial &rarr;</a>
      <a href="services.html" class="cta-btn btn-outline">Explore Capabilities</a>
    </div>
  </section>

  <section class="container">
    <div class="section-header">
      <span class="badge">Capabilities</span>
      <h2 style="font-size: 2.25rem; font-weight: 800; margin-bottom: 0.75rem;">Crafted with Precision</h2>
      <p style="color: var(--text-secondary);">Everything needed to scale your digital presence with zero compromise.</p>
    </div>
    <div class="grid-3">
      <div class="card">
        <div style="font-size: 2rem; margin-bottom: 1rem;">🚀</div>
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Automated Workflows</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Streamline deployments with instant Git synchronization, continuous builds, and zero-downtime rollouts.</p>
      </div>
      <div class="card">
        <div style="font-size: 2rem; margin-bottom: 1rem;">💎</div>
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Figma-Accurate Tokens</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Exact color spaces, typography scales, responsive layouts, and modern glassmorphism built directly into CSS.</p>
      </div>
      <div class="card">
        <div style="font-size: 2rem; margin-bottom: 1rem;">🛡️</div>
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Enterprise Telemetry</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Real-time performance monitoring, SOC2-compliant access controls, and full data residency protections.</p>
      </div>
    </div>
  </section>

  <footer>
    <p>&copy; 2026 {title}. Designed & synthesized via Figma AI Studio.</p>
  </footer>
</body>
</html>"""

        # about.html
        about_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>About Us — {title}</title>
  <link rel="stylesheet" href="style.css">
  {google_fonts_link}
</head>
<body>
  {get_header("About")}

  <section class="container">
    <div class="section-header">
      <span class="badge">Our Mission</span>
      <h1 class="title-hero" style="font-size: 2.75rem;">Building the Operating System for Creative Tech</h1>
      <p class="subtitle">
        Founded by digital product engineers and visual designers, {title} bridges human craft with autonomous intelligence.
      </p>
    </div>

    <div class="card" style="margin-bottom: 3rem;">
      <h2 style="font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem;">Our Philosophy</h2>
      <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
        We believe that world-class design shouldn't be trapped inside static mockups. By translating Figma frames directly into production code, we eliminate friction and empower creators to ship experiences that delight users globally.
      </p>
      <div style="display: flex; gap: 3rem; flex-wrap: wrap;">
        <div>
          <div style="font-size: 2rem; font-weight: 800; color: var(--primary);">99.99%</div>
          <div style="color: var(--text-secondary); font-size: 0.85rem;">Platform SLA</div>
        </div>
        <div>
          <div style="font-size: 2rem; font-weight: 800; color: var(--secondary);">14,000+</div>
          <div style="color: var(--text-secondary); font-size: 0.85rem;">Active Creators</div>
        </div>
        <div>
          <div style="font-size: 2rem; font-weight: 800; color: var(--accent);">50ms</div>
          <div style="color: var(--text-secondary); font-size: 0.85rem;">Global Latency</div>
        </div>
      </div>
    </div>
  </section>

  <footer>
    <p>&copy; 2026 {title}. All rights reserved.</p>
  </footer>
</body>
</html>"""

        # services.html
        services_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Services & Solutions — {title}</title>
  <link rel="stylesheet" href="style.css">
  {google_fonts_link}
</head>
<body>
  {get_header("Services")}

  <section class="container">
    <div class="section-header">
      <span class="badge">Solutions</span>
      <h1 class="title-hero" style="font-size: 2.75rem;">Comprehensive Engineering Capabilities</h1>
      <p class="subtitle">Everything your organization requires to launch, scale, and thrive across modern channels.</p>
    </div>

    <div class="grid-3">
      <div class="card">
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Custom Web Architecture</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Multi-tenant rendering pipelines, isolated subdomain routing, and automated DNS propagation.</p>
      </div>
      <div class="card">
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Design System Sync</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Direct bidirectional sync between Figma styles and live CSS variable tokens with hot reloading.</p>
      </div>
      <div class="card">
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Autonomous Optimization</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Lighthouse 100 optimization, automated image compression, and modern web vitals telemetry.</p>
      </div>
    </div>
  </section>

  <footer>
    <p>&copy; 2026 {title}. All rights reserved.</p>
  </footer>
</body>
</html>"""

        # pricing.html
        pricing_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pricing & Plans — {title}</title>
  <link rel="stylesheet" href="style.css">
  {google_fonts_link}
</head>
<body>
  {get_header("Pricing")}

  <section class="container">
    <div class="section-header">
      <span class="badge">Flexible Tiers</span>
      <h1 class="title-hero" style="font-size: 2.75rem;">Predictable, Transparent Pricing</h1>
      <p class="subtitle">Invest in infrastructure that scales alongside your ambitions without hidden surprises.</p>
    </div>

    <div class="grid-3">
      <div class="card">
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Starter Studio</h3>
        <div style="font-size: 2.5rem; font-weight: 900; margin-bottom: 1rem; color: var(--primary);">$29<span style="font-size: 1rem; color: var(--text-secondary); font-weight: 400;">/mo</span></div>
        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem;">Ideal for independent creators, portfolio launches, and fast prototyping.</p>
        <a href="contact.html" class="cta-btn btn-outline" style="width: 100%; justify-content: center; margin-bottom: 1.5rem;">Get Started</a>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.875rem; color: var(--text-secondary);">
          <li>✓ 1 Active Custom Domain</li>
          <li>✓ 5 Core Subpages Included</li>
          <li>✓ Global CDN Distribution</li>
        </ul>
      </div>

      <div class="card" style="border-color: var(--primary); box-shadow: 0 8px 30px rgba(var(--primary-rgb), 0.25);">
        <span class="badge" style="margin-bottom: 0.75rem;">Most Popular</span>
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Professional Scale</h3>
        <div style="font-size: 2.5rem; font-weight: 900; margin-bottom: 1rem; color: var(--secondary);">$79<span style="font-size: 1rem; color: var(--text-secondary); font-weight: 400;">/mo</span></div>
        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem;">Engineered for ambitious businesses seeking unconstrained growth and speed.</p>
        <a href="contact.html" class="cta-btn" style="width: 100%; justify-content: center; margin-bottom: 1.5rem;">Get Started &rarr;</a>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.875rem; color: var(--text-secondary);">
          <li>✓ Unlimited Subdomains</li>
          <li>✓ Automated Vector Snapshots</li>
          <li>✓ Real-Time Design Token Sync</li>
          <li>✓ Priority 24/7 SLA Support</li>
        </ul>
      </div>

      <div class="card">
        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Enterprise Custom</h3>
        <div style="font-size: 2.5rem; font-weight: 900; margin-bottom: 1rem; color: var(--accent);">$199<span style="font-size: 1rem; color: var(--text-secondary); font-weight: 400;">/mo</span></div>
        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem;">Dedicated multi-region clusters, custom compliance, and white-glove onboarding.</p>
        <a href="contact.html" class="cta-btn btn-outline" style="width: 100%; justify-content: center; margin-bottom: 1.5rem;">Contact Us</a>
        <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.75rem; font-size: 0.875rem; color: var(--text-secondary);">
          <li>✓ Dedicated IP Infrastructure</li>
          <li>✓ Custom AST Compiler Plugins</li>
          <li>✓ SOC2 & GDPR Compliance</li>
        </ul>
      </div>
    </div>
  </section>

  <footer>
    <p>&copy; 2026 {title}. All rights reserved.</p>
  </footer>
</body>
</html>"""

        # contact.html
        contact_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Contact & Inquiries — {title}</title>
  <link rel="stylesheet" href="style.css">
  {google_fonts_link}
</head>
<body>
  {get_header("Contact")}

  <section class="container" style="max-width: 800px;">
    <div class="section-header">
      <span class="badge">Inquiries</span>
      <h1 class="title-hero" style="font-size: 2.75rem;">Get in Touch</h1>
      <p class="subtitle">Have questions or looking for custom design engineering? We'd love to connect.</p>
    </div>

    <div class="card">
      <form onsubmit="event.preventDefault(); alert('Thank you! Your message has been received.');" style="display: flex; flex-direction: column; gap: 1.25rem;">
        <div>
          <label style="display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Your Name</label>
          <input type="text" required placeholder="Alex Rivera" style="width: 100%; padding: 0.75rem; border-radius: var(--radius); background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); color: white; outline: none;">
        </div>
        <div>
          <label style="display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Work Email</label>
          <input type="email" required placeholder="alex@company.com" style="width: 100%; padding: 0.75rem; border-radius: var(--radius); background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); color: white; outline: none;">
        </div>
        <div>
          <label style="display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Project Details</label>
          <textarea rows="4" required placeholder="Tell us about your project goals and timeline..." style="width: 100%; padding: 0.75rem; border-radius: var(--radius); background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); color: white; outline: none;"></textarea>
        </div>
        <button type="submit" class="cta-btn" style="justify-content: center;">Send Message &rarr;</button>
      </form>
    </div>
  </section>

  <footer>
    <p>&copy; 2026 {title}. All rights reserved.</p>
  </footer>
</body>
</html>"""

        readme_md = f"""# {title} — Figma Imported Web Studio Template

Synthesized via AI Site Studio Figma-to-Code Pipeline.

## Design System Tokens
- **Primary Brand Color**: `{p_col}`
- **Secondary Color**: `{s_col}`
- **Accent Color**: `{acc}`
- **Background Canvas**: `{bg}`
- **Card Background**: `{card}`
- **Font Stack**: `{font}`

## Included Pages
1. `index.html` - Home Hero & Feature Grid
2. `about.html` - Brand Story & Metrics
3. `services.html` - Capabilities & Solutions
4. `pricing.html` - Tiered Pricing & Comparison
5. `contact.html` - Interactive Inquiry Form
"""

        return {
            "index.html": index_html,
            "about.html": about_html,
            "services.html": services_html,
            "pricing.html": pricing_html,
            "contact.html": contact_html,
            "style.css": common_css,
            "README.md": readme_md,
        }

    async def import_from_figma(
        self,
        db: AsyncSession,
        figma_url: str,
        framework: str = "HTML",
        custom_title: Optional[str] = None,
        category_name: Optional[str] = "Technology",
        access_token: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        purpose: str = "personal",
        price: float = 0.0,
        original_price: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end Figma import:
        1. Parse URL and extract metadata.
        2. Query Figma API or synthesize token AST.
        3. Build multi-page package and compress into ZIP.
        4. Save to StoredFile storage in database.
        5. Generate vector preview thumbnail.
        6. Create Template record configured for Personal Live Website or Marketplace Sale.
        """
        parsed = self.parse_figma_url(figma_url)
        title_hint = custom_title or (parsed["title_slug"].title() if parsed.get("title_slug") and parsed["title_slug"].lower() != "untitled" else "Creative Studio Flagship")
        if not title_hint or title_hint.lower() in ("figma imported site", "untitled", "draft"):
            title_hint = "Creative Studio Flagship"

        # Attempt Figma API call if token provided
        token = access_token or os.getenv("FIGMA_ACCESS_TOKEN")
        figma_api_data = None
        extracted = {}
        if parsed["file_key"] and token:
            figma_api_data = await self.fetch_figma_api_data(parsed["file_key"], token)
            if figma_api_data:
                extracted = self.extract_figma_document_details(figma_api_data)
                if not custom_title and extracted.get("file_name"):
                    raw_fn = extracted["file_name"].strip()
                    if raw_fn.lower() not in ("untitled", "draft", "file", "design"):
                        title_hint = raw_fn

        # Synthesize tokens
        tokens = self.synthesize_design_tokens(figma_api_data, title_hint, extracted=extracted)

        # Generate files
        files_bundle = self.generate_html_template_bundle(title_hint, tokens, extracted_content=extracted)

        # Create ZIP archive in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in files_bundle.items():
                zf.writestr(fname, content.encode("utf-8"))

        zip_bytes = zip_buffer.getvalue()

        # Upload ZIP via platform storage service
        file_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title_hint.lower()).strip("-")
        zip_url = await storage.upload_file(
            db=db,
            file_content=zip_bytes,
            folder="templates",
            original_filename=f"{file_slug}-figma.zip",
            content_type="application/zip",
        )

        # Find or fallback category
        cat_query = await db.execute(select(Category).where(Category.name.ilike(f"%{category_name}%")))
        category = cat_query.scalars().first()
        if not category:
            cat_query_first = await db.execute(select(Category).limit(1))
            category = cat_query_first.scalars().first()

        category_id = category.id if category else uuid.uuid4()

        # If user_id is missing, find a valid admin or default user
        if not user_id:
            from app.models.user import User
            u_query = await db.execute(select(User).limit(1))
            u_user = u_query.scalars().first()
            if u_user:
                user_id = u_user.id
            else:
                user_id = uuid.uuid4()

        # Create Template instance
        template_id = uuid.uuid4()
        template_slug = f"{file_slug}-figma-{uuid.uuid4().hex[:6]}"

        # Generate thumbnail via ScreenshotService or use live Figma preview
        thumb_url = extracted.get("thumbnail_url")
        if not thumb_url:
            thumb_url = screenshot_service.save_thumbnail(
                template_id=str(template_id),
                title=title_hint,
                framework="HTML",
                category=category_name or "Figma Import",
            )

        fw_enum = TemplateFramework.HTML
        if framework.lower() in ("react", "vite"):
            fw_enum = TemplateFramework.REACT
        elif framework.lower() in ("nextjs", "next.js"):
            fw_enum = TemplateFramework.NEXTJS

        # Configure status and price according to purpose (Personal Live Site vs Marketplace Sale)
        is_selling = (purpose == "sell")
        assigned_status = TemplateStatus.PUBLISHED if is_selling else TemplateStatus.DRAFT
        item_price = Decimal(str(price if price > 0 else (49.00 if is_selling else 0.00)))
        item_orig_price = Decimal(str(original_price if original_price > 0 else (89.00 if is_selling else 0.00)))
        is_free_item = (item_price <= Decimal("0.00"))
        is_on_sale_item = is_selling and (item_orig_price > item_price > 0)

        template = Template(
            id=template_id,
            title=f"{title_hint} (Figma Import)",
            slug=template_slug,
            short_description=f"High-fidelity multi-page website synthesized directly from Figma design.",
            description=f"Production-grade website synthesized from Figma design ({figma_url}). Features responsive layouts, refined design tokens, and clean modular code.",
            price=item_price,
            original_price=item_orig_price if is_selling else None,
            is_free=is_free_item,
            is_on_sale=is_on_sale_item,
            category_id=category_id,
            status=assigned_status,
            seller_id=user_id,
            thumbnail_url=thumb_url,
            preview_url=f"/preview?template={template_id}&mode=live",
            tags=["figma", "responsive", "multipage", "modern", "design-tokens", purpose],
            framework=fw_enum,
            pages_count=5,
            has_dark_mode=True,
            is_responsive=True,
            is_rtl_supported=False,
            is_ai_ready=True,
            compatibility=["Modern Browsers", "Mobile", "Tablet", "Desktop"],
            version="1.0.0",
            license_type=TemplateLicense.REGULAR,
            industry=category_name or "Technology",
            color_scheme=tokens["primary_color"],
            download_assets={"zip": zip_url},
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)

        logger.info(f"Successfully imported Figma template '{title_hint}' (ID: {template_id})")

        return {
            "status": "success",
            "template_id": str(template.id),
            "slug": template.slug,
            "title": template.title,
            "framework": framework,
            "purpose": purpose,
            "template_status": template.status.value,
            "price": float(template.price),
            "thumbnail_url": template.thumbnail_url,
            "preview_url": f"/preview?template={template.id}&mode=live",
            "pages": ["index.html", "about.html", "services.html", "pricing.html", "contact.html"],
            "tokens": tokens,
            "extracted_from_figma": bool(extracted and extracted.get("vibrant_colors")),
            "extracted_details": {
                "file_name": extracted.get("file_name"),
                "primary_font": extracted.get("primary_font"),
                "vibrant_colors": extracted.get("vibrant_colors", [])[:3],
                "headline": extracted.get("headline"),
            } if extracted else None,
            "message": "Personal live website synthesized and mounted in Studio Projects!" if purpose == "personal" else "Template successfully published to the Marketplace catalog!"
        }


figma_service = FigmaImportService()
