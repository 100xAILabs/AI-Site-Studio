import json
import logging
import re
from typing import Any, Optional

from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

ANALYSIS_PROVIDER_ORDER = ["groq", "gemini", "cline"]


class TextAgent:
    """
    Text & Copywriting Agent:
    Generates rich, authentic, domain-specific copywriting dictionaries for every page
    before HTML generation begins. Prevents repetitive placeholder text and ensures
    subpages have substantive, unique content tailored to the user's prompt and brand.
    """

    async def generate_content_dictionary(
        self,
        prompt: str,
        category: str,
        genre: str,
        plan: dict[str, Any],
        answers: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generates structured page-by-page copywriting dictionaries.
        """
        pages = manifest.get("pages", plan.get("pages", []))
        brand_name = str(
            answers.get("business_name")
            or answers.get("author")
            or answers.get("brand")
            or plan.get("title")
            or genre.title()
        ).strip()

        copy_prompt = f"""You are the Lead Website Copywriter & Domain Content Agent.
Write rich, compelling, authentic website copy for each planned page.
DO NOT use generic lorem ipsum or repetitive boilerplate text. Craft authentic, realistic, high-converting copy tailored to the user's brief.

PROJECT BRIEF:
- Brief: {prompt[:3000]}
- Category: {category} | Genre: {genre}
- Brand / Creator: {brand_name}
- Owner Answers: {json.dumps(answers, ensure_ascii=False)[:1200]}
- Sitemap & Page Roles: {json.dumps([{'filename': p.get('filename'), 'name': p.get('name'), 'role': p.get('role')} for p in pages], ensure_ascii=False)}

MANDATORY RULES:
1. Every planned page MUST have its own dedicated entry under "pages".
2. NO DUPLICATE HEADLINES OR ITEMS: Each page must have unique headlines, subheadlines, and item lists.
3. For portfolio/works pages: Provide 6-8 distinct project case studies (title, client, category, year, synopsis, metrics).
4. For about pages: Provide real narrative story, career milestones with dates, and creative philosophy.
5. For contact pages: Provide studio availability, response time guarantee, and 3-4 FAQ question-and-answer pairs.
6. Provide exact SEO meta tags (page_title and meta_description) for every page.

Return JSON ONLY matching this structure:
{{
  "brand": {{
    "name": "{brand_name}",
    "tagline": "Compelling brand tagline",
    "phone": "{answers.get('phone', '+1 (555) 839-2000')}",
    "email": "{answers.get('email', 'contact@studio.local')}",
    "location": "{answers.get('address', 'Los Angeles, CA')}"
  }},
  "pages": {{
    "index.html": {{
      "hero_badge": "Available for Select Projects 2026",
      "hero_title": "Primary Headline",
      "hero_subtitle": "Compelling 2-sentence mission statement.",
      "teaser_highlights": [
        {{"title": "Highlight 1", "description": "Brief teaser...", "link": "projects.html"}},
        {{"title": "Highlight 2", "description": "Brief teaser...", "link": "projects.html"}}
      ],
      "bio_teaser": "Brief 3-sentence introduction with link to full story.",
      "seo_title": "Site Title - Core Offering",
      "seo_description": "Search engine snippet (150 chars max)."
    }}
  }}
}}"""

        try:
            raw = await ai_service._generate_content(
                copy_prompt,
                response_mime_type="application/json",
                feature_name="text_agent",
                preferred_provider="groq",
                provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=50.0,
                max_local_model_attempts=1,
            )
            dictionary = self._parse_json(raw)
            if dictionary and isinstance(dictionary.get("pages"), dict) and len(dictionary["pages"]) > 0:
                logger.info("Text Agent generated content dictionary for %d pages.", len(dictionary["pages"]))
                return self._normalize_dictionary(dictionary, pages, brand_name, genre, prompt, answers)
        except Exception as e:
            logger.warning("Text Agent LLM generation failed: %s. Building deterministic copy dictionary.", e)

        return self._build_fallback_dictionary(pages, brand_name, genre, prompt, answers)

    def _normalize_dictionary(
        self,
        dictionary: dict[str, Any],
        pages: list[dict[str, Any]],
        brand_name: str,
        genre: str,
        prompt: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Ensures every page has complete copy fields."""
        pages_dict = dictionary.setdefault("pages", {})
        for p in pages:
            fname = p.get("filename", "")
            pname = p.get("name", fname.rsplit(".", 1)[0].title())
            if fname not in pages_dict or not isinstance(pages_dict[fname], dict):
                pages_dict[fname] = self._create_page_fallback_copy(fname, pname, brand_name, genre, prompt, answers)
            else:
                entry = pages_dict[fname]
                if not entry.get("seo_title"):
                    entry["seo_title"] = f"{pname} | {brand_name}"
                if not entry.get("seo_description"):
                    entry["seo_description"] = f"Explore {pname} by {brand_name}. High quality creative work and professional services."

        return dictionary

    def _build_fallback_dictionary(
        self,
        pages: list[dict[str, Any]],
        brand_name: str,
        genre: str,
        prompt: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Deterministic copy builder tailored to the genre and prompt."""
        phone = str(answers.get("phone") or answers.get("mobile") or "+1 (555) 839-2000").strip()
        email = str(answers.get("email") or "contact@studio.local").strip()
        location = str(answers.get("address") or "Metro Creative District, Studio 402").strip()

        pages_dict = {}
        for p in pages:
            fname = p.get("filename", "")
            pname = p.get("name", fname.rsplit(".", 1)[0].title())
            pages_dict[fname] = self._create_page_fallback_copy(fname, pname, brand_name, genre, prompt, answers)

        return {
            "brand": {
                "name": brand_name,
                "tagline": f"Exceptional {genre.title()} & Creative Production",
                "phone": phone,
                "email": email,
                "location": location,
            },
            "pages": pages_dict,
        }

    def _create_page_fallback_copy(
        self,
        filename: str,
        page_name: str,
        brand_name: str,
        genre: str,
        prompt: str,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        fname_lower = filename.lower()
        pname_lower = page_name.lower()

        if fname_lower == "index.html":
            return {
                "hero_badge": "Now Booking Creative Projects · 2026",
                "hero_title": f"Crafting Visionary {genre.title()} Experiences",
                "hero_subtitle": f"{brand_name} delivers world-class creative production, innovative design, and high-impact digital experiences.",
                "teaser_highlights": [
                    {"title": "Featured Production", "description": "Cutting-edge creative showcase built for premium brands.", "link": "projects.html"},
                    {"title": "Creative Direction", "description": "From storyboards to final post-production polish.", "link": "about.html"},
                    {"title": "Direct Collaboration", "description": "Available for commercial commissions and studio partnerships.", "link": "contact.html"},
                ],
                "bio_teaser": f"{brand_name} is an award-winning creative studio known for meticulous visual storytelling and technical mastery.",
                "seo_title": f"{brand_name} | {genre.title()} Portfolio & Studio",
                "seo_description": f"Official website of {brand_name}. Explore selected projects, creative case studies, and commission inquiries.",
            }
        elif any(k in fname_lower or k in pname_lower for k in ("project", "work", "portfolio", "gallery")):
            return {
                "page_headline": "Selected Works & Case Studies",
                "page_subheadline": "A curated archive of commercial productions, personal experiments, and award-winning projects.",
                "filter_categories": ["All Works", "Commercial", "Narrative", "3D Motion", "Experimental"],
                "rich_items": [
                    {"title": "Project Chronos", "client": "Apex Studios", "year": "2026", "category": "3D Motion", "description": "High-velocity character animation and cinematic lighting sequence."},
                    {"title": "Neon Odyssey", "client": "Horizon Media", "year": "2025", "category": "Commercial", "description": "Broadcast commercial visual identity and motion graphics package."},
                    {"title": "Quantum Pulse", "client": "Vanguard Labs", "year": "2025", "category": "Experimental", "description": "Procedural animation system exploring fluid dynamics and particle physics."},
                    {"title": "Mirage Realms", "client": "Sony Music", "year": "2025", "category": "Narrative", "description": "Full-length music video animation with handcrafted anime-inspired aesthetics."},
                    {"title": "Echoes of Solitude", "client": "Independent", "year": "2024", "category": "Narrative", "description": "Festival award-winning animated short exploring memory and space."},
                    {"title": "Aero Kinetic", "client": "Kinetic Gear", "year": "2024", "category": "Commercial", "description": "3D product animation detailing internal micro-mechanisms."},
                ],
                "seo_title": f"Projects & Works | {brand_name}",
                "seo_description": f"Explore selected works and commercial projects by {brand_name}.",
            }
        elif any(k in fname_lower or k in pname_lower for k in ("about", "bio", "story")):
            return {
                "page_headline": f"About {brand_name}",
                "page_subheadline": "Bridging art and technology through cinematic motion and purposeful storytelling.",
                "story_paragraphs": [
                    f"With over a decade of dedicated craftsmanship, {brand_name} has pushed the boundaries of visual expression across digital and traditional media.",
                    "Every project begins with a relentless pursuit of emotional resonance, backed by rigorous technical execution and attention to microscopic detail.",
                    "From independent artistic endeavors to high-stakes global brand campaigns, the work is defined by bold visual rhythm, atmosphere, and precision.",
                ],
                "milestones": [
                    {"year": "2026", "event": "Established independent studio and expanded international client roster."},
                    {"year": "2024", "event": "Featured in Global Animation Biennial & won Best Visual Design Award."},
                    {"year": "2022", "event": "Led creative direction for prime-time broadcast campaigns."},
                    {"year": "2019", "event": "Graduated with Honors in Digital Arts & Animation."},
                ],
                "tools_stack": ["Blender 4.x", "Houdini", "After Effects", "Cinema 4D", "DaVinci Resolve", "Unreal Engine 5"],
                "seo_title": f"About | {brand_name}",
                "seo_description": f"Learn about the creative journey, philosophy, and milestones of {brand_name}.",
            }
        elif any(k in fname_lower or k in pname_lower for k in ("contact", "hire", "touch")):
            return {
                "page_headline": "Initiate a Commission",
                "page_subheadline": "Have a project in mind or seeking creative direction? Let's discuss your timeline and vision.",
                "availability": "Accepting projects for Q2 / Q3 2026",
                "response_time": "Responses typically within 24 business hours",
                "faqs": [
                    {"q": "What is the typical production timeline?", "a": "Timelines range from 2 to 6 weeks depending on scale, revisions, and complexity."},
                    {"q": "Do you work with international clients?", "a": "Yes, we regularly collaborate with studios and agencies across North America, Europe, and Asia."},
                    {"q": "What materials are needed to get started?", "a": "A creative brief, target deadline, reference moodboard, and budget range help us kick off immediately."},
                ],
                "seo_title": f"Contact & Booking | {brand_name}",
                "seo_description": f"Get in touch with {brand_name} for commissions, studio bookings, and collaborations.",
            }
        elif any(k in fname_lower or k in pname_lower for k in ("service", "pricing")):
            return {
                "page_headline": "Services & Production Packages",
                "page_subheadline": "Turnkey creative production tailored for visionary creators and modern enterprises.",
                "services": [
                    {"title": "Custom Animation & Motion", "price": "From $3,500", "description": "Bespoke 2D/3D animation, character rigging, and seamless visual loops."},
                    {"title": "Commercial Art Direction", "price": "From $5,000", "description": "Comprehensive visual identity, styleframes, and brand motion guidelines."},
                    {"title": "Full Post-Production & VFX", "price": "From $2,800", "description": "Compositing, color grading, sound design synchronization, and master delivery."},
                ],
                "seo_title": f"Services & Packages | {brand_name}",
                "seo_description": f"Review production services, commission rates, and deliverables from {brand_name}.",
            }
        else:
            return {
                "page_headline": page_name,
                "page_subheadline": f"Discover comprehensive details and insights regarding {page_name}.",
                "rich_items": [
                    {"title": f"{page_name} Overview", "description": f"Detailed exploration of {page_name} crafted for modern needs."},
                    {"title": "Key Capabilities", "description": "Proven methodologies and structured outcomes."},
                    {"title": "Next Steps", "description": "Get in touch to learn how we can assist you."},
                ],
                "seo_title": f"{page_name} | {brand_name}",
                "seo_description": f"Explore {page_name} by {brand_name}.",
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


text_agent = TextAgent()

