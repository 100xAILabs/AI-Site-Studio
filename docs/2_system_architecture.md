# 2. System Architecture & Flows

This document details the high-level system layout, components, and primary data workflows for **AI Site Studio**.

---

## Technical Component Architecture

The application is structured as a decoupled client-server architecture supported by relational/vector databases, caching structures, and asynchronous task workers:

```mermaid
graph TD
    Client["React Frontend (SPA / Vite)"]
    API["FastAPI Backend (API Gateway)"]
    DB[("PostgreSQL (Supabase)")]
    Cache[("Redis (Cache & Celery Broker)")]
    Worker["Celery Background Worker"]
    VectorDB[("Qdrant Vector DB")]
    
    %% External Integrations
    LLM["Google Gemini / OpenAI API"]
    Pay["Stripe / Razorpay SDKs"]
    Storage["Cloudflare R2 / Local Filesystem"]

    Client -->|HTTP / JSON| API
    API -->|Read/Write SQL| DB
    API -->|Cache / Queue Tasks| Cache
    Cache -->|Fetch Tasks| Worker
    Worker -->|Write Analysis Results| DB
    Worker -->|Analyze Files| Storage
    API -->|Vector Queries| VectorDB
    API -->|Embeddings / Prompts| LLM
    API -->|Process Payments| Pay
    API -->|Upload / Download Code| Storage
```

### Component Details
1. **Frontend SPA**: React application styled with vanilla CSS, managed via Zustand stores. Handles rendering templates within custom sandbox preview structures.
2. **Backend API**: FastAPI application containing REST route boundaries, validation schemes (Pydantic), and database interactions (SQLAlchemy + asyncpg).
3. **Relational Database**: PostgreSQL managing users, standard metadata, preview sessions, payment status, and order tracking.
4. **Vector Database**: Qdrant housing template description embeddings (3072 dimensions) for sub-second semantic searches.
5. **Broker & Task Queue**: Redis managing session caches and driving Celery's background template analyzers.
6. **Object Storage**: Local disk or Cloudflare R2 bucket holding code template archives (ZIP) and screenshot image buffers.

---

## System Workflows

### 1. Semantic Search & RankGemini Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend
    participant Backend
    participant Gemini
    participant Qdrant

    User->>Frontend: Enter search query ("cyberpunk blog page")
    Frontend->>Backend: GET /api/v1/search/semantic?q=...
    Backend->>Gemini: Request embedding (text-embedding-004)
    Gemini-->>Backend: Return vector array (3072 dimensions)
    Backend->>Qdrant: Query Cosine Similarity (Fetch top 30)
    Qdrant-->>Backend: Return raw candidate templates
    Backend->>Gemini: Request Reranking (RankGemini Prompt)
    Gemini-->>Backend: Return top relevancy-sorted templates
    Backend-->>Frontend: HTTP 200 (Sorted list of templates)
    Frontend->>User: Display matching results
```

---

### 2. Live Customization & Preview (AI Fill)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend
    participant ControlBar as Preview Control Bar
    participant Sandbox as Preview Canvas (Iframe)
    participant Backend
    participant Gemini

    User->>ControlBar: Click "AI Fill" & Enter Business Details
    ControlBar->>Backend: POST /api/v1/preview/generate-assets
    Backend->>Gemini: Prompt Copywriting & Palette generation (JSON format)
    Gemini-->>Backend: Return copy texts + color HEXs
    Backend-->>ControlBar: Return personalized payload & Save session
    ControlBar->>Sandbox: postMessage(Personalized JSON data)
    Sandbox->>Sandbox: Update DOM elements & CSS variables dynamically
    Sandbox-->>User: Renders customized template in real time
```

---

### 3. Template Ingestion & Analysis Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Creator
    participant Frontend
    participant Backend
    participant Storage
    participant Redis
    participant Worker
    participant Analyzer as Project Analyzer (Python)
    participant Gemini

    Creator->>Frontend: Upload ZIP template
    Frontend->>Backend: POST /api/v1/templates/upload
    Backend->>Storage: Save ZIP file
    Backend->>Redis: Trigger Celery Task (analyze_template)
    Backend-->>Frontend: HTTP 202 (Accepted - task_id returned)
    
    Note over Worker: Celery grabs task from Redis queue
    Worker->>Analyzer: Extract and inspect ZIP contents
    Analyzer->>Analyzer: Verify package.json, index.html structure
    Analyzer->>Gemini: Analyze code to generate description, tags & grade
    Gemini-->>Analyzer: Return metadata JSON
    Analyzer->>Worker: Complete analysis
    Worker->>Backend: Save database record & index in Qdrant
    Frontend->>Backend: Poll /api/v1/templates/status/{task_id}
    Backend-->>Frontend: Ready (Display finalized template detail)
```

---

### 4. Autonomous Multi-Agent Generation Engine (Agentic AI)

AI Site Studio implements an autonomous multi-agent software engineering pipeline where specialized agents collaborate in a staged, self-healing loop:

```mermaid
flowchart TD
    UserBrief["User Prompt & Category"] --> PlanAgent["1. Planning Agent<br/>(Scope, Pages, Questions)"]
    PlanAgent --> Clarification["Owner Clarifications & Brief Approval"]
    Clarification --> UIDesigner["2. UI Designer Agent<br/>(Aesthetic Archetype, Fluid Clamp, Touch 44px)"]
    UIDesigner --> Architect["3. Architect Agent<br/>(Page Manifest, Visual Directives, Contracts)"]
    
    Architect --> ForkArchitecture{Architecture Tier?}
    ForkArchitecture -->|Full-Stack / ATS| DBSchema["4. DB Schema Agent<br/>(SQLAlchemy 2.0 Async, Indexes)"]
    DBSchema --> BackendDev["5. Backend Dev Agent<br/>(FastAPI, @asynccontextmanager lifespan, CRUD)"]
    ForkArchitecture -->|Serverless Hybrid| BackendDev
    ForkArchitecture -->|Static Portfolio| FrontendDev["6. Frontend Dev Agent<br/>(Per-Page HTML/JSX Generation)"]
    BackendDev --> FrontendDev

    FrontendDev --> SEOAgent["7. SEO & A11y Agent<br/>(Headings, Alt Tags, Reduced Motion)"]
    SEOAgent --> AuditorAgent["8. Testing & Self-Repair Agent<br/>(Python/JSX AST Healing, Health Injection)"]
    
    AuditorAgent --> Memory["Agent Learning Memory<br/>(Persistent Mistake Reflection & Heuristics)"]
    Memory -.->|Feed Forward Constraints| FrontendDev
    
    AuditorAgent --> DeployEngine["9. Multi-Target Deployment Engine<br/>(Docker Provider, Static/Hybrid, Live Probe)"]
    DeployEngine --> LiveSite["Production Ready Output<br/>(/api/health Verified, Zero Overflow)"]
```

#### Specialized Agent Roles
1. **Planning Agent**: Analyzes user brief, detects domain/genre, determines optimal architecture tier (`single_page`, `multi_page`, `fullstack`), and generates domain-specific clarification questions.
2. **UI Designer Agent**: Emits tokens for **Premium Dark Luxe** (`#0B0D13`, glowing gradients, glass borders) or **Clean Modern SaaS** (`#FFFFFF`, slate text, diffused shadows), with fluid clamp typography and minimum 44px touch targets.
3. **Architect Agent**: Generates immutable page contracts, component boundaries, and embeds `visual_directive` across every page.
4. **DB Schema Agent**: Models PostgreSQL/SQLite entities using SQLAlchemy 2.0 async engine and `asyncpg`.
5. **Backend Dev Agent**: Generates production-ready FastAPI endpoints with `@asynccontextmanager lifespan` and Pydantic schemas.
6. **Frontend Dev Agent**: Constructs clean pages with dynamic contact/enquiry bindings (`contact_phone`, `contact_email`, motel room routing).
7. **SEO & A11y Agent**: Audits and auto-repairs heading levels, color contrast, keyboard access, and social tags.
8. **Testing & Audit Agent**: Analyzes Python/JSX AST syntax, heals unclosed delimiters, and injects mandatory `/api/health`.
9. **Packaging & Deployment Agent**: Builds multi-stage `Dockerfile`, `docker-compose.yml`, and conducts multi-probe health checks.
