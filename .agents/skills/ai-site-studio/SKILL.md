---
name: ai-site-studio-assistant
description: >-
  Use this skill when developing, debugging, or extending the AI Site Studio template marketplace.
  This includes adding or modifying frontend components and pages, developing FastAPI backend routes,
  modifying database schemas/models, working with the Gemini embedding or copywriting API integrations,
  and configuring database migrations.
---

# AI Site Studio Codebase Skill

This skill guides the AI assistant in developing and maintaining the **AI Site Studio** template marketplace codebase.

## Interaction & Handoff Guidelines

1.  **Strict File Linking**: Always link to files mentioned in conversation using full absolute file scheme markdown links (e.g., `[App.jsx](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/frontend/src/App.jsx)`).
2.  **Verify Imports**: When writing react code, ensure react router imports use `"react-router-dom"`, NOT `"react-router"`. The bundler aliases it automatically.

---

## 1. Frontend Development

### Pages and Layouts
- Frontend routes are mapped in [App.jsx](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/frontend/src/App.jsx).
- Page templates reside under `frontend/src/app/<route-name>/page.jsx`.
- When creating a new page, create its folder and a `page.jsx` file. Define its styling in an adjacent `Page.css` file.
- Add the route mapping in [App.jsx](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/frontend/src/App.jsx).

### Style Standards
- Follow the premium dark aesthetic with glow gradients.
- Custom variables are in [globals.css](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/frontend/src/app/globals.css).
- Prefer **Vanilla CSS** for fine control over transitions and visual components.

---

## 2. Backend Development

### Routes & Endpoints
- API endpoints are in `backend/app/api/v1/routes/`.
- Ensure new endpoints are loaded in `backend/app/main.py`.
- Keep API schemas in `backend/app/schemas/` and models in `backend/app/models/`.

### AI Integrations
- Prompting logic is centralized in [ai_service.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/ai_service.py).
- Semantic search indexing and query logic is in [search_service.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/search_service.py).
- Code auditing/parsing for ZIP files is in [project_analyzer.py](file:///d:/Navin/Proj/Official/AI%20Site%20Studio/backend/app/services/project_analyzer.py).

---

## 3. Database Management

- Models use SQLAlchemy ORM declarations.
- Generate migrations when models are updated:
  ```bash
  cd backend
  alembic revision --autogenerate -m "Describe migration"
  ```
- Apply migrations:
  ```bash
  cd backend
  alembic upgrade head
  ```
