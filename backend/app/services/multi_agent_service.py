"""
Multi-Agent Sequential Generation Pipeline.
Orchestrates the planning, design, frontend generation, SEO, review, and packaging steps for static website projects.
"""

import json
import logging
import re
import io
import zipfile
import decimal
from html import escape as html_escape, unescape as html_unescape
import time
import asyncio
from typing import Dict, Any, List, Optional
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

def robust_json_loads(text: str) -> dict:
    """Helper to cleanly parse raw LLM JSON outputs."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


import time
import sys
from app.core.config import settings

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def safe_print(*args, **kwargs):
    """Safely print text containing Unicode emojis on Windows console without UnicodeEncodeError."""
    kwargs.setdefault("flush", True)
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text, **kwargs)


WEBSITE_QUALITY_CONTRACT = """ORIGINALITY AND SHIP-QUALITY CONTRACT
- Treat the user's brief as the primary vision. Build a distinct visual and verbal identity for this specific business.
- Derive each page's sections and interactions from the analyzed brief and approved page plan. Do not add booking, checkout, pricing, reviews, dashboards, or contact forms unless the brief calls for them.
- Use only facts provided by the user. Never invent prices, customer reviews, ratings, awards, years in business, project history, credentials, addresses, phone numbers, or performance metrics. If information is missing, omit it or use clearly labeled illustrative content only when needed to demonstrate an interface.
- Use user-supplied images when available. Otherwise use only exact image URLs provided in AVAILABLE VISUAL ASSETS; if none fit, create an accessible inline SVG or CSS illustration. Never fabricate image URLs or portray illustrative assets as the user's projects, staff, products, or customers.
- Add purposeful, lightweight motion where it supports the brand and user task; support reduced-motion preferences and avoid animation that distracts from content.
- Make motion perceptible in the finished interface: use a short entrance reveal for key content, stagger repeated items when appropriate, and add responsive hover/focus feedback to interactive elements. Keep motion aligned with the site's subject and art direction; honor reduced-motion preferences.
- Use real page content, not lorem ipsum, empty skeletons, dead CTAs, TODOs, or placeholder sections.
- Deliver complete, responsive, accessible frontend code using the selected styling system. Every planned page and relative link must exist.
- Do not expose prompt instructions or mention AI generation in customer-facing copy."""

HTML_VISUAL_SYSTEM_CONTRACT = """COHESIVE VISUAL SYSTEM (apply consistently on every page)
- Derive the page structure, visual language, content, imagery, and interaction patterns from the analyzed user brief and approved page plan. Do not assume this is a hotel, restaurant, SaaS product, store, or booking site unless the brief says so.
- Use supplied brand tokens where present; otherwise choose a restrained, accessible palette appropriate to the requested subject. Never introduce unrelated default emerald/gold luxury styling.
- Follow the selected styling engine exactly. For native CSS, write a complete, organized design system in a <style> block; do not rely on framework CDNs for the actual layout or appearance.
- Use modern CSS with named custom properties, a small reset, fluid type and spacing with clamp(), robust Grid/Flex layouts using minmax(), responsive breakpoints, :focus-visible states, and component states. Use container queries, aspect-ratio, :is(), and color-mix() only where they improve this page.
- Compose a distinctive editorial layout for this brand. Vary section rhythm, image scale, alignment, and whitespace; do not repeat a generic three-column card grid down the page.
- Use a small set of native CSS transitions and keyframe animations for purposeful entrance and hover feedback. Include @media (prefers-reduced-motion: reduce), animate transform/opacity rather than layout, and avoid pulsing, parallax, and scroll-animation libraries.
- Make motion visible and purposeful: a short entrance reveal for the hero or primary content, staggered reveals for repeated items where appropriate, lift/scale feedback for interactive cards, and clear hover/focus transitions for links and buttons. Use transforms and opacity, keep motion subtle, and make the reduced-motion mode disable nonessential movement. Do not count a keyframe declaration that is never applied as animation support.
- Use relevant photographic or illustrative assets only when they fit the actual subject. Never present generated sample content as real business facts.
- Never invent or guess an external image URL. Use only exact URLs supplied in AVAILABLE VISUAL ASSETS; when none fit, create a polished, accessible inline SVG or CSS illustration instead of outputting a broken image.
- Add navigation and calls to action that serve the planned pages and user tasks. Add mobile navigation when the information architecture needs it.
- Implement only interactions relevant to the brief. Do not insert date, guest, booking, checkout, dashboard, or inquiry controls unless requested.
- Prefer inline SVG icons with accessible titles/labels over third-party icon scripts. If any script is used, place it after the page markup or defer it; initialize after DOMContentLoaded.
- Never output bare unstyled HTML text, primitive pipe-separated nav links, or minimal stub pages."""


class PlanningAgent:
    """Agent 1: Analyzes prompt, determines business intent, and designs page breakdown."""
    async def execute(
        self,
        prompt: str,
        framework: str,
        industry: str,
        requested_pages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from app.services.template_synthesizer import analyze_prompt_intent
        profile = analyze_prompt_intent(prompt=prompt, industry_hint=industry if industry not in ("Auto-Detect from Prompt (Recommended)", "General") else "")
        effective_industry = profile.domain_name if (not industry or industry in ("Auto-Detect from Prompt (Recommended)", "General") or (industry == "SaaS & Tech Platform" and profile.industry_key != "saas")) else industry
        requested_page_outline = [
            {"name": page.get("name"), "filename": page.get("filename"), "purpose_hint": page.get("content_summary") or page.get("summary")}
            for page in (requested_pages or [])
            if isinstance(page, dict) and page.get("selected") is not False
        ]

        planning_prompt = f"""You are an experienced digital product strategist. Turn the user's brief into an implementation-ready website plan.

USER BRIEF: {prompt}
INDUSTRY CONTEXT: {effective_industry}
FRONTEND: {framework}
LIKELY BRAND NAME (use only if the user did not provide one): {profile.business_title}
USER-SELECTED PAGES (preserve each name and filename; create a specific outline for every one): {json.dumps(requested_page_outline, ensure_ascii=False)}

{WEBSITE_QUALITY_CONTRACT}

Plan only what this specific business needs. Infer the audience, key user tasks, positioning, and a memorable creative direction from the brief. Honor explicit page counts. Otherwise, complex multi-role products such as marketplaces, job boards, directories, and learning platforms usually need 4-7 distinct pages that support their separate user journeys; avoid reducing them to only Home and Contact. Each page must have a distinct job, a meaningful filename, and a detailed content outline with real section ideas and primary interaction. Avoid unsupported business claims and invented proof points. Include required information architecture and navigation relationships.

Return valid JSON only, with this structure:
{{
  "domain": "...",
  "business_name": "...",
  "audience": "...",
  "value_prop": "...",
  "creative_direction": "Distinct art direction derived from the brief",
  "pages": [{{"name": "...", "filename": "index.html", "slug": "...", "summary": "Specific sections, content, audience need, and interaction for this page", "page_type": "..."}}]
}}"""
        try:
            raw = await ai_service._generate_content(
                planning_prompt,
                response_mime_type="application/json",
                feature_name="planning_agent",
                preferred_provider=getattr(settings, "AGENT_PLANNING_PROVIDER", "cline")
            )
            return robust_json_loads(raw)
        except Exception as e:
            logger.error(f"Planning Agent execution failed: {e}")
            raise RuntimeError(f"Could not create an original site plan: {e}") from e


class UIDesignerAgent:
    """Agent 2: Establishes visual design system, color palette, and Google Fonts typography."""
    async def execute(self, plan: Dict[str, Any], color_scheme: str) -> Dict[str, Any]:
        is_light = any(w in str(color_scheme).lower() for w in ["light", "white", "bright", "clean", "cream", "ivory", "minimalist"])
        default_bg = "#ffffff" if is_light else "#0f172a"
        default_card = "#f8fafc" if is_light else "#1e293b"
        default_text = "#0f172a" if is_light else "#f8fafc"
        default_aesthetic = "Editorial, restrained light design" if is_light else "Distinctive, high-contrast dark design"

        design_prompt = f"""You are a senior art director creating an ownable visual system for a specific brand.
PROJECT PLAN: {json.dumps(plan, ensure_ascii=False)}
REQUESTED THEME: {color_scheme}

{WEBSITE_QUALITY_CONTRACT}

Create a coherent palette with accessible contrast and a distinctive visual direction grounded in the actual business. Select a display/body type pairing and describe composition, image art direction, shape language, and motion restraint. Avoid default glassmorphism, neon gradients, generic SaaS styling, and repeating the same card layout. Respect the requested light/dark theme.

Return valid JSON only:
{{
  "primary_hex": "#10b981",
  "secondary_hex": "#0f172a",
  "accent_hex": "#38bdf8",
  "bg_hex": "{default_bg}",
  "card_hex": "{default_card}",
  "text_hex": "{default_text}",
  "font_display": "Plus Jakarta Sans",
  "font_body": "Inter",
  "aesthetic": "{default_aesthetic}",
  "creative_direction": "Specific art direction for this business",
  "composition": "Page-specific composition rules",
  "image_direction": "Subject, crop, lighting, and treatment for imagery"
}}"""
        try:
            raw = await ai_service._generate_content(
                design_prompt,
                response_mime_type="application/json",
                feature_name="designer_agent",
                preferred_provider=getattr(settings, "AGENT_DESIGNER_PROVIDER", "kimi")
            )
            res = robust_json_loads(raw)
            if is_light and res.get("bg_hex", "").lower() in ["#0f172a", "#000000", "#111827", "#090d16", "#1e293b", "#09090b", "#040405"]:
                res["bg_hex"] = "#ffffff"
                res["card_hex"] = "#f8fafc"
                res["text_hex"] = "#0f172a"
            return res
        except Exception as e:
            logger.error(f"UI Designer Agent execution failed: {e}")
            logger.warning("Using deterministic design-token fallback so generation can continue.")
            return {
                "primary_hex": "#2563eb", "secondary_hex": "#0f172a", "accent_hex": "#14b8a6",
                "bg_hex": default_bg, "card_hex": default_card, "text_hex": default_text,
                "font_display": "Plus Jakarta Sans", "font_body": "Inter", "aesthetic": default_aesthetic,
            }


class FrontendAgent:
    """Agent 3: Synthesizes high-fidelity frontend component code."""
    async def execute(self, prompt: str, plan: Dict[str, Any], design: Dict[str, Any], framework: str, css_engine: str = "tailwind", project_images: Optional[List[Dict[str, Any]]] = None, validation_feedback: Optional[List[str]] = None) -> Any:
        pages_list = plan.get("pages", [
            {"name": "Home", "filename": "index.html"},
            {"name": "About", "filename": "about.html"},
            {"name": "Services", "filename": "services.html"},
            {"name": "Portfolio", "filename": "portfolio.html"},
            {"name": "Contact", "filename": "contact.html"}
        ])

        bg_hex = design.get("bg_hex", "#0f172a")
        card_hex = design.get("card_hex", "#1e293b")
        text_hex = design.get("text_hex", "#f8fafc")
        primary_hex = design.get("primary_hex", "#6366f1")
        secondary_hex = design.get("secondary_hex", "#8b5cf6")
        accent_hex = design.get("accent_hex", "#ec4899")

        is_html = (framework or "").lower() in ("html", "vanilla", "static")
        is_vue = (framework or "").lower() == "vue"
        is_storefront = bool(re.search(r"\b(shop|store|e-commerce|ecommerce|online retail)\b", prompt, re.IGNORECASE))
        is_tea_site = bool(re.search(r"\b(tea|chai|infusion|teahouse|tea house)\b", prompt, re.IGNORECASE))
        is_demo_site = bool(re.search(r"\b(fictional|sample|demo|concept)\b", prompt, re.IGNORECASE))
        project_assets_contract = (
            "USER-SUPPLIED IMAGE ASSETS: " + json.dumps(project_images or [], ensure_ascii=False)
            + " Use these URLs for the user's actual work where relevant, with descriptive alt text. "
            + "If none are supplied, use relevant stock imagery only as illustrative atmosphere; never represent stock imagery as this business's projects, customers, products, or staff."
        )
        storefront_contract = ""
        if is_storefront:
            storefront_contract = """SHOP API CONTRACT (server authenticates users and writes the isolated commerce database):
- Use the same-origin base `/api/v1/storefront/${encodeURIComponent((window.location.pathname.split('/').filter(Boolean)[0] === 'sites' ? window.location.pathname.split('/').filter(Boolean)[1] : window.location.hostname))}`. Never connect directly to a database or embed database credentials.
- Load the catalog with GET `/products`; render only products returned by that API. If the catalog is empty, clearly ask the store owner to add products; do not invent purchasable stock or prices.
- Register with POST `/auth/register` using `full_name`, `email`, `phone`, and `password`; sign in with POST `/auth/login` using `email` and `password`. The server checks credentials and returns a session token. Keep it in application memory only, send it as `Authorization: Bearer <token>`, and never claim browser-side authentication.
- Place orders with POST `/orders` using `{items:[{product_id,quantity}]}` and the bearer token. Use server-returned prices and inventory; do not calculate or claim payment success in the browser. The API currently records orders as awaiting payment.
- Verify every API response before displaying success. If the API is unavailable, explain that account/order actions are unavailable and do not simulate success.
"""


        css_engine = (css_engine or "tailwind").lower().strip()
        styling_contracts = {
            "tailwind": "Use Tailwind CSS utility classes. Do not substitute another CSS framework.",
            "vanillacss": "Use semantic class names and plain CSS only. Include full responsive component styles in the target framework's native style block. Do not use Tailwind or Bootstrap utility classes.",
            "styledcomponents": "Use React styled-components (the styled API) for component styling; do not use Tailwind classes.",
            "bootstrap": "Use Bootstrap 5 classes and responsive grid/components; do not use Tailwind classes.",
            "sass": "Use semantic class names and include full responsive component styles in the target framework's native style block; do not use Tailwind classes.",
            "chakra": "Use Chakra UI React components and props; do not use Tailwind classes.",
            "cssgrid": "Use semantic class names and component CSS with responsive CSS Grid declarations in the target framework's native style block; do not use Tailwind classes.",
            "glassmorphism": "Use semantic class names and component CSS with restrained backdrop-filter glass surfaces in the target framework's native style block; do not use Tailwind classes.",
        }
        styling_instruction = styling_contracts.get(css_engine, styling_contracts["tailwind"])
        if is_html:
            if css_engine == "vanillacss":
                styling_instruction = (
                    "PRODUCTION NATIVE CSS: Use semantic HTML class names and complete, hand-authored CSS in one well-organized <style> block. "
                    "Do not load Tailwind, Bootstrap, AOS, or any animation/icon framework from a CDN. Define brand tokens for primary "
                    f"{primary_hex}, secondary {secondary_hex}, accent {accent_hex}, background {bg_hex}, and surface {card_hex}. "
                    "Use inline SVG icons and system font stacks (a Google Font is optional, never required for layout)."
                )
            else:
                styling_instruction = (
                    f"Use Tailwind CSS via CDN with explicit tokens for primary {primary_hex}, secondary {secondary_hex}, accent {accent_hex}, background {bg_hex}, and surface {card_hex}. "
                    "Supplement utilities with a complete custom <style> block for fluid type, responsive layouts, accessible focus states, and native reduced-motion-safe animation. "
                    "Do not load AOS or third-party icon scripts; use inline SVG icons."
                )
        multipage_react = {}

        if is_html:
            frontend_prompt = ""
        elif is_vue:
            frontend_prompt = f"""You are the Senior Lead Frontend Developer Agent.
Synthesize complete, production-ready source code for Vue 3 `src/App.vue` tailored specifically to prompt: "{prompt}".
Plan: {json.dumps(plan)}
Design: Primary {primary_hex}, Secondary {secondary_hex}, Accent {accent_hex}, BG {bg_hex}, Card {card_hex}, Text {text_hex}
Styling engine: {css_engine}. {styling_instruction}
Art direction: {design.get('creative_direction', '')}; composition: {design.get('composition', '')}; imagery: {design.get('image_direction', '')}
{storefront_contract}
{project_assets_contract}
{WEBSITE_QUALITY_CONTRACT}
If validation feedback is present, correct each issue without inventing missing company details: {json.dumps(validation_feedback or [], ensure_ascii=False)}
Output valid Vue Single File Component (<template>, <script>, <style>) code only without markdown.
"""
        else:
            next_route_instruction = ""
            if (framework or "").lower() in ("next", "nextjs"):
                next_route_instruction = """- This is a Next.js App Router static export. Accept an `initialPage` prop and initialize the visible page from it; the generated route wrapper passes the route slug. Map every planned page to its matching slug. On internal navigation, update the visible page and browser URL with `window.history.pushState`; listen for `popstate` so back/forward works. Do not rely on state defaulting to home for every URL.
"""
            architecture_instruction = (
                "Build exactly one cohesive single-page experience for the planned home page. Use sections for the brief's distinct user tasks; do not create additional pages."
                if plan.get("architecture_type") == "single_page"
                else "Build dedicated, rich views for exactly the planned pages, with a distinct purpose and content for each."
            )
            frontend_prompt = f"""You are the Senior Lead Frontend Developer Agent.
Synthesize complete, production-ready source code for `src/App.jsx` tailored specifically to prompt: "{prompt}".

PLAN & BRAND SPECIFICATIONS:
- Business Plan: {json.dumps(plan, ensure_ascii=False)}
- Custom Brand Design System:
  * Primary Color: {primary_hex}
  * Secondary Color: {secondary_hex}
  * Accent Color: {accent_hex}
  * Background Color: {bg_hex}
  * Card Surface Color: {card_hex}
  * Text Color: {text_hex}
  * Font Family: {design.get("font_display", "Plus Jakarta Sans")}, {design.get("font_body", "Inter")}
- Target Framework: "{framework}"
- Styling engine: {css_engine}. {styling_instruction}
- Art direction: {design.get('creative_direction', '')}; composition: {design.get('composition', '')}; imagery: {design.get('image_direction', '')}

STRICT PRODUCTION REQUIREMENTS:
0. FRONTEND ONLY: Generate browser-side UI only. Do not create API routes, database code, or server handlers. Contact forms must clearly explain that an external form service is needed to receive messages. For shops, use only the documented same-origin Storefront API contract below; never use browser-side authentication or direct database access.
{storefront_contract}
{project_assets_contract}
{WEBSITE_QUALITY_CONTRACT}
VALIDATION DEFECTS TO CORRECT ON THIS RETRY (when present): {json.dumps(validation_feedback or [], ensure_ascii=False)}. Fix them directly and do not invent missing company facts.
1. PAGE ARCHITECTURE (NO PHANTOM PAGES):
   - {architecture_instruction}
   - Planned pages: {json.dumps([p.get('name') for p in pages_list], ensure_ascii=False)}.
   - Initialize the active view from `initialPage` when supplied, otherwise use the planned home page; map each view to its planned slug.
   - Implement state-driven navigation for the planned views.
   {next_route_instruction}   - Clicking navigation links and CTAs must show their corresponding planned page view.
   - Clicking ANY link in the sticky navbar, footer links, or CTA buttons MUST switch `currentPage` to render the corresponding page view seamlessly.
   - Active navbar navigation link MUST have a distinct visual highlight (e.g. glowing border, background pill, or text accent).

2. MANDATORY BRAND COLOR INTEGRATION:
   - Root container style MUST apply background `{bg_hex}` and text color `{text_hex}`: `style={{{{ backgroundColor: '{bg_hex}', color: '{text_hex}' }}}}`.
   - Cards and containers MUST use surface background `{card_hex}`.
   - Primary action buttons, active navigation indicators, icons, and hero highlights MUST utilize primary color `{primary_hex}` and accent `{accent_hex}` using inline styles or custom Tailwind hex classes (`bg-[{primary_hex}]`, `text-[{primary_hex}]`, `border-[{accent_hex}]`).

3. IMAGERY:
   - Use relevant, available visual assets with descriptive alt text. Never invent project work, people, or brand proof; don't use unrelated stock headshots as testimonials.
   - NEVER leave `src=""` empty or use broken image placeholders.

4. EXPORT & STRUCTURE:
   - Export default App component.
   - Use Lucide React icons (`lucide-react`) and Tailwind CSS.
   - Return valid complete JSX code without markdown formatting or conversational text.
"""
        try:
            from app.services.ai_service import clean_code_response, repair_truncated_jsx
            if is_html:
                from app.services.template_synthesizer import analyze_prompt_intent
                profile = analyze_prompt_intent(
                    prompt=prompt,
                    industry_hint=plan.get("domain", "") if plan else "",
                    business_title_hint=plan.get("business_name", "") if plan else "",
                    plan=plan,
                    design=design
                )
                if isinstance(design, dict):
                    if design.get("primary_hex"): profile.primary_hex = design["primary_hex"]
                    if design.get("secondary_hex"): profile.secondary_hex = design["secondary_hex"]
                    if design.get("accent_hex"): profile.accent_hex = design["accent_hex"]
                    if design.get("bg_hex"): profile.bg_hex = design["bg_hex"]
                    if design.get("card_hex"): profile.card_hex = design["card_hex"]
                    if design.get("text_hex"): profile.text_hex = design["text_hex"]

                generated_pages = {}
                planned_pages = [page for page in pages_list if isinstance(page, dict) and page.get("filename")]
                if not planned_pages or not any(page["filename"].lower() == "index.html" for page in planned_pages):
                    raise RuntimeError("The site plan must include index.html and at least one page.")

                def html_quality_defects(document: str) -> List[str]:
                    defects = []
                    lower = (document or "").lower()
                    if len(document or "") < 1800:
                        defects.append("The page is too short to cover its planned content; build the full page, not a hero-and-footer stub.")
                    required_markup = ("<!doctype html", "<html", "<head", "</head>", "<body", "</body>", "</html>", "<title", "<h1")
                    if not all(marker in lower for marker in required_markup):
                        defects.append("Return complete HTML with doctype, head, title, body, h1, and closing tags.")
                    if len(re.findall(r"<h1\b", lower)) != 1:
                        defects.append("Use exactly one descriptive h1 heading on this page.")
                    elif filename.lower() != "index.html":
                        h1_match = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", document or "", re.IGNORECASE)
                        h1_text = re.sub(r"<[^>]+>", " ", h1_match.group(1) if h1_match else "")
                        h1_text = re.sub(r"\s+", " ", h1_text).strip().lower()
                        planned_name = str(page.get("name") or "").strip().lower()
                        generic_brand_heading = re.match(r"^(?:welcome to |welcome |home(?:page)?(?: for)? )", h1_text)
                        page_heading_keywords = ("menu", "collection", "catalog", "story", "about", "visit", "contact", "guide", "resources", "projects", "work")
                        if generic_brand_heading or (planned_name and planned_name not in h1_text and not any(word in h1_text for word in page_heading_keywords)):
                            defects.append(f"Write an original h1 for the {page.get('name', filename)} page; do not reuse the homepage welcome heading.")
                    if "source.unsplash.com" in lower:
                        defects.append("Replace deprecated source.unsplash.com URLs with a stable, relevant image URL.")
                    if re.search(r"(?:via\.placeholder\.com|placehold\.it|dummyimage\.com)", lower):
                        defects.append("Replace placeholder images with relevant stock imagery or an accessible inline SVG illustration.")
                    if re.search(r"<img\b(?![^>]*\balt\s*=)[^>]*>", document or "", re.IGNORECASE | re.DOTALL) or re.search(
                        r"\balt\s*=\s*([\"'])(?:tea|image|photo)\s*\d*\1", document or "", re.IGNORECASE
                    ):
                        defects.append("Give every content image useful, subject-specific alternative text; avoid generic numbered alt text.")
                    if re.search(r"\b(?:fictional|sample|demo|concept)\b", prompt, re.IGNORECASE) and not re.search(
                        r"\b(?:fictional|sample|demo|concept)\b", re.sub(r"<[^>]+>", " ", document or ""), re.IGNORECASE
                    ):
                        defects.append("Add a short visible notice that this is a concept/demo with sample content.")
                    if profile.industry_key == "construction" and re.search(
                        r"\b(?:hotel|resort|michelin|butler|helipad|infinity pool|presidential suite|private island)\b",
                        lower,
                    ):
                        defects.append("Remove hotel and luxury-resort content; this brief is for a construction business.")
                    if not re.search(r"<(?:img|svg|picture)\b", lower):
                        defects.append("Add relevant imagery or inline SVG artwork with accessible text.")
                    if not re.search(r"<nav\b", lower):
                        defects.append("Add semantic navigation for the planned pages and actions.")
                    if ">home</a> |" in lower or ">home</a>|" in lower or ">home</a> \n|" in lower:
                        defects.append("Replace primitive pipe-separated navigation with a designed navigation layout.")

                    css_blocks = re.findall(r"<style\b[^>]*>([\s\S]*?)</style\s*>", document or "", flags=re.IGNORECASE)
                    css = "\n".join(css_blocks)
                    css_rules = re.findall(r"[^{}]+\{[^{}]*\}", css)
                    if not css_blocks or len(css_rules) < 14:
                        defects.append("Write a substantial custom CSS system with layout, component, responsive, and interaction rules.")
                    if not re.search(r"--[a-z][\w-]*\s*:", css, re.IGNORECASE):
                        defects.append("Define reusable CSS design tokens in :root or a theme scope.")
                    if not re.search(r"\bclamp\s*\(", css) or not re.search(r"\bminmax\s*\(", css):
                        defects.append("Use clamp() for fluid type or spacing and minmax() for resilient responsive sizing.")
                    if not re.search(r"@media[^{}]*(?:max-width|min-width)|@container", css, re.IGNORECASE):
                        defects.append("Add responsive CSS breakpoints or a container query.")
                    if not re.search(r":focus-visible\b", css, re.IGNORECASE):
                        defects.append("Add a visible keyboard focus state with :focus-visible.")
                    if not re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)", css, re.IGNORECASE):
                        defects.append("Respect reduced-motion preferences in CSS.")
                    keyframe_names = re.findall(r"@keyframes\s+([\w-]+)", css, re.IGNORECASE)
                    animation_values = re.findall(r"\banimation(?:-name)?\s*:\s*([^;{}]+)", css, re.IGNORECASE)
                    if not any(
                        re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", value, re.IGNORECASE)
                        for name in keyframe_names
                        for value in animation_values
                    ):
                        defects.append("Add a named @keyframes animation and apply that same animation name to a real page element.")
                    if re.search(r"https://unpkg\.com/aos|AOS\.init", document or "", re.IGNORECASE):
                        defects.append("Remove AOS and use native CSS motion so animation setup cannot run before page markup exists.")
                    head_end = lower.find("</head>")
                    if head_end >= 0 and re.search(r"(?:lucide\.createIcons|AOS\.init)", document[:head_end], re.IGNORECASE):
                        defects.append("Move DOM-dependent initialization out of <head> and run it after page markup is parsed.")
                    return defects

                def repair_html_css_requirements(document: str) -> str:
                    """Patch small, deterministic responsive/accessibility CSS omissions."""
                    style_match = re.search(r"<style\b[^>]*>([\s\S]*?)</style\s*>", document, re.IGNORECASE)
                    if not style_match:
                        return document
                    css = style_match.group(1)
                    additions = []
                    if not re.search(r"\bclamp\s*\(", css, re.IGNORECASE):
                        additions.append("h1 { font-size: clamp(2rem, 5vw, 4rem); }")
                    if not re.search(r"\bminmax\s*\(", css, re.IGNORECASE):
                        grid_rule = re.search(r"([^{}]+)\{[^{}]*(?:\bdisplay\s*:\s*grid\b|\bgrid-template-columns\s*:)[^{}]*\}", css, re.IGNORECASE)
                        if grid_rule:
                            additions.append(f"{grid_rule.group(1).strip()} {{ grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); }}")
                    if not re.search(r":focus-visible\b", css, re.IGNORECASE):
                        additions.append(":where(a, button, input, select, textarea, [tabindex]):focus-visible { outline: 3px solid currentColor; outline-offset: 3px; }")
                    if not re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)", css, re.IGNORECASE):
                        additions.append("@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; } }")
                    if additions:
                        patched_css = css.rstrip() + "\n\n/* Generated accessibility and responsive fallbacks. */\n" + "\n".join(additions) + "\n"
                        return document[:style_match.start(1)] + patched_css + document[style_match.end(1):]
                    return document

                async def generate_page(page: Dict[str, Any]) -> tuple[str, str]:
                    filename = page["filename"]
                    if "/" in filename or "\\" in filename or not filename.lower().endswith((".html", ".htm")):
                        raise RuntimeError(f"Unsafe planned page filename: {filename}")

                    demo_content_contract = ""
                    if is_demo_site:
                        demo_content_contract += """DEMO CONTENT RULES:
- Clearly label this as a concept/demo and identify illustrative sample content where visitors could mistake it for real business data.
- Do not imply that the fictional project is an operating business or that sample interactions persist data.
"""
                    if is_tea_site:
                        demo_content_contract += """TEA-SITE FACT RULES:
- Do not invent prices, stock, address, hours, tea origin, sourcing/certification, health benefits, reviews, awards, founding year, or copyright year.
- Use neutral flavor descriptions; do not make unsupported health or country-of-origin claims.
"""

                    page_prompt = f"""You are a principal frontend engineer and digital art director. Implement one finished, original, visually distinctive static HTML page for this website.

USER BRIEF: {prompt}
FULL SITE PLAN: {json.dumps(plan, ensure_ascii=False)}
THIS PAGE: {json.dumps(page, ensure_ascii=False)}
AVAILABLE VISUAL ASSETS (use only images that fit the requested subject):
- Hero image: {profile.hero_image}
- Gallery images: {json.dumps(profile.gallery_images)}
- User-supplied project/site images: {json.dumps(project_images or [], ensure_ascii=False)}

DESIGN SYSTEM: {json.dumps(design, ensure_ascii=False)}
COLORS: primary {primary_hex}; secondary {secondary_hex}; accent {accent_hex}; background {bg_hex}; surface {card_hex}; text {text_hex}
TYPE: {design.get('font_display', 'Plus Jakarta Sans')} / {design.get('font_body', 'Inter')}
FRAMEWORK & STYLING: {styling_instruction}
{HTML_VISUAL_SYSTEM_CONTRACT}
{storefront_contract}

{WEBSITE_QUALITY_CONTRACT}

{demo_content_contract}

CRITICAL ARCHITECTURAL & INTERACTION REQUIREMENTS:
1. BUILD ONLY `{filename}`. Return only a complete HTML document starting with <!doctype html> and ending with </html>. Include all required CSS and minimal JavaScript so it works as a standalone page; do not require a CDN for layout or animation.
2. SHARED DESIGN SYSTEM: Follow the cohesive visual system above. Use the planned art direction (`{design.get('creative_direction', '')}`), supplied color roles, and font pairing. Keep header, footer, spacing, typography, and reusable components consistent across pages; the active state must identify `{filename}`. Include consistent relative links to all planned pages ({json.dumps([p.get('filename') for p in planned_pages])}). Use supplied images for the user's real work when available. Otherwise use exact stock image URLs from AVAILABLE VISUAL ASSETS only; never invent URLs, and use inline SVG/CSS illustration if none fit.
3. PAGE-SPECIFIC COMPOSITION: This is `{page.get('name', filename)}`. Follow its specific content outline and user task in the plan. Build a complete destination, not an empty shell: give it a page-specific headline, substantial copy grounded in the brief, and enough distinct sections/components to fulfill the outline. Never reuse the homepage headline or copy as the body of another page. Select page sections only when they serve that outline. Never invent prices, product stock, locations, opening hours, credentials, awards, metrics, testimonials, customer ratings, or contact information. Use concise clearly labeled sample/placeholder content only when essential to demonstrate the requested UI, and do not present it as factual.
4. STYLING: Follow the selected styling engine exactly and implement the advanced CSS requirements above. Use a cohesive responsive visual system rather than utility classes alone. Never output unstyled bare text or primitive tags.
   CSS ACCEPTANCE CHECKLIST (all are required in the final <style> block):
   - Define custom properties in :root.
   - Include `font-size: clamp(2rem, 5vw, 4rem);` on a suitable heading.
   - Include `grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));` on a suitable grid.
   - Include `@media (max-width: 48rem)`, a visible `:focus-visible` style, and `@media (prefers-reduced-motion: reduce)` that minimizes motion.
   - Define `@keyframes site-enter` and apply `animation: site-enter 700ms ease-out both;` to the hero or primary content region.
   - Add intentional hover/focus transitions for interactive links, buttons, and page-relevant cards; do not animate unrelated elements.
   Do not merely mention these requirements in comments.
5. REAL INTERACTIONS: Working controls directly related to the requested user workflow, a functional mobile menu when present, and correct internal links. Do not add unrelated booking/date/guest controls.
6. NO TRUNCATION: Return a complete document; do not rely on automatic generic footer injection. No markdown fences or commentary.
7. If validation feedback is supplied, correct each specific defect without adding unsupported facts:
{json.dumps(validation_feedback or [], ensure_ascii=False)}"""

                    last_error = None
                    previous_defects: List[str] = []
                    previous_html = ""
                    for attempt in range(4):
                        try:
                            if attempt == 0:
                                retry_prompt = page_prompt
                            else:
                                retry_prompt = f"""You are correcting your immediately previous HTML page. Keep its existing page-specific content, overall composition, and shared brand styling. Make only the changes needed to pass the failed checks, but return the complete replacement HTML document, not a diff.

USER BRIEF: {prompt}
PAGE: {json.dumps(page, ensure_ascii=False)}
PLANNED HTML FILES: {json.dumps([p.get('filename') for p in planned_pages])}
PAGE PURPOSE AND CONTENT OUTLINE: {page.get('summary', page.get('content_summary', 'Create complete page content from the brief and this page name.'))}
BRAND: {plan.get('business_name') or 'the requested business'}; art direction: {design.get('creative_direction', '')}
COLORS: primary {primary_hex}; secondary {secondary_hex}; accent {accent_hex}; background {bg_hex}; surface {card_hex}; text {text_hex}
FAILED QUALITY CHECKS: {json.dumps(previous_defects or [last_error], ensure_ascii=False)}

REQUIRED REPAIRS:
- Preserve semantic navigation linking to every planned HTML file. Do not use pipe-separated text links.
- Use exactly one h1. Add a visible concept-demo notice and label sample menu content as illustrative.
- Use relevant imagery with descriptive alt text or a self-contained accessible inline SVG. Never use fabricated image URLs, placeholder.com, or generic alt text.
- In the page's <style>, include `font-size: clamp(2rem, 5vw, 4rem);`, `grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));`, `@media (max-width: 48rem)`, a visible `:focus-visible` style, and `@media (prefers-reduced-motion: reduce)`.
- Define `@keyframes site-enter` and apply `animation: site-enter 700ms ease-out both;` to a visible hero or primary content element.
- Do not invent prices, stock, addresses, hours, contact details, origin/sourcing/certification or health claims, reviews, awards, founding years, or copyright years.

PREVIOUS COMPLETE PAGE:
```html
{previous_html}
```

Return only the finished standalone document starting with <!doctype html>."""
                            raw_page = await ai_service._generate_content(
                                retry_prompt,
                                response_mime_type="text/plain",
                                feature_name="website_frontend_generation",
                                preferred_provider=getattr(settings, "AGENT_FRONTEND_PROVIDER", "cline"),
                            )
                            html_page = clean_code_response(raw_page, "html")
                            html_page = repair_html_css_requirements(html_page)
                            defects = html_quality_defects(html_page)
                            if not defects:
                                safe_print(f"     -> HTML quality gate passed on attempt {attempt + 1}.")
                                return filename, html_page
                            previous_html = html_page
                            previous_defects = defects
                            last_error = "; ".join(defects)
                            safe_print("     -> Remaining HTML quality issues: " + last_error)
                        except Exception as gen_exc:
                            last_error = str(gen_exc)
                            previous_defects = [f"The previous generation attempt failed: {last_error}"]
                            logger.warning("AI page generation attempt %s failed for %s: %s", attempt + 1, filename, gen_exc)
                    raise RuntimeError(f"Could not generate a complete, site-specific page '{filename}' after retry: {last_error}")

                concurrency = max(1, min(4, int(getattr(settings, "WEBSITE_PAGE_GENERATION_CONCURRENCY", 3))))
                semaphore = asyncio.Semaphore(concurrency)

                async def bounded_generate(page: Dict[str, Any]) -> tuple[str, str]:
                    async with semaphore:
                        return await generate_page(page)

                page_results = await asyncio.gather(*(bounded_generate(page) for page in planned_pages))
                generated_pages.update(page_results)
                return generated_pages

            raw = await ai_service._generate_content(
                frontend_prompt,
                response_mime_type="text/plain",
                feature_name="website_frontend_generation",
                preferred_provider=getattr(settings, "AGENT_FRONTEND_PROVIDER", "cline"),
            )
            if is_html:
                raise RuntimeError("HTML pages must be generated individually from the site plan.")
            elif is_vue:
                cleaned = clean_code_response(raw, "vue")
                if not cleaned or "<template>" not in cleaned or "</template>" not in cleaned:
                    raise RuntimeError("Frontend Agent received invalid Vue response from AI.")
                return cleaned
            else:
                cleaned = clean_code_response(raw, "jsx")
                if not cleaned or cleaned.strip().startswith("{") or "Dynamic structural synthesis" in cleaned or ("function" not in cleaned and "const " not in cleaned and "export default" not in cleaned):
                    raise RuntimeError("Frontend Agent received invalid or non-JSX response from AI.")
                return repair_truncated_jsx(cleaned)
        except Exception as e:
            logger.error(f"Frontend Agent execution failed: {e}")
            raise RuntimeError(f"Frontend Agent failed: {e}") from e


class BackendAgent:
    """Agent 4: Selects the requested framework's consistent REST API scaffold."""
    async def execute(self, title: str, plan: Dict[str, Any], framework: str) -> Dict[str, str]:
        from app.services.backend_generator import generate_standalone_backend
        files = generate_standalone_backend(framework, title, plan.get("domain", "Business"))
        source = "\n".join(files.values()).lower()
        required = ["/api/contact", "/api/leads", "/api/newsletter", "/api/health", "/api/stats", "sqlite"]
        missing = [capability for capability in required if capability not in source]
        if missing:
            raise ValueError(
                f"The {framework} backend scaffold is not ready for full-stack generation "
                f"(missing: {', '.join(missing)}). Choose FastAPI or Express.js."
            )
        review_payload = "\n\n".join(
            f"--- {path} ---\n{content[:10000]}" for path, content in files.items()
        )[:30000]
        review = await run_advisory_code_review(
            task=f"Review the deterministic {framework} backend scaffold for correctness, security, and frontend integration.",
            evidence=review_payload,
            provider=getattr(settings, "AGENT_BACKEND_PROVIDER", "cline"),
        )
        if review.get("status") == "completed":
            safe_print(f"     -> Backend AI review completed ({len(review.get('findings', []))} advisory findings).")
        else:
            safe_print("     -> Backend AI review unavailable; deterministic scaffold retained.")
        return files


async def run_advisory_code_review(task: str, evidence: str, provider: str = "cline") -> Dict[str, Any]:
    """Run a model-assisted review without allowing it to replace deterministic results."""
    prompt = f"""You are a cautious senior software auditor. Review the supplied project evidence for the task below.
Do not rewrite files, invent missing evidence, or claim that code was executed. Return JSON only with this schema:
{{"summary":"short assessment","findings":[{{"severity":"high|medium|low","file":"path or unknown","issue":"specific evidence-based issue","recommendation":"specific fix"}}]}}
If there are no substantiated issues, return an empty findings array.

TASK: {task}

EVIDENCE (may be truncated):
{evidence[:30000]}
"""
    try:
        raw = await ai_service._generate_content(
            prompt,
            response_mime_type="application/json",
            feature_name="code_assistant",
            preferred_provider=provider,
        )
        review = robust_json_loads(raw)
        if not isinstance(review, dict) or not isinstance(review.get("findings", []), list):
            raise ValueError("The review model returned an invalid review structure.")
        findings = review.get("findings", [])[:20]
        summary = str(review.get("summary", ""))[:1000]
        logger.info("Advisory review completed: %s", summary)
        for finding in findings:
            if isinstance(finding, dict):
                logger.info(
                    "Advisory finding [%s] %s: %s",
                    str(finding.get("severity", "low"))[:20],
                    str(finding.get("file", "unknown"))[:180],
                    str(finding.get("issue", ""))[:500],
                )
        return {"status": "completed", "summary": summary, "findings": findings}
    except Exception as exc:
        logger.warning("Advisory code review failed (provider=%s): %s", provider, exc)
        return {"status": "unavailable", "summary": "Model review was unavailable; deterministic checks remain authoritative.", "findings": []}


class DatabaseAgent:
    """Agent 5: Synthesizes isolated database connection, ORM schemas, and seed data."""
    async def execute(self, title: str, plan: Dict[str, Any]) -> str:
        db_prompt = f"""You are the Lead Database Architect Agent.
Generate a Python database seed script `seed.py` for SQLite `app.db` matching '{title}'.
Domain: {plan.get('domain', 'Business')}

Include domain-specific tables and insert realistic seed records.
Return valid Python script code for `seed.py`.
"""
        try:
            raw = await ai_service._generate_content(
                db_prompt,
                response_mime_type="text/plain",
                feature_name="code_assistant",
                preferred_provider=getattr(settings, "AGENT_DATABASE_PROVIDER", "cline")
            )
            raw = raw.strip()
            if raw.startswith("```python"):
                raw = raw[9:]
            elif raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            if not raw or raw.startswith("{") or "Dynamic structural synthesis" in raw or "sqlite3" not in raw:
                raise ValueError("AI returned non-Python seed script")
            return raw
        except Exception as e:
            logger.error(f"Database Agent execution failed: {e}")
            logger.warning("Using deterministic SQLite seed fallback so generation can continue.")
            seed_title = json.dumps(str(title or "Custom Studio"))
            seed_domain = json.dumps(str(plan.get("domain", "Business")))
            return f'''import sqlite3\n\nDB_PATH = "app.db"\n\ndef seed_database():\n    connection = sqlite3.connect(DB_PATH)\n    try:\n        cursor = connection.cursor()\n        cursor.execute("CREATE TABLE IF NOT EXISTS seed_items (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, domain TEXT NOT NULL)")\n        cursor.executemany("INSERT INTO seed_items (title, domain) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM seed_items WHERE title = ?)", [({seed_title}, {seed_domain}, {seed_title})])\n        connection.commit()\n    finally:\n        connection.close()\n\nif __name__ == "__main__":\n    seed_database()\n'''


class SEOAgent:
    """Agent 6: Synthesizes Schema.org JSON-LD structured data, OpenGraph, Twitter, and SEO tags using Ollama Qwen."""
    async def execute(self, title: str, plan: Dict[str, Any], hero_image: str = "", source_prompt: str = "") -> Dict[str, Any]:
        domain_name = plan.get('domain', 'Business')
        val_prop = plan.get('value_prop', f'Official website layout for {title}.')
        pages_list = [p.get('name', p.get('filename', '')) for p in plan.get('pages', [])]

        seo_prompt = f"""You are an SEO editor. Produce accurate metadata based only on these supplied facts.
Business: {title}
Domain: {domain_name}
Positioning: {val_prop}
Planned pages: {json.dumps(pages_list)}
USER BRIEF (for accurate, non-invented metadata): {source_prompt[:8000]}
Image URL, only if actually supplied: {hero_image or "none"}

Write a precise title under 60 characters, a useful description under 160 characters, and a concise list of relevant search phrases. Do not invent a live domain, canonical URL, customer evidence, location, credentials, or business claims. Use an empty canonical URL if the real domain is unknown. Add image metadata only when a real image URL was supplied. Choose a relevant Schema.org type and include only evidence-backed fields.

Return valid JSON only with: meta_title, meta_description, keywords, canonical_url, og_tags, twitter_tags, schema_json_ld."""
        try:
            raw = await ai_service._generate_content(
                seo_prompt,
                response_mime_type="application/json",
                feature_name="seo_agent",
                preferred_provider=getattr(settings, "AGENT_SEO_PROVIDER", "ollama")
            )
            parsed = robust_json_loads(raw)
            if isinstance(parsed, dict) and "meta_title" in parsed:
                return parsed
        except Exception as e:
            logger.warning(f"SEO Agent Ollama/AI call fallback: {e}")

        # Conservative metadata fallback: never fabricate a domain or social image.
        return {
            "meta_title": title[:60],
            "meta_description": val_prop[:155],
            "keywords": [title.lower(), domain_name.lower(), *[p.lower() for p in pages_list[:4]]],
            "canonical_url": "",
            "og_tags": {
                "title": title,
                "description": val_prop[:155],
                "type": "website",
                **({"image": hero_image} if hero_image else {})
            },
            "twitter_tags": {
                "card": "summary_large_image",
                "title": title,
                "description": val_prop[:155],
                **({"image": hero_image} if hero_image else {})
            },
            "schema_json_ld": {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": title,
                "description": val_prop
            }
        }


class TestingAgent:
    """Runs deterministic static package checks and an advisory source review."""
    async def execute(self, zip_bytes: bytes, expected_pages=None, project_scope="frontend", framework="html", approved_facts: str = "") -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                files = {name.replace("\\", "/") for name in archive.namelist() if not name.endswith("/")}
                errors = []
                import re
                import posixpath
                framework_name = str(framework or "html").lower()
                page_names = [str(p.get("filename", "")) for p in (expected_pages or []) if p.get("filename")]
                html_prefix = "frontend/" if any(name.startswith("frontend/") for name in files) else ""
                for page in page_names:
                    if f"{html_prefix}{page}" not in files:
                        errors.append(f"Missing planned page: {page}")
                    elif framework_name in {"html", "vanilla", "static"}:
                        page_source = archive.read(f"{html_prefix}{page}").decode("utf-8", errors="ignore")
                        if not re.search(r"<title\b[^>]*>[\s\S]*?</title\s*>", page_source, re.IGNORECASE):
                            errors.append(f"HTML SEO metadata is missing a title: {page}")
                        if not re.search(r"<meta\b(?=[^>]*\bname\s*=\s*(['\"])description\1)[^>]*>", page_source, re.IGNORECASE):
                            errors.append(f"HTML SEO metadata is missing a description: {page}")
                        if not re.search(r"<meta\b(?=[^>]*\bproperty\s*=\s*(['\"])og:title\1)[^>]*>", page_source, re.IGNORECASE):
                            errors.append(f"HTML SEO metadata is missing Open Graph title data: {page}")
                if framework_name not in {"html", "vanilla", "static"} and "index.html" in files:
                    index_source = archive.read("index.html").decode("utf-8", errors="ignore")
                    if not re.search(r"<title\b[^>]*>[\s\S]*?</title\s*>", index_source, re.IGNORECASE):
                        errors.append("Framework entry HTML is missing its SEO title")
                    if not re.search(r"<meta\b(?=[^>]*\bname\s*=\s*(['\"])description\1)[^>]*>", index_source, re.IGNORECASE):
                        errors.append("Framework entry HTML is missing its SEO description")
                for page in expected_pages or []:
                    route_slug = page.get("route_slug")
                    page_file = str(page.get("filename", ""))
                    archive_path = f"{html_prefix}{page_file}"
                    if route_slug and archive_path in files:
                        route_source = archive.read(archive_path).decode("utf-8", errors="ignore")
                        if not re.search(rf"initialPage\s*=\s*['\"]{re.escape(str(route_slug))}['\"]", route_source):
                            errors.append(f"Next.js route does not open its planned page: {page_file}")
                if framework_name in {"next", "nextjs"} and "src/App.jsx" in files:
                    app_source = archive.read("src/App.jsx").decode("utf-8", errors="ignore")
                    for required_route_behavior in ("initialPage", "pushState", "popstate"):
                        if required_route_behavior not in app_source:
                            errors.append(f"Next.js application is missing URL navigation behavior: {required_route_behavior}")
                if any(name.startswith("backend/") or name.lower().endswith((".db", ".sqlite", ".sqlite3")) for name in files):
                    errors.append("Static website package contains backend or database files")
                if "README.md" not in files:
                    errors.append("Package is missing README.md")
                if framework_name in {"react", "vue", "next", "nextjs"}:
                    if "package.json" not in files:
                        errors.append("Framework package is missing package.json")
                    else:
                        try:
                            package_json = json.loads(archive.read("package.json").decode("utf-8"))
                            if not isinstance(package_json.get("scripts", {}).get("build"), str):
                                errors.append("Framework package is missing a build script")
                        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                            errors.append("Framework package.json is invalid")
                    required_entries = {
                        "react": ("src/App.jsx", "src/main.jsx", "index.html"),
                        "vue": ("src/App.vue", "src/main.js", "index.html"),
                        "next": ("src/App.jsx", "app/layout.jsx", "app/page.jsx", "next.config.mjs"),
                        "nextjs": ("src/App.jsx", "app/layout.jsx", "app/page.jsx", "next.config.mjs"),
                    }.get(framework_name, ())
                    for entry in required_entries:
                        if entry not in files:
                            errors.append(f"Framework package is missing required entry point: {entry}")
                source_suffixes = (".html", ".htm", ".css", ".scss", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".vue", ".json", ".md")
                for name in sorted(files):
                    if not name.lower().endswith(source_suffixes):
                        continue
                    source = archive.read(name).decode("utf-8", errors="ignore")
                    if not source.strip():
                        errors.append(f"Generated source file is empty: {name}")
                    for placeholder in ("lorem ipsum", "todo:", "fixme:", "your company here", "replace this text"):
                        if placeholder in source.lower():
                            errors.append(f"Placeholder or unfinished content in {name}: {placeholder}")
                    for imported_path in re.findall(r"(?:from|import)\s*[\(]?\s*['\"](\.{1,2}/[^'\"]+)['\"]", source):
                        base = posixpath.normpath(posixpath.join(posixpath.dirname(name), imported_path))
                        candidates = {base, *(base + suffix for suffix in (".js", ".jsx", ".mjs", ".ts", ".tsx", ".vue", ".css", ".scss", ".json"))}
                        candidates.update(posixpath.join(base, "index" + suffix) for suffix in (".js", ".jsx", ".ts", ".tsx", ".vue"))
                        if not candidates.intersection(files):
                            errors.append(f"Missing local import in {name}: {imported_path}")
                # Resolve local HTML links against files in the same frontend tree.
                for path in files:
                    if not path.lower().endswith((".html", ".htm")):
                        continue
                    source = archive.read(path).decode("utf-8", errors="ignore")
                    anchor_ids = set(re.findall(r"\bid=[\"']([^\"']+)[\"']", source, flags=re.IGNORECASE))
                    anchor_names = set(re.findall(r"<a\b[^>]*\bname=[\"']([^\"']+)[\"']", source, flags=re.IGNORECASE))
                    valid_anchors = anchor_ids | anchor_names
                    for target in re.findall(r"(?:href|src)=[\"']([^\"']+)[\"']", source, flags=re.IGNORECASE):
                        raw_target = target
                        if raw_target.startswith("#"):
                            anchor = raw_target[1:]
                            if anchor and anchor not in valid_anchors:
                                errors.append(f"Dead local anchor in {path}: {raw_target}")
                            continue
                        target = raw_target.split("#", 1)[0].split("?", 1)[0]
                        if not target or target.startswith(("http://", "https://", "//", "data:", "mailto:", "tel:", "javascript:", "#")):
                            continue
                        rooted_target = target.startswith("/")
                        if rooted_target and not target.lower().endswith((".html", ".htm", ".css", ".js", ".png", ".jpg", ".svg", ".webp")):
                            continue  # Framework routes (e.g. /about) are not file paths.
                        relative_target = target.lstrip("/") if rooted_target else target
                        sibling = posixpath.normpath(posixpath.join(posixpath.dirname(path), relative_target))
                        normalized_target = posixpath.normpath(relative_target)
                        frontend_target = f"frontend/{normalized_target}" if rooted_target and html_prefix else normalized_target
                        if sibling not in files and normalized_target not in files and frontend_target not in files:
                            errors.append(f"Broken local link in {path}: {target}")
                        elif "#" in raw_target:
                            target_page = sibling if sibling in files else normalized_target
                            if target_page in files and target_page.lower().endswith((".html", ".htm")):
                                fragment = raw_target.split("#", 1)[1]
                                target_source = archive.read(target_page).decode("utf-8", errors="ignore")
                                target_anchors = set(re.findall(r"\bid=[\"']([^\"']+)[\"']", target_source, flags=re.IGNORECASE))
                                target_anchors |= set(re.findall(r"<a\b[^>]*\bname=[\"']([^\"']+)[\"']", target_source, flags=re.IGNORECASE))
                                if fragment and fragment not in target_anchors:
                                    errors.append(f"Dead local anchor in {path}: {raw_target}")
                for name in sorted(files):
                    if name.lower().endswith(".css"):
                        css = archive.read(name).decode("utf-8", errors="ignore")
                        if css.count("{") != css.count("}"):
                            errors.append(f"Unbalanced CSS braces in {name}")
                review_evidence = []
                if approved_facts:
                    review_evidence.append("--- USER-APPROVED FACTS AND BRIEF (source of truth; do not treat code comments as facts) ---\n" + approved_facts[:8000] + "\n")
                allowed_suffixes = (".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".html", ".md")
                budget = 24000
                for name in sorted(files):
                    if not name.lower().endswith(allowed_suffixes) or budget <= 0:
                        continue
                    snippet = archive.read(name).decode("utf-8", errors="ignore")[:5000]
                    block = f"--- {name} ---\n{snippet}\n"
                    review_evidence.append(block[:budget])
                    budget -= len(block)
                claim_patterns = (
                    r"(?<![\w/])(?:[$£€]\s?\d[\d,.]*|\b\d+(?:\.\d+)?\s*(?:%|\b(?:years?|reviews?|projects?|customers?|clients?|homes?|properties?|ratings?)\b)|\b\d+(?:\.\d+)?\s*/\s*5(?:\.0)?\s*(?:rating|stars?)?\b|\b\d+(?:\.\d+)?\s*stars?\b|\b(?:award[- ]winning|award winner|forbes|michelin|verified reviews)\b)",
                )
                if approved_facts:
                    approved_lower = approved_facts.casefold()
                    for name in sorted(files):
                        if not name.lower().endswith((".html", ".htm", ".jsx", ".tsx", ".vue")):
                            continue
                        source = archive.read(name).decode("utf-8", errors="ignore")
                        visible = re.sub(r"<(script|style|noscript)\b[^>]*>[\s\S]*?</\1\s*>", " ", source, flags=re.IGNORECASE)
                        visible = re.sub(r"<!--([\s\S]*?)-->|\{\/\*[\s\S]*?\*\/\}|/\*[\s\S]*?\*/", " ", visible)
                        visible = html_unescape(re.sub(r"<[^>]+>", " ", visible)).casefold()
                        for pattern in claim_patterns:
                            for claim in re.finditer(pattern, visible, flags=re.IGNORECASE):
                                claim_text = claim.group(0).strip()
                                if claim_text and claim_text.casefold() not in approved_lower:
                                    errors.append(f"Unsupported factual claim in {name}: {claim_text}")
                ai_review = await run_advisory_code_review(
                    task="Review the supplied source excerpts for concrete syntax or runtime defects, broken wiring, inaccessible controls, security issues, demo or placeholder copy, fabricated claims, and visual sameness. Compare factual claims with the USER-APPROVED FACTS source; treat facts absent from it as unknown and flag unsupported prices, reviews, awards, metrics, credentials, project history, and business contact details. Call out specific filenames and actionable issues. Deterministic checks separately verify planned pages, local links, and common numeric/award claims.",
                    evidence="\n".join(review_evidence),
                    provider=getattr(settings, "AGENT_TESTING_PROVIDER", "cline"),
                )
                high_findings = [
                    finding for finding in ai_review.get("findings", [])
                    if isinstance(finding, dict) and str(finding.get("severity", "")).lower() in {"high", "critical"}
                ]
                unsupported_claim_findings = [
                    finding for finding in ai_review.get("findings", [])
                    if isinstance(finding, dict) and re.search(
                        r"unsupported|fabricat|invented|unverified|not provided|no evidence|hallucinat|fictional",
                        f"{finding.get('issue', '')} {finding.get('recommendation', '')}", re.IGNORECASE,
                    )
                ]
                errors.extend(
                    f"Code review [{finding.get('severity')}]: {finding.get('file', 'unknown')}: {finding.get('issue', 'high-severity issue')}"
                    for finding in high_findings
                )
                errors.extend(
                    f"Code review [claim verification]: {finding.get('file', 'unknown')}: {finding.get('issue', 'Unsupported factual claim')}"
                    for finding in unsupported_claim_findings
                )
                if errors:
                    return {"status": "failed", "errors": errors, "tech_stack": ["ZIP package"], "ai_review": ai_review}
                return {"status": "passed", "errors": [], "tech_stack": ["ZIP package"], "ai_review": ai_review}
        except Exception as e:
            logger.warning(f"Testing Agent audit warning: {e}")
            return {"status": "failed", "errors": [str(e)], "tech_stack": []}


class DeploymentAgent:
    """Agent 8: Packages ZIP bundle, writes README guide, registers storage assets & returns URLs."""
    @staticmethod
    def _seo_values(seo_data: Optional[Dict[str, Any]], title: str, source_prompt: str = "", approved_images=None) -> Dict[str, Any]:
        seo_data = seo_data if isinstance(seo_data, dict) else {}
        meta_title = str(seo_data.get("meta_title") or title).strip()[:120] or title[:120]
        meta_description = re.sub(r"\s+", " ", str(seo_data.get("meta_description") or "").strip())[:300]
        if not meta_description:
            meta_description = f"Explore the {title} website."[:300]
        raw_keywords = seo_data.get("keywords", [])
        if isinstance(raw_keywords, str):
            raw_keywords = raw_keywords.split(",")
        keywords = []
        if isinstance(raw_keywords, list):
            for keyword in raw_keywords:
                clean_keyword = re.sub(r"\s+", " ", str(keyword)).strip()[:80]
                if clean_keyword and clean_keyword.casefold() not in {item.casefold() for item in keywords}:
                    keywords.append(clean_keyword)
                if len(keywords) >= 12:
                    break

        canonical_url = str(seo_data.get("canonical_url") or "").strip()
        if not (
            canonical_url.startswith("https://")
            and re.fullmatch(r"https://[^\s<>\"']+", canonical_url)
            and canonical_url in (source_prompt or "")
        ):
            canonical_url = ""

        approved_images = set(approved_images or [])
        raw_og = seo_data.get("og_tags") if isinstance(seo_data.get("og_tags"), dict) else {}
        raw_twitter = seo_data.get("twitter_tags") if isinstance(seo_data.get("twitter_tags"), dict) else {}
        image = str(raw_og.get("image") or raw_twitter.get("image") or "").strip()
        if image not in approved_images:
            image = ""
        return {
            "title": meta_title,
            "description": meta_description,
            "keywords": keywords,
            "canonical_url": canonical_url,
            "image": image,
        }

    @classmethod
    def _seo_head_markup(cls, seo_data: Optional[Dict[str, Any]], title: str, source_prompt: str = "", approved_images=None) -> str:
        values = cls._seo_values(seo_data, title, source_prompt, approved_images)
        esc = lambda value: html_escape(str(value), quote=True)
        tags = [
            f'<meta name="description" content="{esc(values["description"])}">',
            f'<meta property="og:title" content="{esc(values["title"])}">',
            f'<meta property="og:description" content="{esc(values["description"])}">',
            '<meta property="og:type" content="website">',
            f'<meta name="twitter:card" content="{"summary_large_image" if values["image"] else "summary"}">',
            f'<meta name="twitter:title" content="{esc(values["title"])}">',
            f'<meta name="twitter:description" content="{esc(values["description"])}">',
        ]
        if values["keywords"]:
            tags.append(f'<meta name="keywords" content="{esc(", ".join(values["keywords"]))}">')
        if values["image"]:
            tags.extend([
                f'<meta property="og:image" content="{esc(values["image"])}">',
                f'<meta name="twitter:image" content="{esc(values["image"])}">',
            ])
        if values["canonical_url"]:
            tags.append(f'<link rel="canonical" href="{esc(values["canonical_url"])}">')
        schema = {"@context": "https://schema.org", "@type": "WebSite", "name": str(title)[:200]}
        # Keep the generated structured data factual and limited to the site identity.
        schema_text = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        tags.append(f'<script type="application/ld+json">{schema_text}</script>')
        return "\n".join(tags)

    @classmethod
    def _apply_seo_metadata(cls, document: str, seo_data: Optional[Dict[str, Any]], title: str, source_prompt: str = "", approved_images=None) -> str:
        if not isinstance(document, str) or not document:
            return document
        values = cls._seo_values(seo_data, title, source_prompt, approved_images)
        head_match = re.search(r"<head\b[^>]*>[\s\S]*?</head\s*>", document, flags=re.IGNORECASE)
        if not head_match:
            return document
        head = head_match.group(0)
        head = re.sub(r"<title\b[^>]*>[\s\S]*?</title\s*>", "", head, flags=re.IGNORECASE)
        head = re.sub(
            r"<meta\b(?=[^>]*(?:\bname|\bproperty)\s*=\s*(['\"])(?:description|keywords|og:[^'\"]+|twitter:[^'\"]+)\1)[^>]*>",
            "",
            head,
            flags=re.IGNORECASE,
        )
        head = re.sub(r"<link\b(?=[^>]*\brel\s*=\s*(['\"])canonical\1)[^>]*>", "", head, flags=re.IGNORECASE)
        markup = f'<title>{html_escape(values["title"])}</title>\n{cls._seo_head_markup(seo_data, title, source_prompt, approved_images)}\n'
        head = re.sub(r"</head\s*>", markup + "</head>", head, count=1, flags=re.IGNORECASE)
        return document[:head_match.start()] + head + document[head_match.end():]

    async def execute(
        self,
        title: str,
        framework: str,
        css_engine: str,
        project_scope: str,
        frontend_code: Any,
        backend_code: Dict[str, str],
        seed_code: str,
        seo_data: Dict[str, Any],
        design: Optional[Dict[str, Any]] = None,
        backend_framework: str = "fastapi",
        prompt: str = "",
        plan: Optional[Dict[str, Any]] = None,
        project_images: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        from app.services.template_synthesizer import (
            analyze_prompt_intent,
        )

        is_html = (framework or "").lower() in ("html", "vanilla", "static")
        is_vue = (framework or "").lower() == "vue"
        is_next = (framework or "").lower() in ("next", "nextjs")
        safe_title = html_escape(title, quote=True)
        domain_hint = (plan.get("domain") if plan else "") or title
        profile = analyze_prompt_intent(
            prompt=prompt or title,
            industry_hint=domain_hint,
            business_title_hint=title,
            plan=plan,
            design=design
        )
        if isinstance(design, dict):
            if design.get("primary_hex"): profile.primary_hex = design["primary_hex"]
            if design.get("secondary_hex"): profile.secondary_hex = design["secondary_hex"]
            if design.get("accent_hex"): profile.accent_hex = design["accent_hex"]
            if design.get("bg_hex"): profile.bg_hex = design["bg_hex"]
            if design.get("card_hex"): profile.card_hex = design["card_hex"]
            if design.get("text_hex"): profile.text_hex = design["text_hex"]

        approved_image_urls = [
            str(image.get("url")) for image in (project_images or [])
            if isinstance(image, dict) and image.get("url")
        ]

        if is_html:
            multipage_files = dict(frontend_code) if isinstance(frontend_code, dict) else {}
            if not multipage_files:
                raise RuntimeError("No AI-generated HTML pages are available to package.")

            expected_files = {str(page.get("filename")) for page in (plan or {}).get("pages", []) if page.get("filename")}
            missing_files = expected_files - set(multipage_files)
            if missing_files:
                raise RuntimeError(f"Refusing to package; AI generation did not produce planned page(s): {', '.join(sorted(missing_files))}")

            if "index.html" not in multipage_files:
                raise RuntimeError("Refusing to package an HTML site without an AI-generated index.html.")

            page_names = {str(page.get("filename")): str(page.get("name") or page.get("filename") or title) for page in (plan or {}).get("pages", []) if page.get("filename")}
            for filename, document in list(multipage_files.items()):
                page_seo = dict(seo_data or {})
                base_meta_title = self._seo_values(seo_data, title, prompt, approved_image_urls)["title"]
                if filename.lower() == "index.html":
                    page_title = title
                else:
                    page_title = f"{page_names.get(filename, title)} | {title}"
                    page_seo["meta_title"] = f"{page_names.get(filename, title)} | {base_meta_title}"[:120]
                    # A site-root canonical must not be copied onto every subpage.
                    page_seo["canonical_url"] = ""
                multipage_files[filename] = self._apply_seo_metadata(document, page_seo, page_title, prompt, approved_image_urls)

            readme = f"""# {title} — Static HTML5 Website

Generated by AI Site Studio as a frontend-only static website. No API server or database is included.

## 🚀 How to Run

### Frontend Preview
Open `index.html` or serve this folder with a local HTTP server. All planned pages are included.

### Method 2: Local HTTP Server
```bash
python -m http.server 3000
```

Contact forms need an external form service to deliver messages. Static files do not store submissions.

## Validation scope
The Studio checks package structure, required files, local links, and known security signatures. It does not launch a browser or execute generated code during generation. Preview the pages before publishing.
"""
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                if project_scope == "fullstack":
                    for fname, fcontent in multipage_files.items():
                        zip_file.writestr(f"frontend/{fname}", fcontent)
                    zip_file.writestr(
                        "index.html",
                        '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=frontend/index.html"><title>Open generated site</title></head><body><a href="frontend/index.html">Open the generated website</a></body></html>',
                    )

                    for bpath, bcontent in backend_code.items():
                        zip_file.writestr(f"backend/{bpath}", bcontent)
                    if backend_framework.lower() == "fastapi":
                        zip_file.writestr("backend/seed.py", seed_code)
                    zip_file.writestr("README.md", readme)
                else:
                    for fname, fcontent in multipage_files.items():
                        zip_file.writestr(fname, fcontent)
                    zip_file.writestr("README.md", readme)

            return zip_buffer.getvalue()

        elif is_vue:
            package_json = {
                "name": "ai-generated-template",
                "private": True,
                "version": "1.0.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "vite build",
                    "preview": "vite preview"
                },
                "dependencies": {
                    "vue": "^3.4.21",
                    "lucide-vue-next": "^0.451.0"
                },
                "devDependencies": {
                    "@vitejs/plugin-vue": "^5.0.4",
                    "vite": "^5.1.6",
                    "tailwindcss": "^3.4.0",
                    "autoprefixer": "^10.4.0",
                    "postcss": "^8.4.0"
                }
            }
            tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,vue}'],
  theme: { extend: {} },
  plugins: [],
}
"""
            postcss_config = "export default { plugins: { tailwindcss: {}, autoprefixer: {} } }\n"
            if css_engine == "bootstrap":
                package_json["dependencies"]["bootstrap"] = "^5.3.3"
            elif css_engine == "sass":
                package_json["devDependencies"]["sass"] = "^1.80.6"
            elif css_engine != "tailwind":
                for dependency in ("tailwindcss", "autoprefixer", "postcss"):
                    package_json["devDependencies"].pop(dependency, None)
                tailwind_config = None
                postcss_config = None
            vite_config = """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: './',
  plugins: [vue()],
})
"""
            main_code = """import { createApp } from 'vue'
import App from './App.vue'
import './index.css'

createApp(App).mount('#root')
"""
            if css_engine == "bootstrap":
                main_code = main_code.replace(
                    "import './index.css'",
                    "import 'bootstrap/dist/css/bootstrap.min.css'\nimport './index.css'",
                )
            elif css_engine == "sass":
                main_code = main_code.replace("./index.css", "./index.scss")
            main_rel = "src/main.js"
            app_rel = "src/App.vue"
            app_content = frontend_code
            if not isinstance(app_content, str) or "<template>" not in app_content or "</template>" not in app_content:
                raise RuntimeError("The original Vue application is incomplete; refusing to package a canned demo.")
            multipage_react = {"src/App.vue": app_content}
            index_html = f'<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{safe_title}"><title>{safe_title}</title></head><body><div id="root"></div><script type="module" src="/src/main.js"></script></body></html>'
            index_css = f"@tailwind base;\n@tailwind components;\n@tailwind utilities;\n:root {{ --primary: {profile.primary_hex}; --secondary: {profile.secondary_hex}; --accent: {profile.accent_hex}; --bg: {profile.bg_hex}; --card: {profile.card_hex}; --text: {profile.text_hex}; }}\nbody {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, sans-serif; }}\n* {{ box-sizing: border-box; }}"
            if css_engine != "tailwind":
                index_css = index_css.replace("@tailwind base;\n@tailwind components;\n@tailwind utilities;\n", "")
            readme = f"""# {title} — Vue 3 Static Website

## Run locally
```bash
npm install
npm run dev
```

Build with `npm run build` to create static files in `dist/`. The planned page experiences are implemented in `src/App.vue`.
"""
        else:
            package_json = {
                "name": re.sub(r'[^a-z0-9-]', '-', title.lower())[:30] or "ai-template",
                "private": True,
                "version": "1.0.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "vite build",
                    "preview": "vite preview"
                },
                "dependencies": {
                    "react": "^18.3.1",
                    "react-dom": "^18.3.1",
                    "lucide-react": "^0.451.0"
                },
                "devDependencies": {
                    "@vitejs/plugin-react": "^4.3.1",
                    "vite": "^5.4.0",
                    "tailwindcss": "^3.4.0",
                    "autoprefixer": "^10.4.0",
                    "postcss": "^8.4.0"
                }
            }
            if is_next:
                package_json["scripts"] = {
                    "dev": "next dev",
                    "build": "next build"
                }
                package_json["dependencies"]["next"] = "^14.2.0"
                package_json["devDependencies"] = {
                    "tailwindcss": "^3.4.0",
                    "autoprefixer": "^10.4.0",
                    "postcss": "^8.4.0"
                }
            vite_config = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',
  plugins: [react()],
})
"""
            tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
"""
            if is_next:
                tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: { extend: {} },
  plugins: [],
}
"""
            postcss_config = """export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
"""
            main_code = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
            index_css = f"""@tailwind base;
@tailwind components;
@tailwind utilities;

:root {{
  --primary: {profile.primary_hex};
  --secondary: {profile.secondary_hex};
  --accent: {profile.accent_hex};
  --bg: {profile.bg_hex};
  --card: {profile.card_hex};
  --text: {profile.text_hex};
}}

body {{
  margin: 0;
  background-color: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

* {{
  box-sizing: border-box;
}}
"""
            if css_engine == "sass":
                main_code = main_code.replace("./index.css", "./index.scss")
            if css_engine == "styledcomponents":
                package_json["dependencies"]["styled-components"] = "^6.1.13"
                package_json["devDependencies"].pop("tailwindcss", None)
                package_json["devDependencies"].pop("autoprefixer", None)
                package_json["devDependencies"].pop("postcss", None)
            elif css_engine == "chakra":
                package_json["dependencies"].update({"@chakra-ui/react": "^2.10.4", "@emotion/react": "^11.13.3", "@emotion/styled": "^11.13.0", "framer-motion": "^11.11.11"})
                package_json["devDependencies"].pop("tailwindcss", None)
                package_json["devDependencies"].pop("autoprefixer", None)
                package_json["devDependencies"].pop("postcss", None)
                main_code = main_code.replace("import './index.css'", "import './index.css'\nimport { ChakraProvider } from '@chakra-ui/react'")
                main_code = main_code.replace("<App />", "<ChakraProvider><App /></ChakraProvider>")
            elif css_engine == "bootstrap":
                package_json["dependencies"]["bootstrap"] = "^5.3.3"
                main_code = main_code.replace("import './index.css'", "import 'bootstrap/dist/css/bootstrap.min.css'\nimport './index.css'")
                package_json["devDependencies"].pop("tailwindcss", None)
                package_json["devDependencies"].pop("autoprefixer", None)
                package_json["devDependencies"].pop("postcss", None)
            elif css_engine in {"vanillacss", "sass", "cssgrid", "glassmorphism"}:
                package_json["devDependencies"].pop("tailwindcss", None)
                package_json["devDependencies"].pop("autoprefixer", None)
                package_json["devDependencies"].pop("postcss", None)
                if css_engine == "sass":
                    package_json["devDependencies"]["sass"] = "^1.80.6"
            if css_engine != "tailwind":
                tailwind_config = None
                postcss_config = None
                index_css = index_css.replace("@tailwind base;\n@tailwind components;\n@tailwind utilities;\n", "")
            app_content = frontend_code
            if not isinstance(app_content, str) or "export default" not in app_content or not any(token in app_content for token in ("function", "const ")):
                raise RuntimeError("The original React application is incomplete; refusing to package a canned demo.")
            multipage_react = {"src/App.jsx": app_content}
            pages_list = plan.get("pages", []) if plan else []
            next_files = {}
            if is_next:
                planned_pages = plan.get("pages", []) if plan else []
                for page in planned_pages:
                    raw_slug = str(page.get("slug") or page.get("filename", "").rsplit(".", 1)[0] or "page")
                    slug = re.sub(r"[^a-z0-9-]+", "-", raw_slug.lower()).strip("-") or "page"
                    is_home_page = slug in {"home", "index"} or str(page.get("filename", "")).lower() == "index.html"
                    route_file = "app/page.jsx" if is_home_page else f"app/{slug}/page.jsx"
                    page_key = "home" if is_home_page else slug
                    relative_app_import = "../src/App.jsx" if route_file == "app/page.jsx" else "../../src/App.jsx"
                    component_name = re.sub(r"[^A-Za-z0-9]", "", str(page.get("name") or "Page")) or "Page"
                    if route_file in next_files:
                        raise RuntimeError(f"Duplicate Next.js route generated for page slug: {slug}")
                    next_files[route_file] = f'"use client";\nimport App from "{relative_app_import}";\nexport default function {component_name}Page() {{ return <App initialPage={json.dumps(page_key)} />; }}\n'
                if "app/page.jsx" not in next_files:
                    next_files["app/page.jsx"] = '"use client";\nimport App from "../src/App.jsx";\nexport default function HomePage() { return <App initialPage="home" />; }\n'
                index_html = f'<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{safe_title}</title></head><body><p>Run <code>npm install</code> and <code>npm run build</code>, then host the static files in <code>out/</code>.</p></body></html>'
            else:
                index_html = f'<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{safe_title}</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>'

        if not is_html:
            index_html = self._apply_seo_metadata(index_html, seo_data, title, prompt, approved_image_urls)

            readme = f"""# {title}

Generated by **AI Site Studio** as a frontend-only static website. No API server or database is included.

## 📁 Project Structure

```
{title}/
├── index.html          ← Vite entry point
├── src/
│   ├── App.jsx         ← Main React component
│   ├── main.jsx        ← Vite entry point
│   ├── index.css       ← Global styles + Tailwind
│   ├── components/     ← Navbar, Footer
│   └── pages/          ← HomePage, AboutPage, ServicesPage, ContactPage
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── README.md
```

## 🚀 Quick Start

### Local development
```bash
npm install
npm run dev
```

### Method 3: Production Build
```bash
npm install
npm run build
{('Static files are exported to `out/`.' if is_next else 'npm run preview')}
```

Contact forms need an external form service to deliver messages. Static files do not store submissions.

## Validation scope
The Studio checks package structure, required files, local imports and links, page routes, and known security signatures. It does not install dependencies or execute generated code during generation. Run `npm run build` in your deployment environment and review the output before publishing.
"""

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            # ── Folder 1: Root — index.html (standalone, browser-ready) ──
            zip_file.writestr("index.html", index_html)
            zip_file.writestr("package.json", json.dumps(package_json, indent=2))
            if tailwind_config:
                zip_file.writestr("tailwind.config.js", tailwind_config)
            if postcss_config:
                zip_file.writestr("postcss.config.js", postcss_config)
            if is_next:
                zip_file.writestr("next.config.mjs", "const nextConfig = { output: 'export' };\nexport default nextConfig;\n")
                zip_file.writestr("jsconfig.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}}, indent=2))
                seo_values = self._seo_values(seo_data, title, prompt, approved_image_urls)
                next_metadata = {
                    "title": seo_values["title"],
                    "description": seo_values["description"],
                    "keywords": seo_values["keywords"],
                    "openGraph": {
                        "title": seo_values["title"],
                        "description": seo_values["description"],
                        "type": "website",
                    },
                    "twitter": {
                        "card": "summary_large_image" if seo_values["image"] else "summary",
                        "title": seo_values["title"],
                        "description": seo_values["description"],
                    },
                }
                if seo_values["image"]:
                    next_metadata["openGraph"]["images"] = [seo_values["image"]]
                    next_metadata["twitter"]["images"] = [seo_values["image"]]
                if seo_values["canonical_url"] and len((plan or {}).get("pages", [])) <= 1:
                    next_metadata["alternates"] = {"canonical": seo_values["canonical_url"]}
                structured_data = {"@context": "https://schema.org", "@type": "WebSite", "name": title[:200]}
                structured_data_text = json.dumps(structured_data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
                next_layout = (
                    "import '../src/" + ("index.scss" if css_engine == "sass" else "index.css") + "';\n"
                    + ("import 'bootstrap/dist/css/bootstrap.min.css';\n" if css_engine == "bootstrap" else "")
                    + "export const metadata = " + json.dumps(next_metadata, ensure_ascii=False) + ";\n"
                    + "const structuredData = " + json.dumps(structured_data_text, ensure_ascii=False) + ";\n"
                    + "export default function RootLayout({ children }) { return <html lang=\"en\"><head><script type=\"application/ld+json\" dangerouslySetInnerHTML={{ __html: structuredData }} /></head><body>{children}</body></html>; }\n"
                )
                zip_file.writestr("app/layout.jsx", next_layout)
                for fpath, fcontent in next_files.items():
                    zip_file.writestr(fpath, fcontent)
            else:
                zip_file.writestr("vite.config.js", vite_config)
            zip_file.writestr("README.md", readme)

            # ── Folder 2: src/ — framework-specific app and page files ──
            if is_next:
                zip_file.writestr("src/App.jsx", multipage_react.get("src/App.jsx", app_content))
            elif is_vue:
                zip_file.writestr("src/App.vue", multipage_react.get("src/App.vue", app_content))
                zip_file.writestr("src/main.js", main_code)
            elif "src/App.jsx" in multipage_react:
                zip_file.writestr("src/App.jsx", multipage_react["src/App.jsx"])
                zip_file.writestr("src/main.jsx", main_code)
            else:
                zip_file.writestr("src/App.jsx", app_content)
                zip_file.writestr("src/main.jsx", main_code)
            zip_file.writestr("src/index.scss" if css_engine == "sass" else "src/index.css", index_css)
            for fpath, fcontent in multipage_react.items():
                if fpath not in ("src/App.jsx", "src/App.vue"):
                    zip_file.writestr(fpath, fcontent)

            # ── Folder 3: backend/ — FastAPI REST API ──
            if project_scope == "fullstack":
                for bpath, bcontent in backend_code.items():
                    zip_file.writestr(f"backend/{bpath}", bcontent)
                if backend_framework.lower() == "fastapi":
                    zip_file.writestr("backend/seed.py", seed_code)

        return zip_buffer.getvalue()

    async def review_release_package(self, zip_bytes: bytes) -> Dict[str, Any]:
        """Review release metadata after deterministic package and audit steps finish."""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                evidence = ["PACKAGE FILES:\n" + "\n".join(names[:160])]
                budget = 18000
                for name in names:
                    if budget <= 0:
                        break
                    if name.lower().endswith(("readme.md", "package.json", "requirements.txt", "pyproject.toml", "vite.config.js", "next.config.mjs")):
                        content = archive.read(name).decode("utf-8", errors="ignore")[:5000]
                        block = f"\n--- {name} ---\n{content}"
                        evidence.append(block[:budget])
                        budget -= len(block)
            return await run_advisory_code_review(
                task="Perform a deployment-readiness review of this generated ZIP. Check whether the documented run/build steps match the manifests and whether expected entry points are present. Do not claim that installation or deployment was executed.",
                evidence="\n".join(evidence),
                provider=getattr(settings, "AGENT_DEPLOYMENT_PROVIDER", "cline"),
            )
        except Exception as exc:
            logger.warning("Deployment readiness review could not inspect the ZIP: %s", exc)
            return {"status": "unavailable", "summary": "Model review was unavailable; deterministic package checks remain authoritative.", "findings": []}



class MultiAgentOrchestrator:
    """Master Orchestrator triggering the 8 sequential AI Agents."""
    def __init__(self):
        self.planning_agent = PlanningAgent()
        self.designer_agent = UIDesignerAgent()
        self.frontend_agent = FrontendAgent()
        self.backend_agent = BackendAgent()
        self.database_agent = DatabaseAgent()
        self.seo_agent = SEOAgent()
        self.testing_agent = TestingAgent()
        self.deployment_agent = DeploymentAgent()

    async def backpropagate_repairs(
        self,
        frontend_code: Any,
        errors: List[str],
        plan: Dict[str, Any],
        framework: str,
        css_engine: str,
        prompt: str,
        title: str,
        design: Dict[str, Any],
        expected_pages: List[Dict[str, Any]],
        project_images: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """
        ML Backpropagation Step:
        Propagates validation loss (audit defects) backwards into code artifacts,
        applying targeted repairs to eliminate broken links, missing pages, and placeholders.
        """
        is_html = (framework or "").lower() in ("html", "vanilla", "static")

        if is_html and isinstance(frontend_code, dict):
            regenerated_pages = None
            for err in errors:
                # 1. Missing planned page
                match_missing = re.search(r"Missing planned page:\s*([^\s]+)", err)
                if match_missing:
                    missing_page = match_missing.group(1).strip()
                    if missing_page not in frontend_code:
                        if regenerated_pages is None:
                            regenerated_pages = await self.frontend_agent.execute(prompt, plan, design, framework, css_engine, project_images=project_images)
                        if isinstance(regenerated_pages, dict) and regenerated_pages.get(missing_page):
                            frontend_code[missing_page] = regenerated_pages[missing_page]
                            safe_print(f"     🛠️ [Backprop Repair] Regenerated missing page using the shared design system: {missing_page}")

                # 2. Broken local link
                match_broken = re.search(r"Broken local link in ([^:]+):\s*([^\s]+)", err)
                if match_broken:
                    source_file = match_broken.group(1).strip()
                    broken_target = match_broken.group(2).strip()
                    if source_file in frontend_code:
                        content = frontend_code[source_file]
                        clean_target = broken_target.split('#')[0].split('?')[0].lstrip('/')
                        target_stem = clean_target.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
                        replacement = next(
                            (name for name in frontend_code if name.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() == target_stem),
                            None,
                        )
                        if replacement:
                            content = re.sub(
                                rf'(href=["\']){re.escape(broken_target)}(["\'])',
                                rf'\g<1>{replacement}\g<2>',
                                content,
                            )
                            frontend_code[source_file] = content

            if any(
                "Placeholder or unfinished content" in err
                or "Code review [" in err
                or "Broken local link" in err
                or "Unsupported factual claim" in err
                for err in errors
            ):
                regenerated_pages = await self.frontend_agent.execute(
                    prompt, plan, design, framework, css_engine,
                    project_images=project_images,
                    validation_feedback=errors,
                )
                if isinstance(regenerated_pages, dict):
                    frontend_code.update(regenerated_pages)

        elif isinstance(frontend_code, str) and any(
            "Placeholder or unfinished content" in err
            or "Code review [" in err
            or "Broken local link" in err
            or "Unsupported factual claim" in err
            for err in errors
        ):
            regenerated = await self.frontend_agent.execute(
                prompt, plan, design, framework, css_engine,
                project_images=project_images,
                validation_feedback=errors,
            )
            return regenerated if isinstance(regenerated, str) and regenerated.strip() else frontend_code

        return frontend_code

    def deterministic_normalize_links_and_content(
        self,
        frontend_code: Any,
        expected_pages: List[Dict[str, Any]],
        framework: str
    ) -> Any:
        """
        Deterministic repair pass: normalize only links with an exact planned destination.
        """
        is_html = (framework or "").lower() in ("html", "vanilla", "static")
        if is_html and isinstance(frontend_code, dict):
            available_files = set(frontend_code.keys())
            for fname, content in list(frontend_code.items()):
                def link_replacer(match):
                    attr = match.group(1)
                    quote = match.group(2)
                    val = match.group(3)
                    if val.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:", "#")):
                        return match.group(0)
                    clean_val = val.split('#')[0].split('?')[0].lstrip('/')
                    if not clean_val or clean_val in available_files:
                        return match.group(0)
                    if clean_val + ".html" in available_files:
                        return f"{attr}{quote}{clean_val}.html{quote}"
                    target_stem = clean_val.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
                    exact_match = next(
                        (af for af in available_files if af.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() == target_stem),
                        None,
                    )
                    if exact_match:
                        return f"{attr}{quote}{exact_match}{quote}"
                    return match.group(0)

                normalized_content = re.sub(r'(href=)(["\'])([^"\']+)\2', link_replacer, content, flags=re.IGNORECASE)
                frontend_code[fname] = normalized_content

        return frontend_code

    async def run_pipeline(
        self,
        prompt: str,
        framework: str = "html",
        css_engine: str = "tailwind",
        project_scope: str = "frontend",
        industry: str = "General",
        color_scheme: str = "Modern Glassmorphism",
        title: str = "AI Multi-Agent Template",
        backend_framework: str = "fastapi",
        requested_pages: Optional[List[Dict[str, Any]]] = None,
        answers: Optional[Dict[str, Any]] = None,
        project_images: Optional[List[Dict[str, Any]]] = None,
        brand_colors: Optional[Dict[str, Any]] = None,
        architecture_type: str = "multi_page",
        is_multipage: bool = True,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        if answers:
            prompt = f"{prompt}\n\nUser-approved customization answers:\n{json.dumps(answers, ensure_ascii=False)}"
        
        primary_model = getattr(settings, "KIMI_MODEL", "moonshot-v1-32k")
        alt_model = getattr(settings, "ALT_MODEL_WEBSITE_CONTENT_GENERATION", "gpt-4o")

        safe_print("\n" + "="*80)
        safe_print("🚀 STATIC WEBSITE GENERATION PIPELINE INITIALIZED")
        safe_print("="*80)
        safe_print(f"📋 Prompt         : \"{prompt}\"")
        safe_print(f"🏢 Target Industry : \"{industry}\"")
        safe_print(f"🎨 Tech Stack      : {framework.upper()} + {css_engine.upper()} ({project_scope.upper()})")
        safe_print("🤖 Multi-Model Swarm Architecture (Cline Autonomous Engine + Ollama):")
        safe_print(f"   ├── [1/6] Planning Agent     : {getattr(settings, 'AGENT_PLANNING_PROVIDER', 'cline').upper()}")
        safe_print(f"   ├── [2/6] UI Designer Agent  : {getattr(settings, 'AGENT_DESIGNER_PROVIDER', 'cline').upper()} ({getattr(settings, 'OLLAMA_MODEL_DESIGNER', 'qwen3.5:9b')})")
        safe_print(f"   ├── [3/6] Frontend Dev Agent : {getattr(settings, 'AGENT_FRONTEND_PROVIDER', 'cline').upper()}")
        safe_print(f"   ├── [4/6] SEO & A11y Agent   : {getattr(settings, 'AGENT_SEO_PROVIDER', 'cline').upper()} ({getattr(settings, 'OLLAMA_MODEL_SEO', 'qwen3.5:9b')})")
        safe_print(f"   ├── [5/6] Testing & Audit    : deterministic checks + {getattr(settings, 'AGENT_TESTING_PROVIDER', 'cline').upper()} review")
        safe_print("   └── [6/6] Packaging Agent    : static frontend ZIP")
        safe_print("-" * 80)

        # Step 1: Planning Agent
        t0 = time.time()
        plan_provider = getattr(settings, 'AGENT_PLANNING_PROVIDER', 'cline').upper()
        safe_print(f"\n[1/6] 📋 PLANNING AGENT (Feature: planning_agent | Provider: {plan_provider})")
        safe_print("     Status: Analyzing prompt architecture & ordering multi-page breakdown...")
        plan = await self.planning_agent.execute(prompt, framework, industry, requested_pages=requested_pages)
        if architecture_type not in {"single_page", "multi_page"} or is_multipage != (architecture_type == "multi_page"):
            raise ValueError("The selected page architecture is invalid or inconsistent.")
        plan["architecture_type"] = architecture_type
        if requested_pages is not None:
            normalized_pages = []
            planned_by_filename = {
                str(page.get("filename", "")).strip().lower(): page
                for page in plan.get("pages", [])
                if isinstance(page, dict) and page.get("filename")
            }
            planned_by_name = {
                re.sub(r"[^a-z0-9]+", "", str(page.get("name", "")).lower()): page
                for page in plan.get("pages", [])
                if isinstance(page, dict) and page.get("name")
            }
            for page in requested_pages:
                if page.get("selected") is False:
                    continue
                filename = str(page.get("filename") or "").strip()
                name = str(page.get("name") or "").strip()
                if not filename or not name:
                    continue
                if "/" in filename or "\\" in filename or not filename.lower().endswith(".html"):
                    raise ValueError(f"Invalid page filename in selected plan: {filename}")
                planned_detail = planned_by_filename.get(filename.lower()) or planned_by_name.get(re.sub(r"[^a-z0-9]+", "", name.lower()), {})
                requested_summary = str(page.get("content_summary") or page.get("summary") or "").strip()
                is_generic_custom_summary = bool(re.match(r"custom\s+.+?\s+page layout tailored to your specific business requirements\.?$", requested_summary, re.IGNORECASE))
                page_summary = str(
                    planned_detail.get("summary") if is_generic_custom_summary and planned_detail.get("summary") else requested_summary
                ).strip()
                if not page_summary or is_generic_custom_summary and not planned_detail.get("summary"):
                    page_summary = (
                        f"Create a complete, original {name} page for {title}, grounded in this website brief and its audience. "
                        "Give this page a distinct user task and headline, useful page-specific sections, substantial real copy derived only from the brief, "
                        "relevant imagery or illustration, and interactions appropriate to this page. Do not reuse the homepage layout or leave placeholder sections."
                    )
                normalized_pages.append({
                    **page,
                    "name": name,
                    "filename": filename,
                    "slug": str(page.get("slug") or filename.rsplit(".", 1)[0]),
                    "summary": page_summary,
                    "page_type": str(page.get("page_type") or page.get("type") or name.lower()),
                })
            if not normalized_pages:
                raise ValueError("Select at least one page before generation.")
            if not any(page["filename"].lower() == "index.html" for page in normalized_pages):
                raise ValueError("The selected page plan must include index.html.")
            filenames = [page["filename"].lower() for page in normalized_pages]
            if len(set(filenames)) != len(filenames):
                raise ValueError("The selected page plan contains duplicate filenames.")
            plan["pages"] = normalized_pages

        if (framework or "").lower() in ("html", "vanilla", "static"):
            canonical_pages = []
            for page in plan.get("pages", []):
                if not isinstance(page, dict):
                    raise ValueError("The generated page plan contains an invalid page entry.")
                filename = str(page.get("filename") or "").strip()
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.html", filename, flags=re.IGNORECASE):
                    raise ValueError(f"Invalid HTML page filename in the page plan: {filename or '(empty)'}")
                canonical_pages.append({**page, "filename": filename.lower()})
            filenames = [page["filename"] for page in canonical_pages]
            if len(filenames) != len(set(filenames)):
                raise ValueError("The page plan contains duplicate HTML filenames after case normalization.")
            if "index.html" not in filenames:
                raise ValueError("The page plan must include index.html.")
            plan["pages"] = canonical_pages

        if not is_multipage:
            planned = plan.get("pages", [])
            if requested_pages is not None and len(planned) != 1:
                raise ValueError("Single-page architecture must contain exactly one selected page.")
            if not planned:
                raise ValueError("The single-page plan must include a home page.")
            home = next((page for page in planned if page.get("filename", "").lower() == "index.html"), planned[0])
            home = {**home, "filename": "index.html", "slug": "home"}
            plan["pages"] = [home]
        elif len(plan.get("pages", [])) < 2:
            raise ValueError("Multi-page architecture must contain at least two selected pages.")
        if answers:
            plan["user_preferences"] = answers
        if (not title or title == "AI Multi-Agent Template") and plan.get("business_name"):
            title = plan["business_name"].strip()
        t1 = time.time()
        pages_str = ", ".join([p.get('filename', p.get('name', '')) for p in plan.get('pages', [])])
        safe_print(f"     -> Domain: {plan.get('domain', 'Business')} | Audience: {plan.get('audience', 'Clients')}")
        safe_print(f"     -> Ordered Pages: {pages_str}")
        safe_print(f"     ✅ [Agent 1 Completed in {t1 - t0:.2f}s]")
        if progress_callback:
            await progress_callback({"step": 1, "agent": "Planning Agent", "status": "completed", "details": f"Ordered Pages: {pages_str}"})

        # Step 2: UI Designer Agent
        t0 = time.time()
        designer_provider = getattr(settings, 'AGENT_DESIGNER_PROVIDER', 'ollama').upper()
        safe_print(f"\n[2/6] 🎨 UI DESIGNER AGENT (Feature: designer_agent | Provider: {designer_provider})")
        safe_print("     Status: Establishing visual design tokens & Google Fonts typography...")
        design = await self.designer_agent.execute(plan, color_scheme)
        if isinstance(brand_colors, dict):
            for design_key, color_key in (
                ("primary_hex", "primary"),
                ("secondary_hex", "secondary"),
                ("accent_hex", "accent"),
                ("bg_hex", "background"),
                ("card_hex", "surface"),
                ("text_hex", "text"),
            ):
                value = brand_colors.get(color_key)
                if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    design[design_key] = value
        t1 = time.time()
        safe_print(f"     -> Palette: Primary {design.get('primary_hex')}, Secondary {design.get('secondary_hex')}, Accent {design.get('accent_hex')}")
        safe_print(f"     -> Typography: Display '{design.get('font_display')}' / Body '{design.get('font_body')}'")
        safe_print(f"     ✅ [Agent 2 Completed in {t1 - t0:.2f}s]")
        if progress_callback:
            await progress_callback({"step": 2, "agent": "UI Designer Agent", "status": "completed", "details": f"Palette: Primary {design.get('primary_hex')}"})

        # Sequential Execution Phase: Agents execute one by one with dedicated GPU/VRAM allocation
        # Step 3: Frontend Developer Agent (Cline Engine)
        t0 = time.time()
        frontend_provider = getattr(settings, 'AGENT_FRONTEND_PROVIDER', 'cline').upper()
        safe_print(f"\n[3/6] 💻 FRONTEND DEVELOPER AGENT (Feature: code_assistant | Provider: {frontend_provider})")
        safe_print("     Status: Generating complete, plan-specific frontend pages...")
        frontend_code = await self.frontend_agent.execute(prompt, plan, design, framework, css_engine, project_images=project_images)
        t1 = time.time()
        generated_character_count = (
            sum(len(source) for source in frontend_code.values() if isinstance(source, str))
            if isinstance(frontend_code, dict)
            else len(frontend_code or "")
        )
        safe_print(f"     -> Source Code Generated: {generated_character_count} characters")
        safe_print(f"     ✅ [Agent 3 Completed in {t1 - t0:.2f}s]")
        if progress_callback:
            await progress_callback({"step": 3, "agent": "Frontend Developer Agent", "status": "completed", "details": f"Code Length: {len(frontend_code)} chars"})

        # Generated site projects contain static frontend files only.
        backend_code: Dict[str, str] = {}
        seed_code = ""

        # Step 6: SEO & Accessibility Agent
        t0 = time.time()
        seo_provider = getattr(settings, 'AGENT_SEO_PROVIDER', 'groq').upper()
        safe_print(f"\n[4/6] 🔍 SEO & ACCESSIBILITY AGENT (Feature: seo_generator | Provider: {seo_provider})")
        safe_print("     Status: Generating Schema.org JSON-LD, OpenGraph, and meta descriptions...")
        user_hero_image = next((str(image.get("url")) for image in (project_images or []) if isinstance(image, dict) and image.get("url")), "")
        seo_data = await self.seo_agent.execute(title, plan, hero_image=user_hero_image, source_prompt=prompt)
        t1 = time.time()
        seo_display_title = seo_data.get('meta_title') or seo_data.get('meta_tags', {}).get('title', title)
        safe_print(f"     -> SEO Meta Title: {seo_display_title}")
        safe_print(f"     ✅ [Agent 4 Completed in {t1 - t0:.2f}s]")
        if progress_callback:
            await progress_callback({"step": 4, "agent": "SEO & Accessibility Agent", "status": "completed", "details": f"SEO Title: {seo_display_title}"})

        # Step 8: Deployment Agent (pre-pack bytes)
        t0 = time.time()
        zip_bytes = await self.deployment_agent.execute(
            title, framework, css_engine, project_scope, frontend_code, backend_code, seed_code, seo_data, design,
            backend_framework=backend_framework,
            prompt=prompt, plan=plan, project_images=project_images
        )

        # Step 7: Testing Agent
        safe_print(f"\n[5/6] 🧪 TESTING & AUDIT AGENT (Provider: {getattr(settings, 'AGENT_TESTING_PROVIDER', 'cline').upper()} | Ollama code model with configured local fallback)")
        safe_print("     Status: Performing static package, import, link, and route audit (framework build is not executed in the application process)...")
        if framework.lower() in ("html", "vanilla", "static"):
            expected_pages = plan.get("pages", [])
        elif framework.lower() == "vue":
            expected_pages = [{"filename": "src/App.vue"}]
        elif framework.lower() in ("next", "nextjs"):
            expected_pages = []
            for page in plan.get("pages", []):
                route_slug = re.sub(r"[^a-z0-9-]+", "-", str(page.get("slug") or page.get("filename", "").rsplit(".", 1)[0] or page.get("name") or "page").lower()).strip("-") or "page"
                page_key = "home" if route_slug in {"home", "index"} or str(page.get("filename", "")).lower() == "index.html" else route_slug
                expected_pages.append({
                    "filename": "app/page.jsx" if page_key == "home" else f"app/{page_key}/page.jsx",
                    "route_slug": page_key,
                })
        else:
            expected_pages = [{"filename": "src/App.jsx"}]
        test_audit = await self.testing_agent.execute(
            zip_bytes,
            expected_pages=expected_pages,
            project_scope=project_scope,
            framework=framework,
            approved_facts=prompt,
        )
        t1 = time.time()
        tech_stack = test_audit.get('tech_stack') or ["HTML, CSS, JavaScript"]
        if isinstance(tech_stack, str):
            tech_stack = [tech_stack]
        safe_print(f"     -> Audit Result: {test_audit.get('status', 'passed').upper()} | Tech Stack: {', '.join(tech_stack)}")
        safe_print(f"     ✅ [Static audit completed in {t1 - t0:.2f}s; framework compilation is explicitly not claimed]")
        if progress_callback:
            audit_detail = "Static package audit passed; framework compilation was not run." if test_audit.get("status") == "passed" else "Static package audit failed."
            await progress_callback({"step": 5, "agent": "Static Package Audit", "status": "completed" if test_audit.get("status") == "passed" else "failed", "details": audit_detail})

        # Repair audited defects, re-package, and re-audit up to three times.
        max_epochs = 3
        epoch = 1
        while test_audit.get("status") != "passed" and epoch <= max_epochs:
            errors = test_audit.get("errors", [])
            safe_print(f"\n🔄 [Backpropagation Epoch {epoch}/{max_epochs}] Loss Signal Detected ({len(errors)} validation defect(s)):")
            for err in errors:
                safe_print(f"     ⚠️ Gradient Loss: {err}")

            if progress_callback:
                await progress_callback({
                    "step": 5,
                    "agent": f"Backpropagation Verification (Epoch {epoch})",
                    "status": "in_progress",
                    "details": f"Self-correcting {len(errors)} validation defect(s)...",
                })

            # Backward Pass: Repair code artifacts based on error gradient
            frontend_code = await self.backpropagate_repairs(
                frontend_code=frontend_code,
                errors=errors,
                plan=plan,
                framework=framework,
                css_engine=css_engine,
                prompt=prompt,
                title=title,
                design=design,
                expected_pages=expected_pages,
                project_images=project_images,
            )

            # Forward Pass: Re-package zip
            zip_bytes = await self.deployment_agent.execute(
                title, framework, css_engine, project_scope, frontend_code, backend_code, seed_code, seo_data, design,
                backend_framework=backend_framework,
                prompt=prompt, plan=plan, project_images=project_images
            )

            # Evaluate Loss: Re-audit package
            test_audit = await self.testing_agent.execute(
                zip_bytes,
                expected_pages=expected_pages,
                project_scope=project_scope,
                framework=framework,
                approved_facts=prompt,
            )
            safe_print(f"     -> Epoch {epoch} Verification: {test_audit.get('status', 'failed').upper()} ({len(test_audit.get('errors', []))} remaining defect(s))")
            epoch += 1

        # Final repair pass: keep unresolved defects visible and fail the generation gate.
        if test_audit.get("status") != "passed":
            safe_print("\n🛠️ [Final Deterministic Repair] Resolving only exact local-link matches before the final audit...")
            frontend_code = self.deterministic_normalize_links_and_content(
                frontend_code=frontend_code,
                expected_pages=expected_pages,
                framework=framework
            )
            zip_bytes = await self.deployment_agent.execute(
                title, framework, css_engine, project_scope, frontend_code, backend_code, seed_code, seo_data, design,
                backend_framework=backend_framework,
                prompt=prompt, plan=plan, project_images=project_images
            )
            test_audit = await self.testing_agent.execute(
                zip_bytes,
                expected_pages=expected_pages,
                project_scope=project_scope,
                framework=framework,
                approved_facts=prompt,
            )
            if test_audit.get("status") != "passed":
                remaining = test_audit.get("errors", [])
                safe_print(f"     ❌ [Audit Gate] Package remains invalid after repair and re-audit: {len(remaining)} defect(s).")
                if progress_callback:
                    await progress_callback({
                        "step": 5,
                        "agent": "Static Package Audit",
                        "status": "failed",
                        "details": "Automatic repair reached its retry limit; the package did not pass verification.",
                    })
                raise RuntimeError(
                    "Generated package failed verification after automatic repair attempts: "
                    + "; ".join(str(error) for error in remaining[:10])
                )
            safe_print("     ✅ [Deterministic Convergence] Re-audit passed with zero reported defects.")

        if progress_callback:
            await progress_callback({
                "step": 5,
                "agent": "Static Package Audit",
                "status": "completed",
                "details": "Static package audit passed after validation and any required repairs.",
            })

        deployment_review = await self.deployment_agent.review_release_package(zip_bytes)
        if deployment_review.get("status") == "completed":
            safe_print(f"     -> Deployment AI review completed ({len(deployment_review.get('findings', []))} advisory findings).")
        else:
            safe_print("     -> Deployment AI review unavailable; deterministic ZIP retained.")

        t0_dep = time.time()
        safe_print("\n[6/6] 📦 PACKAGING AGENT (Static frontend ZIP)")
        safe_print("     Status: Packaging frontend files and README...")
        t1_dep = time.time()
        safe_print(f"     -> Static Frontend ZIP Package Created: {len(zip_bytes)} bytes")
        safe_print(f"     ✅ [Agent 6 Completed in {t1_dep - t0_dep:.2f}s]")
        if progress_callback:
            await progress_callback({"step": 6, "agent": "Packaging Agent", "status": "completed", "details": f"ZIP Package: {len(zip_bytes)} bytes"})

        total_time = time.time() - start_time
        safe_print("\n" + "="*80)
        safe_print("🎉 STATIC WEBSITE PACKAGE CREATED SUCCESSFULLY!")
        safe_print(f"⏱️ Total Pipeline Execution Time: {total_time:.2f}s | ZIP Size: {len(zip_bytes) / 1024:.1f} KB")
        safe_print("="*80 + "\n")

        return {
            "title": title,
            "zip_bytes": zip_bytes,
            "plan": plan,
            "design": design,
            "frontend_code": frontend_code,
            "backend_code": backend_code,
            "seo_data": seo_data,
            "test_audit": test_audit,
            "deployment_review": deployment_review,
        }

multi_agent_orchestrator = MultiAgentOrchestrator()
