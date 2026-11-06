import json
import logging
import re
from typing import Any, Optional

from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

ANALYSIS_PROVIDER_ORDER = ["groq", "gemini", "cline"]


class ArchitectAgent:
    """
    Architect Agent:
    Translates the high-level Plan and UI Design into an authoritative Project Manifest.
    Eliminates the 'single-page trap' by formally assigning distinct roles, component
    boundaries, outbound link contracts, and forbidden duplicate content for every page.
    """

    async def design_manifest(
        self,
        prompt: str,
        category: str,
        genre: str,
        plan: dict[str, Any],
        design: str,
        answers: dict[str, Any],
        stack: str = "html-css-js",
    ) -> dict[str, Any]:
        """
        Builds the authoritative project manifest.
        Guarantees every page has a distinct contract before code generation begins.
        """
        pages = plan.get("pages", [])
        if not pages:
            pages = [{"name": "Home", "filename": "index.html", "purpose": "Main landing page"}]

        architect_prompt = f"""You are the Principal Software & Site Architect Agent.
Your job is to transform the approved website plan and UI design into a strict, authoritative Technical Project Manifest.

PROJECT SPECIFICATION:
- Brief: {prompt[:3000]}
- Category: {category} | Genre: {genre}
- Target Stack: {stack}
- Planned Sitemap: {json.dumps(pages, ensure_ascii=False)}
- Design System: {design[:1200]}
- Owner Answers: {json.dumps(answers, ensure_ascii=False)[:1200]}

MANDATORY ARCHITECTURAL DIRECTIVES:
1. PREVENT THE SINGLE-PAGE TRAP:
   - index.html must be assigned role: "gateway_homepage". It must feature teaser showcases and prominent relative links to sibling pages. It is strictly FORBIDDEN from dumping full interior page content!
   - Every interior page (e.g. about.html, projects.html, services.html, contact.html) must be assigned a specialized role (e.g. "narrative_about", "catalog_portfolio", "services_deep", "contact_hub") and have its own exclusive sections.
2. OUTBOUND LINK CONTRACT:
   - Specify the exact relative filenames each page must link to (e.g. ["projects.html", "about.html", "contact.html"]).
3. FORBIDDEN CONTENT LIST:
   - For each page, explicitly list sections that MUST NOT appear on that page (to prevent duplication across pages).
4. COMPONENT BOUNDARIES:
   - Define shared header (brand logo, navigation links, mobile drawer) and shared footer.

Return JSON ONLY matching this structure:
{{
  "site_title": "Site title",
  "architecture_pattern": "multi_page_static",
  "shared_components": {{
    "header": {{
      "brand_name": "Brand or Owner Name",
      "nav_items": [
        {{"label": "Home", "target": "index.html"}},
        {{"label": "Projects", "target": "projects.html"}}
      ],
      "has_mobile_drawer": true
    }},
    "footer": {{
      "copyright_text": "© 2026 Brand. All rights reserved.",
      "quick_links": ["index.html", "projects.html", "contact.html"]
    }}
  }},
  "pages": [
    {{
      "filename": "index.html",
      "name": "Home",
      "role": "gateway_homepage",
      "primary_focus": "Welcoming entrance, high-impact hero, and teaser previews directing visitors to interior pages.",
      "required_sections": [
        "Hero Banner with primary CTAs linking to interior pages",
        "Teaser Highlights Grid (2-3 items with 'View All' link)",
        "Short Bio / Philosophy Preview (with 'Read Full Story' link)",
        "Contact / Commission CTA Banner"
      ],
      "forbidden_content": [
        "Full project catalog or exhaustive gallery",
        "Full resume / skills history",
        "Full detailed contact inquiry form"
      ],
      "outbound_links": ["projects.html", "about.html", "contact.html"],
      "primary_ctas": [
        {{"label": "Explore Portfolio", "href": "projects.html"}},
        {{"label": "Get In Touch", "href": "contact.html"}}
      ]
    }}
  ]
}}"""

        try:
            raw = await ai_service._generate_content(
                architect_prompt,
                response_mime_type="application/json",
                feature_name="architect_agent",
                preferred_provider="groq",
                provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=45.0,
                max_local_model_attempts=1,
            )
            manifest = self._parse_json(raw)
            if manifest and isinstance(manifest.get("pages"), list) and len(manifest["pages"]) > 0:
                logger.info("Architect Agent generated project manifest with %d page specifications.", len(manifest["pages"]))
                return self._normalize_manifest(manifest, pages, plan, genre)
        except Exception as e:
            logger.warning("Architect Agent LLM generation failed: %s. Building deterministic manifest.", e)

        return self._build_fallback_manifest(prompt, category, genre, plan, answers, stack)

    def _normalize_manifest(
        self,
        manifest: dict[str, Any],
        original_pages: list[dict[str, Any]],
        plan: dict[str, Any],
        genre: str,
    ) -> dict[str, Any]:
        """Ensures all planned pages are present and filenames match."""
        manifest_pages = manifest.get("pages", [])
        page_by_fname = {p.get("filename"): p for p in manifest_pages if isinstance(p, dict) and p.get("filename")}

        normalized_pages = []
        for i, orig in enumerate(original_pages):
            fname = orig.get("filename") or ("index.html" if i == 0 else f"page-{i+1}.html")
            name = orig.get("name") or fname.rsplit(".", 1)[0].title()

            if fname in page_by_fname:
                spec = page_by_fname[fname]
            else:
                spec = self._create_page_spec(fname, name, i, len(original_pages), orig.get("purpose", ""), orig.get("sections", []))

            # Guarantee required fields
            spec["filename"] = fname
            spec["name"] = name
            if not spec.get("role"):
                spec["role"] = "gateway_homepage" if fname == "index.html" else "deep_content_page"
            if not spec.get("outbound_links"):
                spec["outbound_links"] = [p.get("filename", "") for p in original_pages if p.get("filename") != fname]
            normalized_pages.append(spec)

        manifest["pages"] = normalized_pages
        manifest["site_title"] = manifest.get("site_title") or plan.get("title") or genre.title()
        return manifest

    def _build_fallback_manifest(
        self,
        prompt: str,
        category: str,
        genre: str,
        plan: dict[str, Any],
        answers: dict[str, Any],
        stack: str,
    ) -> dict[str, Any]:
        """Deterministic builder creating a robust project manifest without LLM dependency."""
        pages = plan.get("pages", [])
        if not pages:
            pages = [
                {"name": "Home", "filename": "index.html", "purpose": "Main landing entrance"},
                {"name": "About", "filename": "about.html", "purpose": "Story and background"},
                {"name": "Portfolio", "filename": "projects.html", "purpose": "Showcase of work"},
                {"name": "Contact", "filename": "contact.html", "purpose": "Inquiries and booking"},
            ]

        manifest_pages = []
        for i, p in enumerate(pages):
            fname = p.get("filename") or ("index.html" if i == 0 else f"page-{i+1}.html")
            name = p.get("name") or fname.rsplit(".", 1)[0].title()
            purpose = p.get("purpose", "")
            sections = p.get("sections", [])
            spec = self._create_page_spec(fname, name, i, len(pages), purpose, sections)
            manifest_pages.append(spec)

        brand_name = str(answers.get("business_name") or answers.get("author") or answers.get("brand") or plan.get("title") or genre.title()).strip()

        return {
            "site_title": plan.get("title") or f"{genre.title()} Website",
            "architecture_pattern": "multi_page_static" if stack == "html-css-js" else f"{stack}_app",
            "shared_components": {
                "header": {
                    "brand_name": brand_name,
                    "nav_items": [{"label": p["name"], "target": p["filename"]} for p in manifest_pages],
                    "has_mobile_drawer": True,
                },
                "footer": {
                    "copyright_text": f"© 2026 {brand_name}. All rights reserved.",
                    "quick_links": [p["filename"] for p in manifest_pages],
                },
            },
            "pages": manifest_pages,
        }

    def _create_page_spec(
        self,
        filename: str,
        name: str,
        index: int,
        total_pages: int,
        purpose: str,
        sections: list[str],
    ) -> dict[str, Any]:
        name_lower = name.lower()
        fname_lower = filename.lower()

        if index == 0 or fname_lower == "index.html":
            return {
                "filename": "index.html",
                "name": name or "Home",
                "role": "gateway_homepage",
                "primary_focus": "High-impact entrance teaser. Introduces brand and directs visitors to specialized interior pages.",
                "required_sections": sections or [
                    "Hero Banner with primary CTAs linking directly to interior pages",
                    "Teaser Highlights Grid (2-3 sample items with 'View Full Work' link)",
                    "Short Bio / Philosophy Preview (with 'Read Full Story' link)",
                    "Call to Action Banner leading to contact/booking",
                ],
                "forbidden_content": [
                    "Full exhaustive project gallery or catalog",
                    "Full resume / extensive technical skills history",
                    "Complete contact inquiry form with full details",
                ],
                "outbound_links": ["projects.html", "about.html", "contact.html"],
                "primary_ctas": [
                    {"label": "Explore Portfolio", "href": "projects.html"},
                    {"label": "Get In Touch", "href": "contact.html"},
                ],
            }
        elif any(k in fname_lower or k in name_lower for k in ("project", "work", "portfolio", "gallery", "creations", "showcase")):
            return {
                "filename": filename,
                "name": name,
                "role": "catalog_portfolio",
                "primary_focus": "Exhaustive, high-fidelity gallery and case studies.",
                "required_sections": sections or [
                    "Portfolio Page Header & Filter Categories",
                    "Rich Project Grid (6-12 distinct projects with tags, client, year)",
                    "Detailed Case Study Cards / Modals with technical specs",
                    "Client Testimonials & Impact Metrics",
                    "Next Project Inquiry Callout",
                ],
                "forbidden_content": [
                    "Duplicate homepage hero",
                    "Full personal bio or company history",
                    "Unrelated off-topic service tables",
                ],
                "outbound_links": ["index.html", "about.html", "contact.html"],
                "primary_ctas": [
                    {"label": "Commission a Project", "href": "contact.html"},
                ],
            }
        elif any(k in fname_lower or k in name_lower for k in ("about", "bio", "story", "team", "who")):
            return {
                "filename": filename,
                "name": name,
                "role": "narrative_about",
                "primary_focus": "Deep narrative background, career milestones, philosophy, and creative process.",
                "required_sections": sections or [
                    "About Page Header & Mission Statement",
                    "In-Depth Biography / Story Narrative",
                    "Timeline of Career Milestones & Key Achievements",
                    "Creative Tools & Specialized Software Stack",
                    "Industry Awards & Recognitions",
                ],
                "forbidden_content": [
                    "Duplicate homepage hero banner",
                    "Full project showcase gallery",
                    "Complex checkout or booking forms",
                ],
                "outbound_links": ["index.html", "projects.html", "contact.html"],
                "primary_ctas": [
                    {"label": "View My Work", "href": "projects.html"},
                    {"label": "Contact Me", "href": "contact.html"},
                ],
            }
        elif any(k in fname_lower or k in name_lower for k in ("contact", "hire", "touch", "inquire", "reach")):
            return {
                "filename": filename,
                "name": name,
                "role": "contact_hub",
                "primary_focus": "Direct communication channels, project inquiry questionnaire, and direct contact details.",
                "required_sections": sections or [
                    "Contact Page Header & Availability Badge",
                    "Structured Project Inquiry Form (name, email, budget, timeline, project scope)",
                    "Direct Contact Info (Email, Phone, Studio Location, Social Links)",
                    "Frequently Asked Questions (FAQ) Accordion",
                    "Working Hours & Turnaround Times",
                ],
                "forbidden_content": [
                    "Duplicate homepage hero",
                    "Full portfolio gallery",
                    "Full narrative bio",
                ],
                "outbound_links": ["index.html", "projects.html", "about.html"],
                "primary_ctas": [
                    {"label": "Send Inquiry", "href": "#inquiry-form"},
                ],
            }
        elif any(k in fname_lower or k in name_lower for k in ("service", "pricing", "packages", "plans")):
            return {
                "filename": filename,
                "name": name,
                "role": "services_deep",
                "primary_focus": "Detailed breakdown of services, packages, deliverables, and commercial pricing.",
                "required_sections": sections or [
                    "Services Overview Header",
                    "Detailed Service Breakdown with Deliverables and Timelines",
                    "Tiered Pricing / Commission Packages",
                    "Workflow & Client Process Step-by-Step",
                    "Booking CTA linking to Contact",
                ],
                "forbidden_content": [
                    "Duplicate homepage hero",
                    "Full project portfolio",
                    "Full biography",
                ],
                "outbound_links": ["index.html", "projects.html", "contact.html"],
                "primary_ctas": [
                    {"label": "Book Service", "href": "contact.html"},
                ],
            }
        else:
            return {
                "filename": filename,
                "name": name,
                "role": "deep_content_page",
                "primary_focus": purpose or f"Comprehensive exploration of {name}.",
                "required_sections": sections or [
                    f"{name} Page Header",
                    f"Core {name} Content and Feature Highlights",
                    "Interactive Detailed Information Cards",
                    "Related Resources and Call to Action",
                ],
                "forbidden_content": [
                    "Duplicate homepage hero",
                ],
                "outbound_links": ["index.html", "contact.html"],
                "primary_ctas": [
                    {"label": "Get In Touch", "href": "contact.html"},
                ],
            }

    def _parse_json(self, raw: str) -> dict[str, Any]:
        if not raw:
            return {}
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return {}


architect_agent = ArchitectAgent()

