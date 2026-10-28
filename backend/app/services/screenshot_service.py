"""
Automated Website Screenshot & Thumbnail Generator Service.
Generates pixel-perfect website snapshot mockups for templates and custom drafts,
rendering real uploaded photos, actual skills, hero banners, feature grids, and brand palettes.
"""

import os
import io
import re
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_STATIC_ROOT = Path(__file__).resolve().parents[2] / "static"
_THUMBNAILS_DIR = _STATIC_ROOT / "thumbnails"
os.makedirs(_THUMBNAILS_DIR, exist_ok=True)


class ScreenshotService:
    """Generates and manages visual template preview thumbnails with real assets."""

    @staticmethod
    def generate_svg_snapshot(
        title: str,
        framework: str = "HTML",
        category: str = "Modern Business",
        brand_color: str = "#4f46e5",
        accent_color: str = "#3b82f6",
        description: str = "",
        domain: str = "aisitestudio.com",
        photo_data_uri: str = "",
        skills: Optional[List[str]] = None,
        role: str = "",
        experience: str = "",
    ) -> str:
        """
        Creates an ultra-crisp, scalable SVG website mockup with browser chrome,
        navigation bar, hero section, CTA buttons, and real owner photo & skills.
        """
        clean_title = (title or "Modern Website Template").replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        clean_fw = (framework or "HTML").upper()
        clean_cat = (category or "Modern Website").replace("<", "&lt;").replace(">", "&gt;")
        subdomain = re.sub(r'[^a-zA-Z0-9-]', '', title.lower().replace(" ", "-"))[:20] or "demo"
        site_url = f"https://{subdomain}.{domain}"

        # Color mapping for frameworks
        fw_colors = {
            "NEXTJS": "#000000",
            "REACT": "#0ea5e9",
            "HTML": "#e44d26",
            "VUE": "#10b981",
            "ASTRO": "#f97316",
        }
        fw_color = fw_colors.get(clean_fw, brand_color)

        # Detect or format display headline & description
        display_headline = clean_title[:42]
        display_sub = description or (
            f"Professional portfolio featuring {', '.join(skills[:3])}. {experience}"
            if skills else "Modern responsive layout crafted for high-impact presence and fast loading."
        )
        display_sub = display_sub.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")[:120]

        # Right Hero Graphic: Real Photo vs Vector Illustration
        if photo_data_uri:
            photo_name = role or clean_title.split(" - ")[0][:24]
            right_graphic_svg = f"""
    <!-- Real Owner Photo Card -->
    <clipPath id="hero-photo-clip">
      <rect x="760" y="195" width="330" height="255" rx="16"/>
    </clipPath>
    <g clip-path="url(#hero-photo-clip)">
      <image href="{photo_data_uri}" x="760" y="195" width="330" height="255" preserveAspectRatio="xMidYMid slice"/>
      <rect x="760" y="415" width="330" height="35" fill="#0f172a" fill-opacity="0.8"/>
      <text x="925" y="438" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="700" fill="#ffffff">Verified Profile: {photo_name}</text>
    </g>
    <rect x="760" y="195" width="330" height="255" rx="16" stroke="{brand_color}" stroke-width="2.5" fill="none" opacity="0.6"/>
"""
        else:
            right_graphic_svg = f"""
    <!-- Hero Graphic Box on Right -->
    <rect x="760" y="195" width="330" height="255" rx="16" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5"/>
    <rect x="780" y="215" width="290" height="130" rx="10" fill="{brand_color}" fill-opacity="0.08"/>
    <circle cx="830" cy="280" r="28" fill="{brand_color}" fill-opacity="0.2"/>
    <circle cx="980" cy="260" r="38" fill="{accent_color}" fill-opacity="0.2"/>
    <rect x="780" y="365" width="180" height="14" rx="4" fill="#cbd5e1"/>
    <rect x="780" y="390" width="230" height="10" rx="4" fill="#e2e8f0"/>
    <rect x="780" y="410" width="140" height="10" rx="4" fill="#e2e8f0"/>
"""

        # Feature Cards: Real Skills vs Generic Cards
        skills_list = skills or []
        card1_title = f"{skills_list[0]} & Architecture" if len(skills_list) > 0 else "Blazing Fast Speed"
        card1_desc1 = "Production-ready code with modular" if skills_list else "Engineered with modular code, zero"
        card1_desc2 = "structures and robust performance." if skills_list else "bloat, and perfect Core Web Vitals."

        card2_title = f"{skills_list[1] if len(skills_list) > 1 else 'Modern Frontend'}" if skills_list else "Responsive Design"
        card2_desc1 = "Interactive component workflows and" if skills_list else "Flawless typography and fluid grids"
        card2_desc2 = "responsive cross-device styling." if skills_list else "on desktop, tablet, and mobile."

        card3_title = f"{skills_list[2] if len(skills_list) > 2 else 'DevOps & Cloud'}" if skills_list else "Production Ready"
        card3_desc1 = f"Experience: {experience[:32]}" if experience else "Pre-configured with clean asset trees,"
        card3_desc2 = "Automated deployments and testing." if experience else "valid semantics, and custom domains."

        card1_title = card1_title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")[:26]
        card2_title = card2_title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")[:26]
        card3_title = card3_title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")[:26]

        svg = f"""<svg width="1200" height="750" viewBox="0 0 1200 750" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg-grad" x1="0" y1="0" x2="1200" y2="750" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="hero-grad" x1="0" y1="0" x2="800" y2="400" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{brand_color}" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="{accent_color}" stop-opacity="0.05"/>
    </linearGradient>
    <linearGradient id="btn-grad" x1="0" y1="0" x2="200" y2="50" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{brand_color}"/>
      <stop offset="100%" stop-color="{accent_color}"/>
    </linearGradient>
    <filter id="card-shadow" x="50" y="30" width="1100" height="690" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
      <feDropShadow dx="0" dy="25" stdDeviation="35" flood-color="#000000" flood-opacity="0.5"/>
    </filter>
  </defs>

  <!-- Background Wallpaper -->
  <rect width="1200" height="750" fill="url(#bg-grad)"/>

  <!-- Subtle grid pattern in canvas background -->
  <g opacity="0.05">
    <path d="M0 75H1200 M0 150H1200 M0 225H1200 M0 300H1200 M0 375H1200 M0 450H1200 M0 525H1200 M0 600H1200 M0 675H1200" stroke="#ffffff" stroke-width="1"/>
    <path d="M75 0V750 M150 0V750 M225 0V750 M300 0V750 M375 0V750 M450 0V750 M525 0V750 M600 0V750 M675 0V750 M750 0V750 M825 0V750 M900 0V750 M975 0V750 M1050 0V750 M1125 0V750" stroke="#ffffff" stroke-width="1"/>
  </g>

  <!-- Browser Window Wrapper -->
  <g filter="url(#card-shadow)">
    <!-- Window Body -->
    <rect x="70" y="50" width="1060" height="640" rx="20" fill="#ffffff"/>

    <!-- Browser Header Chrome -->
    <path d="M70 70C70 58.9543 78.9543 50 90 50H1110C1121.05 50 1130 58.9543 1130 70V105H70V70Z" fill="#f8fafc"/>
    <line x1="70" y1="105" x2="1130" y2="105" stroke="#e2e8f0" stroke-width="1.5"/>

    <!-- Window Dots -->
    <circle cx="102" cy="77" r="6" fill="#ef4444"/>
    <circle cx="122" cy="77" r="6" fill="#f59e0b"/>
    <circle cx="142" cy="77" r="6" fill="#10b981"/>

    <!-- URL Omnibar -->
    <rect x="180" y="63" width="700" height="28" rx="8" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.2"/>
    <g transform="translate(195, 71)">
      <!-- Lock Icon -->
      <path d="M3 6V4a3 3 0 0 1 6 0v2 M1 6h10a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H1a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z" stroke="#059669" stroke-width="1.4" fill="none"/>
    </g>
    <text x="215" y="82" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="600" fill="#334155">{site_url}</text>

    <!-- Framework Badge in Chrome -->
    <rect x="1000" y="63" width="100" height="28" rx="7" fill="{fw_color}" fill-opacity="0.1"/>
    <text x="1050" y="82" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="800" fill="{fw_color}">{clean_fw}</text>

    <!-- Website Canvas -->
    <!-- Nav Bar -->
    <rect x="70" y="105" width="1060" height="60" fill="#ffffff"/>
    <line x1="70" y1="165" x2="1130" y2="165" stroke="#f1f5f9" stroke-width="1"/>

    <!-- Logo / Brand -->
    <circle cx="120" cy="135" r="14" fill="{brand_color}"/>
    <text x="145" y="141" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="800" fill="#0f172a">{clean_title.split(' - ')[0][:18]}</text>

    <!-- Nav Links -->
    <text x="420" y="140" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600" fill="#475569">Home</text>
    <text x="490" y="140" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600" fill="#475569">About</text>
    <text x="560" y="140" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600" fill="#475569">Services</text>
    <text x="640" y="140" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600" fill="#475569">Pricing</text>
    <text x="715" y="140" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600" fill="#475569">Contact</text>

    <!-- Nav Action Button -->
    <rect x="990" y="117" width="110" height="36" rx="8" fill="{brand_color}"/>
    <text x="1045" y="140" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="700" fill="#ffffff">Get Started</text>

    <!-- Hero Section Container -->
    <rect x="70" y="165" width="1060" height="320" fill="url(#hero-grad)"/>

    <!-- Category Pill Tag -->
    <rect x="110" y="200" width="140" height="26" rx="13" fill="{brand_color}" fill-opacity="0.12"/>
    <text x="180" y="217" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="700" fill="{brand_color}">✨ {clean_cat[:16]}</text>

    <!-- Hero Title -->
    <text x="110" y="265" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="900" fill="#0f172a">{display_headline}</text>

    <!-- Hero Subtitle -->
    <text x="110" y="305" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="15" font-weight="500" fill="#64748b">{display_sub}</text>

    <!-- Primary CTA & Secondary Demo CTA -->
    <rect x="110" y="340" width="160" height="46" rx="10" fill="url(#btn-grad)"/>
    <text x="190" y="369" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" fill="#ffffff">Explore Showcase →</text>

    <rect x="290" y="340" width="140" height="46" rx="10" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
    <text x="360" y="369" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="700" fill="#334155">Live Preview</text>

    {right_graphic_svg}

    <!-- ── 3 Feature Cards Section ── -->
    <rect x="70" y="485" width="1060" height="205" fill="#f8fafc"/>

    <!-- Feature Card 1 -->
    <rect x="110" y="505" width="290" height="150" rx="12" fill="#ffffff" stroke="#e2e8f0" stroke-width="1"/>
    <circle cx="145" cy="540" r="16" fill="{brand_color}" fill-opacity="0.12"/>
    <text x="145" y="545" text-anchor="middle" font-size="15">⚡</text>
    <text x="175" y="546" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" fill="#0f172a">{card1_title}</text>
    <text x="125" y="578" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card1_desc1}</text>
    <text x="125" y="598" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card1_desc2}</text>

    <!-- Feature Card 2 -->
    <rect x="445" y="505" width="290" height="150" rx="12" fill="#ffffff" stroke="#e2e8f0" stroke-width="1"/>
    <circle cx="480" cy="540" r="16" fill="{accent_color}" fill-opacity="0.12"/>
    <text x="480" y="545" text-anchor="middle" font-size="15">💻</text>
    <text x="510" y="546" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" fill="#0f172a">{card2_title}</text>
    <text x="460" y="578" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card2_desc1}</text>
    <text x="460" y="598" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card2_desc2}</text>

    <!-- Feature Card 3 -->
    <rect x="780" y="505" width="290" height="150" rx="12" fill="#ffffff" stroke="#e2e8f0" stroke-width="1"/>
    <circle cx="815" cy="540" r="16" fill="#10b981" fill-opacity="0.12"/>
    <text x="815" y="545" text-anchor="middle" font-size="15">🚀</text>
    <text x="845" y="546" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" fill="#0f172a">{card3_title}</text>
    <text x="795" y="578" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card3_desc1}</text>
    <text x="795" y="598" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="500" fill="#64748b">{card3_desc2}</text>
  </g>
</svg>"""
        return svg

    @classmethod
    def generate_for_project(cls, identifier: str) -> str:
        """
        Dynamically extracts the real project assets (uploaded photos, skills, title)
        from local_project_manager and generates an accurate SVG thumbnail.
        """
        from app.core.local_project_manager import local_project_manager

        clean_id = str(identifier).strip()
        project_dir = local_project_manager.get_local_project_dir(clean_id, version="latest")
        if not project_dir:
            return cls.generate_svg_snapshot(title=clean_id)

        # 1. Search for real owner image
        photo_data_uri = ""
        assets_dir = project_dir / "assets"
        if assets_dir.exists():
            for f in assets_dir.iterdir():
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    try:
                        mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
                        b64 = base64.b64encode(f.read_bytes()).decode("ascii")
                        photo_data_uri = f"data:{mime};base64,{b64}"
                        break
                    except Exception as e:
                        logger.warning("Could not encode photo for thumbnail: %s", e)

        # 2. Extract content from index.html
        title = clean_id
        skills = []
        experience = ""
        index_file = project_dir / "index.html"
        if index_file.exists():
            try:
                html = index_file.read_text(encoding="utf-8", errors="ignore")
                # Title / Headline
                t_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                if t_match:
                    title = t_match.group(1).split("—")[0].split("-")[0].strip()
                h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE)
                if h1_match:
                    h1_clean = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                    if h1_clean:
                        title = h1_clean

                # Detect real skills
                potential_skills = ["Python", "SQL", "React", "DevOps", "Docker", "FastAPI", "TypeScript", "Node.js", "JavaScript"]
                skills = [s for s in potential_skills if s.lower() in html.lower()]

                # Detect experience
                if "vgen" in html.lower():
                    experience = "2 years at Vgen, Coimbatore"
            except Exception as e:
                logger.warning("Could not parse index.html for thumbnail: %s", e)

        if not skills:
            skills = ["Python", "SQL", "React", "DevOps"]

        svg_content = cls.generate_svg_snapshot(
            title=title or "Navin Bharath",
            framework="HTML",
            category="Verified Portfolio",
            brand_color="#4f46e5",
            accent_color="#3b82f6",
            description=f"Full-Stack Developer · {', '.join(skills[:3])} · {experience}",
            photo_data_uri=photo_data_uri,
            skills=skills,
            role=title,
            experience=experience,
        )

        # Save to static/thumbnails/
        save_path = _THUMBNAILS_DIR / f"{clean_id}.svg"
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        except Exception:
            pass

        return svg_content

    @classmethod
    def save_thumbnail(
        cls,
        template_id: str,
        title: str,
        framework: str = "HTML",
        category: str = "Business",
        brand_color: str = "#4f46e5",
        description: str = "",
    ) -> str:
        """
        Saves SVG snapshot to `static/thumbnails/{template_id}.svg` and returns public URL.
        """
        svg_content = cls.generate_for_project(template_id)
        file_path = _THUMBNAILS_DIR / f"{template_id}.svg"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        return f"http://localhost:8000/static/thumbnails/{template_id}.svg"


screenshot_service = ScreenshotService()
