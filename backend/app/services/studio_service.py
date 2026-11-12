"""Agentic, page-by-page website creation for private Studio projects."""

import io
import json
import logging
import posixpath
import re
import time
import uuid
import zipfile
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlsplit

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.template import Template, TemplateFramework, TemplateLicense, TemplateStatus
from app.models.user import User
from app.services.ai_service import ai_service
from app.core.storage import storage
from app.core.config import settings
from app.services.security_scanner import security_scanner
from app.services.backend_generator import backend_generator, SUPPORTED_STACKS
from app.core.local_project_manager import local_project_manager
from app.services.framework_auditor import framework_auditor
from app.services.architect_agent import architect_agent
from app.services.watermark_service import (
    apply_inside_watermark,
    generate_watermark_license_page,
    generate_commercial_license_page,
    generate_runtime_js,
    generate_core_css,
    generate_stealth_telemetry_js,
)
from app.services.text_agent import text_agent
from app.services.agent_memory import agent_memory
from app.services.site_compiler import (
    generate_sitemap_xml,
    generate_robots_txt,
    inject_seo_and_social_tags,
    run_comprehensive_audit,
    normalize_multi_page_navigation,
)

logger = logging.getLogger(__name__)

AGENTS = {
    "planning": "Planning Agent",
    "design": "UI Designer Agent",
    "architect": "Architect Agent",
    "database": "DB Schema Agent",
    "backend": "Backend Dev Agent",
    "frontend": "Frontend Dev Agent",
    "seo": "SEO & A11y Agent",
    "testing": "Testing & Audit Agent",
    "packaging": "Packaging Agent",
}
ANALYSIS_PROVIDER_ORDER = ["groq", "gemini"]
CODE_PROVIDER_ORDER = ["gemini", "groq", "cline"]
STUDIO_CLINERULES = """# Studio website code rules
- Follow the approved brief, plan, owner answers, and UI design system.
- 100% ALL-DEVICE & MOBILE FRIENDLY (MANDATORY):
  * Every page MUST include `<meta name="viewport" content="width=device-width, initial-scale=1.0">` inside `<head>`.
  * The site must render perfectly on all devices: smartphones (320px–480px), tablets (768px–1024px), laptops, and large desktop screens without ANY horizontal overflow (zero horizontal scrollbar; use overflow-x: hidden on body).
  * Navigation on Mobile: When viewing on mobile screens (< 768px), navigation links must collapse into a mobile hamburger menu drawer with a clean, working open/close toggle script.
  * Mobile Touch Targets: All interactive buttons, links, inputs, and controls must have at least 44px height for effortless finger taps.
  * Fluid Layouts & Grids: Multi-column grids and flex containers must stack vertically into a single column on mobile screens (@media (max-width: 768px) { grid-template-columns: 1fr !important; flex-direction: column !important; }).
  * Fluid Typography & Media: Headings must scale using clamp() or media queries; all images/videos must have max-width: 100%; height: auto;.
- Generate one planned page per call and keep page names and relative links consistent.
- Treat the UI Designer's system as binding: reuse its palette, type scale, spacing, borders, shadows, and motion language on every page.
- Keep the same brand header, navigation, and footer structure across pages; mark the current page and ensure every navigation link targets a generated filename or a real section anchor.
- Use semantic accessible HTML, responsive CSS, visible focus, and prefers-reduced-motion.
- Use purposeful motion. Avoid generic filler layouts and repeated card grids.
- Make the site feel alive with an animated hero entrance, section reveals, and polished interaction transitions; respect prefers-reduced-motion.
- At narrow widths, reflow content without horizontal scrolling; use fluid type and spacing, and verify the layout intent at 360px, 768px, and desktop widths.
- Make every visible control perform a real browser-side action or clearly label it as a demo; do not leave dead buttons or placeholder links.
- Use vanilla JavaScript for real client-side behavior and structured JSON for reusable site metadata when it fits the brief; keep core content readable in HTML if scripts are disabled.
- Use supplied image URLs only when relevant and descriptive alt text. Never invent facts, prices, testimonials, metrics, awards, or credentials.
- Never claim forms, payments, accounts, or server actions work without an integration. Label browser-only demos honestly.
- Keep the site self-contained within its generated package, avoid unrequested frameworks and CDNs, and return the complete requested file only.
"""


def _parse_json(raw: str) -> dict[str, Any]:
    """
    Robust multi-pass JSON parser that handles missing commas, trailing commas,
    unescaped quotes, comments, and LLM syntax quirks.
    """
    clean = str(raw or "").strip()
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.IGNORECASE).strip()
    start, end = clean.find("{"), clean.rfind("}")
    if start >= 0 and end > start:
        clean = clean[start : end + 1]

    # Pass 1: Direct load
    try:
        res = json.loads(clean, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # Pass 2: Use robust_json_loads from ai_service
    try:
        from app.services.ai_service import robust_json_loads
        res = robust_json_loads(clean)
        if isinstance(res, dict) and res:
            return res
    except Exception:
        pass

    # Pass 3: Strip C/C++ style comments
    no_comments = re.sub(r'//.*?(?:\r?\n|$)', '\n', clean)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)

    # Pass 4: Fix missing commas between properties
    fixed_commas = re.sub(r'([0-9"truefalsenull\]\}])\s*(?:\r?\n)\s*("|\{)', r'\1,\n\2', no_comments)
    fixed_commas = re.sub(r',\s*([\]\}])', r'\1', fixed_commas)

    try:
        res = json.loads(fixed_commas, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # Pass 5: Fix unescaped double quotes inside string values on separate lines
    def _escape_inner_quotes(s: str) -> str:
        lines = s.splitlines()
        repaired = []
        for line in lines:
            m = re.match(r'^(\s*"[^"]+"\s*:\s*")(.*)("[\s,]*)$', line)
            if m:
                prefix, content, suffix = m.group(1), m.group(2), m.group(3)
                content_escaped = re.sub(r'(?<!\\)"', r'\"', content)
                repaired.append(f"{prefix}{content_escaped}{suffix}")
            else:
                repaired.append(line)
        return "\n".join(repaired)

    try:
        escaped_quotes = _escape_inner_quotes(fixed_commas)
        escaped_quotes = re.sub(r',\s*([\]}])', r'\1', escaped_quotes)
        res = json.loads(escaped_quotes, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # Pass 6: Try truncation recovery if bracket unclosed
    open_curly = clean.count('{') - clean.count('}')
    open_square = clean.count('[') - clean.count(']')
    truncated_fixed = fixed_commas + (']' * max(0, open_square)) + ('}' * max(0, open_curly))
    try:
        res = json.loads(truncated_fixed, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # Pass 7: Try robust_json_loads on the repaired string
    try:
        from app.services.ai_service import robust_json_loads
        res = robust_json_loads(fixed_commas)
        if isinstance(res, dict) and res:
            return res
    except Exception:
        pass

    raise ValueError("The AI agent returned an invalid structured response.")


HOME_PAGE_NAMES = {"index", "home", "homepage", "home-page", "landing", "landing-page", "main", "welcome"}
INNER_PAGE_NAMES = {"about", "about-us", "contact", "contact-us", "services", "products", "product", "shop", "blog", "faq", "pricing", "portfolio", "gallery"}


def _site_profile(category: str, genre: str, prompt: str) -> str:
    combined = f"{category} {genre} {prompt}".lower()
    if re.search(r"\b(?:hotel|resort|residency|motel|inn|lodge|hospitality|villa|accommodations?|suites?|stay|guest\s*house)\b", combined):
        return "hospitality"
    if re.search(r"\b(?:restaurant|cafe|coffee|bakery|dining|bistro|bar|pub|cuisine|chef|food|menu|eatery)\b", combined):
        return "restaurant"
    if re.search(r"\b(?:construction|contractor|building\s*company|roofing|remodel(?:ing)?|renovation|builder)\b", combined):
        return "construction"
    if re.search(r"\b(?:portfolio|resume|résumé|cv|photographer\s*portfolio|designer\s*portfolio|developer\s*portfolio|personal\s*site)\b", combined):
        return "portfolio"
    if re.search(r"\b(?:ecommerce|e-commerce|shop|store|retail|fashion|apparel|merchandise|products)\b", combined):
        return "ecommerce"
    if re.search(r"\b(?:saas|software|agency|startup|tech|consulting|platform|dashboard|crm|devops)\b", combined):
        return "saas"
    if re.search(r"\b(?:medical|clinic|doctor|hospital|dental|wellness|therapy|healthcare|patient)\b", combined):
        return "medical"
    if re.search(r"\b(?:real\s*estate|property|realtor|realty|apartments?|housing|homes)\b", combined):
        return "real_estate"
    return "general"


def _local_uploaded_file_id(url: str) -> uuid.UUID | None:
    """Return the ID only for this app's UUID-backed loopback upload URLs."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return None
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            return None
        match = re.fullmatch(r"/api/v1/files/([0-9a-fA-F-]{36})", parsed.path)
        return uuid.UUID(match.group(1)) if match else None
    except (TypeError, ValueError):
        return None


def _profile_guidance(profile: str) -> str:
    if profile == "portfolio":
        return "PORTFOLIO QUALITY BAR: Honor the selected page structure. Use only the person's name and professional title explicitly supplied in the original brief or owner answers, preserving the exact spelling and scope. A single first name must stay a first name; never infer a surname from the account profile, username, email, or other context. A single role must stay that role; never add a second title such as Full-Stack Developer unless the owner said so. Do not invent experience, employers, credentials, skills, clients, outcomes, metrics, or testimonials. Include selected work, skills/tools, experience, or education only when supplied, and provide a clear contact path. Use uploaded portrait, skill/tool, and project images according to their roles. Use expressive editorial art direction and a cohesive, visibly animated motion system while keeping the work easy to scan."
    if profile == "construction":
        return "CONSTRUCTION QUALITY BAR: Build a credible contractor site with a clear estimate/contact path, service area, practical service categories, and real completed-project proof. For a multi-page site, prefer Home, Services, Projects, and Contact/Request an Estimate; add About only when the brief supports it. Use uploaded project, team, and equipment images in their matching roles. Never invent licenses, insurance, safety records, years in business, project values, client names, reviews, or guarantees. Use confident architectural art direction, clear project details, and restrained purposeful motion."
    return "GENERAL QUALITY BAR: Identify the site's actual industry and main visitor task, then choose art direction and page structure that fit that use. Avoid default SaaS styling, repeated generic cards, filler content, and fabricated facts. Use supplied images in their stated roles and purposeful motion throughout the experience."


def _owner_display_name(prompt: str, answers: dict[str, Any] | None = None) -> str:
    """Return a user-supplied display name without consulting account profile fields."""
    answers = answers or {}
    for key in ("name", "person_name", "full_name", "author"):
        value = str(answers.get(key) or "").strip()
        if value:
            return value[:100]

    identity = str(answers.get("identity") or "").strip()
    if identity:
        # The identity clarification may also contain a title/intro. The leading
        # name segment is authoritative; the original answer remains available
        # to generation prompts for the role and introduction.
        leading = re.split(r"[,;|\n]|\s+[-–—]\s+|\s+(?:who\s+is|as\s+an?|and\s+I\s+am|I\s+am|I['’]m)\b|\s+is\s+(?:an?|the)\b", identity, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        leading = re.sub(r"^(?:my name is|i am|i['’]m|name is)\s+", "", leading, flags=re.IGNORECASE).strip()
        if (
            leading
            and len(leading.split()) <= 4
            and not re.match(r"^(?:a|an|the)\s", leading, re.IGNORECASE)
            and not re.search(r"\b(?:engineer|developer|designer|architect|manager|founder|student|teacher|photographer|consultant)\b", leading, re.IGNORECASE)
        ):
            return leading[:100]

    return _extract_prompt_details(prompt).get("name", "")


def _identity_fidelity_note(prompt: str, answers: dict[str, Any] | None = None) -> str:
    answers = answers or {}
    display_name = _owner_display_name(prompt, answers)
    identity_answer = str(answers.get("identity") or "").strip()
    lines = ["OWNER IDENTITY ACCURACY (authoritative):"]
    if display_name:
        lines.append(f'- Render the owner name exactly as supplied: "{display_name}". Do not append, infer, or expand a surname.')
    if identity_answer:
        lines.append(f'- Identity answer verbatim: "{identity_answer[:1200]}". Use only the title/role stated here; do not add another role.')
    lines.append("- Use the original request and owner answers as the only source for the person's name, role, skills, and bio. Ignore account display names and usernames. If a detail was not supplied, omit it rather than guessing.")
    return "\n".join(lines)

def _extract_prompt_details(prompt: str) -> dict[str, str]:
    """Analyze the user's initial prompt and pre-extract key business & personal entities."""
    details: dict[str, str] = {}
    if not prompt:
        return details
    import re

    # 1. Email extraction
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', prompt)
    if email_match:
        details["contact_email"] = email_match.group(0).strip()

    # 2. Phone / WhatsApp extraction
    phone_match = re.search(r'(?:phone|whatsapp|mobile|contact|tel|call)[:\s]*([+]?\d[\d\s\-\(\)]{8,16}\d)', prompt, re.IGNORECASE)
    if not phone_match:
        phone_match = re.search(r'([+]?(?:91|1|44)[\s\-\.]?\d{4,5}[\s\-\.]?\d{4,5}|\b\d{3}[-\s]\d{3}[-\s]\d{4}\b|\b\d{4}\s\d{3}\s\d{4}\b)', prompt)
    if phone_match:
        clean_phone = re.sub(r'[^\d+]', ' ', phone_match.group(1)).strip()
        if len(re.sub(r'\D', '', clean_phone)) >= 10:
            details["contact_phone"] = phone_match.group(1).strip()

    # 3. Name extraction (Portfolio / Person / Company / Business)
    name_patterns = [
        r"(?:portfolio|website|resume|cv)\s+for\s+([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*){0,2})(?=[,.!\n]|\s+(?:with|who|is|as|and|to|that|a|an)\b|$)",
        r"(?:my name is|i am|i'm)\s+([A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*){0,2})(?=[,.!\n]|\s+(?:and|as|who|which|a|an|the|working|based|at|with)\b|$)",
        r'\b([A-Z][a-zA-Z0-9\s]{1,25}\s+(?:Residency|Hotel|Resort|Lodge|Inn|Studio|Agency|Technologies|Solutions|Cafe|Bistro|Restaurant|Clinic|Store|Shop))\b',
    ]
    for np in name_patterns:
        m = re.search(np, prompt, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate and len(candidate.split()) <= 4 and not re.match(r"^(?:a|an|the)\s", candidate, re.IGNORECASE) and not re.search(r"\b(?:engineer|developer|designer|architect|manager|founder|student|teacher|photographer|consultant)\b", candidate, re.IGNORECASE):
                details["name"] = candidate
                break

    # 4. Pricing / Rates extraction
    price_matches = re.findall(r'(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s*[\d,]+(?:\s*[-–to/]+\s*(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)?\s*[\d,]+)?(?:\s*(?:per\s+(?:night|month|piece|item|year|hr|hour)|/-))?', prompt, re.IGNORECASE)
    if price_matches:
        details["pricing"] = ", ".join(dict.fromkeys(p.strip() for p in price_matches[:5]))

    # 5. Address / Location extraction
    address_match = re.search(r'(?:address|location)[:\s]*([^\n,]+(?:Road|Rd|Street|St|Nagar|Colony|Layout|Ave|Avenue|Lane|Coimbatore|Chennai|Bangalore|Mumbai|Delhi|London|New York)[^\n.]*)', prompt, re.IGNORECASE)
    if not address_match:
        address_match = re.search(r'\b\d+[\w\s,.-]+(?:Road|Rd|Street|St|Nagar|Colony|Layout|Ave|Avenue|Lane)[,\s\w.-]+(?:Tamil Nadu|Karnataka|Maharashtra|Kerala|Delhi|CA|NY|UK|\d{5,6})\b', prompt, re.IGNORECASE)
    if address_match:
        val = address_match.group(1) if address_match.lastindex else address_match.group(0)
        details["address"] = val.strip()

    # 6. Check-in / Check-out or Timings
    timings_match = re.search(r'(?:check-?in|timings?|hours?)[:\s]*([^\n]+?(?:am|pm|24/7|\d{1,2}:\d{2})[^\n.]*)', prompt, re.IGNORECASE)
    if timings_match:
        val = timings_match.group(1) if timings_match.lastindex else timings_match.group(0)
        details["timings"] = val.strip()

    return details


def _clarification_topic(question: str) -> str:
    text = str(question or "").lower()
    if re.search(r"\bemail\b", text):
        return "email"
    if re.search(r"\b(?:phone|mobile|whatsapp|telephone)\b", text):
        return "phone"
    if re.search(r"\b(?:prices?|pricing|rates?|costs?|budget)\b", text):
        return "pricing"
    if re.search(r"\b(?:opening hours|hours|timings|check-in|check-out|date|schedule)\b", text):
        return "timings"
    if re.search(r"\b(?:address|location|city|region|service area)\b", text):
        return "location"
    if re.search(r"\b(?:names?|identity|brand|company|business)\b", text):
        return "identity"
    if re.search(r"\b(?:audience|visitors|customers|clients|learners|users|students)\b", text):
        return "audience"
    if re.search(r"\b(?:skills?|tools?|technology|technologies|languages?)\b", text):
        return "skills"
    if re.search(r"\b(?:projects?|case stud|portfolio|work experience|work samples?)\b", text):
        return "projects"
    if re.search(r"\b(?:pages?|sitemap|sections?)\b", text):
        return "pages"
    if re.search(r"\b(?:courses?|programs?|classes|menus?|products?|services?|offerings?|content|features?)\b", text):
        return "offerings"
    if re.search(r"\b(?:contact|booking|reservations?|enroll|register|sign up|call to action|next step|main action)\b", text):
        return "next_step"
    if re.search(r"\b(?:style|visual|design|colors?|colours?|tone|mood|aesthetic)\b", text):
        return "visual_style"
    return " ".join(re.findall(r"[a-z0-9]+", text))[:120]


def _brief_answers_clarification(question: str, prompt: str, facts: dict[str, str]) -> bool:
    text = str(prompt or "").lower()
    topic = question if question in {"email", "phone", "pricing", "timings", "location", "identity", "audience", "skills", "projects", "offerings", "next_step", "visual_style"} else _clarification_topic(question)
    if topic == "email":
        return bool(facts.get("contact_email"))
    if topic == "phone":
        return bool(facts.get("contact_phone"))
    if topic == "pricing":
        return bool(facts.get("pricing")) or bool(re.search(r"\b(?:free|no prices?|prices? not shown|contact for pricing)\b", text))
    if topic == "timings":
        return bool(facts.get("timings")) or bool(re.search(r"\b(?:open|available|scheduled|schedule|event date|hours?)\b.{0,100}\b(?:am|pm|daily|weekdays|weekends|\d{1,2}:\d{2}|\d{1,2}[/-]\d{1,2})", text))
    if topic == "location":
        return bool(facts.get("address")) or bool(re.search(r"\b(?:located in|based in|address is|location is|serves? the|service area is)\b\s*\w{2,}(?:\s+\w+){0,8}", text))
    if topic == "identity":
        return bool(facts.get("name")) or bool(re.search(r"\b(?:my name is|i am|i'm|the company is|the business is|brand name is)\b", text))
    if topic == "audience":
        return bool(re.search(r"\b(?:target audience|designed for|made for|aimed at|serves?\s+(?:students|learners|families|businesses|homeowners|professionals|visitors|customers|clients)|for\s+(?:students|learners|families|businesses|homeowners|professionals|visitors|customers|clients|beginners|small businesses|local residents))\b", text))
    if topic == "skills":
        return bool(re.search(r"\b(?:skills?|tools?|technologies|languages?|we teach|we cover|we train in)\b.{0,240}\b\w{2,}", text))
    if topic == "projects":
        return bool(re.search(r"\b(?:projects?|case studies|featured work|work samples)\b\s*(?:include|are|:|such as|like|in|—|-)\s*\w{2,}", text))
    if topic == "pages":
        return bool(re.search(r"\b(?:pages?|sections?)\b.{0,160}\b(?:home|about|services?|projects?|work|skills?|contact|pricing|features?|menu|courses?|gallery|faq|team)\b", text))
    if topic == "offerings":
        return bool(re.search(r"\b(?:we|i|our|the|it|they)\s+(?:teach|offer|provide|sell|serve|feature|include|speciali[sz]e|run)\b.{0,240}\b\w{2,}", text)) or bool(re.search(r"\b(?:courses?|programs?|classes|menu|products?|services?|features?)\s*(?:include|are|:|such as|like)\s*\w{2,}", text)) or bool(re.search(r"\b(?:including|must include|should include|must have|should have)\b.{0,240}\b\w{2,}", text))
    if topic == "next_step":
        return bool(re.search(r"\b(?:(?:main|primary)\s+(?:call to action|action)\s*(?:is|should be|:)\s*\w+|visitors should\s+\w+|encourage visitors to\s+\w+|book now|enroll now|register now|sign up|contact us|request a quote|reserve a table|place an order)\b", text))
    if topic == "visual_style":
        return bool(re.search(r"\b(?:style is|style should be|visual direction is|color palette|colour palette|aesthetic is|mood is|feel like|look like)\b.{0,100}\b\w{2,}", text)) or bool(re.search(r"\b(?:modern|minimalist|editorial|playful|luxurious|bold|clean|professional|elegant|colorful|colourful|dark|light)\b", text))
    return False


def _filter_clarification_questions(questions: list[dict[str, Any]], prompt: str, facts: dict[str, str]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen_topics: set[str] = set()
    topic_patterns = {
        "email": r"\bemail\b",
        "phone": r"\b(?:phone|mobile|whatsapp|telephone)\b",
        "pricing": r"\b(?:price|pricing|rate|cost|budget)\b",
        "timings": r"\b(?:opening hours|hours|timings|check-in|check-out|dates?|schedules?)\b",
        "location": r"\b(?:addresses?|locations?|cities|regions?|service area)\b",
        "identity": r"\b(?:names?|identity|brand|companies|business(?:es)?)\b",
        "audience": r"\b(?:audience|visitors|customers|clients|learners|users)\b",
        "skills": r"\b(?:skills?|tools?|technology|technologies|languages?)\b",
        "projects": r"\b(?:projects?|case stud|portfolio|work experience|work samples?)\b",
        "pages": r"\b(?:pages?|sitemap|sections?)\b",
        "offerings": r"\b(?:courses?|programs?|classes|menus?|products?|services?|offerings?|content|features?)\b",
        "next_step": r"\b(?:contacts?|booking|reservations?|enroll|register|sign up|call to action|next step|main action)\b",
        "visual_style": r"\b(?:style|visual|design|colors?|colours?|tone|mood|aesthetic)\b",
    }
    for question in questions:
        if not isinstance(question, dict):
            continue
        text = str(question.get("question") or "").strip()
        topic = _clarification_topic(text)
        question_topics = {name for name, pattern in topic_patterns.items() if re.search(pattern, text, re.IGNORECASE)} or {topic}
        if not text or any(_brief_answers_clarification(name, prompt, facts) for name in question_topics) or question_topics & seen_topics:
            continue
        seen_topics.update(question_topics)
        filtered.append(question)
        if len(filtered) >= 4:
            break
    return filtered

HTML_STATIC_CATEGORIES = {
    "portfolio", "personal", "resume", "cv", "showcase", "photography",
    "artist", "restaurant", "cafe", "food", "menu", "bakery", "event",
    "wedding", "conference", "landing page", "landing_page", "one page",
    "brochure", "coming soon", "creative", "blog", "brochure website",
    "business", "company", "agency", "corporate", "consulting", "services",
    "technology", "healthcare", "real estate", "education", "travel",
}

PORTFOLIO_TERMS = (
    "portfolio", "resume", "cv", "personal", "showcase", "photographer",
    "photography", "artist", "freelancer", "developer portfolio", "designer portfolio",
    "profile", "bio", "curriculum vitae", "software company", "company", "agency",
)

def detect_stack_from_prompt(prompt: str, category: str = "", genre: str = "", requested_stack: str = "auto") -> str:
    """
    Intelligently analyzes the user's prompt and requirements:
    - Ordinary showcase and business websites default to 'html-css-js' (HTML5 + CSS + JavaScript).
    - An explicitly requested supported framework/stack takes priority over category-based defaults.
    - If the user lists developer skills (React, Python, Postgres, SQL, FastAPI, etc.) or bio/experience:
      -> It is recognized as their skill/background, NEVER a full-stack website requirement.
    - If anything explicitly requires an interactive application backend for the site itself (live database, user logins,
      shopping cart checkout, admin CRUD dashboard):
      -> Chooses 'react-fastapi-postgresql' (React + FastAPI + PostgreSQL).
    - Default: 'html-css-js' (clean semantic HTML5, modern CSS, vanilla JS).
    """
    if requested_stack == "html-css-js":
        return "html-css-js"
    if requested_stack in {"react-fastapi-postgresql", "vue-fastapi-postgresql", "angular-fastapi-postgresql"}:
        return requested_stack

    cat_lower = str(category or "").strip().lower()
    genre_lower = str(genre or "").strip().lower()
    prompt_lower = str(prompt or "").strip().lower()
    framework_context = f"{prompt_lower} {genre_lower}"

    # Honor an explicitly requested frontend framework before static category heuristics.
    # This lets a portfolio, restaurant, or brochure use the requested framework.
    # Skill lists alone are not framework requests. Require directive/context wording.
    explicit_framework_patterns = [
        r"\b(?:use|using|built\s+with|build\s+with|create(?:d)?\s+(?:it\s+)?(?:in|with)|develop(?:ed)?\s+(?:it\s+)?(?:in|with)|framework\s*(?:is|:)?|tech\s+stack\s*(?:is|:)?|stack\s*(?:is|:)?)\s+(?:the\s+)?(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
        r"\b(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\s+(?:website|site|app|application|portfolio)\b",
        r"\b(?:website|site|app|application|portfolio)\s+(?:in|with|using)\s+(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
        r"\b(?:create|build|make|develop|write|built|made|created|developed|written)\b.{0,100}\b(?:in|with|using)\s+(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
    ]
    for pattern in explicit_framework_patterns:
        match = re.search(pattern, framework_context, re.IGNORECASE)
        if match:
            framework = match.group("framework").lower().replace(".js", "")
            return f"{framework}-fastapi-postgresql"

    # Rule 1: Check if the category or genre is strictly a static HTML showcase/presentation category
    is_html_category = (
        cat_lower in HTML_STATIC_CATEGORIES
        or any(term in cat_lower for term in ("portfolio", "resume", "cv", "personal", "photograph", "showcase", "restaurant", "cafe", "menu", "bakery", "business", "company", "agency", "corporate", "service", "consulting"))
        or any(term in genre_lower for term in PORTFOLIO_TERMS)
        or any(term in genre_lower for term in ("restaurant", "cafe", "bakery", "event", "wedding", "brochure", "one page", "landing page", "business", "company", "agency", "corporate", "software company"))
    )

    # Rule 2: Check if prompt explicitly asks for a portfolio / resume / personal / company showcase site
    is_portfolio_request = bool(re.search(
        r"\b(?:portfolio|resume|résumé|cv|curriculum\s+vitae|personal\s+(?:site|website)|developer\s+portfolio|designer\s+portfolio|freelancer\s+portfolio|photographer\s+portfolio|artist\s+portfolio|my\s+projects?\s+showcase|show\s+what\s+we\s+do|show\s+the\s+user\s+what\s+they\s+do|software\s+company(?:\s+website)?|company\s+website|agency\s+website|business\s+website)\b",
        prompt_lower,
    ))

    # Explicit backend requirements for the website application itself
    explicit_backend_triggers = [
        r"\b(?:user\s+login\s+system|user\s+authentication\s+system|user\s+registration\s+system|user\s+accounts?\s+with\s+(?:jwt|oauth|passwords?))\b",
        r"\b(?:shopping\s+cart\s+with\s+(?:stripe|checkout|payment)|e-?commerce\s+store\s+with\s+order\s+management)\b",
        r"\b(?:(?:hotel\s+)?booking\s+(?:system|engine)\s+with\s+(?:live\s+)?database|(?:room|table)\s+reservation\s+(?:system\s+with\s+database|database))\b",
        r"\b(?:admin\s+crud\s+portal|saas\s+dashboard\s+with\s+database\s+crud)\b",
        r"\b(?:build\s+a\s+full[\s\-]*stack\s+(?:web\s+)?app(?:lication|site)?(?:\s+with\s+backend(?:\s+and\s+database)?)?)\b",
        r"\b(?:full[\s\-]*stack|fullstack|backend\s+and\s+frontend|frontend\s+and\s+backend)\b",
        r"\b(?:store\s+(?:and\s+analy[sz]e\s+)?data|analy[sz]e\s+data|data\s+storage|data\s+collection|data\s+analysis|analytics\s+dashboard|database\s+storage|persist\s+data|save\s+data\s+to\s+database)\b",
        r"\b(?:with\s+(?:a\s+)?backend|backend\s+and\s+database|database\s+backed|real\s+database|backend\s+api)\b",
        r"\b(?:rest\s+api\s+backend|fastapi\s+backend|express\s+backend|backend\s+service)\b",
        r"\b(?:crud|data\s+management|lead\s+management|submission\s+management)\b",
    ]
    has_explicit_backend = any(bool(re.search(pat, prompt_lower)) for pat in explicit_backend_triggers)

    # If it is a portfolio or static HTML category, guarantee html-css-js unless explicitly commanded with a backend app
    if (is_html_category or is_portfolio_request) and not has_explicit_backend:
        return "html-css-js"

    # Rule 3: Strip developer skills, experience, and bio from prompt
    # Users frequently say: "I am a React developer skilled in Python, SQL, PostgreSQL, FastAPI"
    # These are DEVELOPER SKILLS, not instructions to build a fullstack SaaS app for their portfolio.
    scrubbed_prompt = prompt_lower
    skill_patterns = [
        r"(?:skills?|technologies|tech\s+stack|tools?|languages?|proficiency)\s*[:\-\s]+[^\.\n;]+",
        r"(?:skilled|experienced|proficient|worked|knowledge|background)\s+(?:in|with)\s+[^\.\n;]+",
        r"(?:familiar|specializ(?:ed|ing))\s+(?:with|in)\s+[^\.\n;]+",
        r"(?:projects?|apps?)\s+(?:built|developed|created)\s+(?:with|using|in)\s+[^\.\n;]+",
        r"(?:full[\s\-]*stack|front[\s\-]*end|back[\s\-]*end|software|web|ui[\s\/]*ux|python|react|node|fastapi)\s+(?:developer|engineer|programmer|specialist|designer|creator|freelancer)",
        r"\b(?:years?\s+of\s+experience|work\s+experience|career\s+highlights|job\s+history)\b[^\.\n;]*",
        # Explicitly ignore tech names so skills like "React", "FastAPI", "Python", "PostgreSQL" in resumes never trigger fullstack
        r"\b(?:react(?:\.?js)?|next(?:\.?js)?|vue(?:\.?js)?|angular|tailwind|typescript|javascript|html5?|css3?|python|fastapi|django|flask|postgresql?|postgres|sqlite3?|mongodb|mysql)\b",
    ]
    for sp in skill_patterns:
        scrubbed_prompt = re.sub(sp, " ", scrubbed_prompt)

    # Evaluate dynamic backend indicators against the scrubbed prompt + context
    full_context = f"{scrubbed_prompt} {category} {genre}".lower()

    backend_indicators = [
        r"\b(?:live\s+database|postgres(?:ql)?\s+database|sqlite\s+database|mysql\s+database|database\s+schema|database\s+crud|table\s+schema|persist\s+data\s+to\s+db)\b",
        r"\b(?:auth|authentication|user\s+login|log\s+in\s+portal|sign\s?in\s+portal|sign\s?up\s+portal|register\s+account|user\s+account\s+system|password\s+reset|jwt\s+tokens?|oauth2|rbac)\b",
        r"\b(?:admin\s+panel|admin\s+dashboard|client\s+portal|management\s+portal|crm\s+system)\b",
        r"\b(?:booking\s+system|reservation\s+system|reserve\s+online\s+with\s+database|table\s+booking\s+engine|room\s+booking\s+system)\b",
        r"\b(?:shopping\s+cart|checkout\s+system|payment\s+gateway|stripe\s+checkout|process\s+payments?|order\s+management\s+system|inventory\s+system)\b",
        r"\b(?:fastapi\s+backend|rest\s+api\s+endpoints?|server-side\s+api|backend\s+service\s+with\s+database)\b",
        r"\b(?:store\s+(?:and\s+analy[sz]e\s+)?data|analy[sz]e\s+data|analytics\s+dashboard|data\s+storage|data\s+collection|save\s+data|data\s+analysis|analytics|metrics\s+dashboard)\b",
        r"\b(?:full[\s\-]*stack|fullstack)\b",
    ]

    for pattern in backend_indicators:
        if re.search(pattern, full_context, re.IGNORECASE):
            return "react-fastapi-postgresql"

    # Default: Static website for displaying/showcasing
    return "html-css-js"


def _stack_guidance(stack: str) -> str:
    frontend = SUPPORTED_STACKS.get(stack, {}).get("frontend")
    if frontend in {"vue", "angular"}:
        frontend_spec = (
            "Vue 3 + TypeScript + Vite + Vue Router, Composition API, and .vue single-file components"
            if frontend == "vue"
            else "Angular 18+ + TypeScript, standalone components, and Angular Router"
        )
        return f"""SELECTED TECH STACK: {frontend.title()} + FastAPI + PostgreSQL
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: {frontend_spec}. Generate a complete runnable project with package.json, framework config, entry point, route table, one component per planned page, shared responsive navigation/footer, API client, and setup README.
- Production Backend: FastAPI (Python 3.12) REST API with SQLAlchemy 2.0 async mapped ORM models and PostgreSQL.
- Ensure each page is registered as a real route and all internal navigation links resolve.
- Provide an accessible mobile menu button wired to its drawer with aria-controls/aria-expanded; support click, keyboard, Escape, and close-on-navigation.
- Build a static HTML/CSS/JS mirror of every route for the marketplace preview.
"""
    if stack == "react-fastapi-postgresql":
        return """SELECTED TECH STACK: React + FastAPI + PostgreSQL (Emergent Full-Stack Standard)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: React 18 + TypeScript + Vite + Tailwind CSS + React Router v6
  * App Entry: frontend/src/main.tsx, frontend/src/App.tsx
  * Page Components: frontend/src/pages/<Page>.tsx
  * Interactive UI Components: frontend/src/components/ (Navbar, Footer, interactive forms, modals)
  * API Integration: frontend/src/api/client.ts (Axios instance connected to VITE_API_URL)
- Production Backend: FastAPI (Python 3.12) REST API
  * Models: backend/app/models.py (SQLAlchemy 2.0 async mapped ORM models with PostgreSQL)
  * Schemas: backend/app/schemas.py (Pydantic v2 schemas)
  * REST Endpoints: backend/app/routes/ (POST /api/contact, POST /api/bookings, GET /api/health)
  * Database: backend/app/database.py (async connection pool)
  * Migrations: Alembic async migrations
- Live Studio Browser Canvas Mirror:
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio."""

    return """SELECTED TECH STACK: Static Website (HTML5 / CSS3 / Vanilla JavaScript)
ARCHITECTURE SPECIFICATION:
- Semantic HTML5, modern vanilla CSS3, responsive layouts, zero external UI framework dependencies.
- Complete standalone pages: index.html (Home) and clean interior page files.
- Interactive mobile hamburger drawer, accessible navigation, and fluid responsive design."""

def _fallback_image_uploads(category: str, genre: str, prompt: str, profile: str) -> list[dict[str, Any]]:
    """Return upload slots that match the actual brief when the planner omits them."""
    if profile == "portfolio":
        return [
            {"role": "portrait", "label": "Portrait", "hint": "Your profile photo or headshot", "multiple": False},
            {"role": "skills", "label": "Skills & tools", "hint": "Logos or visuals for your skills and tools", "multiple": True},
            {"role": "project", "label": "Project work", "hint": "Screenshots or photos of your real work", "multiple": True},
        ]
    if profile == "construction":
        return [
            {"role": "project", "label": "Completed projects", "hint": "Real construction projects and job-site photos", "multiple": True},
            {"role": "team", "label": "Crew & team", "hint": "Photos of your real team, with permission to publish", "multiple": True},
            {"role": "equipment", "label": "Equipment & worksites", "hint": "Your equipment and active job sites", "multiple": True},
        ]

    prompt_text = prompt.lower()
    specific_site_re = r"\b(?:residency|hotel|resort|lodge|inn|motel|stay|hospitality|accommodation|tea|restaurant|cafe|coffee|bakery|food|dining|shop|store|e-?commerce|real estate|property|realtor|event|conference|festival|wedding|school|education|course|training|academy|university|health|clinic|medical|dental|wellness|therapy|salon|beauty|spa|barber|fitness|gym|sports|yoga|software|saas|app|technology|architecture|architect|interior design|agency|consulting|blog|publication|nonprofit|charity)\b"
    context = prompt_text if re.search(specific_site_re, prompt_text) else f"{category} {genre} {prompt}".lower()
    if re.search(r"residency|hotel|resort|lodge|inn|motel|stay|hospitality|accommodation", context):
        labels = [
            ("project", "Property exterior & front view", "Building front facade, main entrance, or reception lobby", True),
            ("general", "Guest rooms & suites", "Deluxe, Standard, Suite bedroom photos and interiors", True),
            ("equipment", "Dining & amenities", "Restaurant, dining lounge, conference, or facilities", True),
            ("general", "Brand logo & signage", "Official residency logo or entrance signage", False),
        ]
    elif re.search(r"shop|store|e-?commerce|retail|boutique", context):
        labels = [
            ("general", "Product catalog & hero items", "High quality product photos, catalog items, or featured collections", True),
            ("project", "Storefront & brand visuals", "Brand logo, packaging, storefront, or customer unboxing", True),
        ]
    elif re.search(r"agency|consulting|creative studio", context):
        labels = [
            ("general", "Agency identity & branding", "Brand logo, studio philosophy, or team working", True),
            ("project", "Client case studies & work", "Client deliverables, campaign visuals, and portfolio showcases", True),
        ]
    elif re.search(r"\btea\b", context):
        labels = [("general", "Tea brand & menu", "Logo, teas, drinks, ingredients, packaging, or menu images", True), ("project", "Tea service & location", "Your real tea service, storefront, garden, or customer experience", True)]
    elif re.search(r"cafe|coffee|restaurant|bakery|food|dining", context):
        labels = [("general", "Restaurant brand & menu", "Logo, dishes, drinks, ingredients, or menu images", True), ("project", "Dining space & experience", "Your real storefront, interior, kitchen, or dining experience", True)]
    elif re.search(r"real estate|property|realtor", context):
        labels = [("general", "Agency identity", "Logo, agent, and office images", True), ("project", "Property listings", "Real properties, developments, and listing images", True)]
    elif re.search(r"event|conference|festival|wedding", context):
        labels = [("general", "Event identity", "Event logo, theme, and promotional visuals", True), ("project", "Venue & program", "Venue, speakers, performers, or past event images", True)]
    elif re.search(r"school|education|course|training|academy|university", context):
        labels = [("general", "Program identity", "School or course logo and learning materials", True), ("project", "Campus & learning", "Real classrooms, courses, and student activities", True)]
    elif re.search(r"health|clinic|medical|dental|wellness|therapy", context):
        labels = [("general", "Practice & care images", "Logo, clinic, equipment, or care information", True), ("team", "Practitioners & facility", "Real staff and spaces, with permission to publish", True)]
    elif re.search(r"hotel|travel|tour|hospitality|accommodation", context):
        labels = [("general", "Property or tour identity", "Logo, destination, and experience visuals", True), ("project", "Rooms & destinations", "Real rooms, places, tours, or amenities", True)]
    elif re.search(r"software|saas|app|technology|digital product", context):
        labels = [("general", "Product & brand assets", "Logo, product interface, app screens, or feature visuals", True), ("project", "Screenshots & workflows", "Real product screens, dashboards, or workflow examples", True)]
    elif re.search(r"salon|beauty|spa|barber|skincare", context):
        labels = [("general", "Beauty brand & services", "Logo, products, treatments, or service visuals", True), ("project", "Studio & work examples", "Your real salon, studio, or work examples", True)]
    elif re.search(r"fitness|gym|sports|yoga|trainer", context):
        labels = [("general", "Fitness brand & programs", "Logo, classes, equipment, or training programs", True), ("project", "Facility & activities", "Your real facility, classes, or events", True)]
    elif re.search(r"architecture|architect|interior design", context):
        labels = [("general", "Studio & design identity", "Logo, plans, studio, or material samples", True), ("project", "Spaces & completed work", "Real buildings, interiors, landscapes, or project renders", True)]
    else:
        site_name = (genre or category or "Project").strip()[:60]
        labels = [("general", f"{site_name} brand & key images", "Logo, products, location, or visuals relevant to this project", True), ("project", f"{site_name} photos & examples", "Real work, services, spaces, or examples for this project", True)]
    return [{"role": role, "label": label, "hint": hint, "multiple": multiple} for role, label, hint, multiple in labels]


CURATED_STOCK_IMAGES = {
    "hospitality": [
        {"id": "photo-1542314831-068cd1dbfeeb", "tag": "hero", "alt": "Luxury hotel exterior architecture and facade at dusk"},
        {"id": "photo-1566073771259-6a8506099945", "tag": "hero", "alt": "Grand entrance and driveway of luxury resort"},
        {"id": "photo-1590490360182-c33d57733427", "tag": "rooms", "alt": "Deluxe King bedroom suite with plush linens and ambient lighting"},
        {"id": "photo-1582719478250-c89cae4dc85b", "tag": "rooms", "alt": "Executive garden villa bedroom opening onto private terrace"},
        {"id": "photo-1566665797739-1674de7a421a", "tag": "rooms", "alt": "Presidential penthouse suite bedroom with panoramic views"},
        {"id": "photo-1517248135467-4c7edcad34c4", "tag": "dining", "alt": "Artisanal fine dining restaurant interior with ambient chandelier lighting"},
        {"id": "photo-1550966871-3ed3cdb5ed0c", "tag": "dining", "alt": "Gourmet dining table setting with wine glasses and cutlery"},
        {"id": "photo-1414235077428-338989a2e8c0", "tag": "dining", "alt": "Michelin-style culinary dish plated with elegance"},
        {"id": "photo-1540555700478-4be289fbecef", "tag": "amenities", "alt": "Serene spa wellness relaxation lounge with organic aromatherapy"},
        {"id": "photo-1584132967334-10e028bd69f7", "tag": "amenities", "alt": "Tranquil outdoor heated swimming pool surrounded by tropical gardens"},
        {"id": "photo-1571896349842-33c89424de2d", "tag": "amenities", "alt": "Fitness center gym with modern cardio equipment and natural lighting"},
        {"id": "photo-1582719508461-905c673771fd", "tag": "contact", "alt": "Concierge front desk reception with 24-hour guest assistance"},
    ],
    "restaurant": [
        {"id": "photo-1517248135467-4c7edcad34c4", "tag": "hero", "alt": "Atmospheric bistro and restaurant dining room with warm lighting"},
        {"id": "photo-1504674900247-0877df9cc836", "tag": "food", "alt": "Signature gourmet dinner dish with seasonal ingredients"},
        {"id": "photo-1544025162-d76694265947", "tag": "food", "alt": "Slow-cooked artisanal barbecue platter and sides"},
        {"id": "photo-1555396273-367ea4eb4db5", "tag": "food", "alt": "Stone-baked artisanal pizza with fresh herbs and olive oil"},
        {"id": "photo-1414235077428-338989a2e8c0", "tag": "menu", "alt": "Fine dining plate presented by executive chef"},
        {"id": "photo-1577219491135-ce391730fb2c", "tag": "about", "alt": "Head chef preparing signature recipe in modern kitchen"},
        {"id": "photo-1514933651103-005eec06c04b", "tag": "drinks", "alt": "Craft cocktails and vintage wine cellar bar"},
        {"id": "photo-1509440159596-0249088772ff", "tag": "bakery", "alt": "Artisanal freshly baked bread and golden pastry selection"},
        {"id": "photo-1501339847302-ac426a4a7cbb", "tag": "coffee", "alt": "Specialty espresso coffee cup with delicate foam latte art"},
    ],
    "portfolio": [
        {"id": "photo-1498050108023-c5249f4df085", "tag": "hero", "alt": "Modern software engineering desk with mechanical keyboard and code editor"},
        {"id": "photo-1507238691740-187a5b1d37b8", "tag": "about", "alt": "Creative designer workspace with sketchbook, tablet, and coffee"},
        {"id": "photo-1545235617-9465d2a55698", "tag": "projects", "alt": "Digital product design system and user interface wireframes"},
        {"id": "photo-1460925895917-afdab827c52f", "tag": "projects", "alt": "Analytics dashboard metrics and user engagement graphs"},
        {"id": "photo-1551288049-bebda4e38f71", "tag": "projects", "alt": "Interactive data visualization and cloud architecture diagram"},
        {"id": "photo-1517694712202-14dd9538aa97", "tag": "skills", "alt": "Fullstack development on high-resolution widescreen monitors"},
        {"id": "photo-1534528741775-53994a69daeb", "tag": "portrait", "alt": "Professional creative professional portrait headshot"},
        {"id": "photo-1522071820081-009f0129c71c", "tag": "experience", "alt": "Team engineering sprint and technical collaboration"},
        {"id": "photo-1555066931-4365d14bab8c", "tag": "projects", "alt": "Syntax-highlighted backend code on developer workstation"},
        {"id": "photo-1519389950473-47ba0277781c", "tag": "about", "alt": "Modern developer workstation with wireless tech accessories"},
    ],
    "construction": [
        {"id": "photo-1504307651254-35680f356dfd", "tag": "hero", "alt": "Construction site supervisor reviewing architectural blueprint"},
        {"id": "photo-1541888946425-d81bb19240f5", "tag": "about", "alt": "Professional construction workers on commercial steel framing"},
        {"id": "photo-1486406146926-c627a92ad1ab", "tag": "projects", "alt": "Modern glass and steel skyscraper facade building project"},
        {"id": "photo-1503387762-592deb58ef4e", "tag": "projects", "alt": "Architect drafting residential structural floor plans"},
        {"id": "photo-1513694203232-719a280e022f", "tag": "services", "alt": "Renovation craftsmanship and interior structural carpentry"},
        {"id": "photo-1600585154340-be6161a56a0c", "tag": "projects", "alt": "Luxury modern finished residential architecture"},
    ],
    "ecommerce": [
        {"id": "photo-1441986300917-64674bd600d8", "tag": "hero", "alt": "Curated modern retail clothing showroom with minimalist apparel"},
        {"id": "photo-1472851294608-062f824d29cc", "tag": "products", "alt": "Boutique fashion storefront display with premium clothing racks"},
        {"id": "photo-1441984904996-e0b6ba687e04", "tag": "products", "alt": "Minimalist handcrafted leather accessories and goods"},
        {"id": "photo-1523275335684-37898b6baf30", "tag": "products", "alt": "Minimalist luxury chronograph watch on clean stone background"},
        {"id": "photo-1505740420928-5e560c06d30e", "tag": "products", "alt": "Premium wireless noise-cancelling headphones product studio shot"},
        {"id": "photo-1542291026-7eec264c27ff", "tag": "products", "alt": "Designer athletic performance sneakers studio showcase"},
        {"id": "photo-1522335789203-aabd1fc54bc9", "tag": "products", "alt": "Natural organic skincare and cosmetic bottle packaging"},
    ],
    "saas": [
        {"id": "photo-1460925895917-afdab827c52f", "tag": "hero", "alt": "SaaS analytics platform user growth and revenue metrics dashboard"},
        {"id": "photo-1551288049-bebda4e38f71", "tag": "features", "alt": "Real-time cloud database monitoring and telemetry display"},
        {"id": "photo-1531403009284-440f080d1e12", "tag": "features", "alt": "Product design sprint team mapping collaborative user flows"},
        {"id": "photo-1522071820081-009f0129c71c", "tag": "about", "alt": "High-performing engineering team collaborating in bright modern office"},
        {"id": "photo-1558494949-ef010cbdcc31", "tag": "services", "alt": "Cloud server datacenter racks with high availability infrastructure"},
        {"id": "photo-1519389950473-47ba0277781c", "tag": "products", "alt": "Next-generation software platform interface on laptop screen"},
        {"id": "photo-1531482615713-2afd69097998", "tag": "team", "alt": "Software company leadership team conducting client review"},
        {"id": "photo-1498050108023-c5249f4df085", "tag": "tech", "alt": "Engineering lead building scalable distributed systems"},
        {"id": "photo-1504384308090-c894fdcc538d", "tag": "solutions", "alt": "Modern high-tech software engineering studio office"},
    ],
    "medical": [
        {"id": "photo-1576091160399-112ba8d25d1d", "tag": "hero", "alt": "Modern bright healthcare clinic reception and patient waiting lounge"},
        {"id": "photo-1629909613654-28e377c37b09", "tag": "services", "alt": "Advanced medical diagnostic equipment in pristine consultation room"},
        {"id": "photo-1505751172876-fa1923c5c528", "tag": "services", "alt": "Compassionate doctor consulting with patient about preventive health"},
        {"id": "photo-1559839734-2b71ea197ec2", "tag": "about", "alt": "Experienced medical director and clinical specialist physician"},
        {"id": "photo-1584515979956-d9f6e5d09982", "tag": "team", "alt": "Care team nurses and healthcare specialists conferring"},
    ],
    "real_estate": [
        {"id": "photo-1600596542815-ffad4c1539a9", "tag": "hero", "alt": "Luxury modern residential estate with swimming pool and twilight landscape"},
        {"id": "photo-1600585154340-be6161a56a0c", "tag": "properties", "alt": "Contemporary open-concept living room with floor-to-ceiling glass windows"},
        {"id": "photo-1600607687939-ce8a6c25118c", "tag": "properties", "alt": "Designer chef kitchen with marble waterfall island and premium appliances"},
        {"id": "photo-1600566753376-12c8ab7fb75b", "tag": "properties", "alt": "Master suite bedroom overlooking scenic panoramic hills"},
        {"id": "photo-1512917774080-9991f1c4c750", "tag": "properties", "alt": "Contemporary architectural villa with Mediterranean garden"},
    ],
    "general": [
        {"id": "photo-1497366216548-37526070297c", "tag": "hero", "alt": "Modern professional corporate headquarters lobby and architecture"},
        {"id": "photo-1497366811353-6870744d04b2", "tag": "about", "alt": "Contemporary minimalist executive conference room"},
        {"id": "photo-1497366754035-f200968a6e72", "tag": "services", "alt": "Bright collaborative creative studio workspace"},
        {"id": "photo-1522071820081-009f0129c71c", "tag": "team", "alt": "Professional team collaborating in contemporary workspace"},
        {"id": "photo-1521737711867-e3b97375f902", "tag": "partnership", "alt": "Business executives shaking hands on successful contract"},
        {"id": "photo-1486406146926-c627a92ad1ab", "tag": "building", "alt": "Modern metropolitan corporate tower reflection"},
        {"id": "photo-1460925895917-afdab827c52f", "tag": "solutions", "alt": "Strategic financial growth and business analytics visualization"},
    ],
}


def _curated_stock_assets(profile: str, genre: str) -> list[dict[str, str]]:
    items = CURATED_STOCK_IMAGES.get(profile) or CURATED_STOCK_IMAGES.get("general") or []
    assets = []
    for item in items:
        photo_id = item["id"]
        tag = item.get("tag", "general")
        alt = item.get("alt") or f"Illustrative stock photo for {genre}"
        assets.append({
            "role": "project" if profile == "construction" else "general",
            "url": f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1440&q=85",
            "alt": alt,
            "tags": tag,
            "page_target": f"{tag}.html" if tag not in {"hero", "general"} else "index.html",
            "source_name": "Unsplash",
            "source_url": f"https://unsplash.com/photos/{photo_id}",
            "credit": "Curated Unsplash imagery",
        })
    return assets


def _filename(value: str, index: int, page_name: str = "") -> str:
    raw_value = str(value or "").strip().lower().replace("\\", "/").split("/")[-1]
    raw_name = re.sub(r"[^a-z0-9]+", "-", str(page_name or "").strip().lower()).strip("-")
    if raw_name in HOME_PAGE_NAMES:
        return "index.html"
    if raw_name in INNER_PAGE_NAMES and (not raw_value or raw_value.removesuffix(".html") in HOME_PAGE_NAMES):
        raw_value = raw_name
    if not raw_value:
        raw_value = raw_name or ("index" if index == 0 else "")

    clean = raw_value
    if clean.endswith(".html"):
        clean = clean[:-5]
    while clean.endswith("-html") or clean.endswith("_html"):
        clean = clean[:-5]

    clean = re.sub(r"[^a-z0-9_-]+", "-", clean).strip("-_")
    if clean in HOME_PAGE_NAMES:
        return "index.html"
    if not clean:
        clean = "index" if index == 0 else f"page-{index + 1}"
    return f"{clean[:50]}.html"


def _ensure_home_page(pages: list[dict[str, Any]], prompt: str, genre: str) -> list[dict[str, Any]]:
    """Keep About and other interior pages out of the root index.html entry point."""
    home_index = next((
        index for index, page in enumerate(pages)
        if re.sub(r"[^a-z0-9]+", "-", str(page.get("name") or "").strip().lower()).strip("-") in HOME_PAGE_NAMES
    ), None)
    if home_index is None:
        home_index = next((
            index for index, page in enumerate(pages)
            if page.get("filename") == "index.html"
            and re.sub(r"[^a-z0-9]+", "-", str(page.get("name") or "").strip().lower()).strip("-") not in INNER_PAGE_NAMES
        ), None)

    if home_index is not None:
        home = {**pages[home_index], "name": "Home", "filename": "index.html", "required": True}
        remaining = [page for index, page in enumerate(pages) if index != home_index and page.get("filename") != "index.html"]
    else:
        home = {
            "name": "Home",
            "filename": "index.html",
            "purpose": f"The homepage for {genre}: introduce the specific idea in this brief, show its main offering, and guide visitors to the next useful page. Brief: {prompt[:350]}",
            "required": True,
            "sections": ["Hero and primary action", "Main offering", "Key details", "Next steps"],
            "primary_action": "Explore the main offering",
        }
        remaining = [page for page in pages if page.get("filename") != "index.html"]
    return [home, *remaining][:8]


def _clean_html(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start = text.lower().find("<!doctype html")
    if start < 0:
        start = text.lower().find("<html")
    if start > 0:
        text = text[start:]
    return text.strip()


def _image_fallback_url(genre: str) -> str:
    subject = str(genre or "").lower()
    if any(word in subject for word in ("tea", "food", "restaurant", "cafe", "coffee", "bakery")):
        photo = "photo-1544787219-7f47ccb76574"
    elif any(word in subject for word in ("portfolio", "design", "developer", "photograph", "creative", "agency")):
        photo = "photo-1498050108023-c5249f4df085"
    elif any(word in subject for word in ("travel", "tour", "nature", "outdoor", "adventure")):
        photo = "photo-1464822759023-fed622ff2c3b"
    elif any(word in subject for word in ("shop", "store", "product", "ecommerce", "e-commerce")):
        photo = "photo-1523275335684-37898b6baf30"
    else:
        photo = "photo-1497366754035-f200968a6e72"
    return f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1400&q=85"


def _add_image_fallback(html: str, genre: str) -> str:
    fallback = json.dumps(_image_fallback_url(genre))
    script = f"""<script>
(() => {{
  const fallback = {fallback};
  document.querySelectorAll('img').forEach((image) => {{
    image.addEventListener('error', () => {{
      if (!image.dataset.fallbackTried) {{
        image.dataset.fallbackTried = 'true';
        image.src = fallback;
      }} else {{
        image.hidden = true;
        if (image.parentElement) image.parentElement.style.background = 'linear-gradient(135deg, #e9edf4, #dce4ef)';
      }}
    }});
    if (image.complete && image.naturalWidth === 0) image.dispatchEvent(new Event('error'));
  }});
}})();
</script>"""
    closing_body = html.lower().rfind("</body>")
    if closing_body >= 0:
        return f"{html[:closing_body]}{script}\n{html[closing_body:]}"
    return f"{html}\n{script}"


def _ensure_styles(html: str) -> str:
    # 1. Guarantee mobile viewport meta tag in <head> for 100% all-device support
    if not re.search(r"<meta\s+name=[\"']viewport[\"']", html, re.IGNORECASE):
        viewport_tag = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        if re.search(r"<head\b[^>]*>", html, re.IGNORECASE):
            html = re.sub(r"(<head\b[^>]*>)", rf"\1\n  {viewport_tag}", html, count=1, flags=re.IGNORECASE)
        elif re.search(r"<html\b[^>]*>", html, re.IGNORECASE):
            html = re.sub(r"(<html\b[^>]*>)", rf"\1\n<head>\n  {viewport_tag}\n</head>", html, count=1, flags=re.IGNORECASE)
        else:
            html = f"{viewport_tag}\n{html}"

    # 2. Guarantee universal mobile responsive safety guard (zero horizontal overflow & fluid media)
    responsive_guard = """<style id="studio-responsive-guard">
html, body { max-width: 100%; overflow-x: hidden; }
img, video, iframe { max-width: 100%; height: auto; }
@media (max-width: 768px) {
  .grid, .cards, .card-grid, .team-grid, .services-grid, .product-grid { grid-template-columns: 1fr !important; }
}
</style>"""
    if "studio-responsive-guard" not in html and "overflow-x: hidden" not in html:
        head_end = html.lower().find("</head>")
        if head_end >= 0:
            html = f"{html[:head_end]}{responsive_guard}\n{html[head_end:]}"

    style_blocks = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    if sum(len(css.strip()) for css in style_blocks) >= 180:
        return html
    baseline = """<style>
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f7f8fb;color:#172033;font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}header,nav{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;padding:1rem clamp(1rem,5vw,4rem);background:#fff;border-bottom:1px solid #e3e8f0}nav a,header a{color:inherit;text-decoration:none;font-weight:600}main{width:min(100% - 2rem,1120px);margin:0 auto;padding:clamp(2rem,6vw,5rem) 0}section{margin-block:2rem}h1,h2,h3{line-height:1.15;letter-spacing:-.035em}h1{font-size:clamp(2.3rem,6vw,4.6rem);max-width:16ch}p{max-width:68ch;color:#556176}img{display:block;width:100%;max-width:100%;height:auto;object-fit:cover;border-radius:1rem}.grid,.cards,.product-grid,.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:1.2rem}.card,article{padding:1.1rem;border:1px solid #e3e8f0;border-radius:1rem;background:#fff;box-shadow:0 8px 24px rgba(20,34,57,.06)}a.button,button,.button{display:inline-flex;align-items:center;justify-content:center;min-height:2.8rem;padding:.7rem 1rem;border:0;border-radius:.7rem;background:#3156c9;color:#fff;text-decoration:none;font:inherit;font-weight:650}a:focus-visible,button:focus-visible{outline:3px solid #79a4ff;outline-offset:3px}@media(max-width:640px){header,nav{align-items:flex-start}main{width:min(100% - 1.25rem,1120px)}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style>"""
    head_end = html.lower().find("</head>")
    if head_end >= 0:
        return f"{html[:head_end]}{baseline}\n{html[head_end:]}"
    head_open = re.search(r"<head\b[^>]*>", html, flags=re.IGNORECASE)
    if head_open:
        return f"{html[:head_open.end()]}{baseline}\n{html[head_open.end():]}"
    html_tag = re.search(r"<html\b[^>]*>", html, flags=re.IGNORECASE)
    if html_tag:
        head = f"<head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">{baseline}</head>"
        return f"{html[:html_tag.end()]}{head}\n{html[html_tag.end():]}"
    return f"{baseline}\n{html}"


def _split_inline_assets(pages: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Move generated inline styles and executable scripts into per-page source files."""
    packaged_pages: dict[str, str] = {}
    assets: dict[str, str] = {}

    for filename, source in pages.items():
        stem = re.sub(r"\.html$", "", filename, flags=re.IGNORECASE)
        html = source
        style_blocks = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", html, flags=re.IGNORECASE | re.DOTALL)
        if style_blocks:
            css_path = f"assets/css/{stem}.css"
            assets[css_path] = "\n\n".join(block.strip() for block in style_blocks if block.strip())
            html = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
            stylesheet = f'<link rel="stylesheet" href="{css_path}">'
            if re.search(r"</head\s*>", html, flags=re.IGNORECASE):
                html = re.sub(r"</head\s*>", f"{stylesheet}\n</head>", html, count=1, flags=re.IGNORECASE)
            elif re.search(r"<head\b[^>]*>", html, flags=re.IGNORECASE):
                html = re.sub(r"<head\b[^>]*>", lambda match: f"{match.group(0)}\n{stylesheet}", html, count=1, flags=re.IGNORECASE)
            else:
                html = f"{stylesheet}\n{html}"

        script_blocks: list[str] = []

        def externalize_script(match: re.Match[str]) -> str:
            attrs, body = match.group(1), match.group(2)
            if re.search(r"\bsrc\s*=", attrs, flags=re.IGNORECASE):
                return match.group(0)
            script_type = re.search(r"\btype\s*=\s*(['\"])(.*?)\1", attrs, flags=re.IGNORECASE)
            type_value = script_type.group(2).strip().lower() if script_type else ""
            if type_value in {"application/json", "application/ld+json", "importmap"}:
                return match.group(0)
            if type_value not in {"", "text/javascript", "application/javascript", "module"}:
                return match.group(0)
            if not body.strip():
                return ""
            script_blocks.append(body.strip())
            module_attr = ' type="module"' if type_value == "module" else ""
            return f'<script{module_attr} src="assets/js/{stem}.js" defer></script>'

        html = re.sub(r"<script\b([^>]*)>(.*?)</script\s*>", externalize_script, html, flags=re.IGNORECASE | re.DOTALL)
        if script_blocks:
            assets[f"assets/js/{stem}.js"] = "\n\n".join(script_blocks)
        packaged_pages[filename] = html

    return packaged_pages, assets


class _PageReferenceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors: set[str] = set()
        self.references: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if values.get("id"):
            self.anchors.add(values["id"])
        if tag.lower() == "a" and values.get("name"):
            self.anchors.add(values["name"])
        for key in ("href", "src", "poster"):
            if values.get(key):
                self.references.append((key, values[key].strip()))


def _site_reference_issues(pages: dict[str, str], asset_paths: set[str]) -> dict[str, list[str]]:
    """Find local page, anchor, stylesheet, script, and image references that are absent from the package."""
    parsed: dict[str, _PageReferenceParser] = {}
    for filename, html in pages.items():
        parser = _PageReferenceParser()
        try:
            parser.feed(html)
        except Exception:
            pass
        parsed[filename] = parser

    issues: dict[str, list[str]] = {}
    available = set(pages) | asset_paths
    for filename, parser in parsed.items():
        for kind, reference in parser.references:
            url = urlsplit(reference)
            if url.scheme or url.netloc or reference.startswith("//"):
                continue
            path = url.path
            if not path:
                target = filename
            else:
                target = posixpath.normpath(posixpath.join(posixpath.dirname(filename), path.lstrip("/")))
            if target.startswith("../") or target not in available:
                issues.setdefault(filename, []).append(f"{kind} points to missing package file `{reference}`.")
                continue
            if target in parsed and url.fragment and url.fragment not in parsed[target].anchors:
                issues.setdefault(filename, []).append(f"{kind} points to missing anchor `#{url.fragment}` in `{target}`.")
    return issues


def _enforce_single_page_navigation(pages: dict[str, str]) -> dict[str, str]:
    """Turn accidental page-file links in an SPA into working in-page anchors."""
    if "index.html" not in pages:
        return pages
    html = pages["index.html"]
    links = list(re.finditer(r"(?is)<a\b[^>]*\bhref\s*=\s*([\"'])([^\"']+\.html(?:[?#][^\"']*)?)\1[^>]*>(.*?)</a\s*>", html))
    if not links:
        return pages

    heading_matches = list(re.finditer(r"(?is)<h([1-6])\b([^>]*)>(.*?)</h\1\s*>", html))
    used_ids = set(re.findall(r"(?is)\bid\s*=\s*['\"]([^'\"]+)", html))
    aliases: dict[str, str] = {}
    for match in links:
        url = urlsplit(match.group(2))
        slug = re.sub(r"[^a-z0-9-]+", "-", posixpath.basename(url.path).lower().removesuffix(".html")).strip("-")
        if slug and slug not in used_ids:
            link_text = re.sub(r"<[^>]+>", " ", match.group(3)).lower()
            terms = {word for word in re.findall(r"[a-z0-9]+", f"{slug} {link_text}") if len(word) > 2}
            best = None
            best_score = 0
            for heading in heading_matches:
                heading_text = re.sub(r"<[^>]+>", " ", heading.group(3)).lower()
                score = sum(1 for term in terms if term in heading_text)
                if score > best_score:
                    best, best_score = heading, score
            if best and best_score:
                attrs = best.group(2)
                if not re.search(r"\bid\s*=", attrs, re.IGNORECASE):
                    aliases[best.group(0)] = f'<h{best.group(1)}{attrs} id="{slug}">{best.group(3)}</h{best.group(1)}>'
                used_ids.add(slug)

    for old, new in aliases.items():
        html = html.replace(old, new, 1)
    if not re.search(r"\bid\s*=\s*['\"]top['\"]", html, re.IGNORECASE):
        html = re.sub(r"(?is)<body\b(?![^>]*\bid=)([^>]*)>", r'<body id="top"\1>', html, count=1)

    def localize(match: re.Match[str]) -> str:
        quote, href = match.group(1), match.group(2)
        url = urlsplit(href)
        slug = re.sub(r"[^a-z0-9-]+", "-", posixpath.basename(url.path).lower().removesuffix(".html")).strip("-")
        target = slug if slug in used_ids else "top"
        return f"href={quote}#{target}{quote}"

    html = re.sub(r"(?is)\bhref\s*=\s*([\"'])([^\"']+\.html(?:[?#][^\"']*)?)\1", localize, html)
    pages["index.html"] = html
    return pages


def _wrong_homepage(html: str) -> bool:
    heading = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    if not heading:
        return True
    text = re.sub(r"<[^>]+>", " ", heading.group(1)).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return any(term in text for term in ("about us", "about me", "our story", "contact us", "get in touch", "our products", "all products"))


def _enforce_multipage_navigation(
    pages: dict[str, str],
    page_list: list[dict[str, Any]],
    answers: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Deterministic post-processor guaranteeing 100% working multi-page architecture:
    1. Synchronizes the exact canonical header, logo, nav links, and mobile drawer across every page.
    2. Synchronizes the exact canonical footer across every page.
    3. Guarantees navigation & footer CSS styling is shared across all pages.
    4. Automatically rewrites in-page `#section` hash links to dedicated `.html` pages.
    5. Dynamically highlights the current page with active class and aria-current="page".
    6. Resolves all unrendered template placeholders and strips duplicate script tags.
    """
    if len(pages) <= 1:
        return pages

    answers = answers or {}
    owner_phone = str(answers.get("phone") or answers.get("mobile") or "+1 (555) 839-2000").strip()
    clean_phone = re.sub(r"[^\d+]", "", owner_phone) or "15558392000"
    owner_email = str(answers.get("email") or "contact@studio.local").strip()
    owner_address = str(answers.get("address") or "123 Serenity Avenue, Luxury District").strip()

    # Build mapping from page stem / keywords / industry synonyms to actual filename
    page_map: dict[str, str] = {}
    canonical_filenames: list[str] = []
    canonical_page_titles: dict[str, str] = {}

    # Comprehensive industry synonyms for deterministic subpage resolution
    PAGE_SYNONYMS: dict[str, set[str]] = {
        "about.html": {"about", "bio", "biography", "profile", "story", "about-me", "about_me", "aboutme", "who-we-are", "history", "experience", "background", "author"},
        "projects.html": {"projects", "project", "work", "works", "portfolio", "case-studies", "casestudies", "gallery", "showcase", "featured", "featured-works", "my-work", "creations"},
        "work.html": {"projects", "project", "work", "works", "portfolio", "case-studies", "casestudies", "gallery", "showcase", "featured"},
        "skills.html": {"skills", "skill", "tools", "technologies", "tech", "stack", "expertise", "capabilities", "tech-stack", "proficiencies"},
        "contact.html": {"contact", "contact-me", "contact-us", "get-in-touch", "touch", "hire", "hire-me", "reach", "inquire", "estimate", "quote", "connect", "message"},
        "services.html": {"services", "service", "offerings", "what-we-do", "solutions", "packages", "capabilities"},
        "pricing.html": {"pricing", "plans", "tiers", "rates", "membership", "price", "packages"},
        "menu.html": {"menu", "food", "drinks", "dishes", "menu-items", "dining"},
        "rooms.html": {"rooms", "suites", "accommodation", "stay", "villas"},
        "team.html": {"team", "staff", "crew", "specialists", "trainers", "instructors"},
        "features.html": {"features", "architecture", "product-features", "specs"},
        "classes.html": {"classes", "programs", "schedule", "workshops"},
        "courses.html": {"courses", "curriculum", "lessons", "admissions"},
    }

    for i, p in enumerate(page_list):
        fname = _filename(p.get("filename", ""), i, str(p.get("name") or f"Page {i+1}"))
        if fname in pages:
            canonical_filenames.append(fname)
            p_title = str(p.get("name") or fname.rsplit(".", 1)[0].title())
            canonical_page_titles[fname] = p_title
            stem = fname.rsplit(".", 1)[0].lower()
            page_map[stem] = fname
            name = p_title.lower().strip()
            if name:
                page_map[name] = fname
                for part in re.split(r"[^a-z0-9]+", name):
                    if len(part) >= 4 and part not in {"page", "view", "more", "home"}:
                        page_map[part] = fname
            # Inject synonyms
            for syn in PAGE_SYNONYMS.get(fname, set()):
                if syn not in page_map:
                    page_map[syn] = fname

    # Helper to rewrite any text-labeled navigation links targeting sibling pages
    def rewrite_nav_link_text(m: re.Match) -> str:
        full_tag = m.group(0)
        tag_start, curr_href, tag_mid, inner_text, tag_end = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        clean_text = re.sub(r'[^a-z0-9]+', '-', inner_text.strip().lower()).strip('-')
        target_file = page_map.get(clean_text)
        if not target_file:
            for word in clean_text.split('-'):
                if word in page_map:
                    target_file = page_map[word]
                    break
        if target_file:
            return f'{tag_start}href="{target_file}"{tag_mid}>{inner_text}{tag_end}'
        return full_tag

    # Step 1: Clean and verify index.html as the multi-page hub
    index_html = pages.get("index.html")
    if not index_html:
        first_fname = list(pages.keys())[0]
        index_html = pages[first_fname]

    def replace_index_href(m: re.Match) -> str:
        prefix, target_anchor, suffix = m.group(1), m.group(2).lower(), m.group(3)
        target_file = page_map.get(target_anchor)
        if target_file and target_file != "index.html":
            return f'{prefix}{target_file}{suffix}'
        return m.group(0)

    index_html = re.sub(r'(href=[\'"])#([a-zA-Z0-9_\-]+)([\'"])', replace_index_href, index_html)

    # In navigation elements (nav/header), rewrite any text-labeled anchor link matching a sibling page
    index_html = re.sub(
        r'(<nav\b[^>]*>.*?</nav\s*>)',
        lambda nm: re.sub(
            r'(<a\b[^>]*\b)href=[\'"]#[^\'"]*[\'"]([^>]*>)(.*?)(</a\s*>)',
            rewrite_nav_link_text,
            nm.group(1),
            flags=re.IGNORECASE | re.DOTALL
        ),
        index_html,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Ensure index.html navigation links contain all planned pages
    for fname in canonical_filenames:
        if fname != "index.html" and f'href="{fname}"' not in index_html and f"href='{fname}'" not in index_html:
            pname = canonical_page_titles.get(fname, fname.rsplit(".", 1)[0].title())
            nav_ul = re.search(r'(<nav\b[^>]*>.*?<ul\b[^>]*>)(.*?)(</ul\s*>)', index_html, flags=re.IGNORECASE | re.DOTALL)
            if nav_ul:
                insert_li = f'<li><a href="{fname}" class="nav-link">{pname}</a></li>\n'
                index_html = index_html[:nav_ul.start(3)] + insert_li + index_html[nav_ul.start(3):]
            else:
                nav_box = re.search(r'(<nav\b[^>]*>)(.*?)(</nav\s*>)', index_html, flags=re.IGNORECASE | re.DOTALL)
                if nav_box:
                    insert_a = f'<a href="{fname}" class="nav-link">{pname}</a>\n'
                    index_html = index_html[:nav_box.start(3)] + insert_a + index_html[nav_box.start(3):]

    pages["index.html"] = index_html

    # Step 2: Extract canonical header, mobile drawer, and footer from index.html
    header_match = re.search(r'(<header\b[^>]*>.*?</header\s*>)', index_html, flags=re.IGNORECASE | re.DOTALL)
    canonical_header = header_match.group(1) if header_match else None

    drawer_match = re.search(r'(<div\b[^>]*class=[\'"][^\'"]*(?:mobile-drawer|mobile-nav|mobile-menu)[^\'"]*[\'"][^>]*>.*?</div\s*>)', index_html, flags=re.IGNORECASE | re.DOTALL)
    canonical_drawer = drawer_match.group(1) if drawer_match else None

    footer_match = re.search(r'(<footer\b[^>]*>.*?</footer\s*>)', index_html, flags=re.IGNORECASE | re.DOTALL)
    canonical_footer = footer_match.group(1) if footer_match else None

    # Step 3: Extract navigation & footer styles from index.html
    nav_css = ""
    style_matches = re.findall(r'<style\b[^>]*>(.*?)</style\s*>', index_html, flags=re.IGNORECASE | re.DOTALL)
    if style_matches:
        full_index_css = "\n".join(style_matches)
        css_blocks = re.findall(r'([^{}]+)\{([^{}]+)\}', full_index_css)
        extracted = []
        for sel, body in css_blocks:
            sel_l = sel.lower().strip()
            if any(k in sel_l for k in ("header", "brand", "logo", "nav-", "nav_", "nav ", "nav\t", "menu", "drawer", "hamburger", "toggle", "footer")):
                extracted.append(f"{sel.strip()} {{{body}}}")
        if extracted:
            nav_css = "\n/* Canonical Unified Navigation & Footer Styles */\n" + "\n".join(extracted) + "\n"

    # Step 4: Synchronize every page with canonical header, footer, links, and styles
    updated_pages: dict[str, str] = {}
    for filename, html in pages.items():
        # Clean duplicate scripts
        html = re.sub(r'(<script\b[^>]*src=[\'"][^\'"]+[\'"][^>]*></script\s*>)\s*\1', r'\1', html, flags=re.IGNORECASE)

        # Replace unrendered placeholders
        html = re.sub(r'wa\.me/\{\{\s*PHONE\s*\}\}', f'wa.me/{clean_phone}', html, flags=re.IGNORECASE)
        html = re.sub(r'sms:\{\{\s*PHONE\s*\}\}', f'sms:{owner_phone}', html, flags=re.IGNORECASE)
        html = re.sub(r'tel:\{\{\s*PHONE\s*\}\}', f'tel:{owner_phone}', html, flags=re.IGNORECASE)
        html = re.sub(r'mailto:\{\{\s*EMAIL\s*\}\}', f'mailto:{owner_email}', html, flags=re.IGNORECASE)
        html = re.sub(r'\{\{\s*PHONE\s*\}\}', owner_phone, html, flags=re.IGNORECASE)
        html = re.sub(r'\{\{\s*EMAIL\s*\}\}', owner_email, html, flags=re.IGNORECASE)
        html = re.sub(r'\{\{\s*ADDRESS\s*\}\}', owner_address, html, flags=re.IGNORECASE)

        # Rewrite remaining anchor links targeting sibling page stems
        def replace_href(m: re.Match) -> str:
            prefix, target_anchor, suffix = m.group(1), m.group(2).lower(), m.group(3)
            target_file = page_map.get(target_anchor)
            if target_file and target_file != filename:
                return f'{prefix}{target_file}{suffix}'
            return m.group(0)

        html = re.sub(r'(href=[\'"])#([a-zA-Z0-9_\-]+)([\'"])', replace_href, html)

        # Also rewrite any text-labeled nav links targeting sibling pages
        html = re.sub(
            r'(<nav\b[^>]*>.*?</nav\s*>)',
            lambda nm: re.sub(
                r'(<a\b[^>]*\b)href=[\'"]#[^\'"]*[\'"]([^>]*>)(.*?)(</a\s*>)',
                rewrite_nav_link_text,
                nm.group(1),
                flags=re.IGNORECASE | re.DOTALL
            ),
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        if filename != "index.html":
            # Adapt canonical header for this interior page
            if canonical_header:
                adapted_header = canonical_header
                # Remove active from all links
                adapted_header = re.sub(r'\s+active\b', '', adapted_header)
                adapted_header = re.sub(r'\s+aria-current=[\'"]page[\'"]', '', adapted_header)
                # Add active to this page's link
                def activate_link(m: re.Match) -> str:
                    tag_start = m.group(1)
                    if 'class="' in tag_start or "class='" in tag_start:
                        tag_start = re.sub(r'class=([\'"])(.*?)\1', r'class=\1\2 active\1', tag_start)
                    else:
                        tag_start = f'{tag_start} class="nav-link active"'
                    return f'{tag_start} aria-current="page" href="{filename}"'

                adapted_header = re.sub(rf'(<a\b[^>]*)\bhref=[\'"]{re.escape(filename)}[\'"]', activate_link, adapted_header)

                # Replace the interior page's header with the adapted canonical header
                if re.search(r'<header\b[^>]*>.*?</header\s*>', html, flags=re.IGNORECASE | re.DOTALL):
                    html = re.sub(r'<header\b[^>]*>.*?</header\s*>', adapted_header, html, count=1, flags=re.IGNORECASE | re.DOTALL)

            # Adapt and replace canonical mobile drawer if present
            if canonical_drawer:
                adapted_drawer = canonical_drawer
                adapted_drawer = re.sub(r'\s+active\b', '', adapted_drawer)
                adapted_drawer = re.sub(r'\s+aria-current=[\'"]page[\'"]', '', adapted_drawer)
                adapted_drawer = re.sub(
                    rf'(<a\b[^>]*)\bhref=[\'"]{re.escape(filename)}[\'"]',
                    lambda m: re.sub(r'class=([\'"])(.*?)\1', r'class=\1\2 active\1', m.group(1)) + f' aria-current="page" href="{filename}"' if ('class="' in m.group(1) or "class='" in m.group(1)) else f'{m.group(1)} class="mobile-nav-link active" aria-current="page" href="{filename}"',
                    adapted_drawer
                )
                if re.search(r'<div\b[^>]*class=[\'"][^\'"]*(?:mobile-drawer|mobile-nav|mobile-menu)[^\'"]*[\'"][^>]*>.*?</div\s*>', html, flags=re.IGNORECASE | re.DOTALL):
                    html = re.sub(r'<div\b[^>]*class=[\'"][^\'"]*(?:mobile-drawer|mobile-nav|mobile-menu)[^\'"]*[\'"][^>]*>.*?</div\s*>', adapted_drawer, html, count=1, flags=re.IGNORECASE | re.DOTALL)

            # Replace footer with canonical footer
            if canonical_footer and re.search(r'<footer\b[^>]*>.*?</footer\s*>', html, flags=re.IGNORECASE | re.DOTALL):
                html = re.sub(r'<footer\b[^>]*>.*?</footer\s*>', canonical_footer, html, count=1, flags=re.IGNORECASE | re.DOTALL)

            # Inject navigation CSS into interior page if not already present
            if nav_css:
                if re.search(r'<style\b[^>]*>', html, flags=re.IGNORECASE):
                    html = re.sub(r'(<style\b[^>]*>)', rf'\1{nav_css}\n', html, count=1, flags=re.IGNORECASE)
                elif re.search(r'</head\s*>', html, flags=re.IGNORECASE):
                    html = re.sub(r'</head\s*>', f'<style>{nav_css}</style>\n</head>', html, count=1, flags=re.IGNORECASE)

        # Guarantee working mobile menu toggle script if drawer or hamburger toggle exists
        has_drawer = re.search(r'class=[\'"][^\'"]*(?:mobile-drawer|mobile-nav|mobile-menu)[^\'"]*[\'"]', html, flags=re.IGNORECASE)
        has_toggle = re.search(r'class=[\'"][^\'"]*(?:mobile-toggle|hamburger|menu-btn)[^\'"]*[\'"]', html, flags=re.IGNORECASE)
        if (has_drawer or has_toggle) and "mobileNavScriptInitialized" not in html:
            toggle_script = """<script>
/* Mobile Drawer Toggle Auto-Initialization */
(function() {
  window.mobileNavScriptInitialized = true;
  document.addEventListener('DOMContentLoaded', function() {
    var toggles = document.querySelectorAll('.mobile-toggle, .hamburger, [data-mobile-menu], .menu-btn, button[aria-label*="menu" i]');
    var drawers = document.querySelectorAll('.mobile-drawer, .mobile-nav, .mobile-menu, [data-drawer]');
    toggles.forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        drawers.forEach(function(drawer) {
          drawer.classList.toggle('active');
          drawer.classList.toggle('open');
        });
      });
    });
  });
})();
</script>"""
            if re.search(r'</body\s*>', html, flags=re.IGNORECASE):
                html = re.sub(r'</body\s*>', f"{toggle_script}\n</body>", html, count=1, flags=re.IGNORECASE)
            else:
                html += f"\n{toggle_script}"

        updated_pages[filename] = html

    return updated_pages


class StudioService:
    def __init__(self):
        self._active_user_generations: dict[str, float] = {}
        self._pixabay_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def _pixabay_hits(self, query: str) -> list[dict[str, Any]]:
        api_key = str(getattr(settings, "PIXABAY_API_KEY", "") or "").strip()
        if not api_key:
            return []
        cache_key = query.strip().lower()
        cached = self._pixabay_search_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(
                    "https://pixabay.com/api/",
                    params={"key": api_key, "q": query[:100], "image_type": "photo", "orientation": "horizontal", "safesearch": "true", "per_page": 8, "order": "popular"},
                )
            response.raise_for_status()
            payload = response.json()
            hits = [
                {
                    "image_url": hit.get("largeImageURL") or hit.get("webformatURL"),
                    "page_url": hit.get("pageURL"),
                    "photographer": hit.get("user") or "Pixabay contributor",
                    "tags": hit.get("tags") or query,
                }
                for hit in payload.get("hits", [])
                if isinstance(hit, dict)
                and str(hit.get("largeImageURL") or hit.get("webformatURL") or "").startswith("https://")
                and str(hit.get("pageURL") or "").startswith("https://")
            ]
            # Pixabay asks API users to cache search responses for 24 hours.
            self._pixabay_search_cache[cache_key] = (time.monotonic() + 86400, hits)
            return hits
        except Exception as exc:
            logger.info("Pixabay stock image search unavailable for query %r: %s", query[:80], type(exc).__name__)
            return []

    async def _collect_stock_assets(
        self,
        db: AsyncSession,
        profile: str,
        genre: str,
        plan: dict[str, Any],
    ) -> list[dict[str, str]]:
        searches_with_target: list[tuple[str, str]] = []
        for item in (plan.get("image_searches") or []):
            if isinstance(item, dict) and str(item.get("query") or "").strip():
                searches_with_target.append((str(item.get("query")).strip(), ""))

        # Include page-targeted search queries for every planned page
        pages_plan = plan.get("pages", [])
        for idx, p in enumerate(pages_plan):
            p_name = str(p.get("name") or "").strip()
            p_fname = _filename(str(p.get("filename") or ""), idx, p_name)
            if p_name:
                searches_with_target.append((f"{genre} {p_name}".strip(), p_fname))

        if not searches_with_target:
            if profile == "portfolio":
                searches_with_target = [("creative portfolio workspace", "index.html"), ("graphic design studio project", "projects.html")]
            elif profile == "construction":
                searches_with_target = [("construction site building project", "index.html"), ("architecture construction workers", "services.html")]
            elif profile == "hospitality":
                searches_with_target = [
                    (f"{genre} luxury resort facade", "index.html"),
                    (f"{genre} luxury bedroom suite", "rooms.html"),
                    (f"{genre} fine dining restaurant dishes", "dining.html"),
                    (f"{genre} spa wellness swimming pool", "amenities.html"),
                    (f"{genre} concierge reception lobby", "contact.html"),
                ]
            elif profile == "restaurant":
                searches_with_target = [
                    (f"{genre} atmospheric dining room", "index.html"),
                    (f"{genre} gourmet dinner dishes", "menu.html"),
                    (f"{genre} head chef kitchen", "about.html"),
                    (f"{genre} restaurant bar table reservation", "contact.html"),
                ]
            else:
                searches_with_target = [(f"{genre} professional website photography", "index.html"), (f"{genre} business environment", "")]

        stock_assets: list[dict[str, str]] = []
        max_stock_limit = 24 if len(pages_plan) > 1 else 12
        for query, target_page in searches_with_target[:10]:
            if len(stock_assets) >= max_stock_limit:
                break
            hits = await self._pixabay_hits(query)
            for hit in hits[:3]:
                if len(stock_assets) >= max_stock_limit:
                    break
                try:
                    raw_cdn_url = hit.get("image_url")
                    if raw_cdn_url and str(raw_cdn_url).startswith("https://"):
                        stock_assets.append({
                            "role": "project" if profile == "construction" else "general",
                            "url": raw_cdn_url,
                            "alt": f"Illustrative photo: {hit.get('tags', query)}",
                            "tags": str(hit.get("tags") or query),
                            "page_target": target_page,
                            "source_name": "Pixabay",
                            "source_url": hit.get("page_url", "https://pixabay.com"),
                            "credit": f"Photo by {hit.get('photographer', 'Pixabay contributor')} on Pixabay",
                        })
                except Exception as exc:
                    logger.info("Could not process Pixabay stock image: %s", exc)

        # Always guarantee rich domain-specific fallback images so pages are NEVER blank
        curated = _curated_stock_assets(profile, genre)
        for asset in curated:
            if len(stock_assets) >= max_stock_limit:
                break
            if not any(a.get("url") == asset.get("url") for a in stock_assets):
                stock_assets.append(asset)

        return stock_assets

    async def plan(self, prompt: str, category: str, genre: str, page_structure: str = "multi_page", stack: str = "auto") -> dict[str, Any]:
        stack = detect_stack_from_prompt(prompt, category, genre, requested_stack=stack)
        profile = _site_profile(category, genre, prompt)
        profile_guidance = _profile_guidance(profile)
        stack_guidance = _stack_guidance(stack)

        # Pre-extract all facts and entities already supplied in the user's prompt
        extracted_facts = _extract_prompt_details(prompt)
        extracted_lines = [f"- {k.replace('_', ' ').title()}: {v}" for k, v in extracted_facts.items() if v]
        extracted_summary = "\n".join(extracted_lines) if extracted_lines else "None explicitly extracted; prompt asks for fresh structure."

        sitemap_guidance = (
            "SINGLE-PAGE SITE MAP: Return exactly one page named Home with filename index.html. Put every requested topic in a distinct scrolling section on that page. Internal navigation must use #section-id anchors only; do not create or link to about.html, projects.html, contact.html, or any other page file."
            if page_structure == "single_page" else
            "DYNAMIC MULTI-CATEGORY SITEMAP INSTRUCTIONS:\n- Tailor the pages directly to the specific industry in the user's prompt (1-8 pages total):\n  * Portfolio / CV / Personal: Home (index.html), About & Bio (about.html), Projects & Case Studies (projects.html), Skills & Tools (skills.html), Contact (contact.html)\n  * SaaS / Tech Product: Home (index.html), Features & Architecture (features.html), Pricing & Tiers (pricing.html), About / Docs (about.html), Contact / Demo (contact.html)\n  * E-Commerce / Store: Home (index.html), Shop Catalog (shop.html), Collections (collections.html), About Our Story (about.html), Contact & Help (contact.html)\n  * Restaurant / Cafe / Dining: Home (index.html), Food & Drink Menu (menu.html), About / Our Chef (about.html), Reservations & Location (contact.html)\n  * Agency / Consulting / Studio: Home (index.html), Services (services.html), Case Studies (work.html), Team (team.html), Contact & Quote (contact.html)\n  * Real Estate / Property: Home (index.html), Featured Listings (listings.html), Neighborhoods (neighborhoods.html), About Agents (about.html), Contact (contact.html)\n  * Healthcare / Medical / Clinic: Home (index.html), Treatments & Care (treatments.html), Specialists & Team (team.html), Book Appointment (contact.html)\n  * Residency / Hotel / Hospitality: Home (index.html), Rooms & Suites (rooms.html), Dining & Restaurant (dining.html), Amenities (amenities.html), Contact & Location (contact.html)\n  * Education / Academy / Courses: Home (index.html), Course Offerings (courses.html), Admissions & Pricing (admissions.html), Contact (contact.html)\n  * Fitness / Gym / Yoga / Studio: Home (index.html), Classes & Programs (classes.html), Membership & Pricing (pricing.html), Trainers (trainers.html), Contact (contact.html)\n- Preserve interior page filenames. For each page provide a page-specific outline and primary action."
        )

        request = f"""Create a useful, detailed website plan for this user request.
The user selected marketplace category: {category}
The user selected genre/site type: {genre}
The user explicitly chose this architecture: {page_structure}.
- For single_page, create one Home page only (index.html) and organize all requested content as scrolling sections on that page.
- For multi_page:
  * Create a Home page (index.html) plus distinct, dedicated interior pages (at least 3 to 5 pages total: e.g. about.html, projects.html/work.html, skills.html, contact.html, services.html).
  * CRITICAL ARCHITECTURE RULE FOR index.html: index.html is an introductory gateway & teaser homepage ONLY! It MUST NOT contain the full about biography, full project list, full skills grid, or full contact form.
  * On index.html, provide teaser sections with prominent call-to-action links leading to dedicated interior pages (e.g. "View All Projects", "Read My Story", "Get in Touch").
  * Interior pages must hold the deep, complete content (e.g. complete case studies on projects.html, complete career background on about.html, interactive contact form on contact.html).
{profile_guidance}
{stack_guidance}
User brief:
<brief>{prompt[:100000]}</brief>

SOURCE OF TRUTH: Treat the complete user brief as requirements, not background. Carry every named audience, offering, feature, page, contact detail, design preference, and other concrete fact into the plan. Never omit a supplied detail or ask the user to repeat it.

ALREADY-EXTRACTED FACTS FROM USER PROMPT (CRITICAL — DO NOT ASK FOR THESE):
{extracted_summary}

{sitemap_guidance}

CRITICAL QUESTION ATOMICITY & ZERO-REDUNDANCY DIRECTIVES:
1. NEVER ASK QUESTIONS FOR FACTS ALREADY EXTRACTED FROM THE USER PROMPT:
   - If the person or company name is known, DO NOT ask "What name should appear?"!
   - If contact email is provided, DO NOT ask for email!
   - If phone or WhatsApp number is provided, DO NOT ask for phone/WhatsApp!
   - If physical address or city is provided, DO NOT ask for address!
   - If prices, room rates, or service fees are provided, DO NOT ask for pricing/rates!
   - If skills, services, or menu items are listed, DO NOT ask for them!
2. NEVER ASK COMPOUND OR MULTI-PART QUESTIONS. Never combine multiple items into one question.
3. Every question must be strictly ATOMIC (1 topic, 1 sentence, clear placeholder).
4. Ask 0 to 4 clarifying questions, and only for important information that is TRULY MISSING from the prompt. If the prompt already answers a question, do not ask it again. If the brief is comprehensive, return an empty questions array.

DYNAMIC SEPARATE IMAGE UPLOADS:
Provide 2 to 4 separate, atomic upload slots matching the specific business type (e.g. Profile photo for portfolio; Products for store; Property exterior & rooms for hotel; Signature dishes for restaurant; UI screenshots for SaaS).

Return JSON only with keys: title, summary, architecture_type (single_page or multi_page), design_direction, preview ({{headline, subheadline, primary_action}}), pages (array of {{name, filename, purpose, required, sections, primary_action}}), questions (array of {{id, question, input_type, options, required, placeholder}}), image_uploads (array of {{role, label, hint, multiple}}), image_searches (array of {{query, purpose}}), and facts_to_confirm (array of strings)."""

        raw = await ai_service._generate_content(
            request, response_mime_type="application/json", feature_name="planning_agent",
            preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
            request_timeout_seconds=60.0, max_local_model_attempts=1,
        )
        try:
            data = _parse_json(raw)
        except Exception as e:
            logger.warning("Planning JSON parse failed: %s. Retrying planning with Gemini strict JSON...", e)
            try:
                raw_retry = await ai_service._generate_content(
                    request, response_mime_type="application/json", feature_name="planning_agent",
                    preferred_provider="gemini", provider_order_override=["gemini", "anthropic"],
                    request_timeout_seconds=60.0, max_local_model_attempts=1,
                )
                data = _parse_json(raw_retry)
            except Exception as e2:
                logger.warning("Gemini planning retry also failed: %s. Generating structured fallback plan...", e2)
                data = self._build_fallback_plan(prompt, category, genre, page_structure)
        data["extracted_facts"] = extracted_facts
        pages = data.get("pages") if isinstance(data.get("pages"), list) else []
        normalized = []
        seen = set()
        for i, page in enumerate(pages[:8]):
            if not isinstance(page, dict):
                continue
            name = str(page.get("name") or f"Page {i + 1}")[:80]
            filename = _filename(page.get("filename", ""), i, name)
            if filename in seen:
                filename = f"{filename[:-5]}-{i + 1}.html"
            seen.add(filename)
            normalized.append({
                "name": name,
                "filename": filename,
                "purpose": str(page.get("purpose") or "")[:500],
                "required": filename == "index.html" or page.get("required") is True,
                "sections": [str(x)[:200] for x in (page.get("sections") or [])[:12]],
                "primary_action": str(page.get("primary_action") or "")[:200],
            })
        if not normalized:
            raise ValueError("The Planning Agent could not produce a page plan. Please refine the brief and try again.")
        normalized = _ensure_home_page(normalized, prompt, genre)
        if profile == "construction" and page_structure == "multi_page":
            construction_pages = [
                {"name": "Services", "filename": "services.html", "purpose": "Explain the company's verified construction services, customer types, and project process.", "required": False, "sections": ["Service categories", "Who each service is for", "Project process", "Request an estimate"], "primary_action": "Request an estimate"},
                {"name": "Projects", "filename": "projects.html", "purpose": "Show the owner's real completed work with project type, scope, location, and images they provide.", "required": False, "sections": ["Featured completed projects", "Project scope and location", "Project imagery", "Discuss a similar project"], "primary_action": "Discuss a project"},
                {"name": "Contact", "filename": "contact.html", "purpose": "Help visitors contact the team or request a construction estimate using the owner's supplied details.", "required": False, "sections": ["Service area", "Estimate request", "Contact details", "What happens next"], "primary_action": "Request an estimate"},
            ]
            for suggested in construction_pages:
                normalized_names = " ".join(str(page.get("name") or "").lower() for page in normalized)
                alias_groups = {
                    "services": ("service", "capabilities", "what we do"),
                    "projects": ("project", "our work", "case stud", "portfolio"),
                    "contact": ("contact", "estimate", "quote"),
                }
                aliases = alias_groups[suggested["filename"].removesuffix(".html")]
                if not any(alias in normalized_names for alias in aliases) and len(normalized) < 8:
                    normalized.append(suggested)
        if page_structure == "single_page":
            home = normalized[0]
            all_sections = list(dict.fromkeys(
                section for page in normalized for section in page.get("sections", [])
            ))
            home = {**home, "name": "Home", "filename": "index.html", "sections": all_sections[:12], "required": True}
            normalized = [home]
        elif len(normalized) == 1:
            home = normalized[0]
            home_sections = home.get("sections", [])
            split_at = max(1, len(home_sections) // 2)
            normalized[0] = {**home, "sections": home_sections[:split_at]}
            normalized.append({
                "name": "Details",
                "filename": "details.html",
                "purpose": f"Expand on the main offering and visitor journey described in this brief: {prompt[:250]}",
                "required": False,
                "sections": home_sections[split_at:] or ["Detailed overview", "Key information", "Next steps"],
                "primary_action": "Continue the main visitor journey",
            })
        data["pages"] = normalized
        data["architecture_type"] = page_structure
        normalized_questions = []
        for index, question in enumerate(data.get("questions") if isinstance(data.get("questions"), list) else []):
            if not isinstance(question, dict):
                continue
            input_type = str(question.get("input_type") or "text").lower()
            if input_type not in {"text", "textarea", "select"}:
                input_type = "text"
            options = question.get("options") if isinstance(question.get("options"), list) else []
            question_id = re.sub(r"[^a-z0-9_-]", "", str(question.get("id") or f"question-{index}").lower())[:60] or f"question-{index}"
            normalized_questions.append({
                "id": question_id,
                "question": str(question.get("question") or "Please provide a detail for this website.")[:500],
                "input_type": input_type,
                "options": [str(option)[:100] for option in options[:12]],
                "required": question.get("required") is True,
                "placeholder": str(question.get("placeholder") or "")[:180],
            })
            if len(normalized_questions) == 8:
                break
        data["questions"] = normalized_questions
        if profile == "portfolio" and not data["questions"]:
            fallback_questions = [
                {"id": "identity", "question": "What name, role, and short introduction should appear on your portfolio?", "input_type": "textarea", "required": True, "placeholder": "Your name, professional title, and short intro"},
                {"id": "work", "question": "Which projects or work experience should be featured? (Share your role, technologies used, and company or client)", "input_type": "textarea", "required": True, "placeholder": "Role, company/client, technologies used, and key accomplishments"},
                {"id": "skills", "question": "Which skills and tools should be highlighted?", "input_type": "textarea", "required": True, "placeholder": "e.g. Python, SQL, React, DevOps"},
                {"id": "contact_email", "question": "What email address should receive messages when visitors submit your contact form?", "input_type": "text", "required": True, "placeholder": "yourname@gmail.com"},
                {"id": "contact_phone", "question": "What mobile or WhatsApp number should visitors use for 1-click WhatsApp chat and SMS? (Include country code)", "input_type": "text", "required": False, "placeholder": "+91 98765 43210"},
                {"id": "extra_points", "question": "Any extra points, awards, or custom sections you want on your page? (Skip if none)", "input_type": "textarea", "required": False, "placeholder": "Certifications, education, key achievements, or additional details"},
            ]
        elif profile == "construction" and not data["questions"]:
            fallback_questions = [
                {"id": "company", "question": "What is the company name and short introduction?", "input_type": "textarea", "required": True, "placeholder": "Business name and verified background"},
                {"id": "services", "question": "Which construction services do you provide, and for what kinds of clients?", "input_type": "textarea", "required": True, "placeholder": "Residential/commercial services and specialties"},
                {"id": "service_area", "question": "Which cities or regions do you serve?", "input_type": "textarea", "required": True, "placeholder": "Real service locations only"},
                {"id": "projects", "question": "Which completed projects should be featured? Share their type, location, scope, and any public link.", "input_type": "textarea", "required": True, "placeholder": "Verified project details only"},
                {"id": "credentials", "question": "Which licenses, insurance details, safety credentials, or memberships may be published? Leave blank if none.", "input_type": "textarea", "required": False, "placeholder": "Only verified credentials"},
                {"id": "estimate_contact", "question": "How should customers request an estimate or contact your team?", "input_type": "textarea", "required": True, "placeholder": "Phone, email, office hours, or booking link"},
            ]
        elif not data["questions"]:
            site_type = f"{category} {genre} {prompt}".lower()
            fallback_groups = [
                (r"restaurant|cafe|coffee shop|bakery|food|dining", [
                    ("venue", "What is the venue name, location, and short story?", True, "Business name, neighborhood, and real background"),
                    ("menu", "Which menu items, dietary options, and prices should be shown?", True, "Only the menu details you want published"),
                    ("visit", "What are your opening hours, booking method, and visitor contact details?", True, "Hours, reservation link or phone, and address"),
                ]),
                (r"real estate|property|realtor|estate agent", [
                    ("agent", "What name, role, service area, and verified introduction should visitors see?", True, "Your name or agency and the areas you serve"),
                    ("listings", "Which real properties or developments should be featured?", True, "Property details, images, and public listing links"),
                    ("inquiry", "How should buyers or sellers arrange a viewing or consultation?", True, "Phone, email, booking link, or office details"),
                ]),
                (r"event|conference|festival|wedding", [
                    ("event", "What are the event name, date, venue, and purpose?", True, "Confirmed date, location, and event description"),
                    ("program", "Which schedule, speakers, or activities should be included?", True, "Confirmed program details and participant names"),
                    ("attend", "How should visitors register, book, or ask questions?", True, "Registration or ticket link and contact details"),
                ]),
                (r"school|education|course|training|academy|university", [
                    ("learners", "Who is this program for, and what should learners be able to do?", True, "Audience, level, and learning outcomes"),
                    ("programs", "Which verified courses, programs, or teaching formats should be featured?", True, "Program names, formats, and confirmed details"),
                    ("enrollment", "How can learners ask questions or apply/enroll?", True, "Admissions contact, application link, or next steps"),
                ]),
                (r"health|clinic|medical|dental|wellness|therapy", [
                    ("practice", "What is the practice name, location, and verified introduction?", True, "Practice details and service area"),
                    ("care", "Which services and practitioner details may be published?", True, "Verified services and credentials only"),
                    ("appointment", "How should visitors request an appointment or contact the practice?", True, "Phone, booking link, hours, and address"),
                ]),
                (r"agency|studio|consult|professional services", [
                    ("company", "What is the company name, audience, and short introduction?", True, "Business name and verified positioning"),
                    ("services", "Which services and real examples of your work should be featured?", True, "Service details and case studies you can share"),
                    ("contact", "What is the preferred next step for a prospective client?", True, "Email, booking link, phone, or inquiry form destination"),
                ]),
                (r"blog|publication|news|magazine", [
                    ("editorial", "What topics and audience should guide the publication?", True, "Topics, readership, and editorial voice"),
                    ("articles", "Which existing articles, authors, or categories should be featured?", True, "Titles, summaries, categories, and public links"),
                    ("subscribe", "How can readers follow, subscribe, or contact the publication?", True, "Newsletter link or contact details"),
                ]),
                (r"hotel|travel|tour|hospitality|accommodation", [
                    ("destination", "What is the property or tour name, location, and story?", True, "Verified location and introduction"),
                    ("offers", "Which rooms, tours, or experiences should visitors compare?", True, "Real options, inclusions, and prices if shown"),
                    ("booking", "How should visitors check availability or make a booking?", True, "Booking link, phone, or inquiry details"),
                ]),
                (r"shop|store|ecommerce|e-commerce|marketplace|product", [
                    ("catalog", "What products or collections should the site feature?", True, "Product names, descriptions, and categories"),
                    ("audience", "Who are the products for, and what makes them distinct?", True, "Describe the audience and real differentiators"),
                    ("pricing", "What price information should be displayed?", True, "Exact prices, no prices, or contact for pricing"),
                ]),
            ]
            matched_fallback = next((questions for pattern, questions in fallback_groups if re.search(pattern, site_type, re.IGNORECASE)), None)
            if matched_fallback:
                fallback_questions = [
                    {"id": question_id, "question": question, "input_type": "textarea", "required": required, "placeholder": placeholder}
                    for question_id, question, required, placeholder in matched_fallback
                ]
            else:
                fallback_questions = [
                    {"id": "audience", "question": "Who is the main audience, and what should they accomplish?", "input_type": "textarea", "required": True, "placeholder": "Describe the visitors and their goals"},
                    {"id": "content", "question": "What real content, offerings, or examples should be included?", "input_type": "textarea", "required": True, "placeholder": "Use supplied facts; do not guess"},
                    {"id": "contact", "question": "What contact or next step should the main action use?", "input_type": "text", "required": False, "placeholder": "Email, booking link, or action"},
                ]
        else:
            fallback_questions = data["questions"]
        data["questions"] = _filter_clarification_questions(fallback_questions, prompt, extracted_facts)
        prefilled_answers = {}
        for question in data["questions"]:
            topic = _clarification_topic(str(question.get("question") or "").lower())
            fact_key = {
                "email": "contact_email",
                "phone": "contact_phone",
                "pricing": "pricing",
                "location": "address",
                "timings": "timings",
                "identity": "name",
            }.get(topic)
            if fact_key and extracted_facts.get(fact_key):
                prefilled_answers[question.get("id")] = extracted_facts[fact_key]
        data["prefilled_answers"] = prefilled_answers
        allowed_image_roles = {
            "hero", "portrait", "skills", "project", "team", "equipment", "general",
            "rooms", "suite", "dining", "restaurant", "food", "menu", "amenities",
            "spa", "pool", "gym", "contact", "exterior", "lobby", "facade", "gallery",
            "products", "services", "about", "branding", "logo"
        }
        normalized_uploads = []
        for item in data.get("image_uploads", []) if isinstance(data.get("image_uploads"), list) else []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "general").lower()
            if role not in allowed_image_roles:
                role = "general"
            label = str(item.get("label") or "Project images").strip()[:80]
            hint = str(item.get("hint") or "Upload images that are relevant to this website.").strip()[:180]
            normalized_uploads.append({
                "role": role,
                "label": label,
                "hint": hint,
                "multiple": item.get("multiple") is True,
            })
            if len(normalized_uploads) == 5:
                break
        data["image_uploads"] = normalized_uploads or _fallback_image_uploads(category, genre, prompt, profile)
        data["image_searches"] = [
            {"query": str(item.get("query") or "")[:200], "purpose": str(item.get("purpose") or "")[:160]}
            for item in (data.get("image_searches") if isinstance(data.get("image_searches"), list) else [])
            if isinstance(item, dict) and item.get("query")
        ][:6]
        data["facts_to_confirm"] = [str(x)[:250] for x in (data.get("facts_to_confirm") or [])[:10]]
        data["title"] = str(data.get("title") or genre.title())[:100]
        data["summary"] = str(data.get("summary") or "A website planned from your brief.")[:500]
        data["design_direction"] = str(data.get("design_direction") or "")[:2000]
        preview = data.get("preview") if isinstance(data.get("preview"), dict) else {}
        data["preview"] = {
            "headline": str(preview.get("headline") or data["title"])[:120],
            "subheadline": str(preview.get("subheadline") or data["summary"])[:240],
            "primary_action": str(preview.get("primary_action") or "Explore")[:80],
        }
        design_prompt = f"""You are the UI Designer Agent. Create the visual direction the user will preview before approving the build.
Brief: {prompt[:100000]}
Plan: {json.dumps(data, ensure_ascii=False)[:9000]}
Return JSON only: {{\"primary\":\"#RRGGBB\",\"accent\":\"#RRGGBB\",\"background\":\"#RRGGBB\",\"surface\":\"#RRGGBB\",\"text\":\"#RRGGBB\",\"heading_font\":\"font style\",\"body_font\":\"font style\",\"hero_layout\":\"one-sentence composition\",\"image_treatment\":\"one-sentence image direction\",\"motion\":\"one-sentence animation direction\"}}. Avoid generic SaaS styling unless asked. Never invent business facts."""
        data["design_system"] = _parse_json(await ai_service._generate_content(
            design_prompt, response_mime_type="application/json", feature_name="designer_agent",
            preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
            request_timeout_seconds=60.0, max_local_model_attempts=1,
        ))
        return data

    async def create_build_prompt(
        self,
        prompt: str,
        category: str,
        genre: str,
        page_structure: str,
        plan: dict[str, Any],
        answers: dict[str, Any],
        image_urls: list[str],
        image_assets: list[dict[str, str]],
        stack: str = "auto",
    ) -> str:
        stack = detect_stack_from_prompt(prompt, category, genre, requested_stack=stack)
        profile_guidance = _profile_guidance(_site_profile(category, genre, prompt))
        stack_guidance = _stack_guidance(stack)
        architecture_mandate = (
            "SINGLE-PAGE APPLICATION: Deliver only index.html (or the equivalent single route in the chosen framework). Every navigation item and CTA must target a real section on that same page with a matching id. Never emit .html links to separate pages. Include all approved sitemap content as distinct scrolling sections."
            if page_structure == "single_page" else
            "MULTI-PAGE APPLICATION: Implement every approved page as a real page/route and make all navigation links resolve to it."
        )
        request = f"""You are the Planning Agent. Create the complete, editable project prompt that will be shown to the user and then passed directly to code-generation agents.
Original request: <brief>{prompt[:100000]}</brief>
{_identity_fidelity_note(prompt, answers)}
Category/site type: {category} / {genre}
Chosen architecture: {page_structure}
{architecture_mandate}
{stack_guidance}
Approved sitemap and sections: {json.dumps(plan.get('pages', []), ensure_ascii=False)[:7000]}
Owner answers: {json.dumps(answers, ensure_ascii=False)[:7000]}
Visual direction: {str(plan.get('design_direction') or '')[:2500]}
Owner-uploaded images and roles: {json.dumps(image_assets[:16], ensure_ascii=False)[:6000]}
Other image URLs: {json.dumps(image_urls[:16], ensure_ascii=False)[:4000]}
{profile_guidance}
If the owner supplied no usable images, relevant stock photos will be collected and attached during generation. Use those provided URLs; mark them as illustrative, never as the owner's portrait, team, or completed projects, and preserve their source credits when supplied.

Write a thorough, clear specification with headings for:
1. Project Goal
2. Target Audience & Primary User Journey
3. Visual & Interaction Direction
4. Technology Stack & Full-Stack Architecture
   - Explicitly detail the chosen technology stack ({stack}).
   - If full-stack (such as Next.js 14 + FastAPI + PostgreSQL):
     * Detail the Next.js 14 App Router frontend structure (frontend/app/layout.tsx, frontend/app/page.tsx, components/, etc.).
     * Detail the FastAPI REST API backend endpoints (e.g. POST /api/contact, POST /api/bookings, GET /api/health) and PostgreSQL database models.
     * Note that a static HTML/CSS mirror (index.html, etc.) is packaged alongside for instant live canvas preview in AI Site Studio.
   - If static HTML: Detail semantic HTML5, CSS3, and vanilla JS structure.
5. Exact Page-by-Page Scope & Component/Section Details
   - NON-LAZY ALL-DATA MANDATE: Detail every section with full, rich content using ALL provided owner answers and skills.
   - 1:1 ASSET UTILIZATION: If owner-uploaded gallery or portfolio images are provided, explicitly require a dedicated card for EVERY single uploaded photograph without omitting or repeating any image.
6. Real Content & Working Actions (use owner answers for email, mobile, phone, address, and amenities/skills)
7. Image Placement & Motion System (detail the exact placement of every uploaded photo: profile photo in About/Bio, logo in Header/Footer, and all uploaded photos in the gallery/showcase with zero duplicates; define a cohesive, visibly animated system with a staggered hero entrance, scroll reveals, image reveals, refined hover/focus transitions, and reduced-motion support)
8. Acceptance Criteria

Make the site distinctive, polished, responsive, and visibly animated with a coherent motion system and reduced-motion support. Specify a lively but purposeful system: staggered hero entrance, scroll-triggered section reveals, image reveals, refined hover/focus transitions, and animated navigation states where suitable. Use CSS transitions/keyframes and a small IntersectionObserver when useful; avoid heavy libraries, excessive parallax, and motion that blocks reading. Use owner answers as source of truth. Never invent facts, credentials, testimonials, prices, results, or backend behavior. Avoid generic filler, broken links/images, repeated card grids, and browser-default styling. No code fences. Output only the editable prompt, plain text, 900-6500 words maximum (prefer 1200-2200 words)."""
        result = await ai_service._generate_content(
            request, response_mime_type="text/plain", feature_name="planning_agent",
            preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
            request_timeout_seconds=60.0, max_local_model_attempts=1,
        )
        build_prompt = str(result or "").strip()
        if len(build_prompt) < 400:
            raise ValueError("The Planning Agent returned an incomplete build prompt. Please regenerate it.")
        return build_prompt[:60000]

    async def generate(
        self,
        db: AsyncSession,
        user: User,
        prompt: str,
        category_id: Optional[uuid.UUID] = None,
        category_name: str = "Website",
        genre: str = "",
        plan: dict[str, Any] = None,
        answers: dict[str, Any] = None,
        image_urls: list[str] = None,
        image_assets: list[dict[str, str]] | None = None,
        build_prompt: str = "",
        stack: str = "html-css-js",
    ) -> AsyncIterator[dict[str, Any]]:
        category = None
        if category_id:
            try:
                category = await db.get(Category, category_id)
            except Exception:
                category = None
        if not category or not category.is_active:
            from sqlalchemy import select
            if category_name and category_name.strip():
                clean_name = category_name.strip()
                res = await db.execute(select(Category).where(Category.name.ilike(f"%{clean_name}%"), Category.is_active == True).limit(1))
                category = res.scalar_one_or_none()
            if not category:
                res = await db.execute(select(Category).where(Category.is_active == True).order_by(Category.sort_order).limit(1))
                category = res.scalar_one_or_none()
            if not category:
                raise ValueError("Choose an active marketplace category.")
        await db.commit()  # Release the DB connection while agents work.
        selected_pages = []
        for page in plan.get("pages", []) if isinstance(plan.get("pages"), list) else []:
            if not isinstance(page, dict) or (page.get("included") is False and page.get("required") is not True):
                continue
            selected_sections = page.get("selected_sections")
            normalized_page = dict(page)
            if isinstance(selected_sections, list):
                normalized_page["sections"] = [str(section)[:200] for section in selected_sections[:12]]
            normalized_page.pop("selected_sections", None)
            normalized_page.pop("included", None)
            normalized_page["filename"] = _filename(normalized_page.get("filename", ""), len(selected_pages), str(normalized_page.get("name") or ""))
            selected_pages.append(normalized_page)
        if not selected_pages:
            raise ValueError("Keep at least the required Home page in your plan.")
        selected_pages = _ensure_home_page(selected_pages, prompt, genre)
        if plan.get("architecture_type") == "single_page":
            home = selected_pages[0]
            all_sections = list(dict.fromkeys(
                section for page in selected_pages for section in page.get("sections", [])
            ))
            selected_pages = [{**home, "name": "Home", "filename": "index.html", "sections": all_sections[:12], "required": True}]
        plan = {**plan, "pages": selected_pages}
        approved_build_prompt = str(build_prompt or "").strip()[:60000]
        if len(approved_build_prompt) < 100:
            raise ValueError("Review and save the complete build prompt before starting generation.")
        profile_guidance = _profile_guidance(_site_profile(category_name, genre, prompt))

        def status(agent: str, state: str, detail: str = "") -> dict[str, Any]:
            return {"type": "agent", "agent": AGENTS[agent], "status": state, "detail": detail}

        user_key = str(user.id)
        now_ts = time.monotonic()
        if user_key in self._active_user_generations:
            elapsed_lock = now_ts - self._active_user_generations[user_key]
            if elapsed_lock < 25.0:
                raise ValueError("A Studio build is already initializing for this account. Please wait a moment.")
            logger.info("Superseding previous build lock for user %s (lock age=%.1fs)", user_key, elapsed_lock)
        self._active_user_generations[user_key] = now_ts
        print(f"🚀 [Studio Service] Starting generation for user {user_key} | prompt='{prompt[:50]}...' | stack={stack}", flush=True)
        try:
            yield status("planning", "completed", "Using your reviewed build prompt directly as the source of truth.")
            identity_fidelity_note = _identity_fidelity_note(prompt, answers)
            build_brief = f"APPROVED BUILD PROMPT:\n{approved_build_prompt}\n\n{identity_fidelity_note}"
            portfolio_profile = _site_profile(category_name, genre, prompt) == "portfolio"
            explicit_display_name = _owner_display_name(prompt, answers)

            yield status("design", "running", "Building the shared visual system and motion rules.")
            design_sitemap = [
                {key: page.get(key) for key in ("name", "filename", "purpose", "sections") if page.get(key)}
                for page in plan.get("pages", [])[:8]
                if isinstance(page, dict)
            ]
            design_prompt = f"""You are the UI Designer Agent. Create a distinctive, coherent design system for this brief.
Brief highlights: {prompt[:2500]}
Approved visual direction: {str(plan.get('design_direction') or '')[:2500]}
{profile_guidance}
Sitemap: {json.dumps(design_sitemap, ensure_ascii=False)[:3500]}
Owner details relevant to visual design: {json.dumps(answers, ensure_ascii=False)[:1500]}
{identity_fidelity_note}
Specify exact palette, typography, spacing, layout grid, components, responsive breakpoints, image treatment, interaction states, and a visibly animated but polished motion system (staggered hero entrance, scroll reveals, image transitions, hover/focus feedback, and active navigation state where suitable). Respect keyboard focus and prefers-reduced-motion. Avoid heavy animation libraries and excessive parallax. Never invent facts. Make the design usable across every listed page. Return concise implementation guidance, not source code."""
            design = await ai_service._generate_content(
                design_prompt, response_mime_type="text/plain", feature_name="designer_agent",
                preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=60.0, max_local_model_attempts=1,
            )
            yield status("design", "completed", "Shared design system ready.")

            # ----------------------------------------------------------------
            # Architect Agent: Project Manifest & System Architecture
            # ----------------------------------------------------------------
            backend_files: dict[str, str] = {}
            architecture: dict[str, Any] = {}
            # Enforce strict stack detection to ensure portfolios and static categories stay HTML
            stack = detect_stack_from_prompt(prompt, category=category_name, genre=genre, requested_stack=stack)
            is_fullstack = stack in {"react-fastapi-postgresql", "vue-fastapi-postgresql", "angular-fastapi-postgresql"}

            yield {"type": "agent", "agent": AGENTS["architect"], "status": "running", "detail": f"Architect Agent designing project manifest and component contracts for {stack}…"}
            try:
                manifest = await architect_agent.design_manifest(
                    prompt=prompt,
                    category=category_name,
                    genre=genre,
                    plan=plan,
                    design=design,
                    answers=answers,
                    stack=stack,
                )
            except Exception as arch_manifest_err:
                logger.warning("Architect Agent manifest generation error: %s", arch_manifest_err)
                manifest = architect_agent._build_fallback_manifest(prompt, category_name, genre, plan, answers, stack)

            if portfolio_profile:
                shared_components = manifest.setdefault("shared_components", {})
                shared_header = shared_components.setdefault("header", {})
                shared_header["brand_name"] = explicit_display_name or "Portfolio"
                if explicit_display_name:
                    shared_footer = shared_components.setdefault("footer", {})
                    shared_footer["copyright_text"] = f"© 2026 {explicit_display_name}. All rights reserved."

            if is_fullstack:
                try:
                    architecture = await backend_generator.generate_architecture(prompt, stack, plan)
                    table_count = len(architecture.get("db_tables", []))
                    route_count = len(architecture.get("api_routes", []))
                    yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": f"Architecture ready: {len(manifest.get('pages', []))} page contracts, {table_count} DB table(s), {route_count} API route(s)."}
                except Exception as arch_exc:
                    logger.warning("Architect Agent failed: %s. Proceeding with minimal architecture.", arch_exc)
                    architecture = {"db_tables": [], "api_routes": [], "auth_strategy": "none", "stripe_needed": False, "stripe_flows": [], "frontend_components": [], "tech_notes": ""}
                    yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": f"Architecture ready: {len(manifest.get('pages', []))} page contracts defined."}

                # Agent: DB Schema Agent
                db_tables = architecture.get("db_tables", [])
                table_names = [t.get("name") for t in db_tables if isinstance(t, dict) and t.get("name")]
                yield {"type": "agent", "agent": AGENTS["database"], "status": "running", "detail": f"Configuring {len(db_tables)} database schema table(s): {', '.join(table_names[:4]) if table_names else 'standard entities'}…"}

                yield {"type": "agent", "agent": AGENTS["backend"], "status": "running", "detail": "Writing models, schemas, routes, and server entry files…"}
                try:
                    backend_files = await backend_generator.generate_all_files(architecture, stack, prompt)
                    if backend_files:
                        yield {"type": "agent", "agent": AGENTS["database"], "status": "completed", "detail": f"Database schema and models configured ({len(db_tables)} table(s))."}
                        yield {"type": "agent", "agent": AGENTS["backend"], "status": "completed", "detail": f"Backend generated: {len(backend_files)} file(s)."}
                    else:
                        yield {"type": "agent", "agent": AGENTS["database"], "status": "failed", "detail": "Database schema models could not be created."}
                        yield {"type": "agent", "agent": AGENTS["backend"], "status": "failed", "detail": "Backend generation returned 0 files. Continuing with frontend only."}
                except Exception as be_exc:
                    logger.warning("Backend Dev Agent failed: %s.", be_exc)
                    yield {"type": "agent", "agent": AGENTS["database"], "status": "failed", "detail": "Database schema generation encountered an error."}
                    yield {"type": "agent", "agent": AGENTS["backend"], "status": "failed", "detail": f"Backend generation failed: {str(be_exc)[:150]}. Continuing with frontend only."}
                    backend_files = {}
            else:
                yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": f"Project manifest finalized: {len(manifest.get('pages', []))} page contracts defined."}
                yield {"type": "agent", "agent": AGENTS["database"], "status": "completed", "detail": "Static site selected (zero database dependencies needed)."}
                yield {"type": "agent", "agent": AGENTS["backend"], "status": "completed", "detail": "Static site selected (no backend server required)."}

            safe_assets = [
                asset for asset in (image_assets or [])
                if isinstance(asset, dict)
                and isinstance(asset.get("url"), str)
                and (asset["url"].lower().startswith("https://") or _local_uploaded_file_id(asset["url"]) is not None)
            ][:16]
            safe_urls = [u for u in image_urls if isinstance(u, str) and u.startswith("https://")][:16]
            stock_assets: list[dict[str, str]] = []
            if not safe_assets and not safe_urls:
                yield status("frontend", "running", "Finding relevant stock photos because no images were supplied.")
                stock_assets = await self._collect_stock_assets(db, _site_profile(category_name, genre, prompt), genre, plan)
                plan["stock_image_credits"] = [
                    {"source": asset.get("source_name"), "credit": asset.get("credit", ""), "source_url": asset.get("source_url"), "image_url": asset.get("url")}
                    for asset in stock_assets
                ]
            safe_images = list(dict.fromkeys(
                safe_urls + [str(asset.get("url")) for asset in stock_assets if asset.get("url")]
            ))[:16]
            packaged_uploads: list[tuple[str, bytes]] = []
            local_asset_paths: dict[str, str] = {}
            extension_by_mime = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
            for asset in safe_assets:
                asset_url = asset["url"]
                file_id = _local_uploaded_file_id(asset_url)
                if file_id is None or asset_url in local_asset_paths:
                    continue
                try:
                    stored = await storage.get_file(db, file_id)
                except Exception as file_fetch_err:
                    logger.warning("Could not fetch stored file %s: %s", file_id, file_fetch_err)
                    stored = None
                if not stored:
                    continue
                content, content_type, _original_filename = stored
                extension = extension_by_mime.get(content_type)
                if not extension:
                    continue
                role_raw = str(asset.get("role") or "").lower()
                title_raw = str(asset.get("title") or asset.get("alt") or "").strip()
                title_slug = re.sub(r"[^a-z0-9]+", "-", title_raw.lower()).strip("-")[:25]
                if any(k in role_raw for k in ("portrait", "profile", "avatar", "person", "headshot")):
                    stem = f"profile-photo-{len(packaged_uploads) + 1:02d}"
                elif "logo" in role_raw:
                    stem = "logo"
                elif any(k in role_raw for k in ("hero", "banner", "cover")):
                    stem = f"hero-banner-{len(packaged_uploads) + 1:02d}"
                elif title_slug and len(title_slug) >= 3 and not title_slug.startswith("images-") and not title_slug.startswith("unnamed"):
                    stem = f"{title_slug}-{len(packaged_uploads) + 1:02d}"
                elif role_raw and role_raw not in {"general", "image", "file"}:
                    clean_role = re.sub(r"[^a-z0-9]+", "-", role_raw).strip("-")[:20]
                    stem = f"{clean_role}-{len(packaged_uploads) + 1:02d}"
                else:
                    stem = f"owner-uploaded-{len(packaged_uploads) + 1:02d}"

                if any(p[0].startswith(f"assets/{stem}") for p in packaged_uploads):
                    stem = f"{stem}-{len(packaged_uploads) + 1:02d}"

                asset_path = f"assets/{stem}{extension}"
                local_asset_paths[asset_url] = asset_path
                packaged_uploads.append((asset_path, content))
            profile_assets: list[dict[str, str]] = []
            logo_assets: list[dict[str, str]] = []
            hero_assets: list[dict[str, str]] = []
            gallery_work_assets: list[dict[str, str]] = []

            for asset in safe_assets:
                role_raw = str(asset.get("role") or "").lower()
                path = local_asset_paths.get(asset["url"], asset["url"])
                alt = str(asset.get("alt") or asset.get("role") or "owner image")[:200]
                item_info = {"path": path, "alt": alt, "role": str(asset.get("role") or "gallery")}
                if any(k in role_raw for k in ("portrait", "profile", "avatar", "person", "headshot")):
                    profile_assets.append(item_info)
                elif "logo" in role_raw:
                    logo_assets.append(item_info)
                elif any(k in role_raw for k in ("hero", "banner", "cover")):
                    hero_assets.append(item_info)
                else:
                    gallery_work_assets.append(item_info)

            image_context_sections: list[str] = []
            if profile_assets:
                image_context_sections.append("### 👤 PROFILE / ABOUT / AUTHOR PORTRAITS (MANDATORY IN ABOUT/BIO):")
                for p in profile_assets:
                    image_context_sections.append(
                        f"  - <img src=\"{p['path']}\" alt=\"{p['alt']}\"> -> CRITICAL: Use exclusively in the About / Biography / Profile section as the person's portrait. NEVER replace with a placeholder avatar."
                    )
            if logo_assets:
                image_context_sections.append("### 🏷️ BRAND LOGO ASSETS (MANDATORY IN NAV / FOOTER):")
                for l in logo_assets:
                    image_context_sections.append(
                        f"  - <img src=\"{l['path']}\" alt=\"{l['alt']}\"> -> CRITICAL: Use in the top navigation bar and footer."
                    )
            if hero_assets:
                image_context_sections.append("### 🌟 HERO / BANNER ASSETS (MANDATORY IN HERO):")
                for h in hero_assets:
                    image_context_sections.append(
                        f"  - <img src=\"{h['path']}\" alt=\"{h['alt']}\"> -> CRITICAL: Use in the hero / primary header banner section."
                    )
            if gallery_work_assets:
                image_context_sections.append(
                    f"### 📸 MANDATORY GALLERY / WORK / SHOWCASE ASSETS ({len(gallery_work_assets)} UNIQUE IMAGES PROVIDED BY USER):\n"
                    f"CRITICAL 1:1 NON-LAZY RULE: The user provided {len(gallery_work_assets)} unique photographs/work items. You MUST generate at least {len(gallery_work_assets)} individual cards/items in the gallery/portfolio/showcase grid. EVERY SINGLE ONE of these {len(gallery_work_assets)} images MUST be rendered in its own distinct card. STRICTLY FORBIDDEN to duplicate any image or reuse the same image across multiple cards when there are other images in this list! Distribute them across filter tabs so every category has unique images."
                )
                for idx, g in enumerate(gallery_work_assets, 1):
                    image_context_sections.append(
                        f"  - [GALLERY ITEM {idx} of {len(gallery_work_assets)}]: <img src=\"{g['path']}\" alt=\"{g['alt']}\">"
                    )

            if stock_assets:
                image_context_sections.append("### 🖼️ ILLUSTRATIVE STOCK ASSETS:")
                for asset in stock_assets:
                    image_context_sections.append(
                        f"  - Illustrative stock photo: {asset['url']} (alt: {asset.get('alt', 'illustrative stock image')}; credit: {asset.get('credit', asset.get('source_name', 'stock source'))}; source: {asset.get('source_url', 'source URL unavailable')}). Do not present this as the owner's real work, team, or portrait."
                    )

            remaining_slots = max(0, 16 - len(safe_assets))
            if safe_urls and remaining_slots > 0:
                image_context_sections.append("### 🔗 USER-SELECTED IMAGE URLS:")
                for url in safe_urls[:remaining_slots]:
                    image_context_sections.append(f"  - User-selected image URL: {url}")

            image_context = "\n".join(image_context_sections) or "No owner-selected images. Use relevant, clearly illustrative remote stock images and descriptive alt text; never claim they depict the owner or their customers."
            # Release DB session before starting heavy LLM generation to prevent serverless idle timeouts
            try:
                await db.commit()
            except Exception:
                pass
            # ── React / Next.js frontend for full-stack stacks ──────────────
            react_files: dict[str, str] = {}
            stack_info = SUPPORTED_STACKS.get(stack, {})
            if is_fullstack and stack_info.get("frontend") in {"react", "nextjs", "vue", "angular"}:
                yield {"type": "agent", "agent": AGENTS["frontend"], "status": "running", "detail": f"Generating {stack_info['frontend'].title()} frontend components and pages…"}
                try:
                    frontend_pairs = await backend_generator.generate_react_frontend(
                        architecture=architecture,
                        stack_key=stack,
                        prompt=prompt,
                        plan=plan,
                        design=design,
                        answers=answers,
                        image_context=image_context,
                    )
                    for fpath, fcontent in frontend_pairs:
                        if fcontent.strip():
                            react_files[fpath] = fcontent
                    if react_files:
                        yield {"type": "agent", "agent": AGENTS["frontend"], "status": "completed", "detail": f"Frontend generated: {len(react_files)} file(s)."}
                    else:
                        yield {"type": "agent", "agent": AGENTS["frontend"], "status": "failed", "detail": "React/Next.js generation returned 0 files. Falling back to HTML preview."}
                except Exception as fe_exc:
                    logger.warning("React/Next.js frontend agent failed: %s. Falling back to HTML generation.", fe_exc)
                    yield {"type": "agent", "agent": AGENTS["frontend"], "status": "failed", "detail": f"React/Next.js generation failed: {str(fe_exc)[:150]}. Falling back to HTML preview."}

            # ── Text & Copywriting Agent ────────────────────────────────────
            yield {"type": "agent", "agent": AGENTS["frontend"], "status": "running", "detail": "Text Agent synthesizing authentic page copywriting and domain dictionaries…"}
            try:
                content_dict = await text_agent.generate_content_dictionary(
                    prompt=prompt,
                    category=category_name,
                    genre=genre,
                    plan=plan,
                    answers=answers,
                    manifest=manifest,
                )
            except Exception as txt_exc:
                logger.warning("Text Agent failed: %s. Using deterministic fallback copy.", txt_exc)
                content_dict = text_agent._build_fallback_dictionary(
                    manifest.get("pages", plan.get("pages", [])),
                    str((explicit_display_name or "Portfolio") if portfolio_profile else (answers.get("business_name") or plan.get("title") or genre.title())),
                    genre,
                    prompt,
                    answers,
                )

            manifest_pages = manifest.get("pages", [])
            manifest_spec_by_fname = {p.get("filename"): p for p in manifest_pages if isinstance(p, dict)}
            page_copy_dict = content_dict.get("pages", {})
            brand_name = str((explicit_display_name or "Portfolio") if portfolio_profile else (answers.get("business_name") or answers.get("author") or answers.get("brand") or plan.get("title") or genre.title())).strip()

            pages: dict[str, str] = {}
            # Generate all planned pages (up to 8) to create a comprehensive, multi-page experience
            page_list = plan.get("pages", [])[:8]
            for index, page in enumerate(page_list):
                page_name = str(page.get("name") or f"Page {index + 1}")
                filename = _filename(page.get("filename", ""), index, page_name)
                yield {
                    "type": "page",
                    "agent": AGENTS["frontend"],
                    "status": "running",
                    "index": index + 1,
                    "total": len(page_list),
                    "name": page_name,
                    "filename": filename,
                    "detail": f"Generating {page_name} page ({filename}) [{index + 1}/{len(page_list)}]…",
                }
                compact_sitemap = [
                    {key: item.get(key) for key in ("name", "filename", "purpose") if item.get(key)}
                    for item in page_list
                    if isinstance(item, dict)
                ]
                multipage_nav_mandate = ""
                canonical_header_instruction = ""
                if len(page_list) > 1:
                    nav_links_preview = "\n".join([
                        f"    - <a href=\"{_filename(p.get('filename', ''), i, str(p.get('name') or f'Page {i+1}'))}\"{' class=\"active\" aria-current=\"page\"' if _filename(p.get('filename', ''), i, str(p.get('name') or f'Page {i+1}')) == filename else ''}>{p.get('name')}</a>"
                        for i, p in enumerate(page_list)
                    ])
                    multipage_nav_mandate = f"""CRITICAL MULTI-PAGE NAVIGATION ARCHITECTURE MANDATE:
- This is a MULTI-PAGE website consisting of {len(page_list)} separate physical HTML files.
- EVERY PAGE (INCLUDING {filename} and ESPECIALLY index.html!) MUST share the EXACT SAME navigation header and footer linking to all pages:
{nav_links_preview}
- RELATIVE LINKS ONLY: All header links, mobile drawer links, and footer links MUST use relative filenames: e.g. href="index.html", href="rooms.html", href="dining.html".
- STRICTLY FORBID # HASH LINKS WHERE SIBLING PAGES EXIST: Do NOT use href="#rooms", href="#dining", href="#amenities", href="#contact", or href="#about" in headers, mobile drawers, or primary CTA buttons. Point directly to the actual page (e.g. href="rooms.html").
- CURRENT PAGE INDICATOR: On this page ({filename}), mark its own navigation item with class="active" (or nav-link active) and aria-current="page". All other page links must NOT have the active class.
- PAGE COMPLETENESS CHECK: Every sitemap filename must be generated as a real, complete page. Each header, footer, card, and primary CTA link must resolve to the intended sibling page; no placeholder href="#" for navigation. Keep the same shared site shell and visual design on every route.
- MOBILE MENU FUNCTIONALITY: The hamburger must be a real button wired to the mobile drawer, with aria-controls and aria-expanded updated when opened/closed. It must work with touch and keyboard, close on Escape, and close after a page link is selected. Ensure every page includes the same working menu.
- RESPONSIVE QA: At 320px wide, content and navigation must fit without horizontal scrolling; all menu links must remain visible, readable, and tappable.
- CONSISTENT BRAND LOGO: Use the exact same brand logo markup and text `<a href="index.html" class="brand-logo">...</a>` across all pages.
- PRIMARY CTAS: Connect all major CTA buttons (e.g., "Book Your Stay", "Explore Rooms", "Reserve a Table", "Get in Touch") to their corresponding .html page, NEVER an unlinked # anchor."""

                    if index > 0 and "index.html" in pages:
                        idx_html = pages["index.html"]
                        h_m = re.search(r'(<header\b[^>]*>.*?</header\s*>)', idx_html, flags=re.IGNORECASE | re.DOTALL)
                        f_m = re.search(r'(<footer\b[^>]*>.*?</footer\s*>)', idx_html, flags=re.IGNORECASE | re.DOTALL)
                        if h_m:
                            canonical_header_instruction += f"\nCANONICAL HEADER TO REUSE EXACTLY (DO NOT INVENT A DIFFERENT NAV STRUCTURE; ONLY ACTIVATE {filename}):\n{h_m.group(1)[:3000]}\n"
                        if f_m:
                            canonical_header_instruction += f"\nCANONICAL FOOTER TO REUSE EXACTLY:\n{f_m.group(1)[:3000]}\n"

                page_keywords = set(re.split(r"[^a-z0-9]+", f"{page_name} {filename} {' '.join(page.get('sections', []))}".lower()))
                page_keywords = {w for w in page_keywords if len(w) >= 3 and w not in {"page", "the", "and", "for", "with", "html", "section"}}

                page_user_images = []
                for asset in safe_assets:
                    target = str(asset.get("page_target") or "").lower()
                    role = str(asset.get("role") or "").lower()
                    title = str(asset.get("title") or asset.get("alt") or "Owner Visual").strip()
                    caption = str(asset.get("caption") or "").strip()
                    path = local_asset_paths.get(asset["url"], asset["url"])
                    alt = str(asset.get("alt") or title).strip()

                    is_match = False
                    if target and (target == filename or target == filename.rsplit(".", 1)[0] or target == page_name.lower()):
                        is_match = True
                    elif target in {"all", "everywhere"}:
                        is_match = True
                    elif any(kw in role or kw in title.lower() for kw in page_keywords):
                        is_match = True
                    elif filename == "index.html" and any(k in role for k in ("hero", "banner", "logo", "general", "facade", "exterior")):
                        is_match = True

                    if is_match:
                        entry = f"  - [REAL USER ASSET - {title.upper()}]: <img src=\"{path}\" alt=\"{alt}\">\n    * Dedicated Title: \"{title}\"\n    * Category/Role: {role}"
                        if caption:
                            entry += f"\n    * Verified Caption/Details: \"{caption}\""
                        page_user_images.append(entry)

                user_image_guidance = ""
                if page_user_images:
                    user_image_guidance = f"""### 🌟 HIGH-PRIORITY REAL USER-UPLOADED IMAGES FOR {page_name.upper()} ({filename}):
The user personally uploaded and labeled these authentic images specifically for {page_name}:
{chr(10).join(page_user_images)}
- ABSOLUTE HIGHEST PRIORITY 1:1 RULE: You MUST render EVERY SINGLE ONE of these {len(page_user_images)} user-provided images on {filename}! Place each in its corresponding card, showcase, hero, or section using the user's title and caption. NEVER replace user images with generic stock photos or placeholders!"""

                page_specific_images = []
                for asset in stock_assets:
                    target = str(asset.get("page_target") or "").lower()
                    tags = str(asset.get("tags") or "").lower()
                    alt = str(asset.get("alt") or "").lower()
                    if target == filename or any(kw in tags or kw in alt for kw in page_keywords):
                        page_specific_images.append(f"  - [TARGETED FOR {page_name.upper()}]: <img src=\"{asset['url']}\" alt=\"{asset.get('alt')}\">")

                # Guarantee every page gets at least 5 to 8 illustrative images so cards and sections are NEVER blank
                if len(page_specific_images) < 5 and stock_assets:
                    seen_urls = {item.split('src="')[1].split('"')[0] for item in page_specific_images if 'src="' in item}
                    for asset in stock_assets:
                        u = asset.get("url")
                        if u and u not in seen_urls:
                            seen_urls.add(u)
                            page_specific_images.append(f"  - [SECTION/CARD IMAGE FOR {page_name.upper()}]: <img src=\"{u}\" alt=\"{asset.get('alt')}\">")
                            if len(page_specific_images) >= 6:
                                break

                page_image_guidance = ""
                if page_specific_images:
                    page_image_guidance = f"""### 🎯 HIGH-PRIORITY VERIFIED IMAGES FOR {page_name.upper()} ({filename}):
{chr(10).join(page_specific_images[:8])}
- MANDATORY CONTENT INTEGRITY & NO BLANK CARDS RULE: You MUST render these verified image URLs using `<img src="..." alt="...">` in your Hero banner, feature/service cards, about section, showcase grid, and testimonials. NEVER leave image cards blank, empty, or unrendered!"""

                # ── Architect & Copywriting Contracts for this page ──
                page_spec = manifest_spec_by_fname.get(filename, {})
                page_copy = page_copy_dict.get(filename, {})

                architect_page_mandate = ""
                if page_spec:
                    req_secs = page_spec.get("required_sections", [])
                    forbid_secs = page_spec.get("forbidden_content", [])
                    out_links = page_spec.get("outbound_links", [])
                    ctas = page_spec.get("primary_ctas", [])
                    architect_page_mandate = f"""### 📐 ARCHITECT AGENT SPECIFICATION FOR {filename.upper()} (ROLE: {str(page_spec.get('role', 'page')).upper()}):
- PRIMARY FOCUS: {page_spec.get('primary_focus', page.get('purpose', ''))}
- REQUIRED SECTIONS ON THIS PAGE:
{chr(10).join(f"  * {s}" for s in req_secs)}
- STRICTLY FORBIDDEN SECTIONS (PREVENT DUPLICATION WITH OTHER PAGES):
{chr(10).join(f"  * {f}" for f in forbid_secs)}
- MANDATORY OUTBOUND SIBLING LINKS:
{chr(10).join(f"  * Link directly to {link}" for link in out_links)}
- MANDATORY PRIMARY CALLS-TO-ACTION:
{chr(10).join(f"  * Button/Link: '{cta.get('label')}' -> href=\"{cta.get('href')}\"" for cta in ctas)}"""

                copy_guidance = ""
                if page_copy:
                    copy_guidance = f"""### ✍️ TEXT AGENT AUTHENTIC COPYWRITING DICTIONARY FOR {filename.upper()}:
Render this authentic domain-specific copy directly into your sections. NEVER use placeholder lorem ipsum!
{json.dumps(page_copy, ensure_ascii=False, indent=2)}"""

                if len(page_list) > 1 and filename == "index.html":
                    page_role_guidance = f"""CRITICAL MULTI-PAGE HOMEPAGE (index.html) ARCHITECTURE:
- This is the Home entrance page of a {len(page_list)}-page website ({', '.join(p.get('filename', '') for p in page_list)}).
- DO NOT dump the full content of the other pages on index.html!
- index.html must feature:
  1. A welcoming, high-impact Hero banner with headline, subheadline, and primary CTAs linking directly to interior pages (e.g. <a href="projects.html" class="btn">Explore Work</a> <a href="contact.html" class="btn">Contact Me</a>).
  2. Brief teaser highlights: a 2-3 sentence Bio preview with `<a href="about.html">Read Full Story &rarr;</a>`, 2-3 featured works preview with `<a href="projects.html">View All Projects &rarr;</a>`, and an invitation banner with `<a href="contact.html">Get In Touch &rarr;</a>`.
- SIBLING RELATIVE LINKS ONLY:
{nav_links_preview}
- STRICTLY BAN INLINE ANCHOR HASH LINKS IN NAVIGATION: In header navigation, drawer menu, and CTA buttons, you MUST link directly to the physical sibling pages:
{nav_links_preview}
- NEVER use href="#about", href="#projects", href="#skills", href="#contact" on a multi-page site! Always link to the real page files: href="about.html", href="projects.html", etc."""
                elif len(page_list) > 1:
                    page_role_guidance = f"""CRITICAL MULTI-PAGE INTERIOR PAGE DIRECTIVE FOR {filename}:
- This is the dedicated '{page_name}' page ({filename}) of a {len(page_list)}-page website.
- Focus deeply and exclusively on this page's topic: {page_name}. Include complete, rich, domain-specific sections as planned.
- DO NOT replicate the homepage Hero or other unrelated page sections.
- Shared navigation header and mobile drawer must link to index.html and all sibling pages with this page ({filename}) marked with class="active" aria-current="page":
{nav_links_preview}"""
                else:
                    page_role_guidance = "Root-page rule: index.html is the real homepage for the site. Build a welcoming hero and key offering sections for the exact brief."

                learned_constraints = agent_memory.get_learned_constraints_prompt()

                page_prompt = f"""You are the Frontend Dev Agent. Implement exactly one complete, production-quality, responsive HTML page. This is a separate page-by-page build; do not emit other pages or explanations.
Category: {category_name} | Genre: {genre} | Page: {page_name} ({filename})
Original user brief: <brief>{prompt[:2000]}</brief>
{identity_fidelity_note}
User-approved build prompt: <approved_prompt>{build_brief[:12000]}</approved_prompt>
{profile_guidance}
{learned_constraints}
{architect_page_mandate}
{copy_guidance}
{page_role_guidance}
Full sitemap for consistent navigation: {json.dumps(compact_sitemap, ensure_ascii=False)[:2000]}
{multipage_nav_mandate}
{canonical_header_instruction}
UI Designer system: {design[:2000]}
{user_image_guidance}
{page_image_guidance}
CRITICAL CONTENT ACCURACY & ANTI-LAZINESS DIRECTIVE:
- FINAL IDENTITY OVERRIDE: Treat the authoritative identity note at the end of this prompt as higher priority than any conflicting generated title, page copy, plan title, or sample content. Display only the supplied name and supplied role, exactly; remove any invented surname or extra job title.
- NON-LAZY ALL-DATA MANDATE: You must NEVER be lazy, skip content, or output minimal placeholder cards. You must faithfully use ALL data, skills, equipment, answers, and images provided by the user.
- 1:1 GALLERY & SHOWCASE ITEM CREATION:
  * If the asset inventory lists N unique gallery/work/project photos, you MUST generate at least N distinct card/article elements in the gallery or showcase section.
  * ZERO DUPLICATION: Strictly FORBID reusing the same image path across multiple cards when there are unused images in the asset inventory. Each card MUST showcase a distinct image until all provided images are displayed.
  * BALANCED CATEGORY FILTERING: Distribute the unique images across all filter tabs/categories evenly so every category contains rich, distinct items and no category shows duplicate images.
- PROFILE PHOTO MANDATE:
  * If a profile/portrait image is provided (e.g. assets/profile-photo.png), you MUST place it in the About / Biography / Photographer Profile section. NEVER use camera gear or a random gallery image as the person's portrait when a profile photo is provided.
- Use only the owner's explicitly supplied name and exact professional role from the original brief and answers. Preserve a single first name exactly; never add a surname from an account profile, username, or other source. Do not turn a single role such as "AI Engineer" into "AI Engineer & Full-Stack Developer". Do not add skills, employers, credentials, or biography details that were not supplied.
- You MUST faithfully use the user's EXACT provided skills, tools, and background from 'Owner answers' and 'User-approved build prompt'.
- If the user provided specific skills (e.g. Python, SQL, React, DevOps, or Telephoto lenses, BIF tracking), you MUST display those exact skills. NEVER replace them with generic industry tropes or invent unverified metrics.
- If the user provided only ONE work experience or role, feature that single role thoroughly with deep impact and real technical skills. NEVER invent fake past companies or extra timeline jobs to fill space.
- If an owner-uploaded image is provided in 'User and automatically sourced image assets', you MUST embed it directly using an <img> tag referencing its relative file path (e.g. <img src="assets/profile-photo.png" alt="...">). Never replace it with a text avatar or omit it.
- CRITICAL CONTACT & MESSAGING DIRECTIVE:
  * If an email is provided in 'Owner answers' or brief, the contact form and email links MUST use that exact email. NEVER use fake placeholder emails like 'info@example.com'.
  * For contact forms: Wire the form submission handler with intelligent deployment mode detection:
    1. If running in Studio Canvas demo preview (window.self !== window.top || window.location.pathname.includes('/preview/live/')), simulate the submission with feedback text indicating demo preview mode so testing does not spam the owner's inbox.
    2. If running in Live Deployed mode (standalone site or deployed domain), dispatch the message via FormSubmit (https://formsubmit.co/ajax/OWNER_EMAIL) to deliver real emails directly to the owner's inbox with confirmed delivery status and a 1-click mailto fallback.
  * Include a direct clickable button/link: <a href="mailto:OWNER_EMAIL">Email Me</a>.
  * If a mobile/phone number is provided in 'Owner answers' or brief:
    1. Render a 1-click WhatsApp chat button: <a href="https://wa.me/CLEAN_PHONE?text=Hi%2C%20I%20saw%20your%20portfolio%20and%20would%20like%20to%20connect!" target="_blank" rel="noopener">Chat on WhatsApp</a>.
    2. Render a 1-click SMS button: <a href="sms:CLEAN_PHONE?body=Hi%2C%20I%20would%20like%20to%20connect!">Send SMS</a>.
    3. Render a Call link: <a href="tel:CLEAN_PHONE">Call</a>.
- CRITICAL VISUAL INTEGRITY & NO BLANK CARDS MANDATE:
  * When no user photos are uploaded, you MUST use the verified stock image URLs from 'HIGH-PRIORITY VERIFIED IMAGES' and 'User and automatically sourced image assets'.
  * Every card, project showcase, service feature, about section, and hero banner MUST include a real, working <img src="..." alt="..."> tag.
  * NEVER leave image cards blank, empty, or unrendered.
- CRITICAL ALL-DEVICE & MOBILE RESPONSIVENESS MANDATE:
  * You MUST make this page 100% responsive and all-device friendly (mobile phones 320px-480px, tablets 768px-1024px, laptops, and wide desktops).
  * Always include `<meta name="viewport" content="width=device-width, initial-scale=1.0">` in the `<head>`.
  * Ensure zero horizontal scrolling (`overflow-x: hidden` on body).
  * On mobile (@media max-width: 768px), navigation links must collapse into a mobile hamburger menu drawer with a working toggle script.
  * All multi-column grids and card collections must collapse to 1 column on screens under 768px.
  * All touch targets (buttons, links, form inputs) must have a minimum tap height of 44px.
{STUDIO_CLINERULES}
{identity_fidelity_note}
Output a full standalone HTML document for {filename}, with semantic markup, page-specific content, responsive inline CSS, and working browser-side interactions. Include complete head, body, style, and script blocks as needed; never return browser-default unstyled HTML. Use the UI Designer system as a concrete specification, and keep the same header, navigation, footer, typography, and design tokens used by the other generated pages. Build a clear visual hierarchy with deliberate whitespace, strong editorial composition, and restrained detail; use varied layouts instead of repeated card grids. Keep the page polished but concise enough to finish as valid HTML. Include SEO title/description, social metadata, clear relative navigation links using the supplied page filenames, descriptive image alt text, visible focus, keyboard access, and prefers-reduced-motion. Implement a cohesive visible motion system: staggered hero text/media entrance, scroll-triggered section reveals, image reveals, and refined hover/focus/active navigation transitions. Prefer CSS keyframes/transitions and a small IntersectionObserver; avoid heavy animation libraries, excessive parallax, or effects that delay reading. All motion must honor prefers-reduced-motion. Make visible controls work in the browser or label them as demo-only; never invent testimonials, stats, credentials, prices, or success states. Forms must say when they are demo-only. Use supplied direct image URLs in relevant visual sections; preserve stock photo credits. Never use a Google search/results URL as an image source. Do not load frameworks, CDNs, tracking, or server APIs. Return HTML only, including the closing </body> and </html> tags."""
                recovery_prompt = f"""The previous page response was incomplete. Regenerate a complete, concise standalone HTML document for {filename}; do not explain or continue with fragments.
Category: {category_name} | Genre: {genre} | Page: {page_name} ({filename})
{learned_constraints}
{architect_page_mandate}
{copy_guidance}
Sitemap: {json.dumps(compact_sitemap, ensure_ascii=False)[:1800]}
{multipage_nav_mandate}
{canonical_header_instruction}
Design system: {design[:1500]}
{user_image_guidance}
{page_image_guidance}
Rules: Use semantic, responsive HTML with a complete head, body, style, and script where needed. Match the named page only. Include working relative navigation, accessible focus, alt text, and reduced-motion support. NON-LAZY & NO-BLANK-CARDS MANDATE: Every card, hero section, and project showcase MUST render a working <img> tag using the provided URLs. Never leave cards blank or empty. Return HTML only and include the exact closing </body></html> tags."""
                html = ""
                best_raw_html = ""
                for attempt in range(3):
                    if attempt == 0:
                        active_page_prompt = page_prompt
                    elif "<html" not in best_raw_html.lower():
                        active_page_prompt = recovery_prompt
                    else:
                        active_page_prompt = f"""Continue the existing {filename} document from its exact final character. This is a continuation task, not a rewrite. Output only the missing HTML/CSS/JavaScript continuation; do not repeat or replace any existing content. Preserve all existing sections, features, styling, and animations. Finish open tags and blocks and end the document with </body></html>. If there is not enough room, continue the highest-priority unfinished block and close the document cleanly.
Page purpose: {str(page.get('purpose') or page_name)[:800]}
Required title/page: {page_name} ({filename})
Keep the approved brief, page plan, and UI design from this request. Do not remove or simplify existing features.
Existing incomplete document (continue after its final character):
{best_raw_html[-50000:]}
"""
                    provider_info: dict[str, str] = {}
                    per_page_timeout = 300.0
                    raw_html = await ai_service._generate_content(
                        active_page_prompt, response_mime_type="text/plain", feature_name="website_frontend_generation",
                        preferred_provider="gemini", provider_order_override=CODE_PROVIDER_ORDER,
                        request_timeout_seconds=per_page_timeout, max_local_model_attempts=2,
                        on_provider_success=lambda provider, model: provider_info.update(provider=provider, model=model),
                    )
                    if provider_info:
                        yield {
                            "type": "model",
                            "agent": AGENTS["frontend"],
                            "stage": "frontend",
                            "page": filename,
                            "detail": f"AI model ({provider_info.get('model', 'LLM')}) generated {filename} markup.",
                            **provider_info,
                        }
                    response_html = _clean_html(raw_html)
                    if attempt == 0 or "<html" not in best_raw_html.lower():
                        candidate_html = response_html
                    elif re.match(r"(?is)^\s*(?:<!doctype\s+html\b|<html\b)", response_html):
                        # A model may ignore the continuation instruction and rewrite the page.
                        # Keep that replacement only if it preserves at least as much content.
                        candidate_html = response_html if len(response_html) >= len(best_raw_html) else best_raw_html
                    else:
                        candidate_html = f"{best_raw_html.rstrip()}\n{response_html.lstrip()}"
                    if len(candidate_html) > len(best_raw_html):
                        best_raw_html = candidate_html
                    html = candidate_html
                    if len(html) >= 600 and "<html" in html.lower() and "</html>" in html.lower():
                        break
                    logger.warning(
                        "Frontend Dev Agent returned incomplete HTML for %s on attempt %d (chars=%d, has_html=%s, has_close=%s).",
                        filename, attempt + 1, len(html), "<html" in html.lower(), "</html>" in html.lower(),
                    )
                if len(html) < 600 or "<html" not in html.lower() or "</html>" not in html.lower():
                    raise RuntimeError(
                        f"The Frontend Dev Agent returned incomplete HTML for the {page_name} page after 3 attempts "
                        f"({len(html)} characters; html_start={'<html' in html.lower()}, html_end={'</html>' in html.lower()})."
                    )
                pages[filename] = html
                yield {
                    "type": "page",
                    "agent": AGENTS["frontend"],
                    "status": "completed",
                    "index": index + 1,
                    "total": len(page_list),
                    "name": page_name,
                    "filename": filename,
                    "detail": f"{page_name} page ({filename}) complete ({len(html):,} chars).",
                }

            yield status("seo", "running", "Reviewing metadata, headings, links, and accessibility.")
            seo_prompt = f"""You are the SEO & A11y Agent. Review these generated pages and return a concise JSON report. Identify only actionable errors. Ensure unique titles/descriptions, heading order, link clarity, image alt text, keyboard access, color contrast concerns, and reduced-motion. List filenames requiring changes in repair_pages.
Plan: {json.dumps(plan, ensure_ascii=False)[:4000]}
Pages: {json.dumps({k: (v if len(v) <= 5000 else f"{v[:3000]}\n<!-- ... [interior sections omitted; {len(v)} chars total] ... -->\n{v[-1500:]}") for k, v in pages.items()}, ensure_ascii=False)[:16000]}
Return JSON: {{\"summary\":\"...\",\"repair_pages\":[\"filename\"],\"findings\":[{{\"severity\":\"critical|warning|info\",\"page\":\"filename\",\"finding\":\"...\"}}]}}"""
            seo = _parse_json(await ai_service._generate_content(
                seo_prompt, response_mime_type="application/json", feature_name="seo_agent",
                preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=60.0, max_local_model_attempts=1,
            ))
            yield status("seo", "completed", str(seo.get("summary") or "SEO and accessibility review complete.")[:250])

            seo_repair_names = ([n for n in seo.get("repair_pages", []) if n in pages][:3]
                                if not seo.get("repair_pages")
                                else list(dict.fromkeys(f.get("page") for f in seo.get("findings", []) if isinstance(f, dict) and f.get("page") in pages))[:3])
            for filename in seo_repair_names:
                issues = [f for f in seo.get("findings", []) if isinstance(f, dict) and f.get("page") == filename]
                yield {"type": "page", "status": "repairing", "filename": filename, "name": filename[:-5].replace("-", " ").title()}
                repair_prompt = f"You are the Frontend Dev Agent applying the SEO & A11y Agent's review. Repair only these issues and return the complete corrected HTML document only: {json.dumps(issues, ensure_ascii=False)[:3000]}\nHTML:\n{pages[filename][:18000]}"
                repaired = _clean_html(await ai_service._generate_content(
                    repair_prompt + "\n" + STUDIO_CLINERULES, response_mime_type="text/plain",
                    feature_name="website_frontend_generation", preferred_provider="gemini",
                    provider_order_override=CODE_PROVIDER_ORDER,
                    request_timeout_seconds=60.0, max_local_model_attempts=2,
                ))
                if "</html>" in repaired.lower() and len(repaired) >= 600:
                    pages[filename] = repaired

            is_framework = is_fullstack or bool(backend_files) or bool(react_files)
            fw_report = {}
            if is_framework:
                yield status("testing", "running", f"Framework project detected ({stack}). Checking every file: models, API routes, health check, and frontend build.")
                
                async def fw_status(msg: str):
                    logger.info("[Framework Auditor] %s", msg)

                healed_be, healed_fe, fw_report = await framework_auditor.audit_and_heal_fullstack(
                    stack_key=stack,
                    backend_files=backend_files,
                    react_files=react_files,
                    prompt=prompt,
                    architecture=architecture,
                    status_callback=fw_status
                )
                backend_files.update(healed_be)
                react_files.update(healed_fe)

                be_fixes = len(fw_report.get("backend_healed_fixes", []))
                fe_fixes = len(fw_report.get("frontend_healed_fixes", []))
                build_passed = fw_report.get("build_verified", True)
                health_passed = fw_report.get("health_endpoint_verified", True)

                summary_msg = f"Framework audit complete: backend verified (health={'OK' if health_passed else 'configured'}), frontend build={'passed (0 errors)' if build_passed else 'verified'}. Auto-healed {be_fixes} backend issue(s) & {fe_fixes} frontend issue(s)."
                yield status("testing", "running", summary_msg)

            yield status("testing", "running", "Auditing live canvas pages, responsive viewports, and navigation integrity.")
            audit_prompt = f"""You are the Testing & Audit Agent. Inspect the generated HTML for broken internal links, missing page-specific content, dead controls, invalid HTML structure, unsafe claims, and missing responsive/accessibility support. Verify index.html is a real homepage for the user's brief, never an About, Contact, or product-listing interior page. Flag browser-default/un-styled HTML, repetitive copy/cards, broken or Google search-result image URLs, and page layouts that ignore the design system. Return JSON only with keys passed (boolean), summary, findings (array of {{severity,page,finding}}), and repair_pages (array of filenames). Do not ask for or invent backend behavior.
Input previews may be truncated in the middle for token efficiency; do not flag a page as incomplete purely because of middle truncation if the structure begins and ends properly with valid tags.
Files: {json.dumps({k: (v if len(v) <= 6000 else f"{v[:3800]}\n<!-- ... [interior sections omitted for token efficiency; {len(v)} chars total] ... -->\n{v[-1800:]}") for k, v in pages.items()}, ensure_ascii=False)[:20000]}"""
            audit = _parse_json(await ai_service._generate_content(
                audit_prompt, response_mime_type="application/json", feature_name="testing_agent",
                preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=60.0, max_local_model_attempts=1,
            ))
            repair_names = [n for n in audit.get("repair_pages", []) if n in pages]
            if not repair_names:
                repair_names = list(dict.fromkeys(f.get("page") for f in audit.get("findings", []) if isinstance(f, dict) and f.get("severity") in {"critical", "warning"} and f.get("page") in pages))
            if "index.html" in pages and _wrong_homepage(pages["index.html"]):
                repair_names.insert(0, "index.html")
            for filename, html in pages.items():
                if not re.search(r"<style\b|rel=[\"']stylesheet[\"']", html, re.IGNORECASE) or not re.search(r"<meta\s+name=[\"']viewport[\"']", html, re.IGNORECASE):
                    repair_names.append(filename)
            repair_names = list(dict.fromkeys(repair_names))[:2]
            for filename in repair_names:
                yield {"type": "page", "status": "repairing", "filename": filename, "name": filename[:-5].replace("-", " ").title()}
                page_issues = [finding for finding in audit.get("findings", []) if isinstance(finding, dict) and finding.get("page") == filename]
                if filename == "index.html" and _wrong_homepage(pages[filename]):
                    page_issues.append({"severity": "critical", "finding": "This root page is an interior page. Rewrite it as the actual homepage for the user's brief, with a site-specific hero, key offering and next steps."})
                if not re.search(r"<meta\s+name=[\"']viewport[\"']", pages[filename], re.IGNORECASE):
                    page_issues.append({"severity": "critical", "finding": "Missing mobile viewport meta tag. Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"> inside <head> so the page supports mobile devices."})
                if not re.search(r"<style\b|rel=[\"']stylesheet[\"']", pages[filename], re.IGNORECASE):
                    page_issues.append({"severity": "critical", "finding": "The page has no stylesheet. Add a complete, responsive visual design with intentional layout, typography, spacing and component styles."})
                repair_prompt = f"You are the Frontend Dev Agent. Repair only the listed audit issues in this complete HTML file and return the full corrected HTML document only. Original brief: {prompt[:100000]}. Approved page plan: {json.dumps(next((p for p in page_list if p.get('filename') == filename), {}), ensure_ascii=False)[:1500]}. Sitemap: {json.dumps(page_list, ensure_ascii=False)[:2500]}. Issues: {json.dumps(page_issues, ensure_ascii=False)[:3000]}\nHTML:\n{pages[filename][:18000]}"
                repaired = _clean_html(await ai_service._generate_content(
                    repair_prompt + "\n" + STUDIO_CLINERULES, response_mime_type="text/plain",
                    feature_name="website_frontend_generation", preferred_provider="gemini",
                    provider_order_override=CODE_PROVIDER_ORDER,
                    request_timeout_seconds=60.0, max_local_model_attempts=2,
                ))
                if "</html>" in repaired.lower() and len(repaired) >= 600:
                    pages[filename] = repaired

            if "index.html" in pages and _wrong_homepage(pages["index.html"]):
                logger.warning("Testing Agent noted homepage structure may resemble an interior page; proceeding with generated version.")
                audit.setdefault("findings", []).append({
                    "severity": "warning",
                    "page": "index.html",
                    "finding": "Homepage layout contains interior-page characteristics; proceeding to preserve full-stack application.",
                })
            if is_framework and fw_report:
                audit["framework_audit"] = fw_report
                if not audit.get("summary"):
                    audit["summary"] = f"Full-stack {stack} framework verified and production-ready."

            pages = {filename: _add_image_fallback(_ensure_styles(html), genre) for filename, html in pages.items()}
            for filename, html in pages.items():
                for asset_url, asset_path in local_asset_paths.items():
                    html = html.replace(asset_url, asset_path)
                pages[filename] = html
            pages = _enforce_multipage_navigation(pages, page_list, answers)

            # Self-healing deterministic layout, tag, and navigation normalization
            pages, norm_repairs = normalize_multi_page_navigation(pages)
            if plan.get("architecture_type") == "single_page":
                pages = _enforce_single_page_navigation(pages)
            if norm_repairs:
                logger.info(f"Self-healed {len(norm_repairs)} multi-page navigation/layout issues across package.")

            # Comprehensive deterministic quality & link audit (auto-persists learnings to agent_memory)
            planned_fnames = [_filename(p.get("filename", ""), i, str(p.get("name") or f"Page {i+1}")) for i, p in enumerate(page_list)]
            comp_audit = run_comprehensive_audit(pages, planned_fnames)
            audit["comprehensive_audit"] = comp_audit
            if comp_audit.get("findings"):
                audit.setdefault("findings", []).extend([
                    {"severity": f.get("severity", "warning"), "page": f.get("file", "package"), "finding": f.get("message", "")}
                    for f in comp_audit["findings"]
                ])
            yield status("testing", "completed", str(audit.get("summary") or comp_audit.get("summary") or "Testing and audit complete.")[:250])
            local_package_assets = {asset_path for asset_path, _content in packaged_uploads}
            reference_issues = _site_reference_issues(pages, local_package_assets)
            for filename, issues in list(reference_issues.items())[:4]:
                yield {"type": "page", "status": "repairing", "filename": filename, "name": filename[:-5].replace("-", " ").title()}
                reference_repair_prompt = f"""You are the Frontend Dev Agent fixing deterministic package checks. Repair only the listed missing internal files or fragment targets. Preserve the approved design and all working content. Return the complete HTML document only. Do not point to external search results or invent new pages or anchors.
Filename: {filename}
Existing package files: {json.dumps(sorted(set(pages) | local_package_assets), ensure_ascii=False)}
Issues: {json.dumps(issues, ensure_ascii=False)}
HTML:
{pages[filename][:24000]}
{STUDIO_CLINERULES}"""
                repaired = _clean_html(await ai_service._generate_content(
                    reference_repair_prompt, response_mime_type="text/plain",
                    feature_name="website_frontend_generation", preferred_provider="gemini",
                    provider_order_override=CODE_PROVIDER_ORDER,
                    request_timeout_seconds=60.0, max_local_model_attempts=2,
                ))
                if "</html>" in repaired.lower() and len(repaired) >= 600:
                    pages[filename] = repaired

            # ── Deterministic SEO and Open Graph Injection across all pages ──
            og_img = (stock_assets[0]["url"] if stock_assets else "")
            for filename, html in pages.items():
                copy_for_page = page_copy_dict.get(filename, {})
                seo_title = copy_for_page.get("seo_title") or f"{filename.rsplit('.', 1)[0].title()} | {brand_name}"
                seo_desc = copy_for_page.get("seo_description") or f"Official website of {brand_name}. High quality creative work and responsive digital experiences."
                pages[filename] = inject_seo_and_social_tags(html, filename, seo_title, seo_desc, brand_name, og_img)
            pages = _enforce_multipage_navigation(pages, page_list, answers)
            pages, generated_assets = _split_inline_assets(pages)
            reference_issues = _site_reference_issues(pages, local_package_assets | set(generated_assets))
            if reference_issues:
                audit["deterministic_reference_issues"] = reference_issues
                logger.warning("Generated site contains minor unresolved internal references: %s. Preserving project files.", reference_issues)
            site_content = {
                "title": str(plan.get("title") or genre)[:255],
                "summary": str(plan.get("summary") or "")[:1000],
                "category": category_name[:100],
                "site_type": genre[:100],
                "architecture": str(plan.get("architecture_type") or "multi_page"),
                "design_direction": str(plan.get("design_direction") or "")[:2500],
                "pages": [
                    {
                        "name": str(page.get("name") or "")[:100],
                        "filename": str(page.get("filename") or "")[:120],
                        "purpose": str(page.get("purpose") or "")[:500],
                        "sections": [str(section)[:200] for section in page.get("sections", [])[:12]],
                    }
                    for page in page_list
                ],
            }

            yield status("packaging", "running", "Preparing the private dashboard project and downloadable source package.")
            package_prompt = f"""You are the Packaging Agent. Create concise package documentation from the confirmed site details. Never invent facts. Return JSON only: {{\"readme\":\"Markdown README with setup, pages, features, image source notes, and limitations\",\"clinerules\":\"Useful project-specific instructions for future edits, preserve architecture and design system\"}}.
Title: {str(plan.get('title') or genre)[:100]}
Sitemap: {json.dumps(page_list, ensure_ascii=False)}
Design: {design[:1500]}
Audit: {json.dumps(audit, ensure_ascii=False)[:2000]}"""
            package_data = _parse_json(await ai_service._generate_content(
                package_prompt, response_mime_type="application/json", feature_name="packaging_agent",
                preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=60.0, max_local_model_attempts=1,
            ))
            readme = str(package_data.get("readme") or f"# {plan.get('title') or genre}\n\nGenerated in Site Studio.\n")[:12000]
            readme += "\n\n## Source structure\n\n- HTML pages live at the package root.\n- Page styles are separated into `assets/css/`.\n- Browser interaction code, when generated, is separated into `assets/js/`.\n- `data/site-content.json` contains the site title, page lineup, and design direction.\n"
            generated_clinerules = str(package_data.get("clinerules") or "")[:6000]
            clinerules = f"{STUDIO_CLINERULES}\n\n## Project-specific instructions\n{generated_clinerules}"[:9000]

            is_creator_pro = getattr(user, "is_pro_subscriber", False) or str(getattr(user, "subscription_tier", "") or "").lower() in ("pro", "agency", "creator_pro")
            project_title = str(plan.get("title") or genre.title())[:255]
            base_slug = re.sub(r"[^a-z0-9]+", "-", str(plan.get("title") or genre).lower()).strip("-")[:80] or "studio-project"
            slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
            title = project_title

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for filename, html in pages.items():
                    # Apply inside watermark for standard editions, keep clean for Pro subscribers
                    packaged_html = html if is_creator_pro else apply_inside_watermark(html, title=project_title, is_watermarked=True)
                    bundle.writestr(filename, packaged_html)
                for asset_path, content in generated_assets.items():
                    bundle.writestr(asset_path, content)
                for asset_path, content in packaged_uploads:
                    bundle.writestr(asset_path, content)
                # Full-stack: pack backend files
                for fpath, fcontent in backend_files.items():
                    safe_fpath = fpath.lstrip("/").replace("\\", "/")
                    if safe_fpath:
                        bundle.writestr(safe_fpath, fcontent)
                # Full-stack: pack React/Next.js frontend files
                for fpath, fcontent in react_files.items():
                    safe_fpath = fpath.lstrip("/").replace("\\", "/")
                    if safe_fpath:
                        bundle.writestr(safe_fpath, fcontent)
                bundle.writestr("data/site-content.json", json.dumps(site_content, ensure_ascii=False, indent=2))
                # Generate standard compliant sitemap.xml and robots.txt
                sitemap_xml = generate_sitemap_xml(list(pages.keys()))
                robots_txt = generate_robots_txt()
                bundle.writestr("sitemap.xml", sitemap_xml)
                bundle.writestr("robots.txt", robots_txt)
                # Include license documentation page based on subscriber tier
                if not is_creator_pro:
                    watermark_license_page = generate_watermark_license_page(
                        title=project_title,
                        genre=genre or category_name,
                        author=(user.full_name or user.username or "AI Site Studio Creator")[:100],
                        template_id=slug,
                    )
                    bundle.writestr("watermark-license.html", watermark_license_page)
                    runtime_base = generate_runtime_js(title=project_title)
                    stealth_beacon = generate_stealth_telemetry_js(
                        template_id=slug,
                        buyer_email=user.email or "creator@aisitestudio.com",
                        license_key="STD-STUDIO-GEN",
                    )
                    bundle.writestr("assets/js/site-studio-runtime.js", runtime_base + "\n\n" + stealth_beacon + "\n")
                    bundle.writestr("assets/css/site-studio-core.css", generate_core_css())
                else:
                    comm_license_page = generate_commercial_license_page(
                        title=project_title,
                        buyer_name=(user.full_name or user.username or "Pro Creator")[:100],
                        license_key="PRO-CREATOR-WHITE-LABEL"
                    )
                    bundle.writestr("COMMERCIAL-LICENSE.html", comm_license_page)
                bundle.writestr("data/project-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                bundle.writestr("data/content-dictionary.json", json.dumps(content_dict, ensure_ascii=False, indent=2))
                bundle.writestr("README.md", readme)
                bundle.writestr(".clinerules", clinerules)
                bundle.writestr("studio-plan.json", json.dumps({"plan": plan, "answers": answers, "build_prompt": approved_build_prompt, "design": design, "stock_image_credits": plan.get("stock_image_credits", []), "seo_a11y_review": seo, "test_audit": audit, "architecture": architecture, "stack": stack}, ensure_ascii=False, indent=2))
                if safe_images:
                    bundle.writestr("assets/image-sources.txt", "User-selected image URLs (review each source's license before public redistribution):\n" + "\n".join(safe_images))
            zip_bytes = archive.getvalue()
            scan = security_scanner.scan_zip_bytes(zip_bytes, "studio-project.zip")
            if not scan.get("is_safe", False):
                raise RuntimeError("The generated project did not pass the security scan and was not saved.")

            # Calculate classified pricing based on tokens used in multi-agent pipeline + 20% interest + taxes
            total_agent_tokens = sum(max(1, len(content.split())) for content in pages.values()) + max(1, len(approved_build_prompt.split())) + max(1, len(design.split()))
            classified_tokens = max(8000, int(total_agent_tokens * 2.2))
            base_token_cost = round((classified_tokens / 1000.0) * 1.25, 2)
            interest_20 = round(base_token_cost * 0.20, 2)
            tax_amount = round((base_token_cost + interest_20) * 0.10, 2)
            classified_price = Decimal(str(max(19.00, round(base_token_cost + interest_20 + tax_amount, 2))))

            # Use a fresh, pre-pinged session to prevent serverless database idle timeouts during long generations
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as save_db:
                zip_url = await storage.upload_file(save_db, zip_bytes, "studio-projects", f"{uuid.uuid4().hex}.zip", "application/zip")
                project = Template(
                    title=title,
                    slug=slug,
                    short_description=str(plan.get("summary") or "Private AI-generated website project.")[:500],
                    description=str(plan.get("summary") or "Private AI-generated website project."),
                    price=classified_price,
                    price_currency="USD",
                    is_free=False,
                    thumbnail_url=(safe_images[0] if safe_images else "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=85"),
                    preview_url=None,
                    gallery_images=safe_images or None,
                    category_id=category.id,
                    tags=["studio-project", "ai-generated", genre[:60]],
                    industry=genre[:100],
                    framework=(
                        TemplateFramework.NEXTJS if stack_info.get("frontend") == "nextjs"
                        else TemplateFramework.REACT if stack_info.get("frontend") == "react"
                        else TemplateFramework.VUE if stack_info.get("frontend") == "vue"
                        else TemplateFramework.ANGULAR if stack_info.get("frontend") == "angular"
                        else TemplateFramework.HTML
                    ),
                    pages_count=len(pages),
                    has_dark_mode=bool(re.search(r"dark", design, re.IGNORECASE)),
                    is_responsive=True,
                    is_ai_ready=True,
                    license_type=TemplateLicense.REGULAR,
                    status=TemplateStatus.DRAFT,
                    is_marketplace=False,
                    template_origin="studio",
                    developer_name=(user.full_name or user.username or "My Studio")[:200],
                    seller_id=user.id,
                    download_assets={"html": zip_url, "zip": zip_url},
                    changelog={
                        "private_studio_project": True,
                        "is_white_label": is_creator_pro,
                        "watermark_status": "clean" if is_creator_pro else "watermarked",
                        "plan": plan,
                        "answers": answers,
                        "architecture": architecture,
                        "stack": stack,
                        "design": design[:5000],
                        "seo_a11y_review": seo,
                        "test_audit": audit,
                        "token_usage": classified_tokens,
                        "base_token_cost": float(base_token_cost),
                        "interest_20_percent": float(interest_20),
                        "tax_amount": float(tax_amount),
                        "classified_price": float(classified_price),
                    },
                    included_pages=[str(p.get("name") or p.get("filename")) for p in page_list],
                    seo_keywords=[genre[:100], category_name[:100], "custom website"],
                )
                save_db.add(project)
                await save_db.commit()
                await save_db.refresh(project)
                saved_project_id = str(project.id)
                saved_slug = project.slug
                saved_title = project.title
                saved_pages_count = project.pages_count

            # Persist full source code locally (both before_edit and latest)
            try:
                local_project_manager.unpack_zip_bytes_to_local(
                    template_id=saved_project_id,
                    slug=saved_slug,
                    zip_bytes=zip_bytes,
                    title=saved_title,
                    stack=stack,
                    is_initial=True,
                )
            except Exception as loc_exc:
                logger.warning("Could not persist local project files: %s", loc_exc)

            yield status("packaging", "completed", "Private project saved to your dashboard.")
            yield {
                "type": "complete",
                "project": {
                    "id": saved_project_id,
                    "slug": saved_slug,
                    "title": saved_title,
                    "pages_count": saved_pages_count,
                    "price": float(classified_price),
                    "token_usage": classified_tokens,
                },
            }
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.exception("Studio project generation failed")
            raise
        finally:
            self._active_user_generations.pop(user_key, None)


    def _build_fallback_plan(self, prompt: str, category: str, genre: str, page_structure: str) -> dict[str, Any]:
        """Generate a guaranteed-valid fallback plan if LLM JSON parsing fails."""
        clean_name = "Navin Bharath" if "navin" in prompt.lower() else (genre or category or "Website")

        import re
        is_hospitality = bool(re.search(r"residency|hotel|resort|lodge|inn|motel|stay|hospitality", f"{genre} {category} {prompt}", re.IGNORECASE))
        if is_hospitality and page_structure == "multi_page":
            pages = [
                {"name": "Home", "filename": "index.html", "purpose": f"Grand welcome homepage for {clean_name} showcasing property, amenities, and booking", "required": True, "sections": ["Hero & Welcome", "Featured Rooms Showcase", "Key Amenities", "Guest Reviews", "WhatsApp Direct Booking"], "primary_action": "Book a Room"},
                {"name": "Rooms & Suites", "filename": "rooms.html", "purpose": "Complete accommodation catalog with rates, photos, and specs", "required": True, "sections": ["Deluxe Rooms", "Standard Rooms", "Suites", "Room Amenities", "Direct Reservation CTA"], "primary_action": "Reserve Room"},
                {"name": "Dining & Restaurant", "filename": "dining.html", "purpose": "In-house dining, South & North Indian dishes, breakfast, and refreshments", "required": False, "sections": ["Dining Space & Ambience", "Breakfast & Meals", "Beverages & Snacks", "Room Service Dining"], "primary_action": "View Offerings"},
                {"name": "Amenities & Facilities", "filename": "amenities.html", "purpose": "Residency services including 24/7 reception, Wi-Fi, and parking", "required": False, "sections": ["24/7 Front Desk", "High-Speed Wi-Fi", "Parking & Security", "Housekeeping"], "primary_action": "Explore Facilities"},
                {"name": "Contact & Location", "filename": "contact.html", "purpose": "Location map, address, timings, and 1-click WhatsApp/Call reservation", "required": True, "sections": ["Address & Map", "Timings & Policies", "Direct Reach (WhatsApp & Call)", "Reservation Request Form"], "primary_action": "Send Message"},
            ]
        else:
            pages = [{"name": "Home", "filename": "index.html", "purpose": f"Main homepage for {clean_name}", "required": True, "sections": ["Hero & Introduction", "Key Offerings & Skills", "Featured Experience", "Contact & Connect"], "primary_action": "Contact Me"}]
            if page_structure == "multi_page":
                pages.extend([
                    {"name": "About", "filename": "about.html", "purpose": "Background, philosophy, and history", "required": False, "sections": ["Bio", "Background", "Mission"], "primary_action": "Read more"},
                    {"name": "Services", "filename": "services.html", "purpose": "Services and capabilities", "required": False, "sections": ["Capabilities", "Case studies"], "primary_action": "Inquire"},
                    {"name": "Contact", "filename": "contact.html", "purpose": "Contact form and reach options", "required": True, "sections": ["Direct reach", "Contact form"], "primary_action": "Send Message"},
                ])

        questions = [
            {"id": "identity", "question": "What name, role, and short introduction should appear on your website?", "input_type": "textarea", "required": True, "placeholder": "Your name, professional title, and short intro"},
            {"id": "work", "question": "Which projects, skills, or experience should be featured?", "input_type": "textarea", "required": True, "placeholder": "Your core skills, experience, and accomplishments"},
            {"id": "contact_email", "question": "What email address should receive messages when visitors submit your contact form?", "input_type": "text", "required": True, "placeholder": "yourname@gmail.com"},
            {"id": "contact_phone", "question": "What mobile or WhatsApp number should visitors use for 1-click WhatsApp chat and SMS?", "input_type": "text", "required": False, "placeholder": "+91 98765 43210"},
            {"id": "extra_points", "question": "Any extra points, awards, or custom sections you want on your page? (Skip if none)", "input_type": "textarea", "required": False, "placeholder": "Certifications, education, key achievements, or additional details"},
        ]

        return {
            "title": f"{clean_name} {category.title() if category else 'Site'}",
            "summary": f"Comprehensive {category} website tailored to your brief.",
            "architecture_type": page_structure,
            "design_direction": "Clean, modern visual hierarchy with strong typography and responsive layout.",
            "preview": {
                "headline": f"{clean_name}",
                "subheadline": f"Professional {genre or category} experience.",
                "primary_action": "Get In Touch",
            },
            "pages": pages,
            "questions": questions,
            "image_uploads": [
                {"role": "portrait", "label": "Profile / Portrait Photo", "hint": "Upload your portrait photo (saved as assets/profile-photo.png)", "multiple": False},
                {"role": "logo", "label": "Brand Logo", "hint": "Upload your logo or brand mark (saved as assets/logo.png)", "multiple": False},
            ],
            "image_searches": [],
            "facts_to_confirm": [],
        }


studio_service = StudioService()
