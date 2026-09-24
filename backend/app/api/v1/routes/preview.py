"""
Preview routes — create preview sessions and serve watermarked previews.
"""

import os
import re
import io
import json
import uuid
import shutil
import asyncio
import zipfile
import platform
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Body, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.models.user import User
from app.models.template import Template, TemplateStatus
from app.models.stored_file import StoredFile
from app.services.preview_service import PreviewService
from app.services.ai_service import ai_service
from app.repositories.template_repo import TemplateRepository
from pydantic import BaseModel

router = APIRouter()


class PreviewRequest(BaseModel):
    template_id: str | uuid.UUID
    business_name: str
    industry: str
    primary_color: Optional[str] = "#6366f1"
    secondary_color: Optional[str] = "#8b5cf6"
    about: Optional[str] = None
    services: Optional[list] = None
    contact: Optional[dict] = None
    location: Optional[str] = None
    social_links: Optional[dict] = None
    logo_url: Optional[str] = None
    ai_fill: bool = False  # If True, auto-generate content via AI


class PreviewResponse(BaseModel):
    session_id: uuid.UUID
    preview_image_url: Optional[str] = None
    business_data: dict
    generated_content: Optional[dict] = None
    template_id: str | uuid.UUID
class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None


class AIEditRequest(BaseModel):
    prompt: str




@router.post("", response_model=PreviewResponse)
async def create_preview(
    request: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a watermarked live preview session.

    If `ai_fill=true`, AI generates the business content automatically.
    Returns a watermarked preview image URL + session ID.
    """
    service = PreviewService(db)
    template_repo = TemplateRepository(db)

    template = await template_repo.get_by_id(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    business_data = {
        "business_name": request.business_name,
        "industry": request.industry,
        "primary_color": request.primary_color,
        "secondary_color": request.secondary_color,
        "about": request.about,
        "services": request.services or [],
        "contact": request.contact or {},
        "location": request.location,
        "social_links": request.social_links or {},
        "logo_url": request.logo_url,
    }

    generated_content = None
    if request.ai_fill and ai_service.client:
        try:
            generated_content = await ai_service.generate_business_content(
                business_name=request.business_name,
                industry=request.industry,
                template_type=template.category.name if template.category else "business",
            )
            # Merge AI content into business_data
            business_data.update(generated_content)
        except Exception:
            pass  # AI fill optional — continue without it

    user_email = current_user.email if current_user else None

    session = await service.create_session(
        template_id=request.template_id,
        business_data=business_data,
        user_email=user_email,
        is_ai_filled=request.ai_fill,
    )

    # Generate watermarked preview
    preview_url = None
    try:
        preview_url = await service.generate_preview_screenshot(
            session_id=session.id,
            template_thumbnail_url=template.thumbnail_url,
            user_email=user_email,
        )
        session.preview_image_url = preview_url
        session.generated_content = generated_content
        await db.flush()
    except Exception:
        pass  # Preview image is optional — session is still created

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=preview_url,
        business_data=business_data,
        generated_content=generated_content,
        template_id=request.template_id,
    )


@router.get("/{session_id}", response_model=PreviewResponse)
async def get_preview_session(
    session_id: str | uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an existing preview session by ID."""
    try:
        session_uuid = uuid.UUID(str(session_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Preview session not found")

    from sqlalchemy import select
    from app.models.preview_session import PreviewSession

    result = await db.execute(
        select(PreviewSession).where(PreviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Preview session not found")

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=session.preview_image_url,
        business_data=session.business_data or {},
        generated_content=session.generated_content,
        template_id=session.template_id,
    )


# Global locks to prevent parallel builds of the same template
_build_locks = {}


@router.get("/live/{template_id}/extracted-data")
async def get_live_preview_extracted_data(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Dynamically extract the real template content directly from its source files:
    Real brand name, logo text, H1 headline, subtitle, navigation links, CTA buttons,
    contact info, footer copyright, and lively detected sections (no fake/unrelated sections).
    """
    import zipfile
    import io
    import re
    import tempfile
    from app.models.template import Template
    from app.models.stored_file import StoredFile
    from app.repositories.template_repo import TemplateRepository
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    title = template.title or "Web Template"
    clean_brand = title.split("—")[0].split("-")[0].split("|")[0].strip()
    primary_color = "#4f46e5"
    if template.color_scheme:
        c_lower = template.color_scheme.lower()
        if "red" in c_lower: primary_color = "#C4222C"
        elif "green" in c_lower: primary_color = "#059669"
        elif "blue" in c_lower: primary_color = "#2563eb"
        elif "purple" in c_lower or "violet" in c_lower: primary_color = "#8b5cf6"
        elif "amber" in c_lower or "orange" in c_lower: primary_color = "#d97706"

    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))

    # Read content from preview_dir first (if already extracted/running), else fallback to stored ZIP
    content = ""
    if os.path.exists(preview_dir):
        candidates = []
        for root, _, files in os.walk(preview_dir):
            if any(d in root.replace("\\", "/").split("/") for d in ["node_modules", ".git", "dist", "build", ".output"]):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".html", ".jsx", ".tsx", ".vue"]:
                    candidates.append(os.path.join(root, f))
        
        main_f = None
        for c in candidates:
            if os.path.basename(c).lower() == "index.html":
                main_f = c
                break
        if not main_f:
            for c in candidates:
                if c.endswith(".html"):
                    main_f = c
                    break
        if not main_f and candidates:
            main_f = candidates[0]
            
        if main_f and os.path.exists(main_f):
            try:
                with open(main_f, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e_rf:
                logger.warning(f"Failed to read preview file {main_f}: {e_rf}")

    # Collect ALL source files from DB stored file (HTML + JSX/TSX)
    all_source_files = {}  # filename -> content string
    if not content:
        download_assets = template.download_assets or {}
        zip_url = download_assets.get("zip")
        if zip_url:
            match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
            if match:
                file_id = uuid.UUID(match.group(1))
                sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                stored_file = sf_res.scalar_one_or_none()
                if stored_file and stored_file.data:
                    if zipfile.is_zipfile(io.BytesIO(stored_file.data)):
                        with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z_in:
                            namelist = z_in.namelist()
                            # Collect ALL source files (exclude build dirs)
                            for n in namelist:
                                is_build = any(d in n.replace("\\", "/").split("/")
                                               for d in ["node_modules", "dist", "build", "out", ".output", "__MACOSX"])
                                is_src = (n.endswith(".html") or n.endswith(".jsx") or
                                          n.endswith(".tsx") or n.endswith(".vue") or
                                          n.endswith(".js") or n.endswith(".ts"))
                                if is_src and not is_build:
                                    try:
                                        all_source_files[n] = z_in.read(n).decode("utf-8", errors="ignore")
                                    except Exception:
                                        pass
                            # Pick main file content for BS4 path (use already-read dict)
                            html_keys = [n for n in all_source_files if n.endswith("index.html") or
                                         (n.endswith(".html") and "__MACOSX" not in n)]
                            jsx_keys = [n for n in all_source_files if (n.endswith("App.jsx") or n.endswith("App.tsx"))]
                            if html_keys:
                                content = all_source_files[html_keys[0]]
                            elif jsx_keys:
                                content = all_source_files[jsx_keys[0]]
                            elif all_source_files:
                                content = next(iter(all_source_files.values()))
                    else:
                        content = stored_file.data.decode("utf-8", errors="ignore")

    # Also collect files from already-extracted preview_dir (for JSX builds)
    if not all_source_files and os.path.exists(preview_dir):
        for root, _, files in os.walk(preview_dir):
            if any(d in root.replace("\\", "/").split("/")
                   for d in ["node_modules", ".git", "dist", "build", ".output"]):
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".html", ".jsx", ".tsx", ".vue", ".js", ".ts"]:
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            all_source_files[fpath] = fh.read()
                    except Exception:
                        pass

    # ─── Universal JSX/TSX Source Code Extractor ────────────────────────────
    def extract_from_jsx_sources(src_files: dict, tmpl_title: str, tmpl_color: str):
        """Parse JSX/TSX/Vue source files to extract real sections without BS4."""
        combined = "\n".join(src_files.values())

        # 1. Brand / business name — look for common JSX string patterns
        bname = tmpl_title
        for pattern in [
            r"brandName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
            r"business_name\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
            r"companyName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
            r"siteName\s*[=:]\s*['\"`]([^'\"\`]{2,50})['\"`]",
            r"<title>([^<]{2,50})</title>",
            r"title:\s*['\"`]([^'\"\`]{2,60})['\"`]",
        ]:
            m = re.search(pattern, combined, re.I)
            if m:
                bname = m.group(1).split("—")[0].split("-")[0].strip()
                if 2 < len(bname) < 60:
                    break

        # 2. Primary color
        pcolor = tmpl_color
        for cp in [
            r"primary(?:Color)?\s*[=:]\s*['\"`](#[0-9a-fA-F]{3,8})['\"`]",
            r"--(?:primary|accent|brand)(?:-color)?:\s*(#[0-9a-fA-F]{3,8})",
            r"themeColor\s*[=:]\s*['\"`](#[0-9a-fA-F]{3,8})['\"`]",
            r"--red:\s*(#[0-9a-fA-F]{3,8})",
        ]:
            m = re.search(cp, combined, re.I)
            if m:
                pcolor = m.group(1)
                break

        logo_text = re.sub(r"[^A-Z0-9]", "", bname.upper())[:7] or "BRAND"

        def classify_jsx_section(sid: str):
            k = sid.lower()
            if any(w in k for w in ["hero", "home", "banner", "intro", "landing"]):
                return "Hero & Banner", "Zap"
            if any(w in k for w in ["nav", "header", "menu"]):
                return "Header & Nav", "Monitor"
            if any(w in k for w in ["about", "story", "who", "bio"]):
                return "Content & Story", "FileText"
            if any(w in k for w in ["service", "offering", "solution", "capability", "feature"]):
                return "Capabilities & Services", "Layers"
            if any(w in k for w in ["work", "port", "project", "evidence", "case", "exhibit"]):
                return "Portfolio & Case Files", "Layers"
            if any(w in k for w in ["skill", "dossier", "stack", "tech"]):
                return "Skills & Capabilities", "Shield"
            if any(w in k for w in ["timeline", "history", "log", "experience", "resume"]):
                return "Historical Record", "Clock"
            if any(w in k for w in ["price", "pricing", "plan", "tier", "subscription"]):
                return "Conversion & Plans", "Sparkles"
            if any(w in k for w in ["review", "testimonial", "client", "rating"]):
                return "Social Proof & Reviews", "Star"
            if any(w in k for w in ["contact", "touch", "reach", "inquiry", "lead", "form"]):
                return "Inquiry & Leads", "Mail"
            if any(w in k for w in ["footer", "foot"]):
                return "Footer & Record", "Shield"
            return "Section Content", "Globe"

        def extract_str_near(key: str, text: str, max_len: int = 120) -> str:
            """Find a string value near a JSX key."""
            p = rf"{key}\s*[=:{{]\s*['\"`]([^'\"\`]{{1,{max_len}}})['\"`]"
            m = re.search(p, text, re.I)
            return m.group(1).strip() if m else ""

        # 3. Discover section IDs from JSX
        #    Patterns: id="hero", section id='about', id={sectionId} where sectionId='...',
        #    component names like <HeroSection, <AboutSection, <NavBar etc.
        section_ids_found = []
        seen = set()

        # a) HTML-like id attributes in JSX
        for m in re.finditer(r'id=["\']([a-zA-Z][a-zA-Z0-9_-]{1,30})["\']', combined):
            sid = m.group(1).lower().replace("-", "_")
            if sid not in seen and sid not in ["root", "app", "main", "wrap", "wrapper", "container"]:
                seen.add(sid)
                section_ids_found.append(m.group(1))

        # b) Component function/const names like function HeroSection, const AboutSection
        for m in re.finditer(r'(?:function|const|export\s+default\s+function)\s+([A-Z][a-zA-Z]{3,40})(?:Section|Component|Block|Page)?\b', combined):
            name = m.group(1)
            # Strip 'Section', 'Component' etc suffix to get the base ID
            base = re.sub(r'(?:Section|Component|Block|Page|Widget)$', '', name, flags=re.I)
            sid = base.lower()
            if sid not in seen and sid not in ["app", "root", "main", "index", "default", "export", "import"]:
                seen.add(sid)
                section_ids_found.append(sid)

        # c) Route / page file names (each .jsx/.tsx file is a section/page)
        for fname in src_files.keys():
            base = os.path.splitext(os.path.basename(fname))[0].lower()
            # Skip generic names
            skip_names = {"index", "app", "main", "layout", "root", "vite", "config",
                          "tailwind", "global", "style", "styles", "utils", "helpers",
                          "types", "constants", "context", "hooks", "store", "api"}
            if base not in skip_names and len(base) > 2 and base not in seen:
                seen.add(base)
                section_ids_found.append(base)

        # 4. Build sections list
        out_sections = {}
        out_sections_list = []

        # Always add navbar — extract ALL nav links into array (no fixed limit)
        nav_link_values = []

        # Strategy 1: keyed link1...link20 style
        for i in range(1, 21):
            p = rf"link{i}\s*[=:]\s*['\"`]([^'\"\`]{{1,40}})['\"`]"
            m = re.search(p, combined, re.I)
            if m:
                nav_link_values.append(m.group(1))

        # Strategy 2: navItems / navLinks / menuItems / links arrays
        if len(nav_link_values) < 2:
            arr_m = re.search(
                r'(?:navItems|navLinks|menuItems|links|navMenu|navigation)\s*[=:]\s*\[([^\]]{1,600})\]',
                combined, re.I
            )
            if arr_m:
                raw = arr_m.group(1)
                found = re.findall(r"['\"`]([^'\"\`]{2,40})['\"`]", raw)
                nav_link_values = [f for f in found if 1 < len(f) < 40]

        # Strategy 3: object array [{label:'Home',href:'/'}, ...]
        if len(nav_link_values) < 2:
            obj_arr_m = re.findall(
                r'(?:label|title|name|text)\s*:\s*[\'"`]([^\'"`]{2,30})[\'"`]',
                combined[:5000], re.I
            )
            if obj_arr_m:
                nav_link_values = obj_arr_m[:15]

        # Strategy 4: href="#section" anchor links
        if len(nav_link_values) < 2:
            anchor_matches = re.findall(
                r'href=["\'](?:#|/)[^"\']*["\'][^>]*>\s*([^<]{2,30})\s*<', combined
            )
            if anchor_matches:
                nav_link_values = [a.strip() for a in anchor_matches if a.strip()]

        # Remove duplicates, keep order
        seen_links = set()
        nav_link_values_dedup = []
        for lnk in nav_link_values:
            lc = lnk.strip().lower()
            if lc not in seen_links and lc:
                seen_links.add(lc)
                nav_link_values_dedup.append(lnk.strip())
        nav_link_values = nav_link_values_dedup

        # Fallback: at least provide 4 sensible defaults
        if not nav_link_values:
            nav_link_values = ["Home", "About", "Services", "Contact"]

        cta_m = re.search(r"ctaText\s*[=:]\s*['\"`]([^'\"\`]{1,40})['\"`]", combined, re.I)
        out_sections["navbar"] = {
            "brandName": bname,
            "logoText": logo_text,
            "navLinks": nav_link_values,   # ← unlimited array
            "ctaText": cta_m.group(1) if cta_m else "Get Started",
            "stickyGlass": True,
            "themeColor": pcolor
        }
        out_sections_list.append({
            "id": "navbar", "name": "Navigation Header",
            "category": "Header & Nav", "icon": "Monitor",
            "desc": "Top navigation bar with brand logo and navigation links",
            "targetSection": "navbar"
        })
        seen_sec = {"navbar"}

        # Map each discovered section ID to its data by looking in the relevant file
        for raw_sid in section_ids_found:
            sid = raw_sid.lower().replace("-", "_")
            if sid in seen_sec:
                continue
            # Skip nav-like and footer (we add footer at end)
            if any(x in sid for x in ["nav", "header", "foot", "wrap", "root", "app", "main",
                                       "logo", "menu", "route", "router", "provider"]):
                continue
            seen_sec.add(sid)

            # Find the relevant file(s) for this section
            relevant_text = ""
            for fname, ftext in src_files.items():
                base = os.path.splitext(os.path.basename(fname))[0].lower()
                if base == sid or sid in base or base in sid:
                    relevant_text = ftext
                    break
            if not relevant_text:
                # Search in combined for id="section"
                sec_match = re.search(
                    rf'id=["\'](?:{re.escape(raw_sid)})["\'].*?(?=id=["\'][a-zA-Z]|</(?:section|main|body|div class="(?:footer|nav))|$)',
                    combined, re.DOTALL | re.I
                )
                relevant_text = sec_match.group(0) if sec_match else ""

            if not relevant_text:
                relevant_text = combined  # Use all combined as fallback

            # Extract meaningful strings from the relevant text
            headline = ""
            for hp in [
                r"headline\s*[=:]\s*['\"`]([^'\"\`]{4,120})['\"`]",
                r"title\s*[=:]\s*['\"`]([^'\"\`]{4,100})['\"`]",
                r"h1[^>]*>([^<]{4,100})<",
                r"h2[^>]*>([^<]{4,100})<",
            ]:
                m = re.search(hp, relevant_text, re.I)
                if m and m.group(1).strip():
                    headline = m.group(1).strip()
                    break

            subheadline = ""
            for sp in [
                r"subheadline\s*[=:]\s*['\"`]([^'\"\`]{10,200})['\"`]",
                r"subtitle\s*[=:]\s*['\"`]([^'\"\`]{10,200})['\"`]",
                r"description\s*[=:]\s*['\"`]([^'\"\`]{10,200})['\"`]",
                r"<p[^>]*>([^<]{20,200})</p>",
            ]:
                m = re.search(sp, relevant_text, re.I)
                if m and m.group(1).strip():
                    subheadline = m.group(1).strip()
                    break

            badge = extract_str_near("badgeText|badge|pill|tag", relevant_text, 60)
            email_m = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', relevant_text)
            phone_m = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', relevant_text)

            cat_name, icon_name = classify_jsx_section(sid)
            disp_name = headline if (headline and 3 < len(headline) < 40) else \
                (sid.replace("_", " ").replace("-", " ").title())

            sec_data = {
                "title": headline or disp_name,
                "headline": headline or disp_name,
                "badgeText": badge,
                "subheadline": subheadline,
                "description": subheadline,
                "themeColor": pcolor
            }
            if email_m:
                sec_data["email"] = email_m.group(0)
            if phone_m:
                sec_data["phone"] = phone_m.group(0)

            out_sections[sid] = sec_data
            out_sections_list.append({
                "id": sid,
                "name": disp_name,
                "category": cat_name,
                "icon": icon_name,
                "desc": subheadline[:80] if subheadline else f"Template section for {disp_name}",
                "targetSection": sid
            })

        # Footer
        copy_m = re.search(r"copyright\s*[=:]\s*['\"`]([^'\"\`]{5,100})['\"`]", combined, re.I)
        footer_tagline = extract_str_near("tagline|footerTagline|footerDesc", combined, 120)
        out_sections["footer"] = {
            "brandName": bname,
            "tagline": footer_tagline or f"{bname}. All rights reserved.",
            "copyright": copy_m.group(1) if copy_m else f"© {2026} {bname}. All rights reserved.",
            "themeColor": pcolor
        }
        out_sections_list.append({
            "id": "footer", "name": "Website Footer",
            "category": "Footer & Record", "icon": "Shield",
            "desc": "Site footer with brand signature, legal copyright, and links",
            "targetSection": "footer"
        })

        return {
            "status": "success",
            "brand": {"business_name": bname, "logo_text": logo_text, "primary_color": pcolor},
            "sections": out_sections,
            "sections_list": out_sections_list
        }

    # ─── Decide: use JSX extractor OR BeautifulSoup (HTML) ──────────────────
    # If we have JSX/TSX/Vue files but no real HTML, use the JSX extractor
    jsx_files_found = {k: v for k, v in all_source_files.items()
                       if k.endswith(".jsx") or k.endswith(".tsx") or k.endswith(".vue")}
    html_content_is_html = content and bool(re.search(r'<html|<!DOCTYPE', content, re.I))

    if not html_content_is_html and jsx_files_found:
        # React/Vue template — use the universal JSX extractor
        result = extract_from_jsx_sources(all_source_files, title, primary_color)
        return result

    from bs4 import BeautifulSoup

    def clean_text(text: str) -> str:
        if not text:
            return ""
        c = re.sub(r"<[^>]+>", " ", text)
        c = re.sub(r"\s+([.,!?:;])", r"\1", c)
        return re.sub(r"\s+", " ", c).strip()

    soup = BeautifulSoup(content or "", "html.parser")
    
    # 1. Page Title & Clean Brand
    title_tag = soup.find("title")
    page_title = clean_text(title_tag.string) if title_tag and title_tag.string else title
    clean_brand = page_title.split("—")[0].split("-")[0].split("|")[0].strip() or title
    
    h1_tag = soup.find("h1")
    h1_text = clean_text(h1_tag.get_text()) if h1_tag else ""
    brand_el = soup.find(class_=re.compile(r"\bbrand\b|\blogo\b", re.I)) or soup.find(id=re.compile(r"brand|logo", re.I))
    if h1_text and 2 < len(h1_text) < 40 and not any(w in h1_text.lower() for w in ["welcome", "hello", "home", "loading", "main"]):
        brand_name = h1_text
    elif brand_el and brand_el.get_text(strip=True):
        brand_name = clean_text(brand_el.get_text())
    else:
        brand_name = clean_brand
    if len(brand_name) > 40:
        brand_name = clean_brand

    # Detect theme color from :root or style
    primary_color = "#4f46e5"
    style_tag = soup.find("style")
    if style_tag and style_tag.string:
        st = style_tag.string
        if "--red" in st or "var(--red)" in st or "#c4222c" in st.lower(): primary_color = "#C4222C"
        elif "--blue" in st or "var(--blue)" in st or "#2563eb" in st.lower(): primary_color = "#2563eb"
        elif "--green" in st or "var(--green)" in st or "#059669" in st.lower(): primary_color = "#059669"
        elif "--orange" in st or "--amber" in st: primary_color = "#d97706"

    sections = {}
    sections_list = []
    seen_ids = set()

    # 2. Navigation Header
    nav_el = soup.find("nav") or soup.find("header")
    if nav_el or "<nav" in content.lower() or "logo" in content.lower():
        nav_text_container = nav_el if nav_el else soup
        links = [clean_text(a.get_text()) for a in nav_text_container.find_all("a") if 0 < len(clean_text(a.get_text())) < 25]
        if links and (links[0].lower() == brand_name.lower() or len(links[0]) > 20):
            links = links[1:]
            
        btn = nav_text_container.find("button") or nav_text_container.find(class_=re.compile(r"btn|cta", re.I))
        btn_text = clean_text(btn.get_text()) if btn else (links[-1] if len(links) > 4 else "Get Started")
        
        # Remove CTA link from nav links if it matches the button text
        nav_link_list = [lnk for lnk in links if lnk.lower() != (btn_text or "").lower()]
        if not nav_link_list:
            nav_link_list = ["Home", "About", "Services", "Contact"]

        sections["navbar"] = {
            "brandName": brand_name,
            "logoText": re.sub(r"[^A-Z0-9]", "", brand_name.upper())[:7] or "BRAND",
            "navLinks": nav_link_list,     # unlimited array, all links from template
            "ctaText": btn_text or "Get Started",
            "stickyGlass": True,
            "themeColor": primary_color
        }
        sections_list.append({
            "id": "navbar",
            "name": "Navigation Header",
            "category": "Header & Nav",
            "icon": "Monitor",
            "desc": f"Top navigation bar with brand logo, {len(nav_link_list)} menu links, and action button",
            "targetSection": "navbar"
        })
        seen_ids.add("navbar")

    # 2b. Hero & Banner Section
    hero_el = soup.find(id=re.compile(r"hero|banner|intro", re.I)) or soup.find(class_=re.compile(r"hero|banner|intro|header-wrapper|header-clip", re.I))
    hero_h1 = hero_el.find("h1") if hero_el else soup.find("h1")
    hero_h2 = hero_el.find(["h2", "h3"]) if hero_el else soup.find(["h2", "h3"])
    hero_p = hero_el.find("p") if hero_el else None
    hero_cta = hero_el.find(["a", "button"], class_=re.compile(r"scroll|btn|cta|btn-primary", re.I)) if hero_el else None

    if hero_h1 or hero_h2 or hero_el:
        h1_val = clean_text(hero_h1.get_text()) if hero_h1 else brand_name
        h2_val = clean_text(hero_h2.get_text()) if hero_h2 else (clean_text(hero_p.get_text()) if hero_p else "")
        cta_val = clean_text(hero_cta.get_text()) if hero_cta else "Explore More"
        sections["hero"] = {
            "title": h1_val,
            "headline": h1_val,
            "subheadline": h2_val,
            "description": h2_val,
            "primaryCta": cta_val,
            "themeColor": primary_color
        }
        sections_list.append({
            "id": "hero",
            "name": "Hero & Banner",
            "category": "Hero & Banner",
            "icon": "Zap",
            "desc": "Primary introduction banner with headline and action callout",
            "targetSection": "hero"
        })
        seen_ids.add("hero")

    def classify_section(sid: str, stitle: str):
        k = (sid + " " + stitle).lower()
        if any(w in k for w in ["hero", "home", "banner", "intro"]):
            return "Hero & Banner", "Zap"
        if any(w in k for w in ["about", "story", "who", "bio"]):
            return "Content & Story", "FileText"
        if any(w in k for w in ["service", "offering", "solution", "capability", "feature"]):
            return "Capabilities & Services", "Layers"
        if any(w in k for w in ["work", "port", "project", "evidence", "case", "exhibit"]):
            return "Portfolio & Case Files", "Layers"
        if any(w in k for w in ["skill", "dossier", "stack", "tech"]):
            return "Skills & Capabilities", "Shield"
        if any(w in k for w in ["timeline", "history", "log", "experience", "resume"]):
            return "Historical Record", "Clock"
        if any(w in k for w in ["price", "pricing", "plan", "tier"]):
            return "Conversion & Plans", "Sparkles"
        if any(w in k for w in ["review", "testimonial", "client", "rating"]):
            return "Social Proof & Reviews", "Star"
        if any(w in k for w in ["contact", "touch", "reach", "inquiry", "lead"]):
            return "Inquiry & Leads", "Mail"
        if any(w in k for w in ["info", "address", "phone", "location"]):
            return "Direct Reach & Contact", "Phone"
        if any(w in k for w in ["social", "network"]):
            return "Social Channels", "Share2"
        if any(w in k for w in ["career", "job", "training"]):
            return "Opportunities & Programs", "Globe"
        return "Section Content", "Globe"

    # 3. Discover True Top-Level Sections
    raw_sections = soup.find_all("section")
    if not raw_sections:
        candidates = soup.find_all("div", id=re.compile(r"^[a-zA-Z0-9_-]+$"))
        class_candidates = soup.find_all("div", class_=re.compile(r"\b(review|reviews|testimonial|testimonials|client|clients|about|services|skills|resume|portfolio|work|contact|info|social)\b", re.I))
        for cc in class_candidates:
            if cc not in candidates and not any(cand in cc.parents for cand in candidates):
                candidates.append(cc)

        raw_sections = []
        for c in candidates:
            cid = c.get("id", "").lower()
            cclass = " ".join(c.get("class", [])).lower()
            if cclass in ["footer", "header", "nav", "row", "container", "wrap", "wrapper", "header-clip"]:
                continue
            if any(skip in cid for skip in ["header-clip", "header", "nav", "root", "app", "tab-content", "tab-pane", "clip", "modal", "overlay", "container", "row"]):
                continue
            if c.find_parent("section") or c.find_parent("div", id=re.compile(r"^(?!wrap|main|root|app).*$")):
                continue
            if c.find(["h1", "h2", "h3", "h4", "form", "img"]) or len(clean_text(c.get_text())) > 25:
                raw_sections.append(c)

    for idx, s in enumerate(raw_sections):
        s_id = s.get("id") or (s.get("class", [""])[0] if s.get("class") else f"sec_{idx}")
        s_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(s_id)).lower()
        if not s_id or s_id in seen_ids or s_id in ["header", "nav", "footer", "header_clip"]:
            continue
        seen_ids.add(s_id)

        # Headings
        h_tag = s.find(["h1", "h2", "h3", "h4"])
        headline = clean_text(h_tag.get_text()) if h_tag else ""
        
        # Badge / Pill Tag
        badge_el = s.find(class_=re.compile(r"badge|tag|status|stamp|pill", re.I))
        badge = clean_text(badge_el.get_text()) if badge_el else ""
        
        # Narrative / Description / Bio — extract BOTH subtitle and full narrative
        p_tags = s.find_all("p")
        p_clean = [clean_text(p.get_text()) for p in p_tags if len(clean_text(p.get_text())) > 5]
        subtitle = ""
        story = ""
        if len(p_clean) == 1:
            subtitle = p_clean[0]
            story = p_clean[0]
        elif len(p_clean) >= 2:
            if len(p_clean[0]) < 80:
                subtitle = p_clean[0]
                story = "\n\n".join(p_clean[1:])
            else:
                subtitle = p_clean[0]
                story = "\n\n".join(p_clean)
        narrative = story or subtitle

        # Form Inspection (STRICT: only real fields that exist in this section)
        form_el = s.find("form")
        inputs = [clean_text(inp.get("placeholder") or inp.get("name") or "") for inp in s.find_all("input") if inp.get("type") not in ["hidden", "submit"]]
        textareas = [clean_text(ta.get("placeholder") or ta.get("name") or "") for ta in s.find_all("textarea")]
        submit_btn = s.find(["button", "input"], type=re.compile(r"submit|button", re.I)) or s.find("button")
        submit_text = clean_text(submit_btn.get_text()) if submit_btn and hasattr(submit_btn, "get_text") else "Submit"
        has_form = bool(form_el or (inputs and len(inputs) >= 1))

        # Check Phone & Address STRICTLY in template code
        s_text = s.get_text()
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', s_text)
        has_phone = bool(phone_match or s.find(href=re.compile(r"^tel:", re.I)) or s.find("input", type="tel"))
        phone_val = phone_match.group(0) if phone_match else ""

        has_address = bool(s.find("address") or re.search(r'\b(?:\d{2,}\s+[A-Za-z]+|\b[A-Z]{2}\s+\d{5}\b|suite\s+\d+|floor\s+\d+)\b', s_text, re.I))
        address_val = ""
        if has_address:
            addr_tag = s.find("address")
            address_val = clean_text(addr_tag.get_text()) if addr_tag else ""

        # Key-Value Meta Items (e.g. <div>ROLE<span>...</span></div> or .stat)
        meta_items = []
        div_spans = s.find_all(lambda tag: tag.name == "div" and tag.find("span") and len(tag.get_text(strip=True)) < 60)
        for ds in div_spans:
            sp = ds.find("span")
            k = clean_text(ds.get_text().replace(sp.get_text(), ""))
            v = clean_text(sp.get_text())
            if k and v and len(k) < 20 and len(v) < 35:
                meta_items.append({"label": k, "value": v})

        # Cards / Child items extraction with deduplication & specialized support
        card_items = []
        seen_card_keys = set()

        # 1. Timeline / Resume Milestones
        timeline_lis = []
        for rl in s.find_all(class_=re.compile(r"resume-list|timeline", re.I)):
            timeline_lis.extend(rl.find_all("li", recursive=False))
        if not timeline_lis:
            timeline_lis = s.find_all("li", class_=re.compile(r"timeline", re.I))

        if timeline_lis:
            for tli in timeline_lis:
                date_el = tli.find(class_=re.compile(r"timeline-image|date|year", re.I))
                date_text = clean_text(date_el.get_text()) if date_el else ""
                h_els = tli.find_all(["h4", "h3", "h5", "strong"])
                title_text = ""
                sub_text = ""
                for h in h_els:
                    ht = clean_text(h.get_text())
                    if ht == date_text:
                        continue
                    if not title_text:
                        title_text = ht
                    elif not sub_text:
                        sub_text = ht
                desc_el = tli.find("p")
                desc_text = clean_text(desc_el.get_text()) if desc_el else ""
                if title_text:
                    key = (title_text.lower(), desc_text[:30].lower())
                    if key not in seen_card_keys:
                        seen_card_keys.add(key)
                        card_items.append({
                            "title": title_text,
                            "desc": desc_text,
                            "tag": date_text,
                            "stack": sub_text
                        })

        # 2. Skills / Circular progress meters
        skill_els = s.find_all(class_=re.compile(r"\bskill\b", re.I)) or s.find_all(attrs={"data-percent": True})
        if skill_els and not card_items:
            for sk in skill_els:
                name_el = sk.find(["h4", "h5", "h6", "strong"]) or sk.find("span")
                percent_attr = sk.get("data-percent") or (sk.find(attrs={"data-percent": True}) or {}).get("data-percent")
                percent_el = sk.find(class_=re.compile(r"percent", re.I))
                pct = percent_attr or (clean_text(percent_el.get_text()) if percent_el else "")
                name = clean_text(name_el.get_text()) if name_el else ""
                if name and pct:
                    if name == pct:
                        h = sk.find(["h4", "h5", "h6", "strong"])
                        if h: name = clean_text(h.get_text())
                    key = name.lower()
                    if key not in seen_card_keys:
                        seen_card_keys.add(key)
                        card_items.append({
                            "title": name,
                            "desc": f"Mastery Level: {pct}%",
                            "tag": f"{pct}%",
                            "stack": f"Proficiency: {pct}%"
                        })

        # 3. Portfolio / Projects (e.g. .filtr-item, .portfolio-thumb)
        portfolio_items = s.find_all(class_=re.compile(r"filtr-item|portfolio-thumb", re.I))
        if any("filtr-item" in " ".join(pi.get("class", [])) for pi in portfolio_items):
            portfolio_items = [pi for pi in portfolio_items if "filtr-item" in " ".join(pi.get("class", []))]
        if portfolio_items and not card_items:
            for idx_p, pi in enumerate(portfolio_items):
                th = pi.find(["h3", "h4", "h5", "strong"])
                t_val = clean_text(th.get_text()) if th else f"Project #{idx_p+1}"
                img_el = pi.find("img")
                a_el = pi.find("a")
                img_src = img_el.get("src", "") if img_el else ""
                href = a_el.get("href", "") if a_el else ""
                card_items.append({
                    "title": t_val,
                    "desc": href or f"Portfolio Project #{idx_p+1}",
                    "tag": f"Project #{idx_p+1}",
                    "stack": img_src or href
                })

        # 4. Client Logos / Partners
        logo_imgs = s.find_all("img", class_=re.compile(r"logo|client|partner", re.I))
        if logo_imgs and not card_items:
            for idx_l, img in enumerate(logo_imgs):
                alt = clean_text(img.get("alt", "")) or f"Partner #{idx_l+1}"
                src = img.get("src", "")
                card_items.append({
                    "title": alt.title() if len(alt) < 25 else f"Partner #{idx_l+1}",
                    "desc": f"Client Partner Asset: {src}",
                    "tag": f"Partner {idx_l+1}",
                    "stack": src
                })

        # 5. Reviews / Testimonials
        review_els = s.find_all(class_=re.compile(r"review-wrap|testimonial-wrap|swiper-slide", re.I))
        if any("review-wrap" in " ".join(re_el.get("class", [])) for re_el in review_els):
            review_els = [re_el for re_el in review_els if "review-wrap" in " ".join(re_el.get("class", []))]
        if review_els and not card_items:
            for idx_r, r_el in enumerate(review_els):
                rt = r_el.find(class_=re.compile(r"review-text|testimonial-text", re.I)) or r_el.find("p")
                rn = r_el.find(["h4", "h3", "h5", "strong"])
                img = r_el.find("img")
                r_text = clean_text(rt.get_text()) if rt else ""
                r_author = clean_text(rn.get_text()) if rn else f"Client #{idx_r+1}"
                img_src = img.get("src", "") if img else ""
                card_items.append({
                    "title": r_author,
                    "desc": r_text,
                    "tag": f"Review #{idx_r+1}",
                    "stack": img_src or "5-Star Rating"
                })

        # 6. Social Networks (if social container or footer-social)
        if any(w in s_id for w in ["social", "network"]):
            social_links = s.find_all("a")
            if social_links and not card_items:
                for idx_s, sa in enumerate(social_links):
                    sh = sa.find(["h4", "h5", "span"])
                    sname = clean_text(sh.get_text()) if sh else clean_text(sa.get_text())
                    href = sa.get("href", "#")
                    card_items.append({
                        "title": sname.title() if sname else f"Social #{idx_s+1}",
                        "desc": href,
                        "tag": "Social Profile",
                        "stack": href
                    })

        # 7. Standard Cards / Services / Features (with parent-child deduplication)
        if not card_items:
            # Prefer innermost card wrappers to prevent parent/child duplicate matches
            card_els = s.find_all(class_=re.compile(r"\b(?:card|service-wrap|service-item|service|feature-item|feature|thumb|exhibit|portfolio-item|pricing-card)\b", re.I))
            if not card_els:
                card_els = s.find_all(class_=re.compile(r"col-", re.I))

            for c in card_els:
                if h_tag and (h_tag in c.find_all(["h1", "h2", "h3", "h4"]) or c == h_tag):
                    continue
                ch = c.find(["h3", "h4", "h5", "strong"])
                ctitle = clean_text(ch.get_text()) if ch else ""
                if not ctitle or ctitle.lower() == headline.lower():
                    continue
                cp = c.find("p")
                cdesc = clean_text(cp.get_text()) if cp else ""
                ctag = c.find(class_=re.compile(r"tag|badge|date|year", re.I))
                ctag_text = clean_text(ctag.get_text()) if ctag else ""
                cstack = c.find(class_=re.compile(r"stack|tech|tools", re.I))
                cstack_text = clean_text(cstack.get_text()) if cstack else ""

                key = (ctitle.lower(), cdesc[:30].lower())
                if key not in seen_card_keys:
                    seen_card_keys.add(key)
                    card_items.append({
                        "title": ctitle,
                        "desc": cdesc,
                        "tag": ctag_text,
                        "stack": cstack_text
                    })

        # Check tabs in section (e.g. resume / timeline tabs)
        tabs = []
        for tb in s.find_all(["button", "a"], class_=re.compile(r"nav-link|tab", re.I)):
            t_txt = clean_text(tb.get_text())
            if t_txt and t_txt not in tabs and len(t_txt) < 30:
                tabs.append(t_txt)

        # Check category filter tags (e.g. portfolio work categories)
        filters = []
        filter_els = s.find_all(lambda tag: tag.name in ["li", "button", "a"] and (tag.has_attr("data-filter") or re.search(r"filtr|filter|category", " ".join(tag.get("class", [])))))
        if not filter_els:
            filter_menu = s.find(["ul", "div"], class_=re.compile(r"filter|control|portfolio-menu", re.I))
            if filter_menu:
                filter_els = filter_menu.find_all(["li", "button", "a"])
        for fel in filter_els:
            f_txt = clean_text(fel.get_text())
            if f_txt and f_txt not in filters and 0 < len(f_txt) < 30:
                filters.append(f_txt)

        # Social links extraction
        social_links = []
        if any(w in s_id for w in ["social", "network"]) or s.find(class_=re.compile(r"social", re.I)):
            seen_soc = set()
            for sa in s.find_all("a"):
                stxt = clean_text(sa.get_text())
                shref = sa.get("href", "#")
                if stxt and stxt.lower() not in seen_soc:
                    seen_soc.add(stxt.lower())
                    social_links.append({"platform": stxt.capitalize(), "url": shref})

        cat_name, icon_name = classify_section(s_id, headline)
        if s_id == "info" or any(w in s_id for w in ["contact_info", "reach_us"]):
            disp_name = "Contact Details"
            cat_name = "Direct Reach & Contact"
            icon_name = "Phone"
        elif any(w in s_id for w in ["social", "network"]):
            disp_name = "Social Networks"
            cat_name = "Social Channels"
            icon_name = "Share2"
        elif s_id in ["review", "reviews"]:
            disp_name = "Client Reviews"
            cat_name = "Social Proof & Reviews"
            icon_name = "Star"
        elif headline and 3 < len(headline) < 32:
            disp_name = headline
        elif s_id and len(s_id) > 2:
            disp_name = s_id.replace("_", " ").replace("-", " ").title()
        else:
            disp_name = f"Section {idx+1}"

        sec_data = {
            "title": headline or disp_name,
            "headline": headline or disp_name,
            "badgeText": badge,
            "subtitle": subtitle,
            "subheadline": subtitle,
            "description": narrative,
            "story": story or narrative,
            "themeColor": primary_color
        }

        if tabs:
            sec_data["tabs"] = tabs
        if filters:
            sec_data["filters"] = filters
        if social_links:
            sec_data["socialLinks"] = social_links

        # Buttons
        cta_btns = [clean_text(b.get_text()) for b in s.find_all(["a", "button"], class_=re.compile(r"btn|cta|button", re.I)) if 0 < len(clean_text(b.get_text())) < 25]
        if cta_btns:
            sec_data["primaryCta"] = cta_btns[0]
            if len(cta_btns) > 1:
                sec_data["secondaryCta"] = cta_btns[1]

        # Meta attributes (Role, Years Active, Status, etc. - ONLY real ones)
        if meta_items:
            sec_data["metaItems"] = meta_items
            for mi in meta_items:
                clean_k = re.sub(r"[^a-zA-Z0-9]", "", mi["label"]).lower()
                if "role" in clean_k: sec_data["role"] = mi["value"]
                elif "year" in clean_k: sec_data["yearsActive"] = mi["value"]
                elif "status" in clean_k: sec_data["status"] = mi["value"]
                elif "base" in clean_k or "loc" in clean_k: sec_data["location"] = mi["value"]

        # Specialized handling for direct contact info section
        if s_id == "info" or any(w in s_id for w in ["contact_info", "reach_us"]):
            sec_data["title"] = "Contact Information"
            sec_data["headline"] = "Contact Information"
            card_items = []
            for h in s.find_all(["h4", "h3", "h5", "p", "span", "a"]):
                txt = clean_text(h.get_text())
                if "@" in txt and not sec_data.get("email"):
                    sec_data["email"] = txt
                elif any(ch.isdigit() for ch in txt) and sum(ch.isdigit() for ch in txt) >= 7 and not sec_data.get("phone"):
                    sec_data["phone"] = txt
                elif any(w in txt.lower() for w in ["brooklyn", "st", "ave", "road", "street", "ny", "suite", "floor", "box", "city", "usa", "uk"]) and not sec_data.get("address"):
                    sec_data["address"] = txt

        # Cards (Support up to 20 items without arbitrary 6-item cap)
        if card_items:
            sec_data["cards"] = card_items[:20]
            for c_i, card in enumerate(card_items[:20]):
                sec_data[f"card{c_i+1}_title"] = card["title"]
                sec_data[f"card{c_i+1}_desc"] = card["desc"]
                if card["tag"]: sec_data[f"card{c_i+1}_tag"] = card["tag"]
                if card["stack"]: sec_data[f"card{c_i+1}_stack"] = card["stack"]

        # Form
        if has_form:
            sec_data["hasForm"] = True
            sec_data["buttonText"] = submit_text or "Submit"
            if len(inputs) > 0 and inputs[0]: sec_data["namePlaceholder"] = inputs[0]
            if len(inputs) > 1 and inputs[1]: sec_data["emailPlaceholder"] = inputs[1]
            if textareas and textareas[0]: sec_data["messagePlaceholder"] = textareas[0]
            if has_phone and phone_val:
                sec_data["hasPhone"] = True
                sec_data["phone"] = phone_val
            if has_address and address_val:
                sec_data["hasAddress"] = True
                sec_data["address"] = address_val

        # Contact Info fields (Phone / Email / Address from info section)
        phone_in_s = s.find(class_=re.compile(r"phone", re.I))
        email_in_s = s.find(class_=re.compile(r"email", re.I))
        address_in_s = s.find(class_=re.compile(r"address", re.I))
        if phone_in_s and not sec_data.get("phone"): sec_data["phone"] = clean_text(phone_in_s.get_text())
        if email_in_s and not sec_data.get("email"): sec_data["email"] = clean_text(email_in_s.get_text())
        if address_in_s and not sec_data.get("address"): sec_data["address"] = clean_text(address_in_s.get_text())

        # Universal Leaf Text Collector: Crawl all remaining text elements so NOTHING is missed
        captured_texts = set()
        for v in [sec_data.get("title"), sec_data.get("headline"), sec_data.get("subtitle"),
                  sec_data.get("subheadline"), sec_data.get("badgeText"), sec_data.get("description"),
                  sec_data.get("story"), sec_data.get("phone"), sec_data.get("email"), sec_data.get("address"),
                  sec_data.get("buttonText"), sec_data.get("primaryCta"), sec_data.get("secondaryCta")]:
            if v and isinstance(v, str):
                captured_texts.add(v.lower().strip())
        for c in card_items:
            for cv in [c.get("title"), c.get("desc"), c.get("tag"), c.get("stack")]:
                if cv and isinstance(cv, str):
                    captured_texts.add(cv.lower().strip())
        for tb in tabs:
            captured_texts.add(tb.lower().strip())
        for flt in filters:
            captured_texts.add(flt.lower().strip())
        for sl in social_links:
            captured_texts.add(sl.get("platform", "").lower().strip())

        text_items = []
        seen_leaf = set()
        for el in s.find_all(True):
            if el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'li', 'button', 'label', 'strong', 'em', 'small', 'div']:
                has_child_text = any(child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'li', 'button', 'label', 'strong'] for child in el.find_all(True))
                if not has_child_text:
                    ltxt = clean_text(el.get_text())
                    if ltxt and len(ltxt) > 1:
                        lt_lower = ltxt.lower()
                        is_cap = any(lt_lower == cap or (len(lt_lower) > 10 and lt_lower in cap) for cap in captured_texts)
                        if not is_cap and lt_lower not in seen_leaf:
                            seen_leaf.add(lt_lower)
                            text_items.append({
                                "id": f"txt_{len(text_items)+1}",
                                "tag": el.name,
                                "label": f"<{el.name}> Text",
                                "text": ltxt,
                                "originalText": ltxt
                            })
        if text_items:
            sec_data["textItems"] = text_items

        sections[s_id] = sec_data
        sections_list.append({
            "id": s_id,
            "name": disp_name,
            "category": cat_name,
            "icon": icon_name,
            "desc": f"Showcase component with {len(card_items)} items" if card_items else (f"Interactive form with {len(inputs)} fields" if has_form else "Content presentation section"),
            "targetSection": s_id
        })

    # 4. Footer Section
    footer_el = soup.find("footer")
    f_text = clean_text(footer_el.get_text()) if footer_el else ""
    c_match = re.search(r'(?:©|\(c\)|copyright)\s*\d{4}[^.\n]*', f_text, re.I)
    copyright_text = c_match.group(0) if c_match else f"© 2026 {brand_name}. All rights reserved."
    sections["footer"] = {
        "brandName": brand_name,
        "tagline": "All rights reserved.",
        "copyright": copyright_text,
        "themeColor": primary_color
    }
    sections_list.append({
        "id": "footer",
        "name": "Website Footer",
        "category": "Footer & Record",
        "icon": "Shield",
        "desc": "Site footer with brand signature, legal copyright, and navigation links",
        "targetSection": "footer"
    })

    # Master Brand
    contact_sec = next((s for s in sections.values() if s.get("hasForm")), {})
    info_sec = sections.get("info", {})
    brand = {
        "business_name": brand_name,
        "logo_text": re.sub(r"[^A-Z0-9]", "", brand_name.upper())[:7] or "BRAND",
        "tagline": page_title,
        "primary_color": primary_color
    }
    phone_val = contact_sec.get("phone") or info_sec.get("phone")
    email_val = contact_sec.get("email") or info_sec.get("email")
    if phone_val:
        brand["contact_phone"] = phone_val
    if email_val:
        brand["contact_email"] = email_val

    return {
        "status": "success",
        "template_id": template_id,
        "brand": brand,
        "sections": sections,
        "sections_list": sections_list
    }


@router.post("/live/{template_id}/edit-manual")
async def edit_live_preview_manual(
    template_id: str,
    request: ManualEditRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    original_template_id = str(template.id)
    is_new_clone = False

    # If the template is PUBLISHED or belongs to another user, clone/fork it so the user modifies their own private DRAFT copy
    is_user_owned_draft = (
        template.status == TemplateStatus.DRAFT 
        and current_user 
        and template.seller_id == current_user.id
    )

    if not is_user_owned_draft:
        existing_draft = None
        if current_user:
            slug_prefix = template.slug.split("-custom-")[0]
            ed_res = await db.execute(
                select(Template).where(
                    Template.seller_id == current_user.id,
                    Template.status == TemplateStatus.DRAFT,
                    Template.slug.like(f"{slug_prefix}-custom-%")
                )
            )
            existing_draft = ed_res.scalars().first()
            
        if existing_draft:
            template = existing_draft
            template_id = str(existing_draft.id)
        else:
            is_new_clone = True
            custom_bname = request.business_name.strip() if request.business_name else ""
            custom_title = f"{custom_bname} (Customized)" if custom_bname else f"Customized {template.title}"
            new_template = Template(
                title=custom_title,
                short_description=template.short_description,
                description=template.description,
                slug=f"{template.slug.split('-custom-')[0]}-custom-{uuid.uuid4().hex[:6]}",
                price=template.price,
                original_price=template.original_price,
                is_free=template.is_free,
                is_on_sale=template.is_on_sale,
                category_id=template.category_id,
                status=TemplateStatus.DRAFT,
                seller_id=current_user.id if current_user else template.seller_id,
                thumbnail_url=template.thumbnail_url,
                preview_url=template.preview_url,
                tags=template.tags,
                framework=template.framework,
                pages_count=template.pages_count,
                has_dark_mode=template.has_dark_mode,
                is_responsive=template.is_responsive,
                is_rtl_supported=template.is_rtl_supported,
                is_ai_ready=True,
                compatibility=template.compatibility,
                version=template.version,
                license_type=template.license_type,
                industry=template.industry,
                color_scheme=template.color_scheme,
                seo_keywords=template.seo_keywords,
                included_pages=template.included_pages,
                download_assets=template.download_assets.copy() if template.download_assets else {}
            )
            db.add(new_template)
            await db.flush()
            template = new_template
            template_id = str(new_template.id)

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    if not match:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
    file_id = uuid.UUID(match.group(1))
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")
        
    zip_data = stored_file.data
    
    # 1. Read all editable files in the ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        for name in z_in.namelist():
            is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
            if (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".css") or name.endswith(".tsx") or name.endswith(".ts")) and not is_build:
                try:
                    files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")

    updated_filenames = set()

    # 2. Fast, Guaranteed Direct Deterministic Replacements across all files
    try:
        extracted = await get_live_preview_extracted_data(original_template_id, db)
    except Exception as ex_ext:
        logger.warning(f"Could not pre-extract sections for direct replacement: {ex_ext}")
        extracted = {}

    orig_brand = extracted.get("brand", {}).get("business_name")
    orig_primary_color = extracted.get("brand", {}).get("primary_color")
    orig_sections = extracted.get("sections", {})

    # (a) Business Name Replacement across all case variations
    if request.business_name:
        new_bname = request.business_name.strip()
        names_to_replace = []
        if orig_brand and orig_brand.strip() and orig_brand.strip() != new_bname:
            ob = orig_brand.strip()
            names_to_replace.extend([
                (ob, new_bname),
                (ob.upper(), new_bname.upper()),
                (ob.lower(), new_bname.lower()),
                (ob.title(), new_bname.title()),
            ])
            # Also if original brand was multi-word like "Jerome Pascal", also match "Jerome" or "Pascal" in isolated headers
            parts = ob.split()
            if len(parts) > 1:
                names_to_replace.append((ob.replace(" ", "<br>"), new_bname))
                names_to_replace.append((ob.upper().replace(" ", "<br>"), new_bname.upper()))
        if template.title and template.title.strip() != new_bname:
            tb = template.title.strip()
            names_to_replace.extend([
                (tb, new_bname),
                (tb.upper(), new_bname.upper()),
                (tb.lower(), new_bname.lower()),
                (tb.title(), new_bname.title()),
            ])

        for old_str, new_str in names_to_replace:
            if len(old_str) > 1:
                for fname in files_dict:
                    if old_str in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_str, new_str)
                        updated_filenames.add(fname)

    # (b) Primary Theme Color Replacement
    if request.primary_color:
        new_color = request.primary_color.strip()
        colors_to_replace = set()
        if orig_primary_color and orig_primary_color.lower() != new_color.lower():
            colors_to_replace.add(orig_primary_color)
            colors_to_replace.add(orig_primary_color.lower())
            colors_to_replace.add(orig_primary_color.upper())

        for c_old in colors_to_replace:
            for fname in files_dict:
                if fname.endswith(".css") or fname.endswith(".html") or fname.endswith(".jsx") or fname.endswith(".tsx"):
                    if c_old in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(c_old, new_color)
                        updated_filenames.add(fname)

    # (c) Global Contact Email & Phone
    if request.contact_email:
        new_email = request.contact_email.strip()
        for s_data in orig_sections.values():
            if isinstance(s_data, dict) and s_data.get("email"):
                old_email = s_data["email"].strip()
                if old_email and old_email != new_email:
                    for fname in files_dict:
                        if old_email in files_dict[fname]:
                            files_dict[fname] = files_dict[fname].replace(old_email, new_email)
                            updated_filenames.add(fname)

    if request.contact_phone:
        new_phone = request.contact_phone.strip()
        for s_data in orig_sections.values():
            if isinstance(s_data, dict) and s_data.get("phone"):
                old_phone = s_data["phone"].strip()
                if old_phone and old_phone != new_phone:
                    for fname in files_dict:
                        if old_phone in files_dict[fname]:
                            files_dict[fname] = files_dict[fname].replace(old_phone, new_phone)
                            updated_filenames.add(fname)

    # (d) Section-by-Section Edits (Titles, Subtitles, Descriptions, CTAs, Cards, Tabs, Filters, Text Items)
    if request.page_edits and isinstance(request.page_edits, dict):
        for p_name, p_data in request.page_edits.items():
            if not isinstance(p_data, dict):
                continue
            orig_s = orig_sections.get(p_name, {})

            # Logo Monogram / Code
            new_logo = (p_data.get("logoText") or p_data.get("logo_text") or "").strip()
            old_logo = (orig_s.get("logoText") or orig_s.get("logo_text") or extracted.get("brand", {}).get("logo_text") or "").strip()
            if new_logo and old_logo and new_logo != old_logo:
                for fname in files_dict:
                    if old_logo in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_logo, new_logo)
                        updated_filenames.add(fname)
                    if old_logo.upper() in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_logo.upper(), new_logo.upper())
                        updated_filenames.add(fname)

            # Title / Headline (with case sensitivity variations)
            new_title = (p_data.get("title") or p_data.get("brandName") or "").strip()
            old_title = (orig_s.get("title") or orig_s.get("headline") or orig_s.get("brandName") or "").strip()
            if new_title and old_title and new_title != old_title:
                for fname in files_dict:
                    if old_title in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_title, new_title)
                        updated_filenames.add(fname)
                    if old_title.upper() in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_title.upper(), new_title.upper())
                        updated_filenames.add(fname)
                    if old_title.lower() in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_title.lower(), new_title.lower())
                        updated_filenames.add(fname)

            # Subtitle / Subheadline
            new_sub = (p_data.get("subtitle") or "").strip()
            old_sub = (orig_s.get("subtitle") or orig_s.get("subheadline") or "").strip()
            if new_sub and old_sub and new_sub != old_sub:
                for fname in files_dict:
                    if old_sub in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_sub, new_sub)
                        updated_filenames.add(fname)
                    if old_sub.upper() in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_sub.upper(), new_sub.upper())
                        updated_filenames.add(fname)

            # Description / Story
            new_desc = (p_data.get("description") or "").strip()
            old_desc = (orig_s.get("description") or orig_s.get("story") or "").strip()
            if new_desc and old_desc and new_desc != old_desc:
                for fname in files_dict:
                    if old_desc in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_desc, new_desc)
                        updated_filenames.add(fname)

            # CTA Text
            new_cta = (p_data.get("cta_text") or "").strip()
            old_cta = (orig_s.get("primaryCta") or orig_s.get("buttonText") or orig_s.get("ctaText") or "").strip()
            if new_cta and old_cta and new_cta != old_cta:
                for fname in files_dict:
                    if old_cta in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_cta, new_cta)
                        updated_filenames.add(fname)
                    if old_cta.upper() in files_dict[fname]:
                        files_dict[fname] = files_dict[fname].replace(old_cta.upper(), new_cta.upper())
                        updated_filenames.add(fname)

            # Nav Links
            new_nav_links = p_data.get("navLinks") or p_data.get("nav_links") or []
            old_nav_links = orig_s.get("navLinks") or orig_s.get("nav_links") or []
            if isinstance(new_nav_links, list) and isinstance(old_nav_links, list):
                for o_lnk, n_lnk in zip(old_nav_links, new_nav_links):
                    o_l = str(o_lnk).strip()
                    n_l = str(n_lnk).strip()
                    if o_l and n_l and o_l != n_l:
                        for fname in files_dict:
                            if o_l in files_dict[fname]:
                                files_dict[fname] = files_dict[fname].replace(o_l, n_l)
                                updated_filenames.add(fname)
                            if o_l.upper() in files_dict[fname]:
                                files_dict[fname] = files_dict[fname].replace(o_l.upper(), n_l.upper())
                                updated_filenames.add(fname)

            # Tabs
            new_tabs = p_data.get("tabs", [])
            old_tabs = orig_s.get("tabs", [])
            if isinstance(new_tabs, list) and isinstance(old_tabs, list):
                for o_tab, n_tab in zip(old_tabs, new_tabs):
                    o_tab_s = str(o_tab).strip()
                    n_tab_s = str(n_tab).strip()
                    if o_tab_s and n_tab_s and o_tab_s != n_tab_s:
                        for fname in files_dict:
                            if o_tab_s in files_dict[fname]:
                                files_dict[fname] = files_dict[fname].replace(o_tab_s, n_tab_s)
                                updated_filenames.add(fname)

            # Category Filters
            new_filters = p_data.get("filters", [])
            old_filters = orig_s.get("filters", [])
            if isinstance(new_filters, list) and isinstance(old_filters, list):
                for o_f, n_f in zip(old_filters, new_filters):
                    o_f_s = str(o_f).strip()
                    n_f_s = str(n_f).strip()
                    if o_f_s and n_f_s and o_f_s != n_f_s:
                        for fname in files_dict:
                            if o_f_s in files_dict[fname]:
                                files_dict[fname] = files_dict[fname].replace(o_f_s, n_f_s)
                                updated_filenames.add(fname)

            # Cards
            new_cards = p_data.get("cards", [])
            old_cards = orig_s.get("cards", [])
            if isinstance(new_cards, list) and isinstance(old_cards, list):
                for o_card, n_card in zip(old_cards, new_cards):
                    if isinstance(o_card, dict) and isinstance(n_card, dict):
                        o_ctitle = (o_card.get("title") or "").strip()
                        n_ctitle = (n_card.get("title") or "").strip()
                        if o_ctitle and n_ctitle and o_ctitle != n_ctitle:
                            for fname in files_dict:
                                if o_ctitle in files_dict[fname]:
                                    files_dict[fname] = files_dict[fname].replace(o_ctitle, n_ctitle)
                                    updated_filenames.add(fname)
                        o_cdesc = (o_card.get("desc") or "").strip()
                        n_cdesc = (n_card.get("desc") or "").strip()
                        if o_cdesc and n_cdesc and o_cdesc != n_cdesc:
                            for fname in files_dict:
                                if o_cdesc in files_dict[fname]:
                                    files_dict[fname] = files_dict[fname].replace(o_cdesc, n_cdesc)
                                    updated_filenames.add(fname)
                        o_ctag = (o_card.get("tag") or "").strip()
                        n_ctag = (n_card.get("tag") or "").strip()
                        if o_ctag and n_ctag and o_ctag != n_ctag:
                            for fname in files_dict:
                                if o_ctag in files_dict[fname]:
                                    files_dict[fname] = files_dict[fname].replace(o_ctag, n_ctag)
                                    updated_filenames.add(fname)

            # Text Items (exact match replace)
            for ti in p_data.get("textItems", []):
                orig = (ti.get("originalText") or "").strip()
                new_t = (ti.get("text") or "").strip()
                if orig and new_t and orig != new_t:
                    for fname in files_dict:
                        if orig in files_dict[fname]:
                            files_dict[fname] = files_dict[fname].replace(orig, new_t)
                            updated_filenames.add(fname)

    # 3. Use Gemini for smart content/styling updates across all files
    files_str = ""
    for name, content in files_dict.items():
        files_str += f"\n--- FILE: {name} ---\n{content}\n"

    page_edits_str = ""
    if request.page_edits:
        page_edits_str = "\nAlso apply these page-specific content overrides:\n"
        for page_name, edits in request.page_edits.items():
            page_name_clean = page_name.replace(".html", "").replace(".jsx", "").replace(".js", "").replace(".tsx", "").replace(".ts", "")
            page_edits_str += f"- For page/file '{page_name}' (If the template is a single-page template/only has index.html, map these changes to the corresponding section like #{page_name_clean} or the '{page_name_clean}' area inside index.html):\n"
            if edits.get("title"):
                page_edits_str += f"  * Set main title/header/headline to: \"{edits['title']}\"\n"
            if edits.get("subtitle"):
                page_edits_str += f"  * Set subtitle / hook text to: \"{edits['subtitle']}\"\n"
            if edits.get("description"):
                page_edits_str += f"  * Set main body content/description/story to: \"{edits['description']}\"\n"
            if edits.get("cta_text"):
                page_edits_str += f"  * Set primary Call to Action (CTA) button text to: \"{edits['cta_text']}\"\n"
            if edits.get("cta_link"):
                page_edits_str += f"  * Set primary Call to Action (CTA) button link/href/action to: \"{edits['cta_link']}\"\n"
            if edits.get("phone"):
                page_edits_str += f"  * Set phone number to: \"{edits['phone']}\"\n"
            if edits.get("email"):
                page_edits_str += f"  * Set contact email to: \"{edits['email']}\"\n"
            if edits.get("address"):
                page_edits_str += f"  * Set address / location to: \"{edits['address']}\"\n"
            if edits.get("tabs") and isinstance(edits["tabs"], list):
                page_edits_str += f"  * Set section tabs/pills labels to: {edits['tabs']}\n"
            if edits.get("filters") and isinstance(edits["filters"], list):
                page_edits_str += f"  * Set category filter buttons to: {edits['filters']}\n"
            if edits.get("cards") and isinstance(edits["cards"], list):
                for idx_c, card in enumerate(edits["cards"]):
                    page_edits_str += f"  * Item/Card #{idx_c+1}: title=\"{card.get('title','')}\", description=\"{card.get('desc','')}\", tag=\"{card.get('tag','')}\", stack=\"{card.get('stack','')}\"\n"
            if edits.get("textItems") and isinstance(edits["textItems"], list):
                for ti in edits["textItems"]:
                    orig = ti.get("originalText") or ti.get("text")
                    new_t = ti.get("text")
                    if orig and new_t and orig != new_t:
                        page_edits_str += f"  * Replace text snippet \"{orig}\" with: \"{new_t}\"\n"

    edit_prompt = f"""You are a specialized React/HTML code refactoring tool.
Your task is to take the provided website template files and replace specific business fields and styles with these new values:
- Business Name: {request.business_name}
- About Description: {request.about}
- Primary Theme Color Accent: {request.primary_color}
- Secondary Theme Color Accent: {request.secondary_color}
- Contact Email: {request.contact_email or ""}
- Contact Phone: {request.contact_phone or ""}
{page_edits_str}

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code exactly, including leading spaces and indentation.
3. The "replace" string must contain the updated code to replace it.
4. Replace all occurrences of old business names, descriptions, accent colors, and contact info in the code.
5. If the template is a single-page template (index.html), apply all page/section overrides to the corresponding sections inside index.html.

Format the JSON response exactly like this:
[
  {{
    "filename": "src/App.tsx",
    "find": "const [title, setTitle] = useState('Old Title');",
    "replace": "const [title, setTitle] = useState('New Title');"
  }}
]

Here are the codebase files:
{files_str}
"""
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    try:
        import json
        raw_code = await ai_service._generate_content(edit_prompt, response_mime_type="application/json", feature_name="code_assistant")
        chunks = json.loads(clean_code_response(raw_code, "json"))
        if isinstance(chunks, list):
            for chunk in chunks:
                filename = chunk.get("filename")
                find_str = chunk.get("find")
                replace_str = chunk.get("replace")
                if not filename or find_str is None or replace_str is None:
                    continue
                matched_name = None
                for name in files_dict:
                    if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                        matched_name = name
                        break
                if matched_name:
                    if find_str in files_dict[matched_name]:
                        files_dict[matched_name] = files_dict[matched_name].replace(find_str, replace_str)
                        updated_filenames.add(matched_name)
                    else:
                        cleaned_find = find_str.strip()
                        if cleaned_find and cleaned_find in files_dict[matched_name]:
                            files_dict[matched_name] = files_dict[matched_name].replace(cleaned_find, replace_str.strip())
                            updated_filenames.add(matched_name)
    except Exception as e_ai:
        logger.warning(f"AI edit refactor fallback notice: {e_ai}")

    # If no files updated by AI or direct text, update business name and primary color directly
    if not updated_filenames:
        for name in files_dict:
            if name.endswith(".html") or name.endswith(".jsx") or name.endswith(".tsx"):
                files_dict[name] = files_dict[name].replace(template.title or "Port", request.business_name)
                updated_filenames.add(name)

    # 4. Overwrite files in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename in updated_filenames:
                    content = files_dict[item.filename].encode("utf-8")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 5. Save the updated ZIP back to the database as an isolated StoredFile
    new_stored_file = StoredFile(
        storage_key=f"templates/{uuid.uuid4().hex}/customized.zip",
        original_filename=f"customized_{stored_file.original_filename or 'template.zip'}",
        content_type=stored_file.content_type or "application/zip",
        size=len(new_zip_bytes),
        data=new_zip_bytes
    )
    db.add(new_stored_file)
    await db.flush()
    template.download_assets = {
        "zip": f"/api/v1/files/{new_stored_file.id}"
    }
    if request.business_name and request.business_name.strip():
        template.title = f"{request.business_name.strip()} (Customized)"

    # Automatically generate visual snapshot thumbnail
    try:
        from app.services.screenshot_service import screenshot_service
        cat_name = "Modern Website"
        if hasattr(template, "category") and template.category:
            cat_name = template.category.name if hasattr(template.category, "name") else str(template.category)
        thumb_url = screenshot_service.save_thumbnail(
            template_id=str(template.id),
            title=template.title or "Custom Website",
            framework=template.framework or "HTML",
            category=cat_name,
        )
        template.thumbnail_url = thumb_url
    except Exception as thumb_err:
        logger.warning(f"Could not auto-generate thumbnail: {thumb_err}")

    db.add(template)
    await db.flush()
    
    # 6. Extract updated files ONLY into this user draft's isolated live preview directory
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    os.makedirs(preview_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(new_zip_bytes), "r") as z_refresh:
        z_refresh.extractall(preview_dir)
            
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id), "title": template.title, "thumbnail_url": template.thumbnail_url, "original_template_id": original_template_id}


class FindReplaceRequest(BaseModel):
    find_text: str
    replace_text: str


@router.post("/live/{template_id}/find-replace")
async def edit_live_preview_find_replace(
    template_id: str,
    request: FindReplaceRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # If the template is PUBLISHED, clone it so the user modifies their own private DRAFT copy
    if template.status == TemplateStatus.PUBLISHED:
        new_template = Template(
            title=f"Customized {template.title}",
            short_description=template.short_description,
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            original_price=template.original_price,
            is_free=template.is_free,
            is_on_sale=template.is_on_sale,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            seller_id=current_user.id if current_user else template.seller_id,
            thumbnail_url=template.thumbnail_url,
            preview_url=template.preview_url,
            tags=template.tags,
            framework=template.framework,
            pages_count=template.pages_count,
            has_dark_mode=template.has_dark_mode,
            is_responsive=template.is_responsive,
            is_rtl_supported=template.is_rtl_supported,
            is_ai_ready=template.is_ai_ready,
            compatibility=template.compatibility,
            version=template.version,
            license_type=template.license_type,
            industry=template.industry,
            color_scheme=template.color_scheme,
            seo_keywords=template.seo_keywords,
            included_pages=template.included_pages,
            download_assets=template.download_assets.copy() if template.download_assets else {}
        )
        db.add(new_template)
        await db.flush()
        template = new_template
        template_id = new_template.id

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    file_id_str = zip_url.split("/")[-1]
    try:
        file_id = uuid.UUID(file_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")
        
    zip_data = stored_file.data
    
    # 1. Read files and do find-and-replace
    updated_filenames = set()
    new_zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                is_build = any(d in item.filename.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
                is_text = (item.filename.endswith(".html") or 
                           item.filename.endswith(".jsx") or 
                           item.filename.endswith(".js") or 
                           item.filename.endswith(".css") or 
                           item.filename.endswith(".tsx") or 
                           item.filename.endswith(".ts") or
                           item.filename.endswith(".json")) and not is_build
                           
                if is_text:
                    try:
                        text_content = content.decode("utf-8", errors="ignore")
                        if request.find_text in text_content:
                            text_content = text_content.replace(request.find_text, request.replace_text)
                            content = text_content.encode("utf-8")
                            updated_filenames.add(item.filename)
                            print(f"Replaced text in: {item.filename}")
                    except Exception:
                        pass
                z_out.writestr(item, content)
                
    if not updated_filenames:
        return {"status": "success", "template_id": str(template_id), "matches_found": 0}
        
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 2. Save the updated ZIP back to the database
    stored_file.data = new_zip_bytes
    stored_file.size = len(new_zip_bytes)
    db.add(stored_file)
    await db.flush()
    
    # 3. Clear local preview directory cache
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id), "matches_found": len(updated_filenames)}


@router.post("/live/{template_id}/edit-ai")
async def edit_live_preview_ai(
    template_id: str,
    request: AIEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # If the template is PUBLISHED or belongs to another user, clone/fork it so the user modifies their own private DRAFT copy
    is_user_owned_draft = (
        template.status == TemplateStatus.DRAFT 
        and current_user 
        and template.seller_id == current_user.id
    )

    if not is_user_owned_draft:
        existing_draft = None
        if current_user:
            slug_prefix = template.slug.split("-custom-")[0]
            ed_res = await db.execute(
                select(Template).where(
                    Template.seller_id == current_user.id,
                    Template.status == TemplateStatus.DRAFT,
                    Template.slug.like(f"{slug_prefix}-custom-%")
                )
            )
            existing_draft = ed_res.scalars().first()
            
        if existing_draft:
            template = existing_draft
            template_id = str(existing_draft.id)
        else:
            new_template = Template(
                title=f"Customized {template.title}",
                short_description=template.short_description,
                description=template.description,
                slug=f"{template.slug.split('-custom-')[0]}-custom-{uuid.uuid4().hex[:6]}",
                price=template.price,
                original_price=template.original_price,
                is_free=template.is_free,
                is_on_sale=template.is_on_sale,
                category_id=template.category_id,
                status=TemplateStatus.DRAFT,
                seller_id=current_user.id if current_user else template.seller_id,
                thumbnail_url=template.thumbnail_url,
                preview_url=template.preview_url,
                tags=template.tags,
                framework=template.framework,
                pages_count=template.pages_count,
                has_dark_mode=template.has_dark_mode,
                is_responsive=template.is_responsive,
                is_rtl_supported=template.is_rtl_supported,
                is_ai_ready=True,
                compatibility=template.compatibility,
                version=template.version,
                license_type=template.license_type,
                industry=template.industry,
                color_scheme=template.color_scheme,
                seo_keywords=template.seo_keywords,
                included_pages=template.included_pages,
                download_assets=template.download_assets.copy() if template.download_assets else {}
            )
            db.add(new_template)
            await db.flush()
            template = new_template
            template_id = str(new_template.id)

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    file_id_str = zip_url.split("/")[-1]
    try:
        file_id = uuid.UUID(file_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
        
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")
        
    zip_data = stored_file.data
    
    # 1. Read all editable files in the ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        for name in z_in.namelist():
            is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
            if (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".css") or name.endswith(".tsx") or name.endswith(".ts")) and not is_build:
                try:
                    files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")
        
    # 2. Use Gemini to do AI editing/refinement across the codebase
    files_str = ""
    for name, content in files_dict.items():
        files_str += f"\n--- FILE: {name} ---\n{content}\n"

    ai_prompt = f"""You are a senior lead web developer.
Refine the provided website template files according to this user request: "{request.prompt}".

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code exactly, including leading spaces and indentation.
3. The "replace" string must contain the updated code to replace it.
4. Keep the search blocks as small and precise as possible to avoid mistakes.

Format the JSON response exactly like this:
[
  {{
    "filename": "src/App.tsx",
    "find": "const [title, setTitle] = useState('Old Title');",
    "replace": "const [title, setTitle] = useState('New Title');"
  }}
]

Here are the codebase files:
{files_str}
"""
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    try:
        import json
        raw_code = await ai_service._generate_content(ai_prompt, response_mime_type="application/json", feature_name="code_assistant")
        chunks = json.loads(clean_code_response(raw_code, "json"))
        if not isinstance(chunks, list):
            if isinstance(chunks, dict):
                chunks = [{"filename": k, "find": files_dict.get(k, ""), "replace": v} for k, v in chunks.items()]
            else:
                chunks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine template code via AI: {str(e)}")
        
    # Apply chunks to files_dict
    updated_filenames = set()
    for chunk in chunks:
        filename = chunk.get("filename")
        find_str = chunk.get("find")
        replace_str = chunk.get("replace")
        if not filename or find_str is None or replace_str is None:
            continue
        matched_name = None
        for name in files_dict:
            if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                matched_name = name
                break
        if matched_name:
            if find_str in files_dict[matched_name]:
                files_dict[matched_name] = files_dict[matched_name].replace(find_str, replace_str)
                updated_filenames.add(matched_name)
                print(f"Applied AI replacement chunk for {matched_name}")
            else:
                # Try simple replacement if exact match failed due to spacing
                cleaned_find = find_str.strip()
                if cleaned_find and cleaned_find in files_dict[matched_name]:
                    files_dict[matched_name] = files_dict[matched_name].replace(cleaned_find, replace_str.strip())
                    updated_filenames.add(matched_name)
                    print(f"Applied fuzzy-spaced AI replacement chunk for {matched_name}")

    # 3. Overwrite files in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename in updated_filenames:
                    content = files_dict[item.filename].encode("utf-8")
                    print(f"Saved AI edited file to ZIP: {item.filename}")
                z_out.writestr(item, content)
                
    # 4. Save the updated ZIP back to the database as an isolated StoredFile
    new_stored_file = StoredFile(
        storage_key=f"templates/{uuid.uuid4().hex}/customized_ai.zip",
        original_filename=f"customized_{stored_file.original_filename or 'template.zip'}",
        content_type=stored_file.content_type or "application/zip",
        size=len(new_zip_bytes),
        data=new_zip_bytes
    )
    db.add(new_stored_file)
    await db.flush()
    template.download_assets = {
        "zip": f"/api/v1/files/{new_stored_file.id}"
    }
    db.add(template)
    await db.flush()
    
    # 5. Extract updated files ONLY into this user draft's isolated live preview directory
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    os.makedirs(preview_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(new_zip_bytes), "r") as z_refresh:
        z_refresh.extractall(preview_dir)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id)}

@router.api_route("/live/{template_id}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
@router.api_route("/live/{template_id}/{filepath:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
async def serve_live_preview(
    template_id: str,
    request: Request,
    filepath: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Redirect to URL with trailing slash to ensure relative assets load correctly in browser
    if not filepath and not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=str(request.url) + "/")
    """
    Dynamically extract, compile (if needed), and serve the template's actual frontend code in the browser as a running live demo.
    """
    import os
    import zipfile
    import io
    import mimetypes
    import asyncio
    import platform
    import subprocess
    import tempfile
    from fastapi.responses import Response
    from sqlalchemy import select
    from app.repositories.template_repo import TemplateRepository
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id_or_slug(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    target_slug = template.slug if (template and template.slug) else str(template_id)
    purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

    watermark_payload = """
<!-- Injected Watermark Grid Overlay -->
<div class="preview-watermark-grid"></div>

<!-- Injected Purchase Footer Banner -->
<div class="preview-purchase-footer-banner">
  <span>🔒 Watermarked Draft Preview. Purchase this template to download clean project assets.</span>
  <a href="__PURCHASE_URL__" target="_top">Purchase Template &rarr;</a>
</div>

<style>
  /* Disable text selection across all elements */
  * {
    user-select: none !important;
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
  }

  /* Watermark grid covering full page with pointer-events disabled */
  .preview-watermark-grid {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    pointer-events: none !important;
    z-index: 999999 !important;
    opacity: 0.65 !important;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
    background-repeat: repeat !important;
  }

  /* Bottom floating warning banner */
  .preview-purchase-footer-banner {
    position: fixed !important;
    bottom: 1.5rem !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    background: rgba(15, 23, 42, 0.96) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    color: #ffffff !important;
    padding: 0.625rem 1.25rem !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    border-radius: 9999px !important;
    display: flex !important;
    align-items: center !important;
    gap: 1rem !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
    z-index: 999998 !important;
    white-space: nowrap !important;
    font-family: system-ui, -apple-system, sans-serif !important;
  }

  .preview-purchase-footer-banner a {
    color: #38bdf8 !important;
    text-decoration: none !important;
    font-weight: 800 !important;
    border-left: 1px solid rgba(255, 255, 255, 0.2) !important;
    padding-left: 1rem !important;
    transition: color 0.2s ease !important;
  }

  .preview-purchase-footer-banner a:hover {
    color: #0ea5e9 !important;
  }

  /* Robust navigation bar and button layout protection */
  .navbar, nav, header nav, .nav-container {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 0.5rem !important;
  }

  .navbar .btn, nav a.btn, nav button, nav .nav-btn, .nav-cta, a.btn, button.btn {
    white-space: nowrap !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: max-content !important;
    line-height: 1.25 !important;
  }

  /* Block PDF printing */
  @media print {
    body {
      display: none !important;
    }
  }
</style>

<script>
  (function() {
    // 1. Disable Right-Click Context Menu
    document.addEventListener('contextmenu', function(e) {
      e.preventDefault();
    }, true);

    // 2. Intercept Inspector, View-Source, Copy and Save keys
    document.addEventListener('keydown', function(e) {
      if (
        e.key === 'F12' ||
        (e.ctrlKey && e.shiftKey && e.key === 'I') ||
        (e.ctrlKey && e.shiftKey && e.key === 'C') ||
        (e.ctrlKey && e.shiftKey && e.key === 'J') ||
        (e.ctrlKey && e.key === 'u') ||
        (e.ctrlKey && e.key === 'c') ||
        (e.ctrlKey && e.key === 's')
      ) {
        e.preventDefault();
        e.stopPropagation();
        return false;
      }
    }, true);
  })();
</script>
""".replace("__PURCHASE_URL__", purchase_url)
    async def serve_fallback(err_msg: str = "Preview compilation"):
        if filepath and not (filepath.endswith(".html") or filepath.endswith(".htm")):
            if filepath.endswith(".css"):
                return Response(content=b"", media_type="text/css")
            if filepath.endswith(".js"):
                return Response(content=b"", media_type="application/javascript")
            return Response(content=b"", media_type="application/octet-stream")

        # 1. First attempt: In-Browser Standalone React/Babel Runner for App.jsx
        app_jsx_content = None
        index_css_content = ""
        preview_dir_loc = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
        
        if os.path.isdir(preview_dir_loc):
            for root, _, files in os.walk(preview_dir_loc):
                if any(d in root.replace("\\", "/").split("/") for d in ["dist", "build", ".output"]):
                    continue
                if "App.jsx" in files:
                    try:
                        with open(os.path.join(root, "App.jsx"), "r", encoding="utf-8", errors="ignore") as f:
                            raw_app = f.read()
                            from app.services.ai_service import clean_code_response, repair_truncated_jsx
                            app_jsx_content = repair_truncated_jsx(clean_code_response(raw_app, "jsx"))
                    except Exception:
                        pass
                if "index.css" in files:
                    try:
                        with open(os.path.join(root, "index.css"), "r", encoding="utf-8", errors="ignore") as f:
                            index_css_content = f.read()
                    except Exception:
                        pass

        if app_jsx_content:
            try:
                # Clean imports/exports for in-browser standalone execution
                cleaned_jsx = app_jsx_content
                cleaned_jsx = re.sub(r'import\s+.*?from\s+[\'"].*?[\'"];?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'import\s+[\'"].*?[\'"];?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'export\s+default\s+[A-Za-z0-9_]+\s*;?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'export\s+', '', cleaned_jsx)

                comp_name = "App"
                if "function App" not in cleaned_jsx and "const App" not in cleaned_jsx and "let App" not in cleaned_jsx:
                    func_m = re.search(r'function\s+([A-Za-z0-9_]+)', cleaned_jsx)
                    if func_m:
                        comp_name = func_m.group(1)

                react_runner_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{template.title} - Live Preview</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.24.0/babel.min.js"></script>
  <script src="https://unpkg.com/lucide-react@0.344.0/dist/umd/lucide-react.js"></script>
  <style>
    body {{ margin: 0; background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }}
    {index_css_content}
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    const LucideIcons = window.lucide || window.LucideReact || {{}};
    const {{ 
      Sparkles = () => null, ArrowLeft = () => null, ArrowRight = () => null, 
      Loader2 = () => null, CheckCircle2 = () => null, CheckCircle = () => null, 
      Cpu = () => null, Globe = () => null, Layers = () => null, FileText = () => null, 
      Plus = () => null, Trash2 = () => null, Info = () => null, Building2 = () => null, 
      Palette = () => null, Phone = () => null, Mail = () => null, MapPin = () => null, 
      Share2 = () => null, Wand2 = () => null, Edit3 = () => null, Check = () => null, 
      RefreshCw = () => null, Eye = () => null, Upload = () => null, ShoppingBag = () => null, 
      ShoppingCart = () => null, Folder = () => null, ExternalLink = () => null, 
      Sliders = () => null, Bot = () => null, User = () => null, Zap = () => null, 
      Heart = () => null, Star = () => null, Code = () => null, Play = () => null, 
      AlertCircle = () => null, Shield = () => null, Award = () => null,
      TrendingUp = () => null, DollarSign = () => null, Database = () => null, 
      Server = () => null, Terminal = () => null, Lock = () => null, Key = () => null
    }} = LucideIcons;

    const useState = React.useState;
    const useEffect = React.useEffect;
    const useRef = React.useRef;
    const useMemo = React.useMemo;
    const useCallback = React.useCallback;

    {cleaned_jsx}

    try {{
      const container = document.getElementById('root');
      const root = ReactDOM.createRoot(container);
      root.render(React.createElement({comp_name}));
    }} catch (e) {{
      console.error("Mount error:", e);
      document.getElementById('root').innerHTML = '<div style="padding:2rem;color:#f87171;">Runtime Preview Error: ' + e.message + '</div>';
    }}
  </script>
</body>
</html>"""
                return Response(content=react_runner_html.encode("utf-8"), media_type="text/html")
            except Exception as e_runner:
                logger.warning(f"In-browser React runner fallback failed: {e_runner}")

        # 2. Visual rich landing page fallback

        custom_color = request.query_params.get("primaryColor") or "#6366f1"
        try:
            hex_color = custom_color.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            primary_rgb = f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"
        except Exception:
            primary_rgb = "99, 102, 241"
        b_name = request.query_params.get("businessName") or template.title
        c_title = request.query_params.get("title") or template.title
        c_sub = request.query_params.get("subtitle") or template.short_description
        c_cta = request.query_params.get("ctaText") or "Get Started"
        from app.services.template_synthesizer import analyze_prompt_intent
        domain_profile = analyze_prompt_intent(prompt=c_title, industry_hint=b_name)
        hero_bg_url = domain_profile.hero_image
        gallery_1 = domain_profile.gallery_images[0] if len(domain_profile.gallery_images) > 0 else domain_profile.hero_image
        gallery_2 = domain_profile.gallery_images[1] if len(domain_profile.gallery_images) > 1 else domain_profile.hero_image
        gallery_3 = domain_profile.gallery_images[2] if len(domain_profile.gallery_images) > 2 else domain_profile.hero_image
        
        is_light_fallback = (
            request.query_params.get("theme", "").lower() == "light" 
            or request.query_params.get("theme_mode", "").lower() == "light"
            or "light" in request.query_params.get("prompt", "").lower()
        )
        bg_val = "#f8fafc" if is_light_fallback else "#0f172a"
        card_val = "rgba(255, 255, 255, 0.9)" if is_light_fallback else "rgba(30, 41, 59, 0.7)"
        border_val = "rgba(0, 0, 0, 0.1)" if is_light_fallback else "rgba(255, 255, 255, 0.1)"
        text_val = "#0f172a" if is_light_fallback else "#f8fafc"
        text_muted_val = "#475569" if is_light_fallback else "#94a3b8"

        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{b_name} - Live Preview</title>
  <style>
    :root {{
      --primary: {custom_color};
      --primary-rgb: {primary_rgb};
      --bg: {bg_val};
      --card: {card_val};
      --border: {border_val};
      --text: {text_val};
      --text-muted: {text_muted_val};
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, sans-serif;
    }}
    
    body {{
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }}
    
    .bg-grid {{
      position: fixed;
      inset: 0;
      z-index: -1;
      background-image: radial-gradient(circle at 50% 50%, rgba(var(--primary-rgb), 0.15) 0%, transparent 60%),
                        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 100% 100%, 24px 24px, 24px 24px;
      pointer-events: none;
    }}
    
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.5rem 2rem;
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      background: rgba(15, 23, 42, 0.75);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    
    .logo {{
      font-size: 1.25rem;
      font-weight: 800;
      background: linear-gradient(135deg, #ffffff 0%, var(--primary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    
    nav {{
      display: flex;
      gap: 1.5rem;
    }}
    
    nav a {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      transition: color 0.2s;
    }}
    
    nav a:hover, nav a.active {{
      color: var(--text);
    }}
    
    .nav-btn {{
      background: var(--primary);
      color: #fff;
      padding: 0.5rem 1rem;
      border-radius: 9999px;
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .nav-btn:hover {{
      opacity: 0.9;
    }}
    
    .hero-container {{
      position: relative;
      padding: 5rem 2rem;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3rem;
      align-items: center;
      max-width: 1200px;
      margin: 0 auto;
    }}

    .hero-image-wrapper {{
      position: relative;
      border-radius: 1.5rem;
      overflow: hidden;
      border: 1px solid var(--border);
      box-shadow: 0 20px 40px -15px rgba(0,0,0,0.5);
    }}

    .hero-image-wrapper img {{
      width: 100%;
      height: 380px;
      object-fit: cover;
      display: block;
      transition: transform 0.5s ease;
    }}

    .hero-image-wrapper:hover img {{
      transform: scale(1.05);
    }}
    
    .category-badge {{
      display: inline-block;
      padding: 0.25rem 0.75rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      border: 1px solid rgba(var(--primary-rgb), 0.3);
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 1.5rem;
    }}
    
    h1 {{
      font-size: 3rem;
      font-weight: 850;
      line-height: 1.15;
      margin-bottom: 1.5rem;
      letter-spacing: -0.03em;
    }}
    
    .desc {{
      color: var(--text-muted);
      font-size: 1.125rem;
      line-height: 1.6;
      margin-bottom: 2rem;
    }}
    
    .cta-group {{
      display: flex;
      gap: 1rem;
    }}
    
    .btn {{
      padding: 0.75rem 1.75rem;
      border-radius: 0.75rem;
      font-size: 0.875rem;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s;
    }}
    
    .btn-primary {{
      background: var(--primary);
      color: #fff;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(var(--primary-rgb), 0.5);
    }}
    
    .btn-secondary {{
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }}
    
    .btn-secondary:hover {{
      background: rgba(255,255,255,0.05);
      transform: translateY(-2px);
    }}
    
    .features {{
      padding: 4rem 2rem;
      background: rgba(30, 41, 59, 0.3);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      width: 100%;
    }}
    
    .section-title {{
      text-align: center;
      font-size: 1.75rem;
      font-weight: 800;
      margin-bottom: 3rem;
    }}
    
    .features-grid {{
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }}
    
    .feature-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      overflow: hidden;
      transition: transform 0.3s ease, border-color 0.3s ease;
    }}
    
    .feature-card:hover {{
      transform: translateY(-6px);
      border-color: rgba(var(--primary-rgb), 0.5);
    }}

    .feature-card img {{
      width: 100%;
      height: 180px;
      object-fit: cover;
      display: block;
    }}

    .feature-card-content {{
      padding: 1.5rem;
    }}
    
    .feature-icon {{
      width: 2.5rem;
      height: 2.5rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 0.5rem;
      font-size: 1.25rem;
      font-weight: bold;
      margin-bottom: 1rem;
    }}
    
    .feature-card h3 {{
      font-size: 1.125rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
    }}
    
    .feature-card p {{
      color: var(--text-muted);
      font-size: 0.875rem;
      line-height: 1.5;
    }}
    
    footer {{
      padding: 3rem 2rem 6rem 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.875rem;
      border-top: 1px solid var(--border);
      width: 100%;
    }}
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  
  <header>
    <div class="logo">
      <span>✦</span>
      <span>{b_name}</span>
    </div>
    <nav>
      <a href="#" class="active">Home</a>
      <a href="#">Products & Services</a>
      <a href="#">About Us</a>
      <a href="#">Contact</a>
    </nav>
    <a href="#" class="nav-btn">Get Started</a>
  </header>
  
  <main class="hero-container">
    <div>
      <div class="category-badge">{(template.framework or 'HTML').upper()} Template</div>
      <h1>{c_title}</h1>
      <p class="desc">{c_sub}</p>
      <div class="cta-group">
        <a href="#" class="btn btn-primary">{c_cta}</a>
        <a href="#" class="btn btn-secondary">Explore Gallery</a>
      </div>
    </div>
    <div class="hero-image-wrapper">
      <img src="{hero_bg_url}" alt="Website Hero Visual" />
    </div>
  </main>
  
  <section class="features">
    <h2 class="section-title">Visual Showcase & Signature Features</h2>
    <div class="features-grid">
      <div class="feature-card">
        <img src="{gallery_1}" alt="Feature 1 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">✨</div>
          <h3>Crafted Experience</h3>
          <p>Curated visual layouts designed to elevate your brand presence and engage customers.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_2}" alt="Feature 2 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">⚡</div>
          <h3>Atmospheric Design</h3>
          <p>Modern aesthetics utilizing premium colors, glowing gradients, and responsive grids.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_3}" alt="Feature 3 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">🛡️</div>
          <h3>Artisanal Quality</h3>
          <p>Built with attention to detail across typography, spacing systems, and interactive cards.</p>
        </div>
      </div>
    </div>
  </section>
  
  <footer>
    <p>&copy; 2026 {b_name}. Powered by Site Studio.</p>
  </footer>
  {watermark_payload}
</body>
</html>"""
        return Response(content=fallback_html.encode("utf-8"), media_type="text/html")

    try:
        download_assets = template.download_assets or {}
        zip_url = download_assets.get("zip")
        if not zip_url:
            raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
            
        is_external = False
        file_id = None
        uuid_match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
        if uuid_match:
            try:
                file_id = uuid.UUID(uuid_match.group(1))
            except ValueError:
                is_external = True
        else:
            is_external = True
            
        preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
        os.makedirs(preview_dir, exist_ok=True)
        project_root = preview_dir

        import json
        import shutil
        from app.models.template import TemplateStatus

        def detect_project_ui_package_json(base_dir: str) -> Optional[str]:
            # Priority 1: Check standard UI locations
            for cand in [
                os.path.join(base_dir, "frontend", "package.json"),
                os.path.join(base_dir, "package.json"),
                os.path.join(base_dir, "client", "package.json"),
                os.path.join(base_dir, "web", "package.json"),
                os.path.join(base_dir, "ui", "package.json"),
            ]:
                if os.path.isfile(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            
            # Priority 2: Walk only safe non-vendor directories (NEVER descend into node_modules/backend/dist)
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".output", "vendor", "backend", ".venv", "env"]]
                if "package.json" in files:
                    cand = os.path.join(root, "package.json")
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            return None

        lock = _build_locks.setdefault(template_id, asyncio.Lock())
        async with lock:
            # 1. Detect package.json or check if source files exist
            package_json_path = detect_project_ui_package_json(preview_dir)

            # If directory is missing, empty, or index.html is missing, extract fresh from ZIP safely
            need_extract = not os.path.exists(preview_dir) or not os.listdir(preview_dir)
            if not need_extract and not package_json_path:
                if not os.path.exists(os.path.join(preview_dir, "index.html")):
                    has_html = any(f.endswith(".html") for r, d, files in os.walk(preview_dir) for f in files)
                    if not has_html:
                        need_extract = True

            if need_extract:
                if os.path.exists(preview_dir):
                    shutil.rmtree(preview_dir, ignore_errors=True)
                os.makedirs(preview_dir, exist_ok=True)

                if is_external:
                    import httpx
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(zip_url, follow_redirects=True, timeout=30.0)
                            if response.status_code != 200:
                                raise HTTPException(status_code=400, detail=f"Failed to fetch external ZIP assets: status {response.status_code}")
                            zip_data = response.content
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"Failed to download external template ZIP: {str(e)}")
                else:
                    from app.models import StoredFile
                    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                    stored_file = result.scalar_one_or_none()
                    if not stored_file:
                        raise HTTPException(status_code=404, detail="Source template archive file not found")
                    zip_data = stored_file.data

                # Extract ZIP or write raw HTML file
                from app.services.security_scanner import security_scanner
                if not zipfile.is_zipfile(io.BytesIO(zip_data)):
                    # Raw HTML file uploaded directly
                    index_dest = os.path.join(preview_dir, "index.html")
                    with open(index_dest, "wb") as f:
                        f.write(zip_data)
                else:
                    # Use security_scanner.sanitize_extract_zip to safely extract clean website files
                    security_scanner.sanitize_extract_zip(zip_data, Path(preview_dir))

                # Re-detect package.json after extraction
                package_json_path = detect_project_ui_package_json(preview_dir)

            # Auto-flatten single wrapper subfolder (e.g., port/index.html -> index.html)
            if not package_json_path and os.path.exists(preview_dir):
                subitems = [os.path.join(preview_dir, i) for i in os.listdir(preview_dir) if not i.startswith(".")]
                if len(subitems) == 1 and os.path.isdir(subitems[0]):
                    inner_folder = subitems[0]
                    for sub_item in os.listdir(inner_folder):
                        src_p = os.path.join(inner_folder, sub_item)
                        dst_p = os.path.join(preview_dir, sub_item)
                        shutil.move(src_p, dst_p)
                    try:
                        os.rmdir(inner_folder)
                    except Exception:
                        pass

            build_folders = ["dist", "out", "build", ".output"]
            serve_root = preview_dir
            build_dir = None

            if package_json_path:
                project_root = os.path.dirname(package_json_path)

                # Check if project is already compiled
                for d in build_folders:
                    candidate = os.path.join(project_root, d)
                    if os.path.isdir(candidate):
                        for b_root, b_dirs, b_files in os.walk(candidate):
                            if "index.html" in b_files:
                                build_dir = b_root
                                break
                        if build_dir:
                            break

                # If not compiled, trigger compilation
                if not build_dir:
                    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                    loop = asyncio.get_running_loop()

                    # 1. Verify that node_modules are present and populated
                    node_modules_dir = os.path.join(project_root, "node_modules")
                    is_modules_ready = os.path.isdir(node_modules_dir) and (
                        os.path.exists(os.path.join(node_modules_dir, "vite")) or
                        os.path.exists(os.path.join(node_modules_dir, "next")) or
                        os.path.exists(os.path.join(node_modules_dir, "vue")) or
                        os.path.exists(os.path.join(node_modules_dir, "svelte")) or
                        os.path.exists(os.path.join(node_modules_dir, "astro")) or
                        os.path.exists(os.path.join(node_modules_dir, "nuxt")) or
                        os.path.exists(os.path.join(node_modules_dir, "react")) or
                        (os.path.isdir(node_modules_dir) and len(os.listdir(node_modules_dir)) > 5)
                    )

                    if not is_modules_ready:
                        logger.info(f"[Preview Runner] Clean node_modules install required for {template_id}...")
                        shutil.rmtree(node_modules_dir, ignore_errors=True)
                        try:
                            os.remove(os.path.join(project_root, "package-lock.json"))
                        except OSError:
                            pass
                        def run_npm_install():
                            return subprocess.run(
                                [npm_cmd, "install", "--no-audit", "--no-fund"],
                                cwd=project_root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                            )
                        install_res = await loop.run_in_executor(None, run_npm_install)
                        if install_res.returncode != 0:
                            print(f"npm install failed for {template_id}: {install_res.stderr.decode('utf-8', errors='ignore')}")

                    # Detect framework characteristics
                    is_next = False
                    is_nuxt = False
                    is_vue = False
                    is_svelte = False
                    is_astro = False
                    is_react = False
                    is_angular = False
                    has_generate_script = False
                    has_export_script = False
                    all_deps = {}

                    try:
                        with open(package_json_path, "r", encoding="utf-8") as f:
                            pkg_data = json.load(f)
                            scripts = pkg_data.get("scripts", {})
                            all_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                            is_next = "next" in all_deps or "next" in scripts.get("build", "")
                            is_nuxt = "nuxt" in all_deps or "nuxt" in scripts.get("build", "")
                            is_vue = "vue" in all_deps or "@vitejs/plugin-vue" in all_deps
                            is_svelte = "svelte" in all_deps or "@sveltejs/vite-plugin-svelte" in all_deps
                            is_astro = "astro" in all_deps
                            is_angular = "@angular/core" in all_deps
                            is_react = "react" in all_deps or "@vitejs/plugin-react" in all_deps
                            has_generate_script = "generate" in scripts
                            has_export_script = "export" in scripts
                    except Exception:
                        pass

                    # Determine canonical framework label
                    template_fw_str = (template.framework.value if template.framework else "").lower()
                    if is_vue or template_fw_str == "vue":
                        detected_framework = "vue"
                    elif is_svelte or template_fw_str == "svelte":
                        detected_framework = "svelte"
                    elif is_astro or template_fw_str == "astro":
                        detected_framework = "astro"
                    elif is_next or template_fw_str == "nextjs":
                        detected_framework = "nextjs"
                    elif is_nuxt or template_fw_str == "nuxt":
                        detected_framework = "nuxt"
                    elif is_angular or template_fw_str == "angular":
                        detected_framework = "angular"
                    elif is_react or template_fw_str == "react":
                        detected_framework = "react"
                    else:
                        detected_framework = template_fw_str or "html"

                    # Framework-specific configuration tuning (e.g., forcing static export for Next.js)
                    if is_next:
                        next_cfg_js = os.path.join(project_root, "next.config.js")
                        next_cfg_mjs = os.path.join(project_root, "next.config.mjs")
                        if not os.path.exists(next_cfg_js) and not os.path.exists(next_cfg_mjs):
                            try:
                                with open(next_cfg_js, "w", encoding="utf-8") as f:
                                    f.write("module.exports = { output: 'export', images: { unoptimized: true } };\n")
                            except Exception:
                                pass
                        else:
                            cfg_path = next_cfg_js if os.path.exists(next_cfg_js) else next_cfg_mjs
                            try:
                                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                                    cfg_content = f.read()
                                if "output:" not in cfg_content and "output :" not in cfg_content:
                                    for pattern in ["const nextConfig = {", "module.exports = {", "export default {", "nextConfig = {"]:
                                        if pattern in cfg_content:
                                            cfg_content = cfg_content.replace(pattern, f"{pattern}\n  output: 'export',\n  images: {{ unoptimized: true }},", 1)
                                            break
                                    with open(cfg_path, "w", encoding="utf-8") as f:
                                        f.write(cfg_content)
                            except Exception:
                                pass

                    # Vite config handling (base path adjustment & auto-creation)
                    vite_cfg_js = os.path.join(project_root, "vite.config.js")
                    vite_cfg_ts = os.path.join(project_root, "vite.config.ts")
                    vite_cfg_mjs = os.path.join(project_root, "vite.config.mjs")
                    cfg_file = vite_cfg_js if os.path.exists(vite_cfg_js) else (vite_cfg_ts if os.path.exists(vite_cfg_ts) else (vite_cfg_mjs if os.path.exists(vite_cfg_mjs) else None))

                    # Auto-create vite.config if missing for Vite-based projects
                    if not cfg_file and ("vite" in all_deps or "vite" in pkg_data.get("scripts", {}).get("build", "")):
                        try:
                            if is_vue:
                                v_content = "import { defineConfig } from 'vite'\nimport vue from '@vitejs/plugin-vue'\n\nexport default defineConfig({\n  base: './',\n  plugins: [vue()],\n})\n"
                            elif is_svelte:
                                v_content = "import { defineConfig } from 'vite'\nimport { svelte } from '@sveltejs/vite-plugin-svelte'\n\nexport default defineConfig({\n  base: './',\n  plugins: [svelte()],\n})\n"
                            elif is_react:
                                v_content = "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\n\nexport default defineConfig({\n  base: './',\n  plugins: [react()],\n})\n"
                            else:
                                v_content = "import { defineConfig } from 'vite'\n\nexport default defineConfig({\n  base: './',\n})\n"
                            with open(vite_cfg_js, "w", encoding="utf-8") as f:
                                f.write(v_content)
                            cfg_file = vite_cfg_js
                        except Exception as e_vcfg:
                            logger.warning(f"Could not auto-generate vite.config.js: {e_vcfg}")
                    elif cfg_file:
                        try:
                            with open(cfg_file, "r", encoding="utf-8", errors="ignore") as f:
                                cfg_content = f.read()
                            if "base:" not in cfg_content and "base :" not in cfg_content:
                                if "defineConfig({" in cfg_content:
                                    cfg_content = cfg_content.replace("defineConfig({", "defineConfig({\n  base: './',", 1)
                                elif "export default {" in cfg_content:
                                    cfg_content = cfg_content.replace("export default {", "export default {\n  base: './',", 1)
                                with open(cfg_file, "w", encoding="utf-8") as f:
                                    f.write(cfg_content)
                        except Exception:
                            pass

                    # Determine optimal build/generate command
                    build_cmd = [npm_cmd, "run", "build"]
                    if is_nuxt:
                        if has_generate_script:
                            build_cmd = [npm_cmd, "run", "generate"]
                        else:
                            npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
                            build_cmd = [npx_cmd, "nuxt", "generate"]

                    # Pre-build self-healing: safely sanitize files without touching configs or non-JSX files
                    try:
                        from app.services.ai_service import repair_truncated_jsx, repair_truncated_html
                        CONFIG_AND_ENTRY_FILES = {
                            "vite.config.js", "vite.config.ts", "vite.config.mjs",
                            "next.config.js", "next.config.mjs", "next.config.ts",
                            "nuxt.config.js", "nuxt.config.ts",
                            "svelte.config.js", "svelte.config.ts",
                            "astro.config.mjs", "astro.config.ts", "astro.config.js",
                            "tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs", "tailwind.config.mjs",
                            "postcss.config.js", "postcss.config.cjs", "postcss.config.mjs",
                            "webpack.config.js", "webpack.config.ts",
                            "package.json", "package-lock.json", "tsconfig.json", "jsconfig.json",
                            "main.js", "main.ts", "index.js", "index.ts"
                        }

                        for s_root, _, s_files in os.walk(project_root):
                            norm_s_root = s_root.replace("\\", "/").lower()
                            if any(d in norm_s_root.split("/") for d in ["dist", "node_modules", "build", "out", ".output", ".git", ".cache", ".next", ".nuxt"]):
                                continue
                            for s_fname in s_files:
                                if s_fname.lower() in CONFIG_AND_ENTRY_FILES:
                                    continue

                                s_path = os.path.join(s_root, s_fname)
                                ext = os.path.splitext(s_fname)[1].lower()

                                # ONLY run repair_truncated_jsx on actual JSX / TSX files!
                                if ext in [".jsx", ".tsx"]:
                                    try:
                                        with open(s_path, "r", encoding="utf-8", errors="ignore") as sf:
                                            raw_c = sf.read()
                                        repaired_c = repair_truncated_jsx(raw_c)
                                        if repaired_c and repaired_c != raw_c:
                                            with open(s_path, "w", encoding="utf-8") as sf:
                                                sf.write(repaired_c)
                                    except Exception as e_heal:
                                        logger.warning(f"[Pre-Build Heal] Could not heal {s_fname}: {e_heal}")

                                elif ext in [".html", ".htm"]:
                                    try:
                                        with open(s_path, "r", encoding="utf-8", errors="ignore") as sf:
                                            raw_c = sf.read()
                                        h_c = raw_c
                                        if "</html>" in h_c:
                                            h_c = h_c.split("</html>")[0] + "</html>\n"

                                        # Match index.html entry script to actual file in src/
                                        src_dir = os.path.join(project_root, "src")
                                        if os.path.isdir(src_dir):
                                            src_files = os.listdir(src_dir)
                                            for entry_cand in ["main.js", "main.jsx", "main.ts", "main.tsx", "index.js", "index.jsx", "index.ts", "index.tsx"]:
                                                if entry_cand in src_files:
                                                    for other_cand in ["main.js", "main.jsx", "main.ts", "main.tsx"]:
                                                        if f"/src/{other_cand}" in h_c and other_cand != entry_cand and other_cand not in src_files:
                                                            h_c = h_c.replace(f"/src/{other_cand}", f"/src/{entry_cand}")
                                                            break
                                                    break

                                        repaired_c = repair_truncated_html(h_c)
                                        if repaired_c and repaired_c != raw_c:
                                            with open(s_path, "w", encoding="utf-8") as sf:
                                                sf.write(repaired_c)
                                    except Exception as e_heal:
                                        logger.warning(f"[Pre-Build Heal] Could not heal {s_fname}: {e_heal}")
                    except Exception as e_pre_heal:
                        logger.warning(f"[Pre-Build Heal Pass Failed]: {e_pre_heal}")

                    # 2. Compile/build template project
                    def run_npm_build():
                        res = subprocess.run(
                            build_cmd,
                            cwd=project_root,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        if res.returncode == 0 and is_next and has_export_script:
                            subprocess.run(
                                [npm_cmd, "run", "export"],
                                cwd=project_root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                            )
                        return res

                    build_res = await loop.run_in_executor(None, run_npm_build)
                    if build_res.returncode != 0:
                        error_out = (build_res.stderr or build_res.stdout or b"").decode('utf-8', errors='ignore')
                        print(f"npm run build failed for {template_id}: {error_out}")

                        # 🤖 Trigger Autonomous AI Debugger Agent to inspect and repair syntax/compile errors
                        try:
                            from app.services.debugger_service import ai_debugger
                            print(f"[Autonomous AI Debugger] Activating compiler repair agent for {detected_framework.upper()} template {template_id}...")
                            is_fixed, fix_log, repaired_map = await ai_debugger.debug_project_build(
                                project_root=project_root,
                                build_cmd=build_cmd,
                                initial_error_log=error_out,
                                max_attempts=3,
                                framework=detected_framework
                            )
                            if is_fixed:
                                print(f"[Autonomous AI Debugger] Successfully resolved build errors for {template_id}!")
                                # Also persist repaired files back into the template stored ZIP in database
                                if repaired_map and file_id and not is_external:
                                    try:
                                        from app.models import StoredFile
                                        sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                                        stored_rec = sf_res.scalar_one_or_none()
                                        if stored_rec and stored_rec.data:
                                            in_mem_zip = io.BytesIO()
                                            with zipfile.ZipFile(io.BytesIO(stored_rec.data), 'r') as zin:
                                                with zipfile.ZipFile(in_mem_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
                                                    for item in zin.infolist():
                                                        item_content = zin.read(item.filename)
                                                        # Check if this file was repaired
                                                        norm_name = os.path.normpath(item.filename).replace("\\", "/")
                                                        for rep_rel, rep_content in repaired_map.items():
                                                            norm_rep = os.path.normpath(rep_rel).replace("\\", "/")
                                                            if norm_name.endswith(norm_rep) or norm_rep.endswith(norm_name):
                                                                item_content = rep_content.encode("utf-8")
                                                                break
                                                        zout.writestr(item, item_content)
                                            stored_rec.data = in_mem_zip.getvalue()
                                            await db.commit()
                                            print(f"[Autonomous AI Debugger] Updated stored ZIP with repaired files in database for {template_id}")
                                    except Exception as e_zip_up:
                                        print(f"[Autonomous AI Debugger] Could not update stored ZIP: {e_zip_up}")
                        except Exception as e_ai_debug:
                            print(f"[Autonomous AI Debugger] Automated repair pass encountered an error: {e_ai_debug}")

                    # Locate build dir again after build
                    for d in build_folders:
                        candidate = os.path.join(project_root, d)
                        if os.path.isdir(candidate):
                            for b_root, b_dirs, b_files in os.walk(candidate):
                                if "index.html" in b_files:
                                    build_dir = b_root
                                    break
                            if build_dir:
                                break

            if build_dir:
                serve_root = build_dir
            elif package_json_path:
                return await serve_fallback("Preview compilation fallback")
            else:
                serve_root = project_root
    
        # Locate entry HTML file (index.html, index.htm, or any single/fallback HTML page)
        index_file_path = os.path.join(serve_root, "index.html")
        if not os.path.exists(index_file_path):
            found_html = None
            candidate_names = ["index.htm", "home.html", "landing.html", "main.html", "default.html", "app.html"]
            # 1. Check priority candidates in serve_root
            for cand in candidate_names:
                candidate_path = os.path.join(serve_root, cand)
                if os.path.exists(candidate_path):
                    found_html = candidate_path
                    break

            # 2. Search recursively for index.html, index.htm, or candidate names
            if not found_html:
                for root, dirs, files in os.walk(serve_root):
                    for cand in ["index.html", "index.htm"] + candidate_names:
                        if cand in files:
                            found_html = os.path.join(root, cand)
                            serve_root = root
                            break
                    if found_html:
                        break

            # 3. If still not found, search for ANY .html / .htm file in the extracted template
            if not found_html:
                for root, dirs, files in os.walk(serve_root):
                    html_files = [f for f in files if f.lower().endswith((".html", ".htm"))]
                    if html_files:
                        found_html = os.path.join(root, html_files[0])
                        serve_root = root
                        break

            if found_html:
                index_file_path = found_html
            elif not filepath or filepath == "/" or filepath.endswith(".html") or filepath.endswith(".htm"):
                # Friendly fallback warning message explaining how to structure the HTML template
                missing_html_warning = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Site Studio — Preview Notice</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0b0f19;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 24px;
      box-sizing: border-box;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 32px;
      max-width: 580px;
      text-align: center;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
    }}
    .icon {{ font-size: 42px; margin-bottom: 12px; }}
    h1 {{ font-size: 20px; font-weight: 700; margin: 0 0 12px 0; color: #f8fafc; }}
    p {{ font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 20px 0; }}
    .tip {{
      background: rgba(99, 102, 241, 0.1);
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: 10px;
      padding: 14px 18px;
      font-size: 13px;
      color: #a5b4fc;
      text-align: left;
    }}
    code {{ font-family: monospace; font-weight: bold; color: #e2e8f0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">📄</div>
    <h1>No HTML Entry Point Found</h1>
    <p>We could not find an entry file (e.g. <code>index.html</code> or <code>index.htm</code>) in your uploaded template archive.</p>
    <div class="tip">
      <strong>Tip for HTML Templates:</strong> Please ensure your template archive includes an <code>index.html</code> (or <code>index.htm</code>) file in the root folder, or upload a standalone <code>.html</code> file directly.
    </div>
  </div>
</body>
</html>"""
                return Response(content=missing_html_warning.encode("utf-8"), media_type="text/html")
    
        # Intercept and forward API calls to the template's embedded sub-app
        if filepath and (filepath.startswith("api/") or filepath == "api"):
            backend_dir = os.path.join(project_root, "backend")
            main_py = os.path.join(backend_dir, "main.py")
            if os.path.exists(main_py):
                import sys
                import importlib.util
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                try:
                    spec = importlib.util.spec_from_file_location("template_backend", main_py)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    sub_app = module.app
                    
                    scope = dict(request.scope)
                    scope["path"] = "/" + filepath
                    scope["raw_path"] = ("/" + filepath).encode("ascii")
                    
                    response_body = bytearray()
                    response_status = 200
                    response_headers = []
                    
                    async def send(message):
                        nonlocal response_status, response_headers
                        if message["type"] == "http.response.start":
                            response_status = message["status"]
                            response_headers = message["headers"]
                        elif message["type"] == "http.response.body":
                            response_body.extend(message.get("body", b""))
                            
                    await sub_app(scope, request.receive, send)
                    
                    headers_dict = {}
                    for k, v in response_headers:
                        headers_dict[k.decode("ascii")] = v.decode("ascii")
                        
                    return Response(content=bytes(response_body), status_code=response_status, headers=headers_dict)
                except Exception as e:
                    print(f"Failed to route sub-app request for {template_id}: {e}")

        # Determine file to serve
        if not filepath or filepath == "/":
            full_path = index_file_path
        else:
            safe_path = os.path.normpath(filepath).replace("..", "")
            if safe_path.startswith("/") or safe_path.startswith("\\"):
                safe_path = safe_path[1:]
            full_path = os.path.join(serve_root, safe_path)
            
            # Fallback for nested layouts if not found directly
            if not os.path.exists(full_path):
                subdirs = [d for d in os.listdir(serve_root) if os.path.isdir(os.path.join(serve_root, d)) and d not in ["__MACOSX"]]
                if len(subdirs) == 1:
                    nested_path = os.path.join(serve_root, subdirs[0], safe_path)
                    if os.path.exists(nested_path):
                        full_path = nested_path
    
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            # Fallback to index.html if file not found (e.g. client side routing)
            if os.path.exists(index_file_path):
                full_path = index_file_path
            else:
                raise HTTPException(status_code=404, detail="Requested file not found in template")
                
        mime_type, _ = mimetypes.guess_type(full_path)
        if not mime_type:
            mime_type = "application/octet-stream"
            
        with open(full_path, "rb") as f:
            content = f.read()
    
        # Rewrite absolute references to relative on all HTML preview pages
        if mime_type == "text/html":
            try:
                html_content = content.decode("utf-8", errors="ignore")
                
                # 1. Rewrite absolute references to relative on all HTML preview pages
                html_content = re.sub(r'src="/(?![/])', 'src="./', html_content)
                html_content = re.sub(r'href="/(?![/])', 'href="./', html_content)
    
                # 1a. Ensure viewport meta tag exists for proper mobile/tablet responsiveness in iframe
                if "<meta name=\"viewport\"" not in html_content.lower() and "<meta name='viewport'" not in html_content.lower():
                    viewport_meta = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                    if "<head>" in html_content:
                        html_content = html_content.replace("<head>", f"<head>\n  {viewport_meta}", 1)
                    elif "<html>" in html_content:
                        html_content = html_content.replace("<html>", f"<html>\n  <head>{viewport_meta}</head>", 1)
                    else:
                        html_content = f"<head>{viewport_meta}</head>\n" + html_content
    
                # 1b. Inject dynamic query parameter customizations into HTML for live preview customization
                customized = request.query_params.get("customized") == "true"
                if customized:
                    business_name = request.query_params.get("businessName")
                    primary_color = request.query_params.get("primaryColor")
                    custom_title = request.query_params.get("title")
                    custom_subtitle = request.query_params.get("subtitle")
                    custom_cta = request.query_params.get("ctaText")
                    logo_text = request.query_params.get("logoText")
    
                    # Override primary theme colors in CSS variables dynamically
                    if primary_color:
                        color_override_style = f"""
                        <style>
                          :root {{
                            --primary: {primary_color} !important;
                            --primary-color: {primary_color} !important;
                            --theme-color: {primary_color} !important;
                            --accent: {primary_color} !important;
                            --accent-color: {primary_color} !important;
                            --cta-bg: {primary_color} !important;
                          }}
                          a, button, .btn-primary, .bg-primary {{
                            background-color: {primary_color} !important;
                            border-color: {primary_color} !important;
                          }}
                          .text-primary, a:hover {{
                            color: {primary_color} !important;
                          }}
                        </style>
                        """
                        if "</head>" in html_content:
                            html_content = html_content.replace("</head>", f"{color_override_style}\n</head>", 1)
    
                    # Simple text/copy replacements
                    if business_name:
                        html_content = re.sub(r'<title>.*?</title>', f'<title>{business_name} - Preview</title>', html_content, flags=re.IGNORECASE)
                    if custom_title and template.title:
                        html_content = html_content.replace(template.title, custom_title)
                
                from app.models.template import TemplateFramework
                should_rewrite_history = "true" if template.framework != TemplateFramework.HTML else "false"
                
                # 2. Inject client-side routing and location sandboxing script (including absolute <base> tag)
                sandbox_script = f"""<base href="/api/v1/preview/live/{template_id}/" />
    <script>
      (function() {{
        const basePrefix = "/api/v1/preview/live/{template_id}";
        
        // Intercept fetch calls to rewrite root-relative API calls
        const originalFetch = window.fetch;
        window.fetch = function(input, init) {{
          let url = typeof input === 'string' ? input : (input instanceof Request ? input.url : '');
          if (url.startsWith('/api/')) {{
            url = basePrefix + url;
            if (input instanceof Request) {{
              input = new Request(url, input);
            }} else {{
              input = url;
            }}
          }}
          return originalFetch(input, init);
        }};

        // Intercept XMLHttpRequest
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url, ...args) {{
          if (typeof url === 'string' && url.startsWith('/api/')) {{
            url = basePrefix + url;
          }}
          return originalOpen.apply(this, [method, url, ...args]);
        }};

        // 1. Instantly rewrite history state to relative path so client-side routers match the root route
        try {{
          if ({should_rewrite_history} && window.location.pathname.startsWith(basePrefix)) {{
            let targetPath = window.location.pathname.slice(basePrefix.length);
            if (!targetPath.startsWith('/')) {{
              targetPath = '/' + targetPath;
            }}
            window.history.replaceState(null, '', targetPath);
          }}
        }} catch (e) {{
          console.error("[Live Preview Sandbox] Failed to replace initial state:", e);
        }}
    
        // 2. Intercept click events on links to keep them inside the live preview sandbox
        document.addEventListener('click', function(e) {{
          const link = e.target.closest('a');
          if (link) {{
            const rawHref = link.getAttribute('href');
            if (!rawHref) return;
            if (rawHref.includes('/marketplace') || link.closest('.preview-purchase-footer-banner')) {{
              e.preventDefault();
              window.top.location.href = "{settings.FRONTEND_URL}/marketplace/{template.slug if template and template.slug else template_id}";
              return;
            }}
            if (rawHref.startsWith('#')) {{
              e.preventDefault();
              window.location.hash = rawHref;
              return;
            }}
            if (rawHref.startsWith('javascript:')) {{
              return;
            }}
            // Ensure relative page links (e.g. "about.html", "contact.html", "./menu.html") remain inside the sandbox route
            if (link.href) {{
              try {{
                const url = new URL(link.href, window.location.href);
                if (url.origin === window.location.origin) {{
                  let path = url.pathname;
                  if (!path.startsWith(basePrefix)) {{
                    if (path.startsWith('/')) {{
                      path = path.slice(1);
                    }}
                    link.href = window.location.origin + basePrefix + '/' + path + url.search + url.hash;
                  }}
                }}
              }} catch (err) {{}}
            }}
          }}
        }}, true);
      }})();
    </script>"""
                
                if "<head>" in html_content:
                    html_content = html_content.replace("<head>", f"<head>\n  {sandbox_script}", 1)
                elif "<html>" in html_content:
                    html_content = html_content.replace("<html>", f"<html>\n  {sandbox_script}", 1)
                else:
                    html_content = sandbox_script + "\n" + html_content
    
                # Inject Watermarks & Copy/Inspect/Print Restrictions before </body>
                target_slug = template.slug if (template and template.slug) else str(template_id)
                purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

                watermark_payload = """
    <!-- Injected Watermark Grid Overlay -->
    <div class="preview-watermark-grid"></div>
    
    <!-- Injected Purchase Footer Banner -->
    <div class="preview-purchase-footer-banner">
      <span>🔒 Watermarked Draft Preview. Purchase this template to download clean project assets.</span>
      <a href="__PURCHASE_URL__" target="_top">Purchase Template &rarr;</a>
    </div>
    
    <style>
      /* Disable text selection across all elements */
      * {
        user-select: none !important;
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
      }
    
      /* Watermark grid covering full page with pointer-events disabled */
      .preview-watermark-grid {
        position: fixed !important;
        inset: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        pointer-events: none !important;
        z-index: 999999 !important;
        opacity: 0.65 !important;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
        background-repeat: repeat !important;
      }
    
      /* Bottom floating warning banner */
      .preview-purchase-footer-banner {
        position: fixed !important;
        bottom: 1.5rem !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        background: rgba(15, 23, 42, 0.96) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        color: #ffffff !important;
        padding: 0.625rem 1.25rem !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        border-radius: 9999px !important;
        display: flex !important;
        align-items: center !important;
        gap: 1rem !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
        z-index: 999998 !important;
        white-space: nowrap !important;
        font-family: system-ui, -apple-system, sans-serif !important;
      }
    
      .preview-purchase-footer-banner a {
        color: #38bdf8 !important;
        text-decoration: none !important;
        font-weight: 800 !important;
        border-left: 1px solid rgba(255, 255, 255, 0.2) !important;
        padding-left: 1rem !important;
        transition: color 0.2s ease !important;
      }
    
      .preview-purchase-footer-banner a:hover {
        color: #0ea5e9 !important;
      }
    
      /* Block PDF printing */
      @media print {
        body {
          display: none !important;
        }
      }
    </style>
    
    <script>
      (function() {
        // 1. Disable Right-Click Context Menu
        document.addEventListener('contextmenu', function(e) {
          e.preventDefault();
        }, true);
    
        // 2. Intercept Inspector, View-Source, Copy and Save keys
        document.addEventListener('keydown', function(e) {
          if (
            e.key === 'F12' ||
            (e.ctrlKey && e.shiftKey && e.key === 'I') ||
            (e.ctrlKey && e.shiftKey && e.key === 'C') ||
            (e.ctrlKey && e.shiftKey && e.key === 'J') ||
            (e.ctrlKey && e.key === 'u') ||
            (e.ctrlKey && e.key === 'c') ||
            (e.ctrlKey && e.key === 's')
          ) {
            e.preventDefault();
            e.stopPropagation();
            return false;
          }
        }, true);
      })();
    </script>
    """.replace("__PURCHASE_URL__", purchase_url)

                # Check if this template is a personal project, figma import, customized draft, or live mode
                is_personal_or_clean = (
                    getattr(template, "is_free", False) or
                    getattr(template, "price", 0) <= 0 or
                    template.status == TemplateStatus.DRAFT or
                    "figma" in (template.tags or []) or
                    "personal" in (template.tags or []) or
                    (template.title and "(Figma Import)" in template.title) or
                    (template.title and "(Customized)" in template.title) or
                    (template.slug and "-custom-" in template.slug) or
                    request.query_params.get("mode") == "live" or
                    request.query_params.get("clean") == "1"
                )

                if not is_personal_or_clean:
                    if "</body>" in html_content:
                        html_content = html_content.replace("</body>", f"{watermark_payload}\n</body>", 1)
                    else:
                        html_content = html_content + "\n" + watermark_payload

                # Ensure all /marketplace links point to the React frontend application
                html_content = html_content.replace('href="/marketplace"', f'href="{purchase_url}"')
                html_content = html_content.replace("href='/marketplace'", f"href='{purchase_url}'")
    
                content = html_content.encode("utf-8")
            except Exception:
                pass
        from app.services.security_scanner import security_scanner
        return Response(content=content, media_type=mime_type, headers=security_scanner.get_secure_preview_headers())
    except Exception as e:
        logger.exception(f"🚨 Preview generation error for template {template_id}: {e}")
        return await serve_fallback(str(e))


class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None


class AIEditRequest(BaseModel):
    prompt: str


@router.post("/live/{template_id}/ai-debug")
async def ai_debug_template_code(
    template_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand AI Debugger endpoint:
    Scans the template codebase, detects any broken JSX/TSX/HTML or syntax defects,
    invokes Gemini AI Debugger to fix them, rebuilds the project, and persists the fixes.
    """
    import shutil
    import tempfile
    import zipfile
    import io
    from sqlalchemy import select
    from app.services.debugger_service import ai_debugger
    from app.models.template import Template
    from app.models.stored_file import StoredFile

    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    
    # 1. Fetch template from DB
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP archive")

    match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(zip_url))
    stored_file = None
    if match:
        try:
            file_id = uuid.UUID(match.group(1))
            sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            stored_file = sf_res.scalar_one_or_none()
        except Exception:
            pass

    if not stored_file or not stored_file.data:
        raise HTTPException(status_code=404, detail="Source archive data not found")

    # 2. Extract to preview_dir
    os.makedirs(preview_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z:
        z.extractall(preview_dir)

    # 3. Locate package.json and scan all source files
    fixed_files_count = 0
    repaired_map = {}

    for root, _, files in os.walk(preview_dir):
        if any(d in root.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", ".output"]):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".jsx", ".tsx", ".js", ".ts", ".html"]:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()

                    # Sanitize heuristics first
                    healed = ai_debugger.sanitize_code_heuristics(code, ext)
                    
                    # If suspect syntax or defects detected, invoke Gemini AI Debugger
                    if ");</" in code or ";</" in code or "export default" not in code or code.count("{") != code.count("}") or code.count("<div") != code.count("</div"):
                        rel_path = os.path.relpath(fpath, preview_dir)
                        healed = await ai_debugger.debug_code_with_ai(
                            code=code,
                            filename=rel_path,
                            error_message="Fix unbalanced tags, stray semicolons, missing brackets, and broken exports."
                        )

                    if healed and healed != code:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(healed)
                        rel_p = os.path.relpath(fpath, preview_dir)
                        repaired_map[rel_p] = healed
                        fixed_files_count += 1
                except Exception as e_file:
                    logger.warning(f"AI Debugger skipped {fname}: {e_file}")

    # 4. If files were fixed, re-package the ZIP and save to DB
    if repaired_map and stored_file:
        in_mem = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as zin:
            with zipfile.ZipFile(in_mem, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    item_data = zin.read(item.filename)
                    norm_name = os.path.normpath(item.filename).replace("\\", "/")
                    for rep_rel, rep_content in repaired_map.items():
                        norm_rep = os.path.normpath(rep_rel).replace("\\", "/")
                        if norm_name.endswith(norm_rep) or norm_rep.endswith(norm_name):
                            item_data = rep_content.encode("utf-8")
                            break
                    zout.writestr(item, item_data)
        stored_file.data = in_mem.getvalue()
        await db.commit()

    # 5. Clear compiled dist/build directories in preview_dir to trigger fresh build
    for b_dir in ["dist", "out", "build", ".output"]:
        for root, dirs, _ in os.walk(preview_dir):
            if b_dir in dirs:
                shutil.rmtree(os.path.join(root, b_dir), ignore_errors=True)

    return {
        "status": "success",
        "message": f"AI Debugger analyzed project and successfully fixed {fixed_files_count} file(s).",
        "fixed_files": list(repaired_map.keys()),
        "fixed_count": fixed_files_count
    }


@router.get("/thumbnail/{template_id}.svg", include_in_schema=False)
async def get_dynamic_thumbnail(template_id: str, db: AsyncSession = Depends(get_db)):
    """Dynamically serves or generates on-demand SVG thumbnail snapshot for any template or draft."""
    from fastapi.responses import FileResponse, Response
    from app.services.screenshot_service import screenshot_service, _THUMBNAILS_DIR
    thumb_path = Path(_THUMBNAILS_DIR) / f"{template_id}.svg"
    if thumb_path.exists():
        return FileResponse(str(thumb_path), media_type="image/svg+xml")

    # If not on disk, lookup template and dynamically generate
    try:
        t_res = await db.execute(select(Template).where((Template.id == template_id) | (Template.slug == template_id)))
        tmpl = t_res.scalar_one_or_none()
    except Exception:
        tmpl = None

    title = tmpl.title if tmpl else "Modern Website Template"
    fw = str(tmpl.framework) if tmpl and tmpl.framework else "HTML"
    cat = "Modern Business"
    if tmpl and hasattr(tmpl, "category") and tmpl.category:
        cat = tmpl.category.name if hasattr(tmpl.category, "name") else str(tmpl.category)
    
    svg = screenshot_service.generate_svg_snapshot(title=title, framework=fw, category=cat)
    try:
        with open(thumb_path, "w", encoding="utf-8") as f:
            f.write(svg)
    except Exception:
        pass
    return Response(content=svg, media_type="image/svg+xml")




