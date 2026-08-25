# Template Quality & Full-Stack Architecture Rules

This document establishes the mandatory quality and architectural standards for all website templates generated, developed, or audited within **Site Studio**.

---

## Rule 1: 100% Complete Page Delivery (Zero Missing Pages)

Every template generated or published on Site Studio must provide **all pages displayed, listed, or referenced in its configuration and metadata**.

1. **Explicit File Generation**: If a template specifies or advertises pages (e.g., `Home`, `About`, `Services`, `Pricing`, `Contact`, `Portfolio`, `Blog`, `FAQ`), each corresponding file (`index.html`, `about.html`, `services.html`, `pricing.html`, `contact.html`, etc., or routed React components) **must actually exist** in the project directory.
2. **No Phantom or Placeholder Pages**: Templates must never reference non-existent pages or leave stub pages without rich, domain-specific content.
3. **Consistent Theme & Design Tokens**: Every page in a multi-page template must share the identical design system, typography pairings, color variables (`:root` tokens), header navbar, and footer layout.

---

## Rule 2: 100% Working Links & Navigation Interconnectivity

All links, buttons, navigation menus, and connections across all template pages must be fully functional and properly wired:

1. **Relative Navigation Links**:
   - In HTML multi-page templates, all header navigation links, footer quick links, mobile drawer links, and CTA buttons must use exact relative paths to other pages (e.g., `<a href="index.html">Home</a>`, `<a href="about.html">About</a>`, `<a href="services.html">Services</a>`, `<a href="contact.html">Contact</a>`, `<a href="pricing.html">Pricing</a>`).
   - Never use dead `#` hrefs where a real destination page exists in the package.
2. **Active State Highlighting**:
   - The navigation link corresponding to the current page must be visually highlighted (e.g., `class="nav-link active"` or primary accent color) so users always know their location.
3. **Interactive Mobile Navigation Drawer**:
   - Mobile hamburger menus on every page must include working JavaScript toggles (`toggleMobileMenu()`) that open/close a responsive drawer with all active page links.
4. **Interactive Component Wiring**:
   - Accordions (`toggleAccordion(id)`), category filters (`filterGallery(category)`), billing toggles (`togglePricingBilling()`), modal lightboxes, and smooth scroll buttons must work on every page where they appear.

---

## Rule 3: Powerful, Production-Ready Backend Integration

When a template is generated or uploaded with full-stack scope or a designated backend framework, it must include a **powerful, complete, standalone backend REST API server** tailored to the chosen framework.

### Supported Backend Frameworks:
1. **FastAPI (Python 3.12)**: Async API with Pydantic v2 validation, SQLite database, CORS middleware, and OpenAPI documentation.
2. **Express.js (Node.js)**: Production Express 4 REST server with CORS, SQLite/data persistence, structured routes, and middleware.
3. **NestJS (TypeScript)**: Enterprise modular architecture with Controllers, Services, DTOs, and SQLite database.
4. **Django (Python 5)**: Django REST Framework with models, serializers, views, admin panel, and SQLite.
5. **Spring Boot 3 (Java 21)**: Production-ready Spring Web & JPA backend with REST Controllers, Repositories, Models, and `pom.xml`.
6. **Ruby on Rails 7 (Ruby 3)**: Full-stack Rails API mode with ActionController, ActiveRecord, SQLite, and `Gemfile`.
7. **Laravel 11 (PHP 8.3)**: Elegant PHP backend with Eloquent ORM, Controllers, SQLite database, and `composer.json`.
8. **Actix Web (Rust)**: High-performance async Rust REST server with Tokio, Serde, SQLite persistence, and `Cargo.toml`.

### Mandatory Backend Capabilities:
- **Lead & Contact Ingestion Endpoint**: `POST /api/contact` and `POST /api/leads` to store visitor inquiries in the database.
- **Newsletter Subscription Endpoint**: `POST /api/newsletter` for email collection.
- **Analytics & Health Endpoints**: `GET /api/health` and `GET /api/stats` for uptime monitoring and dashboard metrics.
- **Isolated Database**: Auto-initialized local SQLite/embedded database with CRUD operations.
- **CORS & Security Headers**: Pre-configured to accept requests from the frontend development server (`http://localhost:5173`, `http://localhost:3000`, `http://localhost:8080`, etc.).
- **Frontend Form Wiring**: Contact, newsletter, and inquiry forms on the frontend must submit to the backend API endpoint with a smooth glassmorphic success toast notification and graceful offline fallback.

---

## Rule 4: Standardized Package Architecture

Full-stack template packages must be structured cleanly as follows:

```
template-project/
├── frontend/                     # Complete Frontend (HTML multi-page or React Vite SPA)
│   ├── index.html                # Home Landing Page
│   ├── about.html                # About & Story Page
│   ├── services.html             # Services & Offerings Page
│   ├── contact.html              # Interactive Contact & Map Page
│   └── ...                       # All other requested pages
├── backend/                      # Complete Standalone Backend Server
│   ├── main.py / server.js / ... # Application entry point
│   ├── models / routes / ...     # Structured endpoints & database logic
│   └── requirements.txt / ...    # Dependency manifests
└── README.md                     # Comprehensive dual-server startup guide
```

---

## Rule 5: Automated Verification & Auditing

The Site Studio project analyzer and automated audit tools will verify:
1. That all declared pages are physically present.
2. That all internal page links resolve to valid targets.
3. That backend entry points, dependencies, and endpoints are valid and executable.
