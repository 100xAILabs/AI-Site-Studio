"""
Requirement Analyzer & Intelligent Architecture Selection Engine.

Performs deep architectural analysis on user website briefs to automatically determine:
1. Architecture Tier:
   - Static: Pure frontend (HTML5/CSS/JS or static React) for showcases, blogs, or brochures without dynamic operations.
   - Hybrid: Static frontend with serverless API functions for contact forms, newsletters, and email notifications.
   - Full-Stack: Multi-tier application (React frontend + FastAPI REST backend + PostgreSQL relational database + JWT auth).
2. Required Pages and Navigation Hierarchy.
3. Database and Schema Requirements (PostgreSQL relational tables, models, migrations).
4. Authentication Requirements (JWT, role-based access control, session security).
5. Payment Requirements (Stripe Checkout, Webhook listeners, customer billing).
6. Communication Requirements (Serverless email dispatch, Resend/SMTP).
7. External APIs and Storage Requirements.
8. Environment Variables and Deployment Target.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ArchitectureType(str, Enum):
    STATIC = "static"
    HYBRID = "hybrid"
    FULLSTACK = "fullstack"


class PageRequirement(BaseModel):
    name: str
    filename: str
    purpose: str
    required: bool = True
    sections: List[str] = Field(default_factory=list)
    primary_action: str = ""


class ProjectSpecification(BaseModel):
    project_name: str = "Site Studio Project"
    category: str = "General"
    genre: str = "Website"
    architecture_type: ArchitectureType = ArchitectureType.STATIC
    stack_key: str = "html-css-js"
    frontend_framework: str = "vanilla"  # "vanilla", "react", "vue", "angular"
    backend_required: bool = False
    backend_framework: Optional[str] = None  # "fastapi", "serverless", None
    database_required: bool = False
    database_type: Optional[str] = None  # "postgresql", None
    auth_required: bool = False
    auth_type: Optional[str] = None  # "jwt_rbac", "session", None
    payment_required: bool = False
    payment_gateway: Optional[str] = None  # "stripe", None
    email_required: bool = False
    email_service: Optional[str] = None  # "smtp_resend", "serverless_mail", None
    storage_required: bool = False
    external_apis: List[str] = Field(default_factory=list)
    deployment_target: str = "static_cdn"  # "static_cdn", "hybrid_serverless", "fullstack_container"
    required_env_vars: List[str] = Field(default_factory=list)
    features_detected: List[str] = Field(default_factory=list)
    suggested_pages: List[PageRequirement] = Field(default_factory=list)
    reasoning: str = ""
    confidence_score: float = 1.0


# ---------------------------------------------------------------------------
# Heuristic Matchers & Patterns
# ---------------------------------------------------------------------------

HTML_STATIC_CATEGORIES = {
    "landing pages", "landing page", "one page", "portfolio", "creative",
    "personal", "resume", "cv", "photography", "agency", "business",
    "brochure", "event", "wedding", "nonprofit", "minimal",
}

PORTFOLIO_TERMS = {
    "portfolio", "resume", "cv", "personal", "showcase", "photographer",
    "photography", "artist", "freelancer", "developer portfolio", "designer portfolio",
    "profile", "bio", "curriculum vitae",
}

# Explicit ATS & Candidate Tracking triggers
ATS_TRIGGERS = [
    r"\b(?:ats|applicant\s+tracking(?:\s+system)?)\b",
    r"\b(?:candidate\s+tracking|candidate\s+pipeline|candidate\s+management)\b",
    r"\b(?:recruitment\s+(?:platform|system|portal|management|software|crm))\b",
    r"\b(?:recruiting\s+(?:platform|system|portal|management|software|crm))\b",
    r"\b(?:job\s+application\s+portal|job\s+board\s+with\s+(?:applicants?|candidates?|apply))\b",
    r"\b(?:recruiter\s+dashboard|hiring\s+pipeline|resume\s+screening|resume\s+parser)\b",
]

# General Full-Stack Application Triggers
FULLSTACK_BACKEND_TRIGGERS = [
    r"\b(?:user\s+login(?:\s+system)?|user\s+authentication|user\s+registration|user\s+accounts?\s+with\s+(?:jwt|oauth|passwords?))\b",
    r"\b(?:role-based\s+access|rbac|sign\s?in\s+portal|sign\s?up\s+portal|register\s+account)\b",
    r"\b(?:shopping\s+cart\s+with\s+(?:stripe|checkout|payment)|e-?commerce\s+store\s+with\s+order\s+management)\b",
    r"\b(?:(?:hotel\s+)?booking\s+(?:system|engine)\s+with\s+(?:live\s+)?database|(?:room|table)\s+reservation\s+(?:system\s+with\s+database|database))\b",
    r"\b(?:admin\s+crud\s+portal|admin\s+dashboard\s+with\s+crud|saas\s+dashboard\s+with\s+database\s+crud|crm\s+system)\b",
    r"\b(?:build\s+a\s+full[\s\-]*stack\s+(?:web\s+)?app(?:lication|site)?(?:\s+with\s+backend(?:\s+and\s+database)?)?)\b",
    r"\b(?:full[\s\-]*stack|fullstack|backend\s+and\s+frontend|frontend\s+and\s+backend)\b",
    r"\b(?:live\s+database|postgres(?:ql)?\s+database|database\s+storage|persist\s+data\s+to\s+(?:db|database)|database\s+crud|database\s+schema)\b",
    r"\b(?:with\s+(?:a\s+)?backend|backend\s+and\s+database|database\s+backed|real\s+database|backend\s+api)\b",
    r"\b(?:rest\s+api\s+backend|fastapi\s+backend|express\s+backend|backend\s+service)\b",
    r"\b(?:data\s+management|lead\s+management|submission\s+management)\b",
    r"\b(?:order\s+management|inventory\s+management|customer\s+management)\b",
]

# Explicit Framework Directional Patterns (e.g., "build in React", "using Vue")
EXPLICIT_FRAMEWORK_PATTERNS = [
    r"\b(?:use|using|built\s+with|build\s+with|create(?:d)?\s+(?:it\s+)?(?:in|with)|develop(?:ed)?\s+(?:it\s+)?(?:in|with)|framework\s*(?:is|:)?|tech\s+stack\s*(?:is|:)?|stack\s*(?:is|:)?)\s+(?:the\s+)?(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
    r"\b(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\s+(?:website|site|app|application|portal|dashboard)\b",
    r"\b(?:website|site|app|application|portal|dashboard)\s+(?:in|with|using)\s+(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
    r"\b(?:create|build|make|develop|write|built|made|created|developed|written)\b.{0,100}\b(?:in|with|using)\s+(?P<framework>react(?:\.js)?|vue(?:\.js)?|angular)\b",
]

# Dynamic Form & Hybrid Triggers
HYBRID_DYNAMIC_TRIGGERS = [
    r"\b(?:contact\s+form|inquiry\s+form|send\s+(?:us\s+an?\s+)?email|email\s+notification)\b",
    r"\b(?:newsletter\s+sign[\s\-]*up|subscribe\s+to\s+newsletter|lead\s+capture\s+form)\b",
    r"\b(?:quote\s+request|request\s+a\s+quote|get\s+a\s+quote|estimate\s+form)\b",
    r"\b(?:booking\s+request|reservation\s+request|appointment\s+request|table\s+reservation)\b",
    r"\b(?:submit\s+inquiry|feedback\s+form|message\s+us)\b",
]

# Developer skill scrub patterns (distinguish author credentials from app specifications)
DEVELOPER_SKILL_SCRUB_PATTERNS = [
    r"\b(?:i\s+am\s+(?:a|an)|i\'m\s+(?:a|an)|as\s+(?:a|an))\s+[^,\.\n;]*(?:developer|engineer|programmer|creator|freelancer|designer|architect)",
    r"\b(?:with\s+)?\d+\+?\s+years?\s+(?:of\s+)?experience[^\.\n;]*",
    r"(?:skills?|technologies|tech\s+stack|tools?|languages?|proficiency)\s*[:\-\s]+[^\.\n;]+",
    r"(?:skilled|experienced|proficient|worked|knowledge|background)\s+(?:in|with)\s+[^\.\n;]+",
    r"(?:familiar|specializ(?:ed|ing))\s+(?:with|in)\s+[^\.\n;]+",
    r"(?:projects?|apps?)\s+(?:built|developed|created)\s+(?:with|using|in)\s+[^\.\n;]+",
    r"\b(?:full[\s\-]*stack|front[\s\-]*end|back[\s\-]*end|lead|senior|junior|staff|principal)?\s*(?:software|web|systems?|ui[\s\/]*ux|python|react|node|fastapi)?\s*(?:developer|engineer|programmer|specialist|designer|creator|freelancer|architect)\b",
    r"\b(?:years?\s+of\s+experience|work\s+experience|career\s+highlights|job\s+history)\b[^\.\n;]*",
    r"\b(?:react(?:\.?js)?|next(?:\.?js)?|vue(?:\.?js)?|angular|tailwind|typescript|javascript|html5?|css3?|python|fastapi|django|flask|postgresql?|postgres|sqlite3?|mongodb|mysql)\b",
]


class RequirementAnalyzer:
    """
    Intelligent Requirement Analysis & Architecture Selection Engine.
    Evaluates briefs against deep heuristic classifiers and produces authoritative
    ProjectSpecification contracts before generation begins.
    """

    def scrub_author_skills(self, prompt: str) -> str:
        """
        Removes author bio/skill mentions (e.g. 'I am a full stack React/Python developer')
        so personal resumes and portfolios are not mistakenly classified as full-stack apps.
        """
        scrubbed = prompt.lower()
        for pattern in DEVELOPER_SKILL_SCRUB_PATTERNS:
            scrubbed = re.sub(pattern, " ", scrubbed, flags=re.IGNORECASE)
        return scrubbed

    def analyze_requirements(
        self,
        prompt: str,
        category: str = "",
        genre: str = "",
        requested_stack: str = "auto",
        page_structure: str = "multi_page",
    ) -> ProjectSpecification:
        """
        Analyzes the prompt, category, genre, and requested stack to produce
        a structured ProjectSpecification.
        """
        prompt_lower = (prompt or "").strip().lower()
        cat_lower = (category or "").strip().lower()
        genre_lower = (genre or "").strip().lower()
        full_context = f"{prompt_lower} {genre_lower} {cat_lower}"

        # -------------------------------------------------------------------
        # Step 1: Explicit Stack Selection Override
        # -------------------------------------------------------------------
        if requested_stack == "html-css-js":
            return self._build_static_spec(
                prompt, category, genre,
                reasoning="Static HTML5/CSS3/Vanilla JS explicitly selected by user.",
                features=["Static Showcase", "Zero Runtime Dependencies"]
            )

        if requested_stack in {"react-fastapi-postgresql", "vue-fastapi-postgresql", "angular-fastapi-postgresql"}:
            fw = requested_stack.split("-")[0]
            return self._build_fullstack_spec(
                prompt, category, genre,
                frontend_fw=fw,
                reasoning=f"Full-stack architecture ({fw.title()} + FastAPI + PostgreSQL) explicitly requested.",
                features=["Explicit Full-Stack Architecture", "FastAPI REST API", "PostgreSQL Relational Storage"]
            )

        # -------------------------------------------------------------------
        # Step 2: Explicit Framework Directive Pattern (e.g., "build in React")
        # -------------------------------------------------------------------
        for pattern in EXPLICIT_FRAMEWORK_PATTERNS:
            match = re.search(pattern, f"{prompt_lower} {genre_lower}", re.IGNORECASE)
            if match:
                fw = match.group("framework").lower().replace(".js", "")
                return self._build_fullstack_spec(
                    prompt, category, genre,
                    frontend_fw=fw,
                    reasoning=f"Explicit frontend framework requested in prompt: {fw.title()}.",
                    features=[f"{fw.title()} Single Page Application", "FastAPI REST API", "PostgreSQL Relational DB"]
                )

        # -------------------------------------------------------------------
        # Step 3: ATS / Applicant Tracking System Detection (PRIORITY)
        # -------------------------------------------------------------------
        is_ats = any(bool(re.search(pat, full_context)) for pat in ATS_TRIGGERS)
        if is_ats:
            return self._build_ats_spec(prompt, category, genre)

        # -------------------------------------------------------------------
        # Step 4: E-Commerce Store with Checkout / Orders
        # -------------------------------------------------------------------
        is_ecommerce = bool(re.search(
            r"\b(?:shopping\s+cart\s+with\s+(?:stripe|checkout|payment)|e-?commerce\s+store\s+with\s+order|order\s+management\s+system|product\s+inventory\s+tracking|digital\s+downloads\s+store)\b",
            full_context
        ))
        if is_ecommerce:
            return self._build_ecommerce_spec(prompt, category, genre)

        # -------------------------------------------------------------------
        # Step 5: Author Bio / Resume Portfolio Detection
        # -------------------------------------------------------------------
        is_portfolio_presentation = (
            cat_lower in HTML_STATIC_CATEGORIES
            or any(term in cat_lower for term in ("portfolio", "resume", "cv", "personal", "photograph", "showcase"))
            or any(term in genre_lower for term in PORTFOLIO_TERMS)
            or bool(re.search(
                r"\b(?:portfolio|resume|résumé|cv|curriculum\s+vitae|personal\s+(?:site|website)|developer\s+portfolio|designer\s+portfolio|freelancer\s+portfolio|photographer\s+portfolio|artist\s+portfolio|my\s+projects?\s+showcase)\b",
                prompt_lower
            ))
        )

        # Check for explicit application backend instructions outside developer skill text
        scrubbed = self.scrub_author_skills(prompt_lower)
        has_explicit_backend = any(bool(re.search(pat, scrubbed)) for pat in FULLSTACK_BACKEND_TRIGGERS)

        if is_portfolio_presentation and not has_explicit_backend:
            # Check if portfolio has interactive contact form -> Hybrid
            has_form = any(bool(re.search(pat, prompt_lower)) for pat in HYBRID_DYNAMIC_TRIGGERS)
            if has_form:
                return self._build_hybrid_spec(
                    prompt, category, genre,
                    reasoning="Developer portfolio with interactive contact/inquiry form requiring serverless email delivery.",
                    features=["Showcase Portfolio", "Interactive Contact Form", "Serverless Email Notifications"]
                )
            return self._build_static_spec(
                prompt, category, genre,
                reasoning="Showcase portfolio/resume presenting work without dynamic backend requirements.",
                features=["Curated Work Showcase", "Responsive Reflow", "Zero Server Overhead"]
            )

        # -------------------------------------------------------------------
        # Step 6: Interactive Full-Stack SaaS, Portals, CRUD & Databases
        # -------------------------------------------------------------------
        if has_explicit_backend:
            return self._build_fullstack_spec(
                prompt, category, genre,
                frontend_fw="react",
                reasoning="Interactive web application requiring persistent database storage, CRUD operations, or user accounts.",
                features=["FastAPI REST API", "PostgreSQL Relational DB", "Interactive Dashboard", "Role-Based Permissions"]
            )

        # -------------------------------------------------------------------
        # Step 7: Hybrid Website (Forms, Email Notifications, Bookings)
        # -------------------------------------------------------------------
        has_hybrid_forms = any(bool(re.search(pat, full_context)) for pat in HYBRID_DYNAMIC_TRIGGERS)
        is_hybrid_business = any(term in full_context for term in (
            "restaurant", "cafe", "clinic", "dental", "doctor", "lawyer",
            "consulting", "agency", "real estate", "salon", "spa", "catering"
        ))

        if has_hybrid_forms or is_hybrid_business:
            return self._build_hybrid_spec(
                prompt, category, genre,
                reasoning="Content-driven website with dynamic lead capture, contact forms, or booking inquiries requiring serverless API dispatch.",
                features=["Static High-Performance Frontend", "Serverless Form Dispatcher", "Resend/SMTP Email Integration"]
            )

        # -------------------------------------------------------------------
        # Step 8: Default Static Showcase
        # -------------------------------------------------------------------
        return self._build_static_spec(
            prompt, category, genre,
            reasoning="Presentation showcase website with responsive layouts and zero server-side state requirements.",
            features=["High-Speed Static Delivery", "Modern CSS & Responsive Layout", "Zero Backend Maintenance"]
        )

    # -----------------------------------------------------------------------
    # Factory Helpers
    # -----------------------------------------------------------------------

    def _build_ats_spec(self, prompt: str, category: str, genre: str) -> ProjectSpecification:
        pages = [
            PageRequirement(name="Dashboard", filename="index.html", purpose="Recruiter overview with pipeline stats, active jobs, and recent applicant activity", required=True, sections=["Key Metrics (Open Jobs, Applicants, Interviews)", "Active Hiring Pipelines", "Recent Applications Table", "Quick Actions"]),
            PageRequirement(name="Jobs", filename="jobs.html", purpose="Requisition management catalog with job creation, department filters, and applicant counts", required=True, sections=["Requisition List", "Department Filter", "Create Job Requisition Modal", "Job Details Preview"]),
            PageRequirement(name="Candidates", filename="candidates.html", purpose="Candidate tracking database with stage filtering, resume review, and rating", required=True, sections=["Candidate Roster", "Stage Filter (Applied, Screen, Interview, Offer, Rejected)", "Resume Viewer", "Evaluation Notes"]),
            PageRequirement(name="Pipeline", filename="pipeline.html", purpose="Kanban stage board for drag-and-drop applicant pipeline flow", required=False, sections=["Kanban Columns (Screening, Interview, Offer)", "Candidate Cards", "Stage Move Action", "Bulk Actions"]),
            PageRequirement(name="Settings", filename="settings.html", purpose="Recruiter and team management, email templates, and ATS configurations", required=False, sections=["Hiring Team Members", "Notification Preferences", "Interview Stages Configuration", "API Keys"]),
        ]
        return ProjectSpecification(
            project_name="ATS Candidate Tracking Platform",
            category=category or "SaaS & Technology",
            genre=genre or "Applicant Tracking System",
            architecture_type=ArchitectureType.FULLSTACK,
            stack_key="react-fastapi-postgresql",
            frontend_framework="react",
            backend_required=True,
            backend_framework="fastapi",
            database_required=True,
            database_type="postgresql",
            auth_required=True,
            auth_type="jwt_rbac",
            payment_required=False,
            email_required=True,
            email_service="smtp_resend",
            storage_required=True,
            deployment_target="fullstack_container",
            required_env_vars=["DATABASE_URL", "JWT_SECRET", "ACCESS_TOKEN_EXPIRE_MINUTES", "RESEND_API_KEY"],
            features_detected=[
                "Applicant Tracking System (ATS)",
                "Candidate Pipeline Management",
                "Job Requisitions & Applications",
                "Resume Review & Status Tracking",
                "Role-Based Recruiter Auth",
                "PostgreSQL Relational Persistence",
            ],
            suggested_pages=pages,
            reasoning="ATS platforms require persistent relational candidate tracking, status pipelines, role-based recruiter/candidate auth, and structured relational queries for jobs and applications, which mandates a full-stack PostgreSQL + FastAPI backend.",
            confidence_score=0.98,
        )

    def _build_ecommerce_spec(self, prompt: str, category: str, genre: str) -> ProjectSpecification:
        pages = [
            PageRequirement(name="Home", filename="index.html", purpose="Featured collections, hero deals, and bestsellers", required=True, sections=["Hero Banner", "Featured Categories", "Best Sellers Grid", "Promotional Callout"]),
            PageRequirement(name="Shop", filename="shop.html", purpose="Product catalog with price, category, and sorting filters", required=True, sections=["Filter Sidebar", "Product Grid", "Sorting Bar", "Pagination"]),
            PageRequirement(name="Cart & Checkout", filename="cart.html", purpose="Shopping cart review and Stripe Checkout redirection", required=True, sections=["Cart Line Items", "Subtotal & Tax Calculation", "Stripe Checkout Button"]),
            PageRequirement(name="Order Status", filename="order-status.html", purpose="Order confirmation and live fulfillment tracking", required=False, sections=["Order Confirmation", "Receipt Summary", "Shipping Timeline"]),
        ]
        return ProjectSpecification(
            project_name="E-Commerce Storefront & Order Management",
            category=category or "E-Commerce",
            genre=genre or "Storefront",
            architecture_type=ArchitectureType.FULLSTACK,
            stack_key="react-fastapi-postgresql",
            frontend_framework="react",
            backend_required=True,
            backend_framework="fastapi",
            database_required=True,
            database_type="postgresql",
            auth_required=True,
            auth_type="jwt_rbac",
            payment_required=True,
            payment_gateway="stripe",
            email_required=True,
            email_service="smtp_resend",
            storage_required=True,
            deployment_target="fullstack_container",
            required_env_vars=["DATABASE_URL", "JWT_SECRET", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
            features_detected=[
                "Product Catalog & Real-time Inventory",
                "Shopping Cart & Session Management",
                "Stripe Checkout Session Integration",
                "Order Tracking & Receipt Generation",
                "PostgreSQL Relational Persistence",
            ],
            suggested_pages=pages,
            reasoning="E-Commerce stores require relational tables for products, inventory, orders, customer accounts, and secure Stripe webhook listeners, requiring a full-stack architecture.",
            confidence_score=0.96,
        )

    def _build_fullstack_spec(
        self,
        prompt: str,
        category: str,
        genre: str,
        frontend_fw: str = "react",
        reasoning: str = "",
        features: Optional[List[str]] = None,
    ) -> ProjectSpecification:
        pages = [
            PageRequirement(name="Dashboard", filename="index.html", purpose="Application overview and primary management dashboard", required=True, sections=["Stats Overview", "Primary Data Table", "Recent Activity", "Quick Actions"]),
            PageRequirement(name="Management", filename="manage.html", purpose="Data management with CRUD records, search, and filters", required=True, sections=["Records Table", "Search & Filter Bar", "Create/Edit Modal", "Bulk Operations"]),
            PageRequirement(name="Analytics", filename="analytics.html", purpose="Metrics, charts, and data visualizations", required=False, sections=["Trend Charts", "Key Performance Indicators", "Export Reports"]),
            PageRequirement(name="Settings", filename="settings.html", purpose="Account preferences, user profile, and system configuration", required=False, sections=["Profile Settings", "Security & Passwords", "System Config"]),
        ]
        stack_key = f"{frontend_fw}-fastapi-postgresql" if frontend_fw in {"vue", "angular"} else "react-fastapi-postgresql"
        return ProjectSpecification(
            project_name=f"{genre or category or 'Full-Stack'} Application",
            category=category or "SaaS & Technology",
            genre=genre or "Web Application",
            architecture_type=ArchitectureType.FULLSTACK,
            stack_key=stack_key,
            frontend_framework=frontend_fw,
            backend_required=True,
            backend_framework="fastapi",
            database_required=True,
            database_type="postgresql",
            auth_required=True,
            auth_type="jwt_rbac",
            payment_required=False,
            email_required=True,
            email_service="smtp_resend",
            storage_required=False,
            deployment_target="fullstack_container",
            required_env_vars=["DATABASE_URL", "JWT_SECRET", "ACCESS_TOKEN_EXPIRE_MINUTES"],
            features_detected=features or ["FastAPI REST API", "PostgreSQL Relational DB", "Interactive CRUD Dashboard", "JWT Authentication"],
            suggested_pages=pages,
            reasoning=reasoning or "Application requires dynamic CRUD operations, relational database models, and server-side processing.",
            confidence_score=0.92,
        )

    def _build_hybrid_spec(
        self,
        prompt: str,
        category: str,
        genre: str,
        reasoning: str = "",
        features: Optional[List[str]] = None,
    ) -> ProjectSpecification:
        pages = [
            PageRequirement(name="Home", filename="index.html", purpose="Brand welcome and teaser showcases", required=True, sections=["Hero Section", "Key Offerings", "Testimonials", "Contact Teaser"]),
            PageRequirement(name="About", filename="about.html", purpose="Company background, mission, and team", required=False, sections=["Company Story", "Core Values", "Team Roster"]),
            PageRequirement(name="Services", filename="services.html", purpose="Complete service details and pricing packages", required=False, sections=["Service Grid", "Pricing Tiers", "FAQs"]),
            PageRequirement(name="Contact", filename="contact.html", purpose="Inquiry form wired to serverless email dispatch", required=True, sections=["Interactive Form", "Contact Details", "Location Map"]),
        ]
        return ProjectSpecification(
            project_name=f"{genre or category or 'Hybrid'} Site",
            category=category or "Business",
            genre=genre or "Company Website",
            architecture_type=ArchitectureType.HYBRID,
            stack_key="hybrid-serverless-api",
            frontend_framework="vanilla",
            backend_required=True,
            backend_framework="serverless",
            database_required=False,
            database_type=None,
            auth_required=False,
            auth_type=None,
            payment_required=False,
            email_required=True,
            email_service="smtp_resend",
            storage_required=False,
            deployment_target="hybrid_serverless",
            required_env_vars=["RESEND_API_KEY", "NOTIFICATION_EMAIL"],
            features_detected=features or ["Interactive Contact Form", "Serverless Email Dispatch", "Static High-Speed Delivery"],
            suggested_pages=pages,
            reasoning=reasoning or "Site contains dynamic form operations (contact, newsletter, quote) requiring serverless backend email dispatch.",
            confidence_score=0.90,
        )

    def _build_static_spec(
        self,
        prompt: str,
        category: str,
        genre: str,
        reasoning: str = "",
        features: Optional[List[str]] = None,
    ) -> ProjectSpecification:
        pages = [
            PageRequirement(name="Home", filename="index.html", purpose="Welcome entrance, hero, and highlights", required=True, sections=["Hero Banner", "Highlights", "Showcase Grid", "Footer CTA"]),
            PageRequirement(name="About", filename="about.html", purpose="Detailed biography or company narrative", required=False, sections=["Narrative", "Experience / History"]),
            PageRequirement(name="Showcase", filename="projects.html", purpose="Complete catalog of work or items", required=False, sections=["Filterable Gallery", "Project Details"]),
            PageRequirement(name="Contact", filename="contact.html", purpose="Direct contact channels (mailto, phone, social)", required=False, sections=["Direct Links", "Social Channels", "Office Hours"]),
        ]
        return ProjectSpecification(
            project_name=f"{genre or category or 'Static'} Website",
            category=category or "Creative",
            genre=genre or "Showcase",
            architecture_type=ArchitectureType.STATIC,
            stack_key="html-css-js",
            frontend_framework="vanilla",
            backend_required=False,
            backend_framework=None,
            database_required=False,
            database_type=None,
            auth_required=False,
            auth_type=None,
            payment_required=False,
            email_required=False,
            storage_required=False,
            deployment_target="static_cdn",
            required_env_vars=[],
            features_detected=features or ["Zero-Dependency Static HTML5", "Modern CSS Layout", "Ultra-Fast Edge CDN Delivery"],
            suggested_pages=pages,
            reasoning=reasoning or "Showcase presentation site without server-side dynamic requirements.",
            confidence_score=0.95,
        )


# Global Singleton Instance
requirement_analyzer = RequirementAnalyzer()
