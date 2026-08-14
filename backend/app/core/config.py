"""
Application configuration via Pydantic Settings.

All values are read from environment variables (or .env file).
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "Site Studio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_site_studio"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-must-be-at-least-32-characters"
    OLD_SECRET_KEYS: str = ""  # Comma-separated list of older keys for token rotation
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        if self.ENVIRONMENT not in ("development", "local", "test"):
            if (
                self.SECRET_KEY == "change-me-in-production-must-be-at-least-32-characters"
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError("Insecure SECRET_KEY configured in a non-local environment.")
        return self


    # ── OAuth (Google / Facebook) ─────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Separate Gemini models per feature (Gemini 3.5 Flagship Tiers)
    GEMINI_MODEL_AI_CHAT_ASSISTANT: str = "gemini-3.5-flash"
    GEMINI_MODEL_WEBSITE_CONTENT_GENERATION: str = "gemini-3.5-flash"
    GEMINI_MODEL_SEO_GENERATOR: str = "gemini-3.5-flash"
    GEMINI_MODEL_SEMANTIC_SEARCH: str = "text-embedding-004"
    GEMINI_MODEL_TEMPLATE_RECOMMENDATION: str = "text-embedding-004"
    GEMINI_MODEL_ACCESSIBILITY_REVIEW: str = "gemini-3.5-flash"
    GEMINI_MODEL_CODE_ASSISTANT: str = "gemini-3.5-flash"
    GEMINI_MODEL_CODE_DEBUGGING_AGENT: str = "gemini-3.5-flash"
    GEMINI_MODEL_PROJECT_ZIP_ANALYSIS: str = "gemini-3.5-flash"
    GEMINI_MODEL_TRANSLATION: str = "gemini-3.5-flash"
    GEMINI_MODEL_BUSINESS_ANALYSIS: str = "gemini-3.5-flash"
    GEMINI_MODEL_LOGO_IDEAS: str = "gemini-3.5-flash"
    GEMINI_MODEL_IMAGE_GENERATION: str = "flux"
    GEMINI_MODEL_OCR_DOCUMENT_UNDERSTANDING: str = "gemini-3.5-flash"

    # Alternative models per feature (Highest Flagship Tiers)
    ALT_MODEL_AI_CHAT_ASSISTANT: str = "gpt-4o"
    ALT_MODEL_WEBSITE_CONTENT_GENERATION: str = "gpt-4o"
    ALT_MODEL_SEO_GENERATOR: str = "gpt-4o"
    ALT_MODEL_SEMANTIC_SEARCH: str = "text-embedding-3-large"
    ALT_MODEL_TEMPLATE_RECOMMENDATION: str = "text-embedding-3-large"
    ALT_MODEL_ACCESSIBILITY_REVIEW: str = "gpt-4o"
    ALT_MODEL_CODE_ASSISTANT: str = "gpt-4o"
    ALT_MODEL_CODE_DEBUGGING_AGENT: str = "gpt-4o"
    ALT_MODEL_PROJECT_ZIP_ANALYSIS: str = "gpt-4o"
    ALT_MODEL_TRANSLATION: str = "gpt-4o"
    ALT_MODEL_BUSINESS_ANALYSIS: str = "gpt-4o"
    ALT_MODEL_LOGO_IDEAS: str = "gpt-4o"
    ALT_MODEL_IMAGE_GENERATION: str = "dall-e-3"
    ALT_MODEL_OCR_DOCUMENT_UNDERSTANDING: str = "gpt-4o"

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Azure deployment mappings (leave blank by default, will fallback to AZURE_DEPLOYMENT_CHAT if not set)
    AZURE_DEPLOYMENT_CHAT: str = ""
    AZURE_DEPLOYMENT_AI_CHAT_ASSISTANT: str = ""
    AZURE_DEPLOYMENT_WEBSITE_CONTENT_GENERATION: str = ""
    AZURE_DEPLOYMENT_SEO_GENERATOR: str = ""
    AZURE_DEPLOYMENT_SEMANTIC_SEARCH: str = ""
    AZURE_DEPLOYMENT_TEMPLATE_RECOMMENDATION: str = ""
    AZURE_DEPLOYMENT_ACCESSIBILITY_REVIEW: str = ""
    AZURE_DEPLOYMENT_CODE_ASSISTANT: str = ""
    AZURE_DEPLOYMENT_PROJECT_ZIP_ANALYSIS: str = ""
    AZURE_DEPLOYMENT_TRANSLATION: str = ""
    AZURE_DEPLOYMENT_BUSINESS_ANALYSIS: str = ""
    AZURE_DEPLOYMENT_LOGO_IDEAS: str = ""
    AZURE_DEPLOYMENT_IMAGE_GENERATION: str = ""
    AZURE_DEPLOYMENT_OCR_DOCUMENT_UNDERSTANDING: str = ""



    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "templates"

    # ── Cloudflare R2 (optional — not used when STORAGE_BACKEND=postgres) ────
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "ai-site-studio"
    R2_PUBLIC_URL: str = ""

    # ── File Storage ──────────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "postgres"  # postgres
    STORAGE_BASE_URL: str = "http://localhost:8000/api/v1/files"

    # ── Razorpay ──────────────────────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # ── Stripe ────────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # ── SMTP Settings ──────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@aisitestudio.com"
    SMTP_USE_TLS: bool = True

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── File Uploads ──────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp,image/gif"

    # ── Computed Properties ───────────────────────────────────────────────────
    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def ALLOWED_IMAGE_TYPES_LIST(self) -> List[str]:
        return [t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",")]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
