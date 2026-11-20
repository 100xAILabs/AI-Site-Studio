"""
Environment Variables & Secrets Scanner Service — Phase 4.

Scans project files, templates, and specifications to identify all required
environment variables, explains their purpose, provides provider console links,
detects missing credentials, and validates format before deployment.
"""

from __future__ import annotations

import os
import re
import secrets
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EnvVarMetadata(BaseModel):
    key: str
    description: str
    provider_name: str
    provider_url: Optional[str] = None
    is_secret: bool = True
    is_required: bool = False
    has_default: bool = False
    default_value: Optional[str] = None
    placeholder: str = ""
    example: str = ""
    status: str = "missing"  # "configured", "missing", "optional", "default"
    validation_regex: Optional[str] = None
    validation_error: Optional[str] = None


# Registry of known environment variables with rich developer documentation
KNOWN_ENV_REGISTRY: Dict[str, Dict[str, Any]] = {
    "DATABASE_URL": {
        "description": "PostgreSQL async connection URI (postgresql+asyncpg://user:pass@host:5432/db).",
        "provider_name": "PostgreSQL",
        "provider_url": "https://supabase.com/dashboard",
        "is_secret": True,
        "is_required": True,
        "has_default": True,
        "default_value": "sqlite+aiosqlite:///./app_data.db",
        "placeholder": "postgresql+asyncpg://postgres:password@localhost:5432/app_db",
        "example": "postgresql+asyncpg://postgres:secret@db.project.supabase.co:5432/postgres",
        "validation_regex": r"^(?:postgres(?:ql)?(?:\+asyncpg)?|sqlite(?:\+aiosqlite)?)://.*$",
        "validation_error": "Must be a valid PostgreSQL or SQLite connection URI (e.g. postgresql+asyncpg://...)",
    },
    "SECRET_KEY": {
        "description": "Cryptographic key used to sign JWT tokens, session cookies, and authentication payloads.",
        "provider_name": "Security / System",
        "provider_url": None,
        "is_secret": True,
        "is_required": True,
        "has_default": True,
        "default_value": None,  # Dynamically generated if missing
        "placeholder": "32+ characters random secure secret key",
        "example": "v8kQ9mX2pL5nZ8wY1tB4cR7eA0dF3gH6jK9mP2sV5xY8",
        "validation_regex": r"^.{16,}$",
        "validation_error": "Secret key must be at least 16 characters long for security.",
    },
    "JWT_SECRET": {
        "description": "Secret key used specifically for JSON Web Token signature verification.",
        "provider_name": "Security / System",
        "provider_url": None,
        "is_secret": True,
        "is_required": True,
        "has_default": True,
        "default_value": None,
        "placeholder": "32+ characters random secure JWT secret",
        "example": "jW7s3Cr3t-k3y-v8kQ9mX2pL5nZ8wY1tB4cR7eA0dF",
        "validation_regex": r"^.{16,}$",
        "validation_error": "JWT secret key must be at least 16 characters long.",
    },
    "STRIPE_SECRET_KEY": {
        "description": "Stripe API Secret Key used to process server-side payments and create checkout sessions.",
        "provider_name": "Stripe",
        "provider_url": "https://dashboard.stripe.com/apikeys",
        "is_secret": True,
        "is_required": True,
        "has_default": False,
        "placeholder": "sk_live_... or sk_test_...",
        "example": "sk_test_placeholder_key_format_12345",
        "validation_regex": r"^(?:sk|rk)_(?:live|test)_[a-zA-Z0-9_]{10,}$",
        "validation_error": "Stripe secret key must start with sk_test_, sk_live_, rk_test_, or rk_live_.",
    },
    "STRIPE_WEBHOOK_SECRET": {
        "description": "Stripe Webhook Signing Secret used to verify that incoming webhook events are genuinely from Stripe.",
        "provider_name": "Stripe",
        "provider_url": "https://dashboard.stripe.com/webhooks",
        "is_secret": True,
        "is_required": False,
        "has_default": False,
        "placeholder": "whsec_...",
        "example": "whsec_abc123def456ghi789jkl012mno345pqr",
        "validation_regex": r"^whsec_[a-zA-Z0-9]{20,}$",
        "validation_error": "Stripe webhook secret must start with whsec_.",
    },
    "RESEND_API_KEY": {
        "description": "Resend API Key used to dispatch transactional emails and contact form inquiries.",
        "provider_name": "Resend",
        "provider_url": "https://resend.com/api-keys",
        "is_secret": True,
        "is_required": False,
        "has_default": False,
        "placeholder": "re_...",
        "example": "re_123456789_abcdefghijklmnopqrstuvwxyz",
        "validation_regex": r"^re_[a-zA-Z0-9_]{10,}$",
        "validation_error": "Resend API key must start with re_.",
    },
    "BREVO_API_KEY": {
        "description": "Brevo (Sendinblue) API Key used for transactional email delivery and newsletter campaigns.",
        "provider_name": "Brevo",
        "provider_url": "https://app.brevo.com/settings/keys/api",
        "is_secret": True,
        "is_required": False,
        "has_default": False,
        "placeholder": "xkeysib-...",
        "example": "xkeysib-1234567890abcdef1234567890abcdef",
        "validation_regex": r"^.{16,}$",
        "validation_error": "Brevo API key must be at least 16 characters.",
    },
    "NOTIFICATION_EMAIL": {
        "description": "Destination email address where contact form submissions and lead notifications are routed.",
        "provider_name": "Email Settings",
        "provider_url": None,
        "is_secret": False,
        "is_required": False,
        "has_default": True,
        "default_value": "admin@example.com",
        "placeholder": "you@yourcompany.com",
        "example": "notifications@myagency.com",
        "validation_regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        "validation_error": "Please enter a valid email address.",
    },
    "RAZORPAY_KEY_ID": {
        "description": "Razorpay Key ID used for Indian and international payment checkout flows.",
        "provider_name": "Razorpay",
        "provider_url": "https://dashboard.razorpay.com/#/app/keys",
        "is_secret": False,
        "is_required": True,
        "has_default": False,
        "placeholder": "rzp_test_... or rzp_live_...",
        "example": "rzp_test_1DP5mmOlF5G5ag",
        "validation_regex": r"^rzp_(?:test|live)_[a-zA-Z0-9]{10,}$",
        "validation_error": "Razorpay key ID must start with rzp_test_ or rzp_live_.",
    },
    "RAZORPAY_KEY_SECRET": {
        "description": "Razorpay Key Secret used to verify payment signatures server-side.",
        "provider_name": "Razorpay",
        "provider_url": "https://dashboard.razorpay.com/#/app/keys",
        "is_secret": True,
        "is_required": True,
        "has_default": False,
        "placeholder": "Razorpay secret key",
        "example": "abc123XYZ456Secret789",
        "validation_regex": r"^.{8,}$",
        "validation_error": "Razorpay secret key must be at least 8 characters.",
    },
    "VITE_API_URL": {
        "description": "Backend API origin URL consumed by the React single-page frontend.",
        "provider_name": "Frontend Config",
        "provider_url": None,
        "is_secret": False,
        "is_required": False,
        "has_default": True,
        "default_value": "http://localhost:8000",
        "placeholder": "https://api.yourdomain.com",
        "example": "https://api.myproject.com",
        "validation_regex": r"^https?://.*$",
        "validation_error": "VITE_API_URL must start with http:// or https://",
    },
    "NEXT_PUBLIC_API_URL": {
        "description": "Backend API origin URL consumed by Next.js client components.",
        "provider_name": "Frontend Config",
        "provider_url": None,
        "is_secret": False,
        "is_required": False,
        "has_default": True,
        "default_value": "http://localhost:8000",
        "placeholder": "https://api.yourdomain.com",
        "example": "https://api.myproject.com",
        "validation_regex": r"^https?://.*$",
        "validation_error": "NEXT_PUBLIC_API_URL must start with http:// or https://",
    },
    "POSTGRES_PASSWORD": {
        "description": "Root database password for PostgreSQL Docker service.",
        "provider_name": "Docker / PostgreSQL",
        "provider_url": None,
        "is_secret": True,
        "is_required": False,
        "has_default": True,
        "default_value": "postgres",
        "placeholder": "postgres",
        "example": "secure_db_password_123",
        "validation_regex": r"^.{4,}$",
        "validation_error": "Postgres password must be at least 4 characters.",
    },
    "ENVIRONMENT": {
        "description": "Application execution environment.",
        "provider_name": "Runtime",
        "provider_url": None,
        "is_secret": False,
        "is_required": False,
        "has_default": True,
        "default_value": "production",
        "placeholder": "production",
        "example": "production",
        "validation_regex": r"^(?:production|staging|development|test)$",
        "validation_error": "Environment must be production, staging, or development.",
    },
}


class EnvScannerService:
    """
    Intelligent environment variable and secrets detection, explanation,
    and validation engine.
    """

    def scan_env_requirements(
        self,
        env_keys: Optional[List[str]] = None,
        file_contents: Optional[Dict[str, str]] = None,
        existing_env: Optional[Dict[str, str]] = None,
        stack_key: Optional[str] = None,
        auth_required: bool = False,
        stripe_needed: bool = False,
    ) -> List[EnvVarMetadata]:
        """
        Scans explicit keys, files (.env.example, docker-compose, source code),
        and architecture flags to produce an exhaustive, documented list of
        environment variables for pre-deployment inspection.
        """
        detected_keys: set[str] = set(env_keys or [])
        files = file_contents or {}
        existing = existing_env or {}

        # 1. Parse .env.example files if provided in files dict
        for path, content in files.items():
            if ".env" in path.lower() or path.endswith(".example"):
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        var_name = line.split("=", 1)[0].strip()
                        if var_name:
                            detected_keys.add(var_name)

        # 2. Heuristically discover env variables referenced in code
        for path, content in files.items():
            if path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml")):
                # Match os.getenv("VAR") or os.environ.get("VAR")
                for match in re.finditer(r'(?:os\.getenv|os\.environ\.get)\(\s*["\']([A-Z0-9_]+)["\']', content):
                    detected_keys.add(match.group(1))
                # Match process.env.VAR or import.meta.env.VAR
                for match in re.finditer(r'(?:process\.env|import\.meta\.env)\.([A-Z0-9_]+)', content):
                    detected_keys.add(match.group(1))

        # 3. Stack & Architecture Inferences
        if stack_key in ("react-fastapi-postgresql", "vue-fastapi-postgresql", "angular-fastapi-postgresql"):
            detected_keys.add("DATABASE_URL")
            detected_keys.add("PORT")
            detected_keys.add("ENVIRONMENT")
            detected_keys.add("VITE_API_URL")

        if auth_required:
            detected_keys.add("SECRET_KEY")

        if stripe_needed:
            detected_keys.add("STRIPE_SECRET_KEY")
            detected_keys.add("STRIPE_WEBHOOK_SECRET")

        # 4. Build rich metadata records
        results: List[EnvVarMetadata] = []
        for key in sorted(detected_keys):
            meta = KNOWN_ENV_REGISTRY.get(key)
            current_val = existing.get(key)

            if meta:
                item = EnvVarMetadata(
                    key=key,
                    description=meta["description"],
                    provider_name=meta["provider_name"],
                    provider_url=meta.get("provider_url"),
                    is_secret=meta.get("is_secret", True),
                    is_required=meta.get("is_required", False),
                    has_default=meta.get("has_default", False),
                    default_value=meta.get("default_value"),
                    placeholder=meta.get("placeholder", ""),
                    example=meta.get("example", ""),
                    validation_regex=meta.get("validation_regex"),
                    validation_error=meta.get("validation_error"),
                )
            else:
                # Custom / user-defined variable
                is_secret_heuristic = any(
                    term in key.lower() for term in ("secret", "key", "token", "password", "auth", "cred")
                )
                item = EnvVarMetadata(
                    key=key,
                    description=f"Custom environment variable required by {key.lower()}.",
                    provider_name="Custom Service",
                    is_secret=is_secret_heuristic,
                    is_required=False,
                    has_default=False,
                    placeholder=f"Enter {key}...",
                )

            # Determine configuration status
            if current_val is not None and str(current_val).strip() != "":
                item.status = "configured"
            elif item.has_default:
                item.status = "default"
            elif not item.is_required:
                item.status = "optional"
            else:
                item.status = "missing"

            results.append(item)

        return results

    def validate_deployment_env(
        self,
        env_vars: Dict[str, str],
        required_specs: Optional[List[EnvVarMetadata]] = None,
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Validates user-submitted environment variables against specifications.
        Returns:
            {
                "valid": bool,
                "errors": list[str],
                "warnings": list[str],
                "missing_critical": list[str],
                "sanitized_env": dict[str, str]
            }
        """
        errors: List[str] = []
        warnings: List[str] = []
        missing_critical: List[str] = []
        sanitized_env: Dict[str, str] = dict(env_vars or {})

        specs = required_specs or []
        spec_map = {s.key: s for s in specs}

        # Check required variables
        for spec in specs:
            val = sanitized_env.get(spec.key)
            is_empty = val is None or str(val).strip() == ""

            if is_empty:
                if spec.is_required and not spec.has_default:
                    missing_critical.append(spec.key)
                    errors.append(f"Missing required credential: '{spec.key}' ({spec.provider_name}).")
                elif spec.has_default and spec.default_value is not None:
                    sanitized_env[spec.key] = spec.default_value
                elif spec.key in ("SECRET_KEY", "JWT_SECRET"):
                    # Auto-generate cryptographically secure default if empty
                    auto_key = secrets.token_urlsafe(32)
                    sanitized_env[spec.key] = auto_key
                    warnings.append(f"Auto-generated secure random key for '{spec.key}'.")
            else:
                # Format validation
                val_str = str(val).strip()
                if spec.validation_regex and not re.match(spec.validation_regex, val_str):
                    msg = spec.validation_error or f"Invalid format for '{spec.key}'."
                    if strict_mode:
                        errors.append(msg)
                    else:
                        warnings.append(msg)

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "missing_critical": missing_critical,
            "sanitized_env": sanitized_env,
        }


# Global singleton instance
env_scanner_service = EnvScannerService()
