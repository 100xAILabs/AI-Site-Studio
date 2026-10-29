"""Agentic, page-by-page website creation for private Studio projects."""

import io
import json
import logging
import posixpath
import re
import time
import uuid
import zipfile
from html.parser import HTMLParser
from typing import Any, AsyncIterator
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
CODE_PROVIDER_ORDER = ["gemini", "cline", "groq"]
STUDIO_CLINERULES = """# Studio website code rules
- Follow the approved brief, plan, owner answers, and UI design system.
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
    selected_type = f"{category} {genre}".lower()
    prompt_text = prompt.lower()
    construction_re = r"construction|contractor|building company|roofing|remodel(?:ing)?|renovation|home improvement|(?:home|house|custom|commercial|residential) builder"
    portfolio_re = r"\bportfolio\b|\bresume\b|résumé|\bcv\b|personal\s+(?:site|website)\b|photographer\s+portfolio"
    other_site_re = r"\b(?:tea|restaurant|cafe|coffee|bakery|food|dining|shop|store|e-?commerce|real estate|property|realtor|event|conference|festival|wedding|school|education|course|training|academy|university|health|clinic|medical|dental|wellness|therapy|hotel|travel|tour|hospitality|salon|beauty|fitness|gym|agency|consulting|software|saas|app|blog|publication|nonprofit|charity)\b"
    if re.search(construction_re, prompt_text):
        return "construction"
    explicit_portfolio_request = r"(?:portfolio\s+(?:website|site|homepage|landing page)|(?:personal|photography|designer|developer|creative)\s+portfolio|(?:build|create|make|design)\s+(?:me\s+)?(?:a\s+)?portfolio\b|resume\s+(?:website|site)|résumé\s+(?:website|site)|\bcv\s+(?:website|site))"
    if re.search(explicit_portfolio_request, prompt_text):
        return "portfolio"
    if re.search(other_site_re, prompt_text):
        return "general"
    if re.search(construction_re, selected_type):
        return "construction"
    if re.search(portfolio_re, selected_type):
        return "portfolio"
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
        return "PORTFOLIO QUALITY BAR: Honor the selected page structure. Build a polished personal brand with a distinctive introduction using the owner's real name and role, selected work with case-study context, skills/tools, experience or education when supplied, and a clear contact path. Use uploaded portrait, skill/tool, and project images according to their roles. Never fabricate clients, outcomes, qualifications, metrics, or testimonials. Use expressive editorial art direction and purposeful motion while keeping the work easy to scan."
    if profile == "construction":
        return "CONSTRUCTION QUALITY BAR: Build a credible contractor site with a clear estimate/contact path, service area, practical service categories, and real completed-project proof. For a multi-page site, prefer Home, Services, Projects, and Contact/Request an Estimate; add About only when the brief supports it. Use uploaded project, team, and equipment images in their matching roles. Never invent licenses, insurance, safety records, years in business, project values, client names, reviews, or guarantees. Use confident architectural art direction, clear project details, and restrained purposeful motion."
    return "GENERAL QUALITY BAR: Identify the site's actual industry and main visitor task, then choose art direction and page structure that fit that use. Avoid default SaaS styling, repeated generic cards, filler content, and fabricated facts. Use supplied images in their stated roles and purposeful motion throughout the experience."

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
        r'(?:portfolio|website|resume|cv)\s+for\s+([A-Z][a-zA-Z\s]{1,30}?)(?=[,.\n]|\s+with|\s+who|\s+is|\s+a\b|$)',
        r"(?:my name is|i am|i'm)\s+([A-Z][a-zA-Z\s]{1,30}?)(?=[,.\n]|$)",
        r'\b([A-Z][a-zA-Z0-9\s]{1,25}\s+(?:Residency|Hotel|Resort|Lodge|Inn|Studio|Agency|Technologies|Solutions|Cafe|Bistro|Restaurant|Clinic|Store|Shop))\b',
    ]
    for np in name_patterns:
        m = re.search(np, prompt, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate and len(candidate.split()) <= 4:
                details["name"] = candidate.title()
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

def _stack_guidance(stack: str) -> str:
    stack_info = SUPPORTED_STACKS.get(stack) or SUPPORTED_STACKS.get("html-css-js", {})
    frontend = stack_info.get("frontend")
    backend = stack_info.get("backend")
    db = stack_info.get("db")
    label = stack_info.get("label", "Static (HTML / CSS / JS)")

    if stack == "nextjs-fastapi-postgresql":
        return f"""SELECTED TECH STACK: {label} (Next.js 14 App Router + FastAPI + PostgreSQL)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: Next.js 14 App Router (TypeScript, Tailwind CSS, Lucide React icons)
  * Root Layout: frontend/app/layout.tsx (fonts, global styles, sticky Navbar, Footer)
  * Page Routes: frontend/app/page.tsx (Home), and frontend/app/<route>/page.tsx for each interior page (e.g. frontend/app/rooms/page.tsx, frontend/app/about/page.tsx)
  * Client Components: frontend/components/ (Navbar, Footer, room cards, booking/inquiry forms, date pickers, modals)
  * API Integration: frontend/lib/api.ts typed fetch wrapper connected to NEXT_PUBLIC_API_URL
- Production Backend: FastAPI (Python 3.12) REST API
  * Models: backend/app/models.py (SQLAlchemy 2.0 async mapped ORM models with PostgreSQL)
  * Schemas: backend/app/schemas.py (Pydantic v2 validation models)
  * REST Endpoints: backend/app/routes/ (e.g. GET /api/rooms, POST /api/bookings, POST /api/contact, GET /api/health)
  * Database Connection: backend/app/database.py (async connection pool)
  * Migrations: Alembic async migrations
- Live Studio Browser Canvas Mirror:
  * For instant in-browser live canvas editing and zero-install preview in AI Site Studio, a responsive static HTML mirror (index.html, etc.) is generated alongside the full-stack codebase.
  * DO NOT restrict the project prompt to 'Plain HTML/CSS/JS only'. Clearly specify both the Next.js 14 App Router + FastAPI + PostgreSQL production codebase AND the preview mirror."""

    if stack == "nextjs-nestjs-postgresql":
        return f"""SELECTED TECH STACK: {label} (Next.js 14 App Router + NestJS + PostgreSQL - TypeScript End-to-End)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: Next.js 14 App Router (TypeScript, Tailwind CSS, Lucide React icons)
  * Root Layout: frontend/app/layout.tsx (fonts, global styles, sticky Navbar, Footer)
  * Page Routes: frontend/app/page.tsx (Home), and frontend/app/<route>/page.tsx for each interior page
  * Client Components: frontend/components/ (Navbar, Footer, interactive forms, modals, carousels)
  * API Integration: frontend/lib/api.ts typed fetch wrapper connected to NEXT_PUBLIC_API_URL
- Production Backend: NestJS Enterprise TypeScript REST API
  * App Root: backend/src/app.module.ts, backend/src/main.ts (Bootstrap with CORS, ValidationPipe)
  * Entities: backend/src/entities/ (TypeORM entity classes with PostgreSQL)
  * DTOs: backend/src/dto/ (class-validator typed DTOs for request validation)
  * Modules: backend/src/<resource>/ (module, controller, and service per resource group)
  * Endpoints: POST /api/contact, POST /api/inquiries, POST /api/newsletter, GET /api/health
  * Database: TypeORM async connection pool
- Live Studio Browser Canvas Mirror:
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio.
  * DO NOT restrict the project prompt to 'Plain HTML/CSS/JS only'. Document the Next.js + NestJS + PostgreSQL architecture."""

    if stack == "react-fastapi-postgresql":
        return f"""SELECTED TECH STACK: {label} (React 18 + FastAPI + PostgreSQL - Emergent Standard)
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
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio.
  * DO NOT restrict the project prompt to 'Plain HTML/CSS/JS only'. Document the React + FastAPI + PostgreSQL architecture."""

    if stack == "react-fastapi-mongodb":
        return f"""SELECTED TECH STACK: {label} (React 18 + FastAPI + MongoDB - Emergent FARM Stack)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: React 18 + TypeScript + Vite + Tailwind CSS + React Router v6
  * App Entry: frontend/src/main.tsx, frontend/src/App.tsx
  * Page Components: frontend/src/pages/<Page>.tsx
  * Interactive UI Components: frontend/src/components/ (Navbar, Footer, interactive forms)
  * API Integration: frontend/src/api/client.ts (Axios instance connected to VITE_API_URL)
- Production Backend: FastAPI (Python 3.12) + Motor (Async MongoDB)
  * Driver: Async Motor AsyncIOMotorClient in backend/app/database.py
  * Models: backend/app/models.py (Pydantic v2 document models with Mongo ObjectId serialization)
  * Schemas: backend/app/schemas.py (Request/response validation schemas)
  * REST Endpoints: backend/app/routes/ (POST /api/contact, POST /api/inquiries, GET /api/health)
  * Config: Pydantic Settings reading MONGO_URI and DATABASE_NAME
- Live Studio Browser Canvas Mirror:
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio.
  * DO NOT restrict the project prompt to 'Plain HTML/CSS/JS only'. Document the FARM stack architecture."""

    if stack == "react-express-mongodb":
        return f"""SELECTED TECH STACK: {label} (React 18 + Express.js + MongoDB - MERN Stack)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: React 18 + TypeScript + Vite + Tailwind CSS + React Router v6
  * App Entry: frontend/src/main.tsx, frontend/src/App.tsx
  * Page Components: frontend/src/pages/<Page>.tsx
  * Interactive UI Components: frontend/src/components/ (Navbar, Footer, interactive forms)
  * API Integration: frontend/src/api/client.ts (Axios instance connected to VITE_API_URL)
- Production Backend: Node.js Express.js REST API + Mongoose
  * Server Entry: backend/src/server.js, backend/src/app.js (Express app factory with CORS & JSON body parser)
  * Models: backend/src/models/ (Mongoose schemas and models)
  * Routes: backend/src/routes/ (Express routers for /api/contact, /api/inquiries, /api/health)
  * Middleware: backend/src/middleware/ (JWT auth verify, error handler)
  * Database: backend/src/config/database.js (Mongoose connect)
- Live Studio Browser Canvas Mirror:
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio.
  * DO NOT restrict the project prompt to 'Plain HTML/CSS/JS only'. Document the MERN architecture."""

    if stack == "react-django-postgresql":
        return f"""SELECTED TECH STACK: {label} (React 18 + Django REST Framework + PostgreSQL)
FULL-STACK ARCHITECTURE SPECIFICATION:
- Production Frontend: React 18 + TypeScript + Vite + Tailwind CSS + React Router v6
  * App Entry: frontend/src/main.tsx, frontend/src/App.tsx
  * Page Components: frontend/src/pages/<Page>.tsx
  * Interactive UI Components: frontend/src/components/
  * API Integration: frontend/src/api/client.ts
- Production Backend: Django 5 + Django REST Framework (DRF) + PostgreSQL
  * Models: backend/<app_name>/models.py (Django ORM models)
  * Serializers: backend/<app_name>/serializers.py (ModelSerializers)
  * Views: backend/<app_name>/views.py (DRF ViewSets/APIViews)
  * Routes: backend/<app_name>/urls.py and backend/config/urls.py
- Live Studio Browser Canvas Mirror:
  * Responsive static HTML mirror (index.html, etc.) for zero-install preview in AI Site Studio."""

    return """SELECTED TECH STACK: Static Website (HTML5 / CSS3 / Vanilla JavaScript)
ARCHITECTURE SPECIFICATION:
- Semantic HTML5, modern vanilla CSS3, responsive layouts, zero external UI framework dependencies.
- Filenames: index.html (Home) and clean interior page files."""


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
    "portfolio": [
        "photo-1498050108023-c5249f4df085", "photo-1507238691740-187a5b1d37b8", "photo-1545235617-9465d2a55698",
    ],
    "construction": [
        "photo-1504307651254-35680f356dfd", "photo-1541888946425-d81bb19240f5", "photo-1486406146926-c627a92ad1ab",
    ],
    "general": [
        "photo-1497366754035-f200968a6e72", "photo-1497366811353-6870744d04b2", "photo-1497366216548-37526070297c",
    ],
}


def _curated_stock_assets(profile: str, genre: str) -> list[dict[str, str]]:
    image_ids = CURATED_STOCK_IMAGES.get(profile, CURATED_STOCK_IMAGES["general"])
    return [
        {
            "role": "general" if profile == "portfolio" else "project" if profile == "construction" else "general",
            "url": f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1440&q=85",
            "alt": f"Illustrative Unsplash stock photo for {genre}; not a verified image of the site owner or their work",
            "source_name": "Unsplash",
            "source_url": "https://unsplash.com/",
        }
        for photo_id in image_ids
    ]


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


def _wrong_homepage(html: str) -> bool:
    heading = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    if not heading:
        return True
    text = re.sub(r"<[^>]+>", " ", heading.group(1)).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return any(term in text for term in ("about us", "about me", "our story", "contact us", "get in touch", "our products", "all products"))


class StudioService:
    def __init__(self):
        self._active_user_generations: set[str] = set()
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
        searches = [
            str(item.get("query") or "").strip()
            for item in (plan.get("image_searches") or [])
            if isinstance(item, dict) and str(item.get("query") or "").strip()
        ]
        if not searches:
            if profile == "portfolio":
                searches = ["creative portfolio workspace", "graphic design studio project" ]
            elif profile == "construction":
                searches = ["construction site building project", "architecture construction workers" ]
            else:
                searches = [f"{genre} professional website photography", f"{genre} business environment" ]

        stock_assets: list[dict[str, str]] = []
        for query in searches[:3]:
            hits = await self._pixabay_hits(query)
            for hit in hits[:3]:
                if len(stock_assets) >= 8:
                    break
                try:
                    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                        response = await client.get(hit["image_url"])
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    content = response.content
                    if content_type not in {"image/jpeg", "image/png", "image/webp"} or not content or len(content) > 8 * 1024 * 1024:
                        continue
                    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
                    stored_url = await storage.upload_file(
                        db=db,
                        file_content=content,
                        folder="studio-stock",
                        original_filename=f"pixabay-stock-{uuid.uuid4().hex[:12]}{extension}",
                        content_type=content_type,
                    )
                    stock_assets.append({
                        "role": "project" if profile == "construction" else "general",
                        "url": stored_url,
                        "alt": f"Illustrative stock photo: {hit['tags']}; not a verified image of the owner or their work",
                        "source_name": "Pixabay",
                        "source_url": hit["page_url"],
                        "credit": f"Photo by {hit['photographer']} on Pixabay",
                    })
                except Exception as exc:
                    logger.info("Could not store a Pixabay stock image: %s", type(exc).__name__)
            if len(stock_assets) >= 8:
                break

        if stock_assets:
            return stock_assets
        return _curated_stock_assets(profile, genre)

    async def plan(self, prompt: str, category: str, genre: str, page_structure: str = "multi_page", stack: str = "html-css-js") -> dict[str, Any]:
        profile = _site_profile(category, genre, prompt)
        profile_guidance = _profile_guidance(profile)
        stack_guidance = _stack_guidance(stack)

        # Pre-extract all facts and entities already supplied in the user's prompt
        extracted_facts = _extract_prompt_details(prompt)
        extracted_lines = [f"- {k.replace('_', ' ').title()}: {v}" for k, v in extracted_facts.items() if v]
        extracted_summary = "\n".join(extracted_lines) if extracted_lines else "None explicitly extracted; prompt asks for fresh structure."

        request = f"""Create a useful, detailed website plan for this user request.
The user selected marketplace category: {category}
The user selected genre/site type: {genre}
The user explicitly chose this architecture: {page_structure}. For single_page, create one Home page only and organize all requested content as sections on that page. For multi_page, create a Home page plus distinct, relevant interior pages (at least two pages total when the brief supports it).
{profile_guidance}
{stack_guidance}
User brief:
<brief>{prompt[:100000]}</brief>

ALREADY-EXTRACTED FACTS FROM USER PROMPT (CRITICAL — DO NOT ASK FOR THESE):
{extracted_summary}

DYNAMIC MULTI-CATEGORY SITEMAP INSTRUCTIONS:
- Tailor the pages directly to the specific industry in the user's prompt (1-8 pages total):
  * Portfolio / CV / Personal: Home (index.html), About & Bio (about.html), Projects & Case Studies (projects.html), Skills & Tools (skills.html), Contact (contact.html)
  * SaaS / Tech Product: Home (index.html), Features & Architecture (features.html), Pricing & Tiers (pricing.html), About / Docs (about.html), Contact / Demo (contact.html)
  * E-Commerce / Store: Home (index.html), Shop Catalog (shop.html), Collections (collections.html), About Our Story (about.html), Contact & Help (contact.html)
  * Restaurant / Cafe / Dining: Home (index.html), Food & Drink Menu (menu.html), About / Our Chef (about.html), Reservations & Location (contact.html)
  * Agency / Consulting / Studio: Home (index.html), Services (services.html), Case Studies (work.html), Team (team.html), Contact & Quote (contact.html)
  * Real Estate / Property: Home (index.html), Featured Listings (listings.html), Neighborhoods (neighborhoods.html), About Agents (about.html), Contact (contact.html)
  * Healthcare / Medical / Clinic: Home (index.html), Treatments & Care (treatments.html), Specialists & Team (team.html), Book Appointment (contact.html)
  * Residency / Hotel / Hospitality: Home (index.html), Rooms & Suites (rooms.html), Dining & Restaurant (dining.html), Amenities (amenities.html), Contact & Location (contact.html)
  * Education / Academy / Courses: Home (index.html), Course Offerings (courses.html), Admissions & Pricing (admissions.html), Contact (contact.html)
  * Fitness / Gym / Yoga / Studio: Home (index.html), Classes & Programs (classes.html), Membership & Pricing (pricing.html), Trainers (trainers.html), Contact (contact.html)
- Preserve interior page filenames. For each page provide a page-specific outline and primary action.

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
4. Ask 2 to 4 clarifying questions ONLY for information that is TRULY MISSING from the prompt. If the prompt is already comprehensive, ask only 1-2 preference questions (e.g. primary call-to-action text or preferred visual tone).

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
        # Match questions against extracted details to prefill answers
        prefilled_answers = {}
        for q in data.get("questions", []):
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id") or "").lower()
            qtext = str(q.get("question") or "").lower()
            if ("email" in qid or "email" in qtext) and "contact_email" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["contact_email"]
            elif ("phone" in qid or "whatsapp" in qid or "phone" in qtext or "whatsapp" in qtext) and "contact_phone" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["contact_phone"]
            elif ("name" in qid or "identity" in qid or "name" in qtext) and "name" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["name"]
            elif ("price" in qid or "rate" in qid or "price" in qtext or "rate" in qtext) and "pricing" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["pricing"]
            elif ("address" in qid or "location" in qid or "address" in qtext) and "address" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["address"]
            elif ("timing" in qid or "hour" in qid or "check" in qtext or "timing" in qtext) and "timings" in extracted_facts:
                prefilled_answers[q.get("id")] = extracted_facts["timings"]

        data["prefilled_answers"] = prefilled_answers
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
        if profile == "portfolio" and len(data["questions"]) < 3:
            fallback_questions = [
                {"id": "identity", "question": "What name, role, and short introduction should appear on your portfolio?", "input_type": "textarea", "required": True, "placeholder": "Your name, professional title, and short intro"},
                {"id": "work", "question": "Which projects or work experience should be featured? (Share your role, technologies used, and company or client)", "input_type": "textarea", "required": True, "placeholder": "Role, company/client, technologies used, and key accomplishments"},
                {"id": "skills", "question": "Which skills and tools should be highlighted?", "input_type": "textarea", "required": True, "placeholder": "e.g. Python, SQL, React, DevOps"},
                {"id": "contact_email", "question": "What email address should receive messages when visitors submit your contact form?", "input_type": "text", "required": True, "placeholder": "yourname@gmail.com"},
                {"id": "contact_phone", "question": "What mobile or WhatsApp number should visitors use for 1-click WhatsApp chat and SMS? (Include country code)", "input_type": "text", "required": False, "placeholder": "+91 98765 43210"},
                {"id": "extra_points", "question": "Any extra points, awards, or custom sections you want on your page? (Skip if none)", "input_type": "textarea", "required": False, "placeholder": "Certifications, education, key achievements, or additional details"},
            ]
        elif profile == "construction" and len(data["questions"]) < 3:
            fallback_questions = [
                {"id": "company", "question": "What is the company name and short introduction?", "input_type": "textarea", "required": True, "placeholder": "Business name and verified background"},
                {"id": "services", "question": "Which construction services do you provide, and for what kinds of clients?", "input_type": "textarea", "required": True, "placeholder": "Residential/commercial services and specialties"},
                {"id": "service_area", "question": "Which cities or regions do you serve?", "input_type": "textarea", "required": True, "placeholder": "Real service locations only"},
                {"id": "projects", "question": "Which completed projects should be featured? Share their type, location, scope, and any public link.", "input_type": "textarea", "required": True, "placeholder": "Verified project details only"},
                {"id": "credentials", "question": "Which licenses, insurance details, safety credentials, or memberships may be published? Leave blank if none.", "input_type": "textarea", "required": False, "placeholder": "Only verified credentials"},
                {"id": "estimate_contact", "question": "How should customers request an estimate or contact your team?", "input_type": "textarea", "required": True, "placeholder": "Phone, email, office hours, or booking link"},
            ]
        elif len(data["questions"]) < 3:
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
        data["questions"] = fallback_questions
        allowed_image_roles = {"portrait", "skills", "project", "team", "equipment", "general"}
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
        stack: str = "html-css-js",
    ) -> str:
        profile_guidance = _profile_guidance(_site_profile(category, genre, prompt))
        stack_guidance = _stack_guidance(stack)
        request = f"""You are the Planning Agent. Create the complete, editable project prompt that will be shown to the user and then passed directly to code-generation agents.
Original request: <brief>{prompt[:100000]}</brief>
Category/site type: {category} / {genre}
Chosen architecture: {page_structure}
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
6. Real Content & Working Actions (use owner answers for email, mobile, phone, address, and amenities/skills)
7. Image Placement & Motion System
8. Acceptance Criteria

Make the site distinctive, polished, responsive, and visibly animated with a coherent motion system and reduced-motion support. Use owner answers as source of truth. Never invent facts, credentials, testimonials, prices, results, or backend behavior. Avoid generic filler, broken links/images, repeated card grids, and browser-default styling. No code fences. Output only the editable prompt, plain text, 900-6500 words maximum (prefer 1200-2200 words)."""
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
        category_id: uuid.UUID,
        category_name: str,
        genre: str,
        plan: dict[str, Any],
        answers: dict[str, Any],
        image_urls: list[str],
        image_assets: list[dict[str, str]] | None = None,
        build_prompt: str = "",
        stack: str = "html-css-js",
    ) -> AsyncIterator[dict[str, Any]]:
        category = await db.get(Category, category_id)
        if not category or not category.is_active:
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
        if user_key in self._active_user_generations:
            raise ValueError("A Studio build is already running for this account. Wait for it to finish before starting another.")
        self._active_user_generations.add(user_key)
        try:
            yield status("planning", "completed", "Using your reviewed build prompt directly as the source of truth.")
            build_brief = approved_build_prompt

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
Specify exact palette, typography, spacing, layout grid, components, responsive breakpoints, image treatment, interaction states, and purposeful animations. Include keyboard focus and prefers-reduced-motion rules. Never invent facts. Make the design usable across every listed page. Return concise implementation guidance, not source code."""
            design = await ai_service._generate_content(
                design_prompt, response_mime_type="text/plain", feature_name="designer_agent",
                preferred_provider="groq", provider_order_override=ANALYSIS_PROVIDER_ORDER,
                request_timeout_seconds=60.0, max_local_model_attempts=1,
            )
            yield status("design", "completed", "Shared design system ready.")

            # ----------------------------------------------------------------
            # Full-stack generation: Architect + DB Schema + Backend Dev agents
            # ----------------------------------------------------------------
            backend_files: dict[str, str] = {}
            architecture: dict[str, Any] = {}
            is_fullstack = stack and stack != "html-css-js"

            if is_fullstack:
                yield {"type": "agent", "agent": AGENTS["architect"], "status": "running", "detail": f"Designing database schema and API routes for {stack} stack…"}
                try:
                    architecture = await backend_generator.generate_architecture(prompt, stack, plan)
                    table_count = len(architecture.get("db_tables", []))
                    route_count = len(architecture.get("api_routes", []))
                    yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": f"Architecture ready: {table_count} DB table(s), {route_count} API route(s)."}
                except Exception as arch_exc:
                    logger.warning("Architect Agent failed: %s. Proceeding with minimal architecture.", arch_exc)
                    architecture = {"db_tables": [], "api_routes": [], "auth_strategy": "none", "stripe_needed": False, "stripe_flows": [], "frontend_components": [], "tech_notes": ""}
                    yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": "Architecture planning used fallback (AI unavailable). Proceeding."}

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
                yield {"type": "agent", "agent": AGENTS["architect"], "status": "completed", "detail": "Static architecture selected (pure client-side application)."}
                yield {"type": "agent", "agent": AGENTS["database"], "status": "completed", "detail": "Static site selected (zero database dependencies needed)."}
                yield {"type": "agent", "agent": AGENTS["backend"], "status": "completed", "detail": "Static site selected (no backend server required)."}

            safe_assets = [
                asset for asset in (image_assets or [])
                if isinstance(asset, dict)
                and asset.get("role") in {"portrait", "skills", "project", "team", "equipment", "general"}
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
                if any(k in role_raw for k in ("portrait", "profile", "avatar", "person", "headshot")):
                    stem = "profile-photo"
                elif "logo" in role_raw:
                    stem = "logo"
                elif any(k in role_raw for k in ("hero", "banner", "cover")):
                    stem = "hero-banner"
                elif any(k in role_raw for k in ("project", "work")):
                    stem = f"project-{len(packaged_uploads) + 1:02d}"
                else:
                    stem = f"owner-uploaded-{len(packaged_uploads) + 1:02d}"

                if any(p[0].startswith(f"assets/{stem}") for p in packaged_uploads):
                    stem = f"{stem}-{len(packaged_uploads) + 1:02d}"

                asset_path = f"assets/{stem}{extension}"
                local_asset_paths[asset_url] = asset_path
                packaged_uploads.append((asset_path, content))
            image_context_lines = [
                f"- Owner uploaded {asset['role']} image file: {local_asset_paths.get(asset['url'], asset['url'])} (alt: {str(asset.get('alt') or asset['role'])[:200]}). CRITICAL: You MUST render this image in the appropriate section using <img src=\"{local_asset_paths.get(asset['url'], asset['url'])}\">."
                for asset in safe_assets
            ]
            image_context_lines.extend(
                f"- Illustrative stock photo: {asset['url']} (alt: {asset.get('alt', 'illustrative stock image')}; credit: {asset.get('credit', asset.get('source_name', 'stock source'))}; source: {asset.get('source_url', 'source URL unavailable')}). Do not present this as the owner's real work, team, or portrait."
                for asset in stock_assets
            )
            remaining_slots = max(0, 16 - len(safe_assets))
            image_context_lines.extend(f"- User-selected image URL: {url}" for url in safe_urls[:remaining_slots])
            image_context = "\n".join(image_context_lines) or "No owner-selected images. Use relevant, clearly illustrative remote stock images and descriptive alt text; never claim they depict the owner or their customers."
            # ── React / Next.js frontend for full-stack stacks ──────────────
            react_files: dict[str, str] = {}
            stack_info = SUPPORTED_STACKS.get(stack, {})
            if is_fullstack and stack_info.get("frontend") in {"react", "nextjs"}:
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

            pages: dict[str, str] = {}
            # Generate all planned pages (up to 8) to create a comprehensive, multi-page experience
            page_list = plan.get("pages", [])[:8]
            for index, page in enumerate(page_list):
                page_name = str(page.get("name") or f"Page {index + 1}")
                filename = _filename(page.get("filename", ""), index, page_name)
                yield {"type": "page", "status": "running", "index": index + 1, "total": len(page_list), "name": page_name, "filename": filename}
                compact_sitemap = [
                    {key: item.get(key) for key in ("name", "filename", "purpose") if item.get(key)}
                    for item in page_list
                    if isinstance(item, dict)
                ]
                page_prompt = f"""You are the Frontend Dev Agent. Implement exactly one complete, production-quality, responsive HTML page. This is a separate page-by-page build; do not emit other pages or explanations.
Original user brief highlights: <brief>{prompt[:3000]}</brief>
Category: {category_name}; genre: {genre}
User-approved build prompt (authoritative; follow it directly): {build_brief[:18000]}
{profile_guidance}
Page plan: {json.dumps(page, ensure_ascii=False)}
Root-page rule: index.html is the real homepage for the whole requested site. Build a welcoming, site-specific hero and key offering sections for the exact brief. Never make it an About, Contact, Products listing, or blog detail page. Interior pages must focus only on their named purpose.
Full sitemap for consistent navigation: {json.dumps(compact_sitemap, ensure_ascii=False)[:3000]}
Owner answers relevant to this page: {json.dumps(answers, ensure_ascii=False)[:3500]}
UI Designer system: {design[:2500]}
User and automatically sourced image assets: {image_context}
CRITICAL CONTENT ACCURACY DIRECTIVE:
- You MUST faithfully use the user's EXACT provided skills, tools, and background from 'Owner answers' and 'User-approved build prompt'.
- If the user provided specific skills (e.g. Python, SQL, React, DevOps), you MUST display those exact skills. NEVER replace them with generic industry tropes or invent unverified metrics, years of experience, or certifications.
- If the user provided only ONE work experience or role, feature that single role thoroughly with deep impact and real technical skills. NEVER invent fake past companies or extra timeline jobs to fill space.
- If an owner-uploaded image is provided in 'User and automatically sourced image assets', you MUST embed it directly using an <img> tag referencing its relative file path (e.g. <img src="assets/profile-photo.png" alt="...">). Never replace it with a text avatar or omit it.
- CRITICAL CONTACT & MESSAGING DIRECTIVE:
  * If an email is provided in 'Owner answers' or brief, the contact form and email links MUST use that exact email. NEVER use fake placeholder emails like 'info@example.com'.
  * For contact forms: Wire the form to submit to the owner's email address (e.g. action="https://api.web3forms.com/submit" or a working submission script that sends to that email, or mailto: fallback). Include a direct clickable button: <a href="mailto:OWNER_EMAIL">Email Me</a>.
  * If a mobile/phone number is provided in 'Owner answers' or brief:
    1. Render a 1-click WhatsApp chat button: <a href="https://wa.me/CLEAN_PHONE?text=Hi%2C%20I%20saw%20your%20portfolio%20and%20would%20like%20to%20connect!" target="_blank" rel="noopener">Chat on WhatsApp</a>.
    2. Render a 1-click SMS button: <a href="sms:CLEAN_PHONE?body=Hi%2C%20I%20would%20like%20to%20connect!">Send SMS</a>.
    3. Render a Call link: <a href="tel:CLEAN_PHONE">Call</a>.
{STUDIO_CLINERULES}
Output a full standalone HTML document for {filename}, with semantic markup, page-specific content, responsive inline CSS, and working browser-side interactions. Include complete head, body, style, and script blocks as needed; never return browser-default unstyled HTML. Use the UI Designer system as a concrete specification, and keep the same header, navigation, footer, typography, and design tokens used by the other generated pages. Build a clear visual hierarchy with deliberate whitespace, strong editorial composition, and restrained detail; use varied layouts instead of repeated card grids. Keep the page polished but concise enough to finish as valid HTML. Include SEO title/description, social metadata, clear relative navigation links using the supplied page filenames, descriptive image alt text, visible focus, keyboard access, and prefers-reduced-motion. Add purposeful animation that honors reduced motion. Make visible controls work in the browser or label them as demo-only; never invent testimonials, stats, credentials, prices, or success states. Forms must say when they are demo-only. Use supplied direct image URLs in relevant visual sections; preserve stock photo credits. Never use a Google search/results URL as an image source. Do not load frameworks, CDNs, tracking, or server APIs. Return HTML only, including the closing </body> and </html> tags."""
                recovery_prompt = f"""The previous page response was incomplete. Regenerate a complete, concise standalone HTML document for {filename}; do not explain or continue with fragments.
Brief highlights: {prompt[:1800]}
Approved project requirements: {build_brief[:9000]}
Page plan: {json.dumps(page, ensure_ascii=False)[:3500]}
Sitemap: {json.dumps(compact_sitemap, ensure_ascii=False)[:1800]}
Design system: {design[:1800]}
Owner details: {json.dumps(answers, ensure_ascii=False)[:2500]}
Images: {image_context[:2500]}
Rules: Use semantic, responsive HTML with a complete head, body, style, and script where needed. Match the named page only. Include working relative navigation, accessible focus, alt text, and reduced-motion support. Do not invent facts. Limit section count and prose so the full document fits in one response. Return HTML only and include the exact closing </body></html> tags."""
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
                    raw_html = await ai_service._generate_content(
                        active_page_prompt, response_mime_type="text/plain", feature_name="website_frontend_generation",
                        preferred_provider="gemini", provider_order_override=CODE_PROVIDER_ORDER,
                        request_timeout_seconds=600.0, max_local_model_attempts=2,
                        on_provider_success=lambda provider, model: provider_info.update(provider=provider, model=model),
                    )
                    if provider_info:
                        yield {"type": "model", "stage": "frontend", "page": filename, **provider_info}
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
                yield {"type": "page", "status": "completed", "index": index + 1, "total": len(page_list), "name": page_name, "filename": filename}

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

            seo_repair_names = [n for n in seo.get("repair_pages", []) if n in pages][:3]
            if not seo_repair_names:
                seo_repair_names = list(dict.fromkeys(f.get("page") for f in seo.get("findings", []) if isinstance(f, dict) and f.get("page") in pages))[:3]
            for filename in seo_repair_names:
                issues = [f for f in seo.get("findings", []) if isinstance(f, dict) and f.get("page") == filename]
                yield {"type": "page", "status": "repairing", "filename": filename, "name": filename[:-5].replace("-", " ").title()}
                repair_prompt = f"You are the Frontend Dev Agent applying the SEO & A11y Agent's review. Repair only these issues and return the complete corrected HTML document only: {json.dumps(issues, ensure_ascii=False)[:3000]}\nHTML:\n{pages[filename][:18000]}"
                repaired = _clean_html(await ai_service._generate_content(
                    repair_prompt + "\n" + STUDIO_CLINERULES, response_mime_type="text/plain",
                    feature_name="website_frontend_generation", preferred_provider="gemini",
                    provider_order_override=CODE_PROVIDER_ORDER,
                    request_timeout_seconds=600.0, max_local_model_attempts=2,
                ))
                if "</html>" in repaired.lower() and len(repaired) >= 600:
                    pages[filename] = repaired

            yield status("testing", "running", "Checking generated pages and their navigation.")
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
                if not re.search(r"<style\b|rel=[\"']stylesheet[\"']", html, re.IGNORECASE):
                    repair_names.append(filename)
            repair_names = list(dict.fromkeys(repair_names))[:2]
            for filename in repair_names:
                yield {"type": "page", "status": "repairing", "filename": filename, "name": filename[:-5].replace("-", " ").title()}
                page_issues = [finding for finding in audit.get("findings", []) if isinstance(finding, dict) and finding.get("page") == filename]
                if filename == "index.html" and _wrong_homepage(pages[filename]):
                    page_issues.append({"severity": "critical", "finding": "This root page is an interior page. Rewrite it as the actual homepage for the user's brief, with a site-specific hero, key offering and next steps."})
                if not re.search(r"<style\b|rel=[\"']stylesheet[\"']", pages[filename], re.IGNORECASE):
                    page_issues.append({"severity": "critical", "finding": "The page has no stylesheet. Add a complete, responsive visual design with intentional layout, typography, spacing and component styles."})
                repair_prompt = f"You are the Frontend Dev Agent. Repair only the listed audit issues in this complete HTML file and return the full corrected HTML document only. Original brief: {prompt[:100000]}. Approved page plan: {json.dumps(next((p for p in page_list if p.get('filename') == filename), {}), ensure_ascii=False)[:1500]}. Sitemap: {json.dumps(page_list, ensure_ascii=False)[:2500]}. Issues: {json.dumps(page_issues, ensure_ascii=False)[:3000]}\nHTML:\n{pages[filename][:18000]}"
                repaired = _clean_html(await ai_service._generate_content(
                    repair_prompt + "\n" + STUDIO_CLINERULES, response_mime_type="text/plain",
                    feature_name="website_frontend_generation", preferred_provider="gemini",
                    provider_order_override=CODE_PROVIDER_ORDER,
                    request_timeout_seconds=600.0, max_local_model_attempts=2,
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
            yield status("testing", "completed", str(audit.get("summary") or "Testing and audit complete.")[:250])

            pages = {filename: _add_image_fallback(_ensure_styles(html), genre) for filename, html in pages.items()}
            for filename, html in pages.items():
                for asset_url, asset_path in local_asset_paths.items():
                    html = html.replace(asset_url, asset_path)
                pages[filename] = html
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
                    request_timeout_seconds=600.0, max_local_model_attempts=2,
                ))
                if "</html>" in repaired.lower() and len(repaired) >= 600:
                    pages[filename] = repaired
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

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for filename, html in pages.items():
                    bundle.writestr(filename, html)
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
                bundle.writestr("README.md", readme)
                bundle.writestr(".clinerules", clinerules)
                bundle.writestr("studio-plan.json", json.dumps({"plan": plan, "answers": answers, "build_prompt": approved_build_prompt, "design": design, "stock_image_credits": plan.get("stock_image_credits", []), "seo_a11y_review": seo, "test_audit": audit, "architecture": architecture, "stack": stack}, ensure_ascii=False, indent=2))
                if safe_images:
                    bundle.writestr("assets/image-sources.txt", "User-selected image URLs (review each source's license before public redistribution):\n" + "\n".join(safe_images))
            zip_bytes = archive.getvalue()
            scan = security_scanner.scan_zip_bytes(zip_bytes, "studio-project.zip")
            if not scan.get("is_safe", False):
                raise RuntimeError("The generated project did not pass the security scan and was not saved.")

            base_slug = re.sub(r"[^a-z0-9]+", "-", str(plan.get("title") or genre).lower()).strip("-")[:80] or "studio-project"
            slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
            title = str(plan.get("title") or genre.title())[:255]

            # Use a fresh, pre-pinged session to prevent serverless database idle timeouts during long generations
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as save_db:
                zip_url = await storage.upload_file(save_db, zip_bytes, "studio-projects", f"{uuid.uuid4().hex}.zip", "application/zip")
                project = Template(
                    title=title,
                    slug=slug,
                    short_description=str(plan.get("summary") or "Private AI-generated website project.")[:500],
                    description=str(plan.get("summary") or "Private AI-generated website project."),
                    price=0,
                    price_currency="USD",
                    is_free=True,
                    thumbnail_url=(safe_images[0] if safe_images else "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=85"),
                    preview_url=f"{settings.FRONTEND_URL.rstrip('/')}/preview?template={slug}",
                    gallery_images=safe_images or None,
                    category_id=category.id,
                    tags=["studio-project", "ai-generated", genre[:60]],
                    industry=genre[:100],
                    framework=(
                        TemplateFramework.NEXTJS if stack_info.get("frontend") == "nextjs"
                        else TemplateFramework.REACT if stack_info.get("frontend") == "react"
                        else TemplateFramework.HTML
                    ),
                    pages_count=len(pages),
                    has_dark_mode=bool(re.search(r"dark", design, re.IGNORECASE)),
                    is_responsive=True,
                    is_ai_ready=True,
                    license_type=TemplateLicense.REGULAR,
                    status=TemplateStatus.DRAFT,
                    developer_name=(user.full_name or user.username or "My Studio")[:200],
                    seller_id=user.id,
                    download_assets={"html": zip_url, "zip": zip_url},
                    changelog={"private_studio_project": True, "plan": plan, "answers": answers, "architecture": architecture, "stack": stack, "design": design[:5000], "seo_a11y_review": seo, "test_audit": audit},
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
            yield {"type": "complete", "project": {"id": saved_project_id, "slug": saved_slug, "title": saved_title, "pages_count": saved_pages_count}}
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.exception("Studio project generation failed")
            raise
        finally:
            self._active_user_generations.discard(user_key)


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
