# AI Site Studio Agent Guidelines

This document provides project-specific rules, style guidelines, and codebase architecture for AI assistants working on **AI Site Studio**.

---

## 1. Project Overview & Tech Stack

**AI Site Studio** is a website template marketplace where users can semantically search, personalize templates in a live canvas using AI ("AI Fill"), and creators/admins upload and audit templates.

*   **Frontend**: React 19, Vite 8, React Router v8, Zustand, Framer Motion, Vanilla CSS (with tailwind support).
*   **Backend**: FastAPI (Python 3.12), SQLAlchemy 2.0 (asyncpg), Alembic, Pydantic, Celery (Redis broker), PostgreSQL.
*   **Vector DB**: Qdrant (storing 3072-dimensional template text embeddings).
*   **AI Integration**: Google Gemini (`1.5-flash` / `text-embedding-004`), OpenAI (`gpt-4o`).

---

## 2. Directory Structure

```
ai-site-studio/
├── docs/                                # Project documentation folder
├── backend/                             # Python FastAPI REST API backend
│   ├── alembic/                         # Database schema migrations
│   ├── app/
│   │   ├── api/                         # Endpoint Router Modules
│   │   │   ├── auth.py                  # OAuth + JWT auth
│   │   │   ├── templates.py             # Template catalogs & upload handlers
│   │   │   └── search.py                # Vector search endpoints
│   │   ├── core/                        # System config & database adapters
│   │   ├── models/                      # SQLAlchemy ORM Models
│   │   ├── repositories/                # Database abstraction repositories
│   │   ├── schemas/                     # Pydantic models for validation
│   │   ├── services/                    # Core Business & AI logic services
│   │   │   ├── ai_service.py            # LLM copywriting & color palette prompts
│   │   │   ├── preview_service.py       # Pillow watermark overlay builder
│   │   │   ├── project_analyzer.py      # Automated zip scanner & tech auditor
│   │   │   └── search_service.py        # Gemini embedding + Qdrant similarity
│   │   └── tasks/                       # Celery worker background tasks
└── frontend/                            # React Single Page App frontend
    ├── src/
        ├── App.jsx                      # Route configurations
        ├── main.jsx                     # Hydration entry point
        ├── app/                         # App pages (Next.js-style file structure)
        │   ├── marketplace/             # Template discovery & search views
        │   ├── preview/                 # Iframe canvas sandboxed environment
        │   └── globals.css              # Styling design tokens & color schemes
        ├── components/                  # Re-usable UI elements
        ├── hooks/                       # Custom React hooks
        └── store/                       # Zustand store modules
```

---

## 3. Frontend Development Rules

1.  **Routing**: The application uses client-side routing configured in [App.jsx](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/frontend/src/App.jsx).
2.  **Page Organization**: Pages are organized Next.js App Router style inside `frontend/src/app/<route>/page.jsx`, but they are loaded as a SPA via client-side routing.
3.  **React Router Imports**: 
    *   The project uses `react-router` version 8.3.0.
    *   **CRITICAL**: Always import React Router hooks and components from `"react-router-dom"`. There is a Vite alias in `frontend/vite.config.js` that maps `'react-router-dom'` to `'react-router'`. Do not change imports to `'react-router'` directly, as it may cause import conflicts or bundle issues in this setup.
4.  **Styling**: Prefer custom **Vanilla CSS** (stored in CSS modules or adjacent files, e.g., `Page.css`, `Layout.css`) for high-fidelity interactive elements, in line with the marketplace's premium look.

---

## 4. Backend Development Rules

1.  **FastAPI Endpoints**: Defined in `backend/app/api/v1/routes/`.
2.  **Database Models**: Defined in `backend/app/models/` using SQLAlchemy ORM.
3.  **Database Repositories**: Data access goes through repository classes in `backend/app/repositories/`.
4.  **AI Integration**: AI logic goes through services like [ai_service.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/ai_service.py) (which implements Gemini `text-embedding-004` and `1.5-flash`).
5.  **Celery Tasks**: Long-running or heavy operations (such as parsing zip files) must be run asynchronously as Celery tasks in `backend/app/tasks/`.

---

## 5. Template Quality & Full-Stack Architecture Rules

All templates generated, developed, or audited must strictly adhere to the following standards:

1. **Complete Page Delivery (Zero Missing Pages)**:
   - Every page listed, shown, or configured (e.g. `index.html`, `about.html`, `services.html`, `pricing.html`, `contact.html`, `portfolio.html`, etc.) **must physically exist** and contain complete, rich, domain-specific content. No empty stubs or missing files are allowed.
2. **100% Working Links & Navigation**:
   - All links in headers, footers, mobile drawers, and CTA buttons must use relative links to other pages (e.g. `href="about.html"`, `href="contact.html"`).
   - Never use non-functional `#` hrefs where an actual page exists.
   - The current page navigation item must have an active visual highlight.
3. **Powerful & Complete Backend Integration**:
   - When templates include a backend or fullstack scope, generate a complete, production-ready standalone REST API tailored to the selected framework (**FastAPI, Express.js, NestJS, Django, Spring Boot, Ruby on Rails, Laravel, Actix Web**).
   - Include REST endpoints for contact submissions (`POST /api/contact`), lead capture (`POST /api/leads`), newsletter subscriptions (`POST /api/newsletter`), health checks (`GET /api/health`), and analytics (`GET /api/stats`).
   - Include local database persistence (SQLite schema with CRUD models), CORS middleware, and complete dependency files.
   - Frontend forms must be wired to submit asynchronously to backend endpoints with graceful offline fallback.
4. **Standard Package Structure**:
   - Fullstack templates must be packaged with clean `frontend/` and `backend/` folders, accompanied by a comprehensive `README.md`.

---

## 6. Development & Testing Commands

*   **Frontend**: `npm run dev` (run from `frontend/`)
*   **Backend Run**: `uvicorn app.main:app --reload --port 8000` (run from `backend/`)
*   **Run Migrations**: `alembic upgrade head` (run from `backend/`)
*   **Seed DB**: `python scripts/seed.py` (run from `backend/`)
*   **Run Tests**: `pytest` (run from `backend/`)

