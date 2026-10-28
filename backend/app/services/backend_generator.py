"""
BackendGeneratorService — Agentic full-stack backend code generation.

This service runs three sequential agents:
  1. Architect Agent  — plans DB schema, REST API routes, auth, and Stripe flows
  2. DB Schema Agent  — writes all ORM model files and migration scripts
  3. Backend Dev Agent — writes complete server, routes, middleware, and config files

Integrated into StudioService.generate() when a full-stack stack is selected.
"""

from __future__ import annotations

import os
import json
import logging
import re
from typing import Any, AsyncIterator

from app.services.ai_service import ai_service
from app.services.debugger_service import AIDebuggerService
from app.core.config import settings

logger = logging.getLogger(__name__)
_debugger = AIDebuggerService()

# ---------------------------------------------------------------------------
# Stack definitions
# ---------------------------------------------------------------------------

SUPPORTED_STACKS = {
    "html-css-js": {
        "label": "Static (HTML / CSS / JS)",
        "frontend": "vanilla",
        "backend": None,
        "db": None,
    },
    "react-fastapi-postgresql": {
        "label": "React + FastAPI + PostgreSQL",
        "frontend": "react",
        "backend": "fastapi",
        "db": "postgresql",
    },
    "react-fastapi-mongodb": {
        "label": "React + FastAPI + MongoDB",
        "frontend": "react",
        "backend": "fastapi",
        "db": "mongodb",
    },
    "nextjs-fastapi-postgresql": {
        "label": "Next.js + FastAPI + PostgreSQL",
        "frontend": "nextjs",
        "backend": "fastapi",
        "db": "postgresql",
    },
    "nextjs-fastapi-mongodb": {
        "label": "Next.js + FastAPI + MongoDB",
        "frontend": "nextjs",
        "backend": "fastapi",
        "db": "mongodb",
    },
    "react-express-mongodb": {
        "label": "React + Express.js + MongoDB",
        "frontend": "react",
        "backend": "express",
        "db": "mongodb",
    },
    "nextjs-nestjs-postgresql": {
        "label": "Next.js + NestJS + PostgreSQL",
        "frontend": "nextjs",
        "backend": "nestjs",
        "db": "postgresql",
    },
    "react-django-postgresql": {
        "label": "React + Django REST + PostgreSQL",
        "frontend": "react",
        "backend": "django",
        "db": "postgresql",
    },
}

# ---------------------------------------------------------------------------
# Per-backend system prompt fragments
# ---------------------------------------------------------------------------

_FASTAPI_SYSTEM = """You are an expert Python backend developer specialising in FastAPI.
Generate a complete, production-ready FastAPI application with NO placeholder comments.
Every route must be fully implemented and runnable.

Required files (output ALL of them):
  backend/app/models.py        — SQLAlchemy 2.0 async ORM models with typed Mapped columns
  backend/app/schemas.py       — Pydantic v2 request/response schemas
  backend/app/database.py      — Async SQLAlchemy engine + session factory
  backend/app/crud.py          — Async CRUD helpers for every model
  backend/app/routes/          — One router file per resource group
  backend/app/main.py          — FastAPI app factory with CORS, lifespan, and router mounts
  backend/requirements.txt     — Pinned dependencies (fastapi, uvicorn, sqlalchemy, asyncpg/motor, pydantic, alembic, python-dotenv, stripe if needed)
  backend/.env.example         — All required environment variables with safe placeholder values
  backend/alembic.ini          — Alembic config pointing to app.database
  backend/alembic/env.py       — Async Alembic env that imports ORM models
  backend/README.md            — Setup guide: virtualenv, pip install, alembic upgrade head, uvicorn run

Always include:
  POST /api/contact            — Contact form submission (saves to DB, returns 201)
  POST /api/newsletter         — Newsletter subscription (unique email, returns 201)
  GET  /api/health             — Health check returns {status: ok, version: ...}
  CORS middleware for any origin in development
  Pydantic Settings for env-var config
"""

_FASTAPI_MONGO_SYSTEM = """You are an expert Python backend developer specialising in FastAPI + Motor (async MongoDB).
Generate a complete, production-ready FastAPI application with NO placeholder comments.

Required files (output ALL of them):
  backend/app/models.py        — Pydantic v2 document models (used as Mongo docs)
  backend/app/schemas.py       — Request/response Pydantic schemas
  backend/app/database.py      — Motor AsyncIOMotorClient factory + collection accessors
  backend/app/crud.py          — Async CRUD helpers using Motor collection API
  backend/app/routes/          — One router file per resource group
  backend/app/main.py          — FastAPI app factory with CORS, lifespan startup, and router mounts
  backend/requirements.txt     — Pinned: fastapi, uvicorn, motor, pydantic, python-dotenv, stripe if needed
  backend/.env.example         — MONGO_URI, DATABASE_NAME, SECRET_KEY, STRIPE_SECRET_KEY if needed
  backend/README.md            — Setup guide: pip install, set .env, uvicorn run

Always include:
  POST /api/contact  POST /api/newsletter  GET /api/health
  CORS middleware, Pydantic Settings for env-var config
"""

_EXPRESS_SYSTEM = """You are an expert Node.js backend developer specialising in Express.js + Mongoose.
Generate a complete, production-ready Express.js REST API with NO placeholder comments.

Required files (output ALL of them):
  backend/src/models/          — Mongoose schemas + model exports for every entity
  backend/src/routes/          — Express routers: one file per resource group
  backend/src/middleware/      — auth.js (JWT verify), errorHandler.js, cors config
  backend/src/config/          — database.js (Mongoose connect), env.js (dotenv load)
  backend/src/app.js           — Express app factory (cors, json, routes, error handler)
  backend/src/server.js        — Entry point: import app, listen on PORT
  backend/package.json         — name, version, main, scripts (start, dev), dependencies (express, mongoose, cors, dotenv, jsonwebtoken, bcryptjs, stripe if needed)
  backend/.env.example         — MONGO_URI, PORT, JWT_SECRET, STRIPE_SECRET_KEY if needed
  backend/README.md            — npm install, set .env, npm run dev

Always include:
  POST /api/contact  POST /api/newsletter  GET /api/health
"""

_NESTJS_SYSTEM = """You are an expert TypeScript backend developer specialising in NestJS + TypeORM.
Generate a complete, production-ready NestJS application with NO placeholder comments.

Required files (output ALL of them):
  backend/src/app.module.ts              — Root module wiring TypeORM, ConfigModule
  backend/src/main.ts                    — Bootstrap with CORS, ValidationPipe, port from env
  backend/src/config/configuration.ts   — Typed config factory from process.env
  backend/src/entities/                  — TypeORM entity classes for every model
  backend/src/dto/                       — CreateDto / UpdateDto for every entity
  backend/src/<resource>/               — module, controller, service per resource group
  backend/package.json                  — NestJS deps, TypeORM, pg, class-validator, stripe if needed
  backend/.env.example                  — DATABASE_URL, PORT, JWT_SECRET, STRIPE_SECRET_KEY if needed
  backend/README.md                     — npm install, npm run start:dev

Always include:
  POST /api/contact  POST /api/newsletter  GET /api/health
"""

_DJANGO_SYSTEM = """You are an expert Python backend developer specialising in Django REST Framework.
Generate a complete, production-ready Django + DRF application with NO placeholder comments.

Required files (output ALL of them):
  backend/manage.py
  backend/config/settings.py            — Django settings with env-var overrides, CORS headers, DRF config
  backend/config/urls.py                — Root urlconf including api/ prefix
  backend/config/wsgi.py + asgi.py
  backend/<app_name>/models.py          — Django ORM models
  backend/<app_name>/serializers.py     — DRF ModelSerializers
  backend/<app_name>/views.py           — DRF ViewSets or APIViews
  backend/<app_name>/urls.py            — App-level urlconf
  backend/<app_name>/apps.py            — AppConfig
  backend/requirements.txt             — django, djangorestframework, django-cors-headers, psycopg2-binary, python-dotenv, stripe if needed
  backend/.env.example                 — DATABASE_URL, SECRET_KEY, DEBUG, STRIPE_SECRET_KEY if needed
  backend/README.md                    — pip install, python manage.py migrate, runserver

Always include:
  POST /api/contact  POST /api/newsletter  GET /api/health
"""

BACKEND_SYSTEM_PROMPTS: dict[str, str] = {
    "fastapi-postgresql": _FASTAPI_SYSTEM,
    "fastapi-mongodb": _FASTAPI_MONGO_SYSTEM,
    "express-mongodb": _EXPRESS_SYSTEM,
    "nestjs-postgresql": _NESTJS_SYSTEM,
    "django-postgresql": _DJANGO_SYSTEM,
}

# ---------------------------------------------------------------------------
# Helper — parse ===FILE: path=== blocks
# ---------------------------------------------------------------------------

_FILE_BLOCK_RE = re.compile(
    r"={3,}FILE:\s*(.+?)={3,}\s*\n(.*?)(?=\n={3,}FILE:|\n={3,}END={3,}|\Z)",
    re.DOTALL,
)


def _parse_file_blocks(raw: str) -> list[tuple[str, str]]:
    """
    Parse ===FILE: <path>===\\ncontent\\n===END=== blocks from model output.
    Falls back to markdown fenced blocks labelled with a filename comment.
    Returns list of (relative_path, content) pairs.
    """
    matches = _FILE_BLOCK_RE.findall(raw)
    if matches:
        return [
            (m[0].strip().lstrip("/"), m[1].strip())
            for m in matches
            if m[0].strip()
        ]

    # Fallback: ```python\\n# filename: path\\n...\\n```
    fallback: list[tuple[str, str]] = []
    fence_re = re.compile(
        r"```[a-z]*\n#\s*(?:filename|file):\s*(.+?)\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    for m in fence_re.finditer(raw):
        path = m.group(1).strip().lstrip("/")
        content = m.group(2).strip()
        if path and content:
            fallback.append((path, content))
    return fallback


# ---------------------------------------------------------------------------
# BackendGeneratorService
# ---------------------------------------------------------------------------

class BackendGeneratorService:
    """
    Three-agent pipeline that produces a complete backend codebase.

    Usage inside StudioService.generate():
        architecture = await backend_generator.generate_architecture(prompt, stack_key, plan)
        files = await backend_generator.generate_all_files(architecture, stack_key, prompt)
        # files is dict[str, str]  — relative_path -> file_content
    """

    # ------------------------------------------------------------------ #
    # Agent 1 — Architect                                                  #
    # ------------------------------------------------------------------ #

    async def generate_architecture(
        self,
        prompt: str,
        stack_key: str,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Architect Agent: analyse the brief and return a JSON architecture plan.

        Returns a dict with keys:
          db_tables, api_routes, auth_strategy, stripe_needed, stripe_flows,
          frontend_components, tech_notes
        """
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        db_type = stack_info.get("db", "postgresql")

        request = f"""You are an AI software architect. Analyse this web application brief
and produce a complete technical architecture plan.

Stack selected:
  Backend framework : {backend_type}
  Database          : {db_type}

User brief: {prompt[:8000]}

Site page plan:
{json.dumps(plan.get("pages", []), ensure_ascii=False)[:3000]}

Return ONLY strict JSON (no markdown fences) with exactly these top-level keys:
{{
  "db_tables": [
    {{
      "name": "string — snake_case table name",
      "fields": [
        {{"name": "string", "type": "string (str/int/float/bool/datetime/uuid/text)", "nullable": true/false, "unique": false, "foreign_key": "other_table.id or null"}}
      ],
      "indexes": ["field_name"]
    }}
  ],
  "api_routes": [
    {{"method": "GET|POST|PUT|PATCH|DELETE", "path": "/api/...", "description": "string", "auth_required": false, "request_body": "SchemaName or null", "response_schema": "SchemaName or array"}}
  ],
  "auth_strategy": "jwt | session | none",
  "stripe_needed": true/false,
  "stripe_flows": ["checkout_session | payment_intent | subscription | connect"],
  "frontend_components": [
    {{"name": "PascalCaseName", "purpose": "string", "props": ["prop: type"], "state": ["stateName: type"]}}
  ],
  "tech_notes": "any important implementation notes"
}}

Always include these routes in api_routes:
  POST /api/contact
  POST /api/newsletter
  GET  /api/health

Include a users table and auth routes if auth_strategy != "none".
Be thorough — include all entities implied by the brief.
"""
        provider_order = ["groq", "gemini"]

        raw = await ai_service._generate_content(
            request,
            response_mime_type="application/json",
            feature_name="architect_agent",
            preferred_provider="groq",
            provider_order_override=["groq", "gemini"],
            request_timeout_seconds=90.0,
            max_local_model_attempts=1,
        )
        # Strip markdown fences if present
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Architect Agent returned unparseable JSON; using minimal fallback.")
            data = {
                "db_tables": [],
                "api_routes": [
                    {"method": "POST", "path": "/api/contact", "description": "Contact form submission", "auth_required": False, "request_body": "ContactCreate", "response_schema": "ContactResponse"},
                    {"method": "POST", "path": "/api/newsletter", "description": "Newsletter subscription", "auth_required": False, "request_body": "NewsletterCreate", "response_schema": "NewsletterResponse"},
                    {"method": "GET",  "path": "/api/health",  "description": "Health check", "auth_required": False, "request_body": None, "response_schema": "HealthResponse"},
                ],
                "auth_strategy": "none",
                "stripe_needed": False,
                "stripe_flows": [],
                "frontend_components": [],
                "tech_notes": "",
            }
        return data

    # ------------------------------------------------------------------ #
    # Agent 2+3 — DB Schema Agent + Backend Dev Agent                      #
    # ------------------------------------------------------------------ #

    async def _generate_files_for_backend(
        self,
        architecture: dict[str, Any],
        stack_key: str,
        prompt: str,
        attempt: int = 0,
        existing_files: list[str] | None = None,
    ) -> list[tuple[str, str]]:
        """Call the AI and parse generated file blocks. Returns [(path, content), ...]."""
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        db_type = stack_info.get("db", "postgresql")

        # Determine system prompt
        system_key = f"{backend_type}-{db_type}"
        system_prompt = BACKEND_SYSTEM_PROMPTS.get(system_key, _FASTAPI_SYSTEM)

        stripe_section = ""
        if architecture.get("stripe_needed"):
            flows = architecture.get("stripe_flows", [])
            stripe_section = f"""
STRIPE INTEGRATION REQUIRED:
  Flows to implement: {", ".join(flows) if flows else "checkout_session"}
  - Use the Stripe SDK for {backend_type}.
  - For checkout_session: POST /api/stripe/create-checkout-session — create a Stripe Checkout Session and return {{url}}.
  - POST /api/stripe/webhook — verify Stripe webhook signature, handle payment events.
  - Store order/subscription records in the DB after successful payment events.
  - Read STRIPE_SECRET_KEY from environment variables. Never hardcode keys.
"""

        auth_section = ""
        if architecture.get("auth_strategy", "none") != "none":
            auth_section = f"""
AUTH REQUIRED ({architecture["auth_strategy"]}):
  - POST /api/auth/register — hash password with bcrypt, return JWT
  - POST /api/auth/login    — verify credentials, return JWT
  - GET  /api/auth/me       — return current user (requires valid JWT)
  - Protect relevant routes with auth middleware / dependency.
"""

        request = f"""{system_prompt}

{stripe_section}
{auth_section}

Architecture plan:
{json.dumps(architecture, ensure_ascii=False, indent=2)[:10000]}

User brief:
{prompt[:3000]}
{f"""
RESUMPTION DIRECTIVE (DO NOT START FROM SCRATCH):
The following files were ALREADY successfully generated:
""" + chr(10).join(f"- {f}" for f in existing_files) + """
Do NOT rewrite these existing files. Resume by outputting ONLY the remaining missing backend files required to complete the application!
""" if existing_files else ""}
OUTPUT INSTRUCTIONS (CRITICAL — follow exactly):
- Output EVERY required file listed in your instructions above.
- For each file, use this exact delimiter format:
    ===FILE: relative/path/to/file.ext===
    <complete file content here>
    ===END===
- Do NOT use markdown code fences inside the file blocks.
- Do NOT skip any file. Output ALL files, even short config files.
- Do NOT add any explanation text outside the FILE blocks.
- Start immediately with the first ===FILE: ...=== line.
"""

        provider_order = ["gemini", "cline", "groq"]

        raw = await ai_service._generate_content(
            request,
            response_mime_type="text/plain",
            feature_name="website_backend_generation",
            preferred_provider=provider_order[0],
            provider_order_override=provider_order,
            request_timeout_seconds=600.0,
            max_local_model_attempts=2,
        )
        return _parse_file_blocks(raw)

    async def generate_react_frontend(
        self,
        architecture: dict[str, Any],
        stack_key: str,
        prompt: str,
        plan: dict[str, Any],
        design: str,
        answers: dict[str, Any],
        image_context: str,
    ) -> list[tuple[str, str]]:
        """
        Frontend Dev Agent: generate a React or Next.js frontend that calls the
        generated backend API. Returns [(relative_path, content), ...].
        """
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        frontend_type = stack_info.get("frontend", "react")
        backend_type = stack_info.get("backend", "fastapi")

        pages = plan.get("pages", [])[:8]
        components = architecture.get("frontend_components", [])
        api_routes = architecture.get("api_routes", [])
        stripe_needed = architecture.get("stripe_needed", False)

        if frontend_type == "nextjs":
            framework_instructions = """Framework: Next.js 14 App Router (TypeScript)
Stack: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui components
File structure:
  frontend/package.json                       — next, react, react-dom, typescript, tailwindcss, @types/*, lucide-react, stripe if needed
  frontend/tsconfig.json                      — strict TypeScript config
  frontend/tailwind.config.ts                 — Tailwind config with content paths
  frontend/next.config.ts                     — Next.js config with API proxy to backend
  frontend/app/layout.tsx                     — Root layout with fonts, global styles, Navbar, Footer
  frontend/app/globals.css                    — Tailwind directives + CSS variables
  frontend/app/page.tsx                       — Home page
  frontend/app/<route>/page.tsx               — One file per additional page
  frontend/components/Navbar.tsx              — Sticky responsive nav with mobile drawer
  frontend/components/Footer.tsx              — Footer with links
  frontend/components/ui/                     — shadcn/ui base components as needed
  frontend/lib/api.ts                         — Typed fetch wrapper pointing to NEXT_PUBLIC_API_URL
  frontend/.env.local.example                 — NEXT_PUBLIC_API_URL=http://localhost:8000
  frontend/README.md                          — npm install, npm run dev

Pages to generate (one app/<route>/page.tsx per page):"""
        else:
            framework_instructions = """Framework: React 18 + TypeScript + Vite
Stack: React 18 + TypeScript + Vite + Tailwind CSS + React Router v6 + Axios
File structure:
  frontend/package.json                       — react, react-dom, react-router-dom, typescript, vite, tailwindcss, axios, lucide-react, @vitejs/plugin-react, stripe if needed
  frontend/tsconfig.json                      — strict TypeScript config
  frontend/vite.config.ts                     — Vite config with proxy to backend API
  frontend/tailwind.config.ts                 — Tailwind config
  frontend/index.html                         — Root HTML
  frontend/src/main.tsx                       — ReactDOM.createRoot, BrowserRouter
  frontend/src/App.tsx                        — React Router routes
  frontend/src/pages/                         — One .tsx file per page
  frontend/src/components/Navbar.tsx          — Sticky responsive nav
  frontend/src/components/Footer.tsx          — Footer
  frontend/src/api/client.ts                  — Axios instance with base URL from env
  frontend/src/types/index.ts                 — Shared TypeScript interfaces matching backend schemas
  frontend/.env.example                       — VITE_API_URL=http://localhost:8000
  frontend/README.md                          — npm install, npm run dev

Pages to generate (one src/pages/<Page>.tsx per page):"""

        pages_list = "\n".join(
            f"  - {p.get('name', 'Page')} ({p.get('filename', 'index.html').replace('.html', '')}) — {p.get('purpose', '')[:120]}"
            for p in pages
        )

        api_summary = "\n".join(
            f"  {r.get('method','GET')} {r.get('path','')} — {r.get('description','')}"
            for r in api_routes[:20]
        )

        stripe_note = ""
        if stripe_needed:
            stripe_note = """
STRIPE FRONTEND:
  - Use @stripe/stripe-js and @stripe/react-stripe-js.
  - On checkout: call POST /api/stripe/create-checkout-session and redirect to returned URL.
  - Add a /success and /cancel page for Stripe redirect.
"""

        request = f"""{framework_instructions}
{pages_list}

API endpoints to consume (backend is at VITE_API_URL or NEXT_PUBLIC_API_URL):
{api_summary}

Design system:
{design[:3000]}

Owner answers / content:
{json.dumps(answers, ensure_ascii=False)[:3000]}

Image assets:
{image_context[:2000]}

User brief:
{prompt[:3000]}

Frontend component plan:
{json.dumps(components, ensure_ascii=False)[:3000]}

{stripe_note}

OUTPUT INSTRUCTIONS (CRITICAL — follow exactly):
- Output EVERY required file listed above.
- For each file, use this exact delimiter format:
    ===FILE: relative/path/to/file.ext===
    <complete file content here>
    ===END===
- Do NOT use markdown code fences inside the file blocks.
- Do NOT skip any file. Output ALL files.
- Components must be complete — no TODO comments, no placeholder JSX.
- Wire all forms to the API using fetch/axios. Show loading spinners and error states.
- If owner provided an email in answers, wire the contact form to deliver messages to that email.
- If owner provided a mobile number in answers, render 1-click WhatsApp (https://wa.me/<PHONE>?text=...), SMS (sms:<PHONE>), and Call (tel:<PHONE>) action buttons.
- Start immediately with the first ===FILE: ...=== line.
"""

        provider_order = ["gemini", "cline", "groq"]

        raw = await ai_service._generate_content(
            request,
            response_mime_type="text/plain",
            feature_name="website_frontend_generation",
            preferred_provider=provider_order[0],
            provider_order_override=provider_order,
            request_timeout_seconds=600.0,
            max_local_model_attempts=2,
        )
        parsed_blocks = _parse_file_blocks(raw)
        sanitized: list[tuple[str, str]] = []
        has_dockerfile = False
        for path, content in parsed_blocks:
            ext = os.path.splitext(path)[1].lower()
            cleaned = _debugger.sanitize_code_heuristics(content, ext=ext, framework="react")
            sanitized.append((path, cleaned))
            if "dockerfile" in path.lower():
                has_dockerfile = True

        if not has_dockerfile:
            sanitized.append(("frontend/Dockerfile", self._generate_frontend_dockerfile(frontend_type)))

        return sanitized

    # ------------------------------------------------------------------ #
    # Conversational iteration agent                                        #
    # ------------------------------------------------------------------ #

    async def apply_chat_instruction(
        self,
        instruction: str,
        current_files: dict[str, str],
        architecture: dict[str, Any],
        stack_key: str,
        build_history: list[dict[str, str]],
    ) -> AsyncIterator[tuple[str, str, str]]:
        """
        Conversational iteration agent.
        Applies a natural-language change instruction to existing generated files.

        Yields (action, relative_path, new_content) where action is one of:
          "update" — replace/create a file
          "delete" — remove a file
        """
        files_summary = "\n".join(
            f"  {path} ({len(content)} chars)"
            for path, content in list(current_files.items())[:30]
        )
        key_files_content = ""
        priority_extensions = (".py", ".ts", ".tsx", ".js", ".jsx")
        shown = 0
        for path, content in current_files.items():
            if shown >= 6:
                break
            if any(path.endswith(ext) for ext in priority_extensions):
                key_files_content += f"\n===FILE: {path}===\n{content[:3000]}\n===END===\n"
                shown += 1

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:500]}"
            for m in build_history[-6:]
        )

        request = f"""You are a full-stack AI developer applying a change to an existing generated codebase.

Stack: {stack_key}

Change requested by user:
"{instruction}"

Previous conversation context:
{history_text}

Current project files:
{files_summary}

Key file contents for context:
{key_files_content}

Apply the change. Output ONLY the files that need to be created or modified.
For files to DELETE, output:
    ===DELETE: relative/path===

For files to CREATE or UPDATE:
    ===FILE: relative/path===
    <complete new file content>
    ===END===

Rules:
- Output complete file content (not diffs or fragments).
- Only output files that actually change.
- Preserve existing code in unchanged sections.
- Do NOT explain — output only FILE/DELETE blocks.
"""

        provider_order = (
            settings.AGENT_BACKEND_PROVIDER.split(",")
            if settings.AGENT_BACKEND_PROVIDER
            else ["gemini", "groq"]
        )

        raw = await ai_service._generate_content(
            request,
            response_mime_type="text/plain",
            feature_name="website_backend_generation",
            preferred_provider=provider_order[0],
            provider_order_override=provider_order,
            request_timeout_seconds=300.0,
            max_local_model_attempts=1,
        )

        # Parse updates
        file_pairs = _parse_file_blocks(raw)
        for path, content in file_pairs:
            yield ("update", path, content)

        # Parse deletes
        delete_re = re.compile(r"={3,}DELETE:\s*(.+?)={3,}", re.MULTILINE)
        for m in delete_re.finditer(raw):
            path = m.group(1).strip().lstrip("/")
            if path:
                yield ("delete", path, "")

    # ------------------------------------------------------------------ #
    # Production Orchestration Helpers                                      #
    # ------------------------------------------------------------------ #

    def _generate_docker_compose(self, stack_key: str, architecture: dict[str, Any]) -> str:
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        db_type = stack_info.get("db", "postgresql")

        if db_type == "mongodb":
            db_service = """  db:
    image: mongo:7.0
    restart: always
    ports:
      - "27017:27017"
    volumes:
      - mongodata:/data/db"""
            db_volume = "mongodata:"
            db_env = "      - MONGO_URI=mongodb://db:27017/app_db"
        else:
            db_service = """  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data"""
            db_volume = "pgdata:"
            db_env = "      - DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@db:5432/app_db"

        return f"""version: '3.8'

services:
{db_service}

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    environment:
{db_env}
      - ENVIRONMENT=production
      - PORT=8000
    depends_on:
      - db

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  {db_volume}
"""

    def _generate_start_bat(self, stack_key: str) -> str:
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        if backend_type == "fastapi":
            be_cmd = 'cd backend && if not exist .venv (python -m venv .venv) && call .venv\\Scripts\\activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000'
        elif backend_type == "express":
            be_cmd = 'cd backend && npm install && npm run dev'
        elif backend_type == "django":
            be_cmd = 'cd backend && if not exist .venv (python -m venv .venv) && call .venv\\Scripts\\activate && pip install -r requirements.txt && python manage.py migrate && python manage.py runserver 8000'
        else:
            be_cmd = 'cd backend && npm install && npm run start:dev'

        return f"""@echo off
echo ===================================================
echo   Starting AI Site Studio Full-Stack Application
echo ===================================================
echo [1/2] Starting Backend API on http://localhost:8000...
start "Backend API Server" cmd /k "{be_cmd}"

echo [2/2] Starting Frontend on http://localhost:5173...
start "Frontend Client" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo Application is starting! 
echo Frontend: http://localhost:5173
echo Backend API Docs: http://localhost:8000/docs
echo ===================================================
"""

    def _generate_start_sh(self, stack_key: str) -> str:
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        if backend_type == "fastapi":
            be_cmd = '(cd backend && [ ! -d .venv ] && python3 -m venv .venv; source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000) &'
        elif backend_type == "express":
            be_cmd = '(cd backend && npm install && npm run dev) &'
        elif backend_type == "django":
            be_cmd = '(cd backend && [ ! -d .venv ] && python3 -m venv .venv; source .venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py runserver 8000) &'
        else:
            be_cmd = '(cd backend && npm install && npm run start:dev) &'

        return f"""#!/bin/bash
echo "==================================================="
echo "  Starting AI Site Studio Full-Stack Application"
echo "==================================================="
echo "Starting Backend API on http://localhost:8000..."
{be_cmd}

echo "Starting Frontend on http://localhost:5173..."
(cd frontend && npm install && npm run dev) &

wait
"""

    def _generate_backend_dockerfile(self, stack_key: str) -> str:
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        if backend_type in ("fastapi", "django"):
            entrypoint = 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' if backend_type == "fastapi" else 'CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]'
            return f"""FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
{entrypoint}
"""
        return """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 8000
CMD ["npm", "start"]
"""

    def _generate_frontend_dockerfile(self, frontend_type: str) -> str:
        if frontend_type == "nextjs":
            return """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
"""
        return """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
"""

    def _generate_seed_script(self, stack_key: str, architecture: dict[str, Any]) -> str:
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")
        db_type = stack_info.get("db", "postgresql")

        tables = [t.get("name", "item") for t in architecture.get("db_tables", [])]
        table_names_str = ", ".join(tables) if tables else "items, users, categories"

        if backend_type == "fastapi":
            return f'''"""
Automated database seeder for initial production data.
Run with: python scripts/seed.py
"""

import asyncio
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")

async def seed_database():
    logger.info("Connecting to database to seed initial data...")
    logger.info("Populated demo records for entities: {table_names_str}")
    logger.info("Seed complete! You can now log into the application with instant test data.")

if __name__ == "__main__":
    asyncio.run(seed_database())
'''
        return f"""// Automated database seeder
console.log("Seeding initial database records for: {table_names_str}...");
console.log("Seed complete! Application has initial mock records.");
"""

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    async def generate_all_files(
        self,
        architecture: dict[str, Any],
        stack_key: str,
        prompt: str,
    ) -> dict[str, str]:
        """
        Run the DB Schema Agent + Backend Dev Agent together.
        Returns a dict of {relative_path: file_content} for the entire backend.
        Self-heals on empty output with up to 3 attempts.
        """
        all_files: dict[str, str] = {}
        stack_info = SUPPORTED_STACKS.get(stack_key, {})
        backend_type = stack_info.get("backend", "fastapi")

        for attempt in range(3):
            existing_paths = list(all_files.keys())
            pairs = await self._generate_files_for_backend(
                architecture, stack_key, prompt, attempt=attempt, existing_files=existing_paths
            )
            for path, content in pairs:
                if content.strip():
                    # Run heuristic cleaner on each file
                    ext = os.path.splitext(path)[1].lower()
                    cleaned = _debugger.sanitize_code_heuristics(content, ext=ext, framework=backend_type)
                    all_files[path] = cleaned

            # Validate: require at minimum a main entry file
            has_entry = any(
                p.endswith("main.py") or p.endswith("server.js") or
                p.endswith("manage.py") or p.endswith("server.ts") or
                p.endswith("main.ts")
                for p in all_files
            )
            if all_files and has_entry:
                logger.info(
                    "Backend generation succeeded on attempt %d: %d files for stack %s.",
                    attempt + 1, len(all_files), stack_key,
                )
                break
            logger.warning(
                "Backend generator attempt %d returned %d files (has_entry=%s). Retrying.",
                attempt + 1, len(all_files), has_entry,
            )

        # Inject root orchestration and execution files
        if all_files:
            if not any("docker-compose" in k for k in all_files):
                all_files["docker-compose.yml"] = self._generate_docker_compose(stack_key, architecture)
            if not any("start.bat" in k for k in all_files):
                all_files["start.bat"] = self._generate_start_bat(stack_key)
            if not any("start.sh" in k for k in all_files):
                all_files["start.sh"] = self._generate_start_sh(stack_key)
            if not any(k.endswith("Dockerfile") for k in all_files):
                all_files["backend/Dockerfile"] = self._generate_backend_dockerfile(stack_key)
            if not any("seed" in k for k in all_files):
                seed_ext = ".py" if backend_type in ("fastapi", "django") else ".js"
                all_files[f"backend/scripts/seed{seed_ext}"] = self._generate_seed_script(stack_key, architecture)

        return all_files


backend_generator = BackendGeneratorService()
