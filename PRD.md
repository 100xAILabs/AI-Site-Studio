# Product Requirements Document (PRD)
## Project Name: AI Site Studio
## Status: Live Draft

---

## 1. Executive Summary & Objective

**AI Site Studio** is a next-generation website template marketplace. Traditional template marketplaces sell static codebase skeletons which developers must manually download, configure, populate with custom copy, and styling assets. 

**AI Site Studio solves this by integrating AI inline:**
*   **Discovery:** Users can perform semantic searches using natural language to retrieve matched templates.
*   **Customization:** Users can preview templates on the fly, custom-populate website texts using generative AI copywriters, and generate tailored color palettes for specific business industries and moods.
*   **Admin/Creator Ingestion:** Automated scanners parse uploaded ZIPs or Git repositories to verify template compatibility, auto-tag features, identify dependencies, and predict performance/accessibility metrics using generative AI.

---

## 2. Product Features & Scope

### A. Template Discovery & Semantic Vector Search
*   **Keyword & Taxonomy Search:** Traditional text-based search filtering by framework (React, NextJS, Vue, Svelte, HTML), tags, price, and category.
*   **AI Semantic Search:** Users search with semantic intent (e.g. *"dark-mode SaaS dashboard with cyber aesthetic"*).
*   **LLM Re-ranking:** A RankGemini pipeline filters semantic candidates and sorts them based on high-level relevance to the search query.

### B. Interactive Preview Builder & AI Fill
*   **Live Preview Canvas:** Renders templates inside an iframe or browser canvas with live-preview data bindings.
*   **AI-Powered Copywriting:** Generating headlines, taglines, "about us" sections, service descriptions, and primary/secondary CTAs dynamically adjusted to the buyer's business industry.
*   **Color Palette Suggestions:** Generating cohesive hex codes for primary, secondary, text, accent, and background options fitting the business context.
*   **Pre-purchase Protection:** Applying diagonal, tiled watermarks dynamically overlaying preview screenshot assets.

### C. Developer & Admin Portal
*   **Project Uploader:** Upload template files via custom file uploader (ZIP format) or Git Clone pipeline.
*   **Automated Quality Audit:** Validates codebases to verify they contain web templates (rejecting backend-only structures like Node/Python scripts).
*   **AI Metadata Tagging:** Scans source code and utilizes LLMs to generate titles, descriptions, categories, features list, and code improvement suggestions.

### D. Billing, Order Management, and Licensing
*   **Dual Payments Gateways:** Integrating Stripe and Razorpay processing pipelines.
*   **Licensing Rules:** Offering "Regular" and "Extended" usage licenses for developer files.

---

## 3. Tech Stack & Environment Architecture

| Layer | Technologies Used |
| :--- | :--- |
| **Frontend Framework** | React 18, Vite 5, React Router DOM, Zustand (State Management) |
| **Styles & Animations** | Vanilla CSS, Framer Motion |
| **Backend API Gateway** | FastAPI, SQLAlchemy (asyncpg), Alembic, Pydantic, Celery |
| **Databases** | PostgreSQL (Supabase persistent layer), Redis (Caching & Job Broker) |
| **Vector DB** | Qdrant (supports dense semantic vector storage) |
| **AI Integration** | Gemini (1.5-flash / text-embedding-004), OpenAI (GPT-4o) |
| **Image Processing** | Pillow (image watermarking overlays) |

---

## 4. System Directory Map

Below is a map of the repository's major files and directory components:

```
ai-site-studio/
├── backend/                             # Python FastAPI REST API backend
│   ├── alembic/                         # Database schema migrations
│   ├── app/
│   │   ├── api/                         # Endpoint Router Modules
│   │   │   ├── auth.py                  # Custom OAuth + JWT authentication routes
│   │   │   ├── templates.py             # Template catalogs, listings, and uploads
│   │   │   └── search.py                # AI Semantic & Keyword query endpoints
│   │   ├── core/                        # System configuration & environment files
│   │   │   ├── config.py                # Global settings and secrets validation
│   │   │   └── storage.py               # Cloudflare R2 / Local disk binary storage wrappers
│   │   ├── models/                      # SQLAlchemy ORM Models
│   │   │   ├── user.py                  # User profiles and roles
│   │   │   ├── template.py              # Main template metadata & license definitions
│   │   │   ├── preview_session.py       # Live personalization sessions
│   │   │   ├── order.py                 # Invoice database schema
│   │   │   └── ai_history.py            # Audit records of LLM prompt usages
│   │   ├── repositories/                # Database abstraction pattern implementations
│   │   ├── schemas/                     # Pydantic schema validation structures
│   │   ├── services/                    # Core Business & AI logic services
│   │   │   ├── ai_service.py            # OpenAI copywriting & color palette prompts
│   │   │   ├── preview_service.py       # Pillow watermark overlay builder
│   │   │   ├── project_analyzer.py      # Automated zip scanner & technical audit agent
│   │   │   └── search_service.py        # Gemini dense vector embedder + Qdrant similarity
│   │   └── tasks/                       # Celery worker background tasks
│   ├── Dockerfile                       # Container deployment config
│   ├── docker-compose.yml               # PostgreSQL & Redis infrastructure config
│   └── requirements.txt                 # Backend dependencies manifest
│
└── frontend/                            # React Single Page App frontend
    ├── public/                          # Static browser assets
    ├── src/
    │   ├── App.jsx                      # Router routes configuration
    │   ├── main.jsx                     # SPA Entrypoint React hydration
    │   ├── app/                         # App pages
    │   │   ├── marketplace/             # Template gallery & search page
    │   │   ├── preview/                 # Iframe sandbox custom preview UI
    │   │   ├── dashboard/               # Purchased orders and history views
    │   │   └── globals.css              # Typography & styling tokens design system
    │   ├── components/                  # Global re-usable UI components
    │   │   └── support/                 # Customer care chatbot controls
    │   ├── hooks/                       # Shared React hooks
    │   └── store/                       # Zustand store modules
```

---

## 5. AI Services Detail Spec

### A. AI Copywriter & Palette Generator
*   **File Path:** [ai_service.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/ai_service.py)
*   **Operations:**
    *   `generate_business_content`: Generates JSON object with headlines, paragraphs, and CTAs utilizing structural prompts.
    *   `generate_seo`: Creates tags mapping industry keywords, descriptions, and OpenGraph variables.
    *   `generate_color_palette`: Suggestions of cohesive HEX palettes with accompanying reasoning.

### B. Project Analyzer & Technical Auditor
*   **File Path:** [project_analyzer.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/project_analyzer.py)
*   **Operations:**
    *   `analyze_zip` / `analyze_git_repo`: Extracts files, checks for backend framework triggers (e.g. Django, Flask, Express) to auto-reject backend files, and extracts page/component names.
    *   `_run_ai_analysis`: Generates template title, description, categories score distributions, performance estimates, and code optimizations.

### C. Dense Semantic Search & Re-ranking
*   **File Path:** [search_service.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/search_service.py)
*   **Operations:**
    *   `_get_gemini_embedding`: Calls Gemini `text-embedding-004` to create vector structures (3072 dimensions).
    *   `index_template`: Compiles name, tag list, category, features, typography, styles, and colors to create a dense vector description stored inside Qdrant.
    *   `semantic_search`: Conducts cosine-similarity search over Qdrant, yielding the top 30 templates.
    *   `_rank_templates`: Leverages RankGemini (LLM) to perform context-aware ranking of candidate results.

---

## 6. Core Database Schemas

### A. Template Table Model (`templates`)
*   `id`: UUID (Primary Key)
*   `title`: String (Template Name)
*   `slug`: String (SEO URL Key, Unique)
*   `short_description`: String
*   `description`: Text
*   `price`: Decimal
*   `framework`: Enum (`react`, `nextjs`, `vue`, `nuxt`, `html`, `angular`, `svelte`)
*   `thumbnail_url` & `preview_url`: String
*   `category_id`: ForeignKey (`categories.id`)

### B. Preview Session Table Model (`preview_sessions`)
*   `id`: UUID (Primary Key)
*   `template_id`: ForeignKey (`templates.id`)
*   `user_email`: String (Optional)
*   `business_data`: JSON (AI generated and personalized texts)
*   `is_ai_filled`: Boolean
*   `expires_at`: DateTime

---

## 7. Development & Verification Plan

### Automated Test Suites
Execute python endpoints verification:
```bash
cd backend
pytest
```

### Manual Verification
1. Open the local frontend server (`http://localhost:5173`).
2. Search templates using conversational phrasing in the search input (e.g., *"clean dashboard template"*).
3. Open the Preview Builder, click **AI Fill**, input business metadata, and verify generated layouts replace target copy blocks in the template preview.
