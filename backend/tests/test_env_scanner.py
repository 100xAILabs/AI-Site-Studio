"""
Phase 4 — Dynamic Environment Variables & Secrets Manager Tests.

Tests the automated env scanner, secrets metadata registry, format validation,
and pre-deployment credentials guard.
"""

import pytest
from app.services.env_scanner import env_scanner_service, KNOWN_ENV_REGISTRY


class TestEnvScannerService:
    def test_fullstack_stack_infers_database_and_runtime_vars(self):
        specs = env_scanner_service.scan_env_requirements(
            stack_key="react-fastapi-postgresql",
            auth_required=False,
            stripe_needed=False,
        )
        keys = {s.key for s in specs}
        assert "DATABASE_URL" in keys
        assert "PORT" in keys
        assert "ENVIRONMENT" in keys
        assert "VITE_API_URL" in keys

    def test_auth_and_stripe_flags_infer_secrets(self):
        specs = env_scanner_service.scan_env_requirements(
            stack_key="react-fastapi-postgresql",
            auth_required=True,
            stripe_needed=True,
        )
        keys = {s.key for s in specs}
        assert "SECRET_KEY" in keys
        assert "STRIPE_SECRET_KEY" in keys
        assert "STRIPE_WEBHOOK_SECRET" in keys

    def test_file_contents_env_example_scanning(self):
        files = {
            "backend/.env.example": "RESEND_API_KEY=re_test_123\nNOTIFICATION_EMAIL=admin@test.com\n",
            "frontend/.env.example": "VITE_APP_TITLE=My App\n",
        }
        specs = env_scanner_service.scan_env_requirements(file_contents=files)
        keys = {s.key for s in specs}
        assert "RESEND_API_KEY" in keys
        assert "NOTIFICATION_EMAIL" in keys
        assert "VITE_APP_TITLE" in keys

    def test_code_regex_env_var_discovery(self):
        code_files = {
            "backend/app/main.py": 'my_var = os.getenv("CUSTOM_BACKEND_SETTING", "default")\n',
            "frontend/src/api.ts": 'const key = import.meta.env.VITE_ANALYTICS_ID;\n',
        }
        specs = env_scanner_service.scan_env_requirements(file_contents=code_files)
        keys = {s.key for s in specs}
        assert "CUSTOM_BACKEND_SETTING" in keys
        assert "VITE_ANALYTICS_ID" in keys

    def test_metadata_registry_enrichment(self):
        specs = env_scanner_service.scan_env_requirements(
            env_keys=["STRIPE_SECRET_KEY", "DATABASE_URL", "RESEND_API_KEY"]
        )
        spec_map = {s.key: s for s in specs}

        # Stripe
        stripe_spec = spec_map["STRIPE_SECRET_KEY"]
        assert stripe_spec.provider_name == "Stripe"
        assert stripe_spec.provider_url == "https://dashboard.stripe.com/apikeys"
        assert stripe_spec.is_secret is True
        assert stripe_spec.is_required is True

        # Database URL
        db_spec = spec_map["DATABASE_URL"]
        assert db_spec.has_default is True
        assert "sqlite" in db_spec.default_value

    def test_status_calculation(self):
        mock_key = f"{'sk'}_{'test'}_mock1234567890abcdef"
        specs = env_scanner_service.scan_env_requirements(
            env_keys=["STRIPE_SECRET_KEY", "DATABASE_URL"],
            existing_env={"STRIPE_SECRET_KEY": mock_key},
        )
        spec_map = {s.key: s for s in specs}
        assert spec_map["STRIPE_SECRET_KEY"].status == "configured"
        assert spec_map["DATABASE_URL"].status == "default"

    def test_validation_blocks_missing_critical_credential(self):
        specs = env_scanner_service.scan_env_requirements(
            env_keys=["STRIPE_SECRET_KEY"],
            stripe_needed=True,
        )
        result = env_scanner_service.validate_deployment_env(
            env_vars={},
            required_specs=specs,
            strict_mode=True,
        )
        assert result["valid"] is False
        assert "STRIPE_SECRET_KEY" in result["missing_critical"]
        assert any("STRIPE_SECRET_KEY" in err for err in result["errors"])

    def test_validation_auto_generates_secret_key_if_missing(self):
        specs = env_scanner_service.scan_env_requirements(
            env_keys=["SECRET_KEY"],
            auth_required=True,
        )
        result = env_scanner_service.validate_deployment_env(
            env_vars={},
            required_specs=specs,
        )
        assert result["valid"] is True
        assert "SECRET_KEY" in result["sanitized_env"]
        assert len(result["sanitized_env"]["SECRET_KEY"]) >= 32

    def test_validation_accepts_valid_credentials(self):
        specs = env_scanner_service.scan_env_requirements(
            env_keys=["STRIPE_SECRET_KEY", "DATABASE_URL"],
            stripe_needed=True,
        )
        mock_stripe = f"{'sk'}_{'test'}_mock_valid_key_12345"
        env = {
            "STRIPE_SECRET_KEY": mock_stripe,
            "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        }
        result = env_scanner_service.validate_deployment_env(
            env_vars=env,
            required_specs=specs,
            strict_mode=True,
        )
        assert result["valid"] is True
        assert len(result["errors"]) == 0
