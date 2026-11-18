# AI Site Studio

> **AI-powered Website Template Marketplace** — Browse, preview with your own business info, customize via AI, purchase, and deploy professional website templates.

[![React](https://img.shields.io/badge/React-18.2-blue?logo=react)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5.x-646CFF?logo=vite)](https://vitejs.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://python.org/)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, React Router DOM, Zustand, Framer Motion, Vanilla CSS |
| Backend | FastAPI, SQLAlchemy (asyncpg), Alembic, Pydantic, Celery |
| Database | PostgreSQL (Supabase) |
| Cache | Redis |
| Auth | Custom OAuth (Google / GitHub) + JWT Database Authentication |
| Storage | Database-backed Binary Storage / Cloudflare R2 |
| AI | Gemini (1.5-flash) / OpenAI (GPT-4o) |
| Vector DB | Qdrant |
| Payments | Razorpay + Stripe |
| Deploy | Vercel (frontend) + Railway/Docker (backend) |

---

## Project Structure

```
ai-site-studio/
├── frontend/          # React Single Page App (Vite)
├── backend/           # FastAPI Python REST API
├── docker-compose.yml # Local services (Postgres + Redis)
└── README.md
```

## Quick Start (Local Development)

### Prerequisites
- Node.js 20+
- Python 3.12+
- Docker & Docker Compose

### 1. Clone & Configure

```bash
git clone https://github.com/100xAILabs/AI-Site-Studio.git
cd ai-site-studio

# Backend env
cp backend/.env.example backend/.env
# Fill in your keys in backend/.env
```

### 2. Start Infrastructure

```bash
docker-compose up -d   # Starts Postgres 16 + Redis 7
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed database (100 templates)
python scripts/seed.py

# Start API
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev   # Runs on http://localhost:5173
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing secret |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth app credentials |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth app credentials |
| `GEMINI_API_KEY` | Gemini API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `QDRANT_URL` | Qdrant instance URL |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay Key ID and Secret |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` | Stripe credentials |

---

## API Documentation

Start the backend and visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## License

MIT © AI Site Studio