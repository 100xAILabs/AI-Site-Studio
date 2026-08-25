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
