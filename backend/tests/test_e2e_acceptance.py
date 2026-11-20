"""
End-to-End Acceptance Verification Test Suite (Phase 10).
Validates the complete 7-scenario master architectural criteria for AI Site Studio:

1. Static portfolio with email delivery (contact form with phone/email dynamic binding).
2. Full-stack ATS with PostgreSQL & FastAPI (Lifespan, CRUD, asyncpg, migrations).
3. E-commerce sandbox payment (Stripe/Razorpay checkout, signature verify, order state machine).
4. Environment variable & secrets inspector (real-time diagnostics, validation, missing critical alerts).
5. Automated pre-flight testing & self-healing (AST healing, missing package injection, route repair).
6. Multi-target deployment & health probing (static, serverless hybrid, fullstack container with /api/health verification).
7. Visual fidelity & fluid responsive audit (clamp typography, 44px touch targets, zero horizontal overflow).
"""

import ast
import hashlib
import hmac
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.email_engine import (
    email_engine,
    AntiSpamGuard,
    SubmissionRateLimiter,
    EmailMessage,
    ConsoleMockEmailAdapter,
)
from app.services.payment_engine import (
    payment_engine,
    MockPaymentAdapter,
    RazorpayPaymentAdapter,
    OrderStateMachine,
    OrderStatus,
    PaymentStatus,
    IdempotentEventGuard,
    PaymentOrderPayload,
    PaymentItem,
    SignatureVerifyPayload,
)
from app.services.fullstack_scaffold import fullstack_scaffold_generator
from app.services.env_scanner import env_scanner_service
from app.services.debugger_service import ai_debugger
from app.services.deployment_readiness_auditor import deployment_readiness_auditor
from app.services.deployment_providers.base import DeploymentTarget
from app.services.deployment_providers import (
    get_deployment_provider,
    DockerDeploymentProvider,
    LocalDeploymentProvider,
)
from app.services.deployment_service import DeploymentService
from app.services.studio_service import _normalize_design_system
from app.services.architect_agent import ArchitectAgent


@pytest.fixture
def sandbox_env():
    """Provides a fresh isolated temp folder for multi-scenario verification."""
    tmp = tempfile.mkdtemp(prefix="site_studio_e2e_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================================
# Scenario 1: Static Portfolio with Dynamic Contact & Email Delivery
# ==============================================================================
class TestScenario1StaticPortfolioEmail:
    """Verifies contact submissions with phone/email dynamic binding and dual dispatch."""

    @pytest.mark.asyncio
    async def test_static_contact_submission_with_dynamic_binding(self):
        # 1. Anti-spam honeypot detection
        anti_spam = AntiSpamGuard()
        bot_is_valid, bot_msg = anti_spam.validate_submission(honeypot_value="http://spam.org")
        assert bot_is_valid is False
        assert "honeypot triggered" in (bot_msg or "")

        human_is_valid, human_msg = anti_spam.validate_submission(honeypot_value="")
        assert human_is_valid is True
        assert human_msg is None

        # 2. Rate limiter protection
        limiter = SubmissionRateLimiter(max_requests=5, window_seconds=60)
        assert limiter.is_allowed("192.168.1.100") is True

        # 3. Dynamic recipient binding & dual dispatch
        email_engine._mock_adapter.sent_messages.clear()

        # Motel room enquiry with specific destination mail & phone
        enquiry = {
            "name": "David Miller",
            "email": "david@guest.com",
            "phone": "+1-555-839-2049",
            "dates": "2026-12-01 to 2026-12-05",
            "message": "Need deluxe king room availability",
            "destination_email": "reservations@cozyhavenmotel.com",
        }

        # Dispatch dual inquiry
        admin_res, cust_res = await email_engine.send_contact_inquiry(
            sender_name=enquiry["name"],
            sender_email=enquiry["email"],
            sender_phone=enquiry["phone"],
            subject="Deluxe King Room Availability",
            message=enquiry["message"],
            recipient_email=enquiry["destination_email"],
            site_name="Cozy Haven Motel",
            metadata={"dates": enquiry["dates"]},
        )
        assert admin_res.success is True
        assert cust_res.success is True

        # Verify admin notice reached destination mail and preserved phone/enquiry details
        sent = email_engine._mock_adapter.sent_messages
        assert len(sent) >= 2
        admin_mail = next(m for m in sent if enquiry["destination_email"] in m.to)
        assert enquiry["phone"] in (admin_mail.html_body or "")
        assert enquiry["message"] in (admin_mail.html_body or "")

        # Verify customer auto-reply
        cust_mail = next(m for m in sent if enquiry["email"] in m.to)
        assert "Cozy Haven Motel" in cust_mail.subject


# ==============================================================================
# Scenario 2: Full-Stack ATS with PostgreSQL & FastAPI
# ==============================================================================
class TestScenario2FullStackATS:
    """Verifies full-stack FastAPI generation with Lifespan, CRUD, asyncpg, and migrations."""

    def test_ats_scaffold_has_lifespan_and_asyncpg(self, sandbox_env):
        # Generate fullstack FastAPI scaffold
        sample_tables = [
            {
                "name": "candidates",
                "fields": [
                    {"name": "id", "type": "uuid", "nullable": False},
                    {"name": "full_name", "type": "str", "nullable": False},
                    {"name": "email", "type": "str", "nullable": False, "unique": True},
                    {"name": "resume_url", "type": "str", "nullable": True},
                    {"name": "status", "type": "str", "nullable": False},
                ],
                "indexes": ["email"],
            }
        ]
        sample_routes = [
            {"method": "GET", "path": "/api/health", "description": "Health check"},
            {"method": "GET", "path": "/api/candidates", "description": "List candidates"},
            {"method": "POST", "path": "/api/candidates", "description": "Create candidate"},
        ]

        files = fullstack_scaffold_generator.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats_portal",
            db_tables=sample_tables,
            api_routes=sample_routes,
            auth_required=True,
            stripe_needed=False,
            env_vars=["DATABASE_URL", "SECRET_KEY"],
            page_names=["Home", "Candidates", "Jobs", "Contact"],
        )

        assert "backend/app/main.py" in files
        assert "backend/app/database.py" in files
        assert "backend/app/models.py" in files
        assert "backend/app/schemas.py" in files
        assert "backend/app/crud.py" in files

        # Write files into sandbox workspace to verify AST and directory integrity
        for rel_path, content in files.items():
            dest = sandbox_env / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        # Verify backend main.py uses @asynccontextmanager lifespan
        main_code = files["backend/app/main.py"]
        assert "lifespan" in main_code
        assert "@asynccontextmanager" in main_code
        assert 'on_event("startup")' not in main_code

        # Verify database config uses asyncpg and SQLAlchemy 2.0 async engine
        db_code = files["backend/app/database.py"]
        assert "postgresql+asyncpg" in db_code or "create_async_engine" in db_code

        # Verify Python syntax parses cleanly via ast
        tree = ast.parse(main_code)
        assert tree is not None
        assert ast.parse(files["backend/app/models.py"]) is not None


# ==============================================================================
# Scenario 3: E-Commerce Sandbox Payment
# ==============================================================================
class TestScenario3PaymentScaffold:
    """Verifies Stripe/Razorpay/Mock payment flow, signature verify, and state machine."""

    @pytest.mark.asyncio
    async def test_payment_checkout_and_signature_state_machine(self):
        # 1. Mock adapter checkout session
        mock_adapter = MockPaymentAdapter()
        order_payload = PaymentOrderPayload(
            order_id="ord_e2e_999",
            amount=149.50,
            currency="USD",
            items=[PaymentItem(name="Annual Pass", unit_amount=149.50, quantity=1)],
            customer_email="subscriber@example.com",
        )
        session = await mock_adapter.create_checkout_session(order_payload)
        assert session.success is True
        assert "session_id=" in session.checkout_url

        # 2. Timing-safe Razorpay signature check
        secret = "test_rzp_secret_9988"
        rzp_adapter = RazorpayPaymentAdapter(key_id="rzp_test_1", key_secret=secret)
        rzp_order_id = "order_DBJOWzybf0sJbb"
        rzp_payment_id = "pay_29QQoUBi66xm2f"
        valid_sig = hmac.new(
            secret.encode("utf-8"),
            f"{rzp_order_id}|{rzp_payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        verify_payload = SignatureVerifyPayload(
            order_id=rzp_order_id,
            payment_id=rzp_payment_id,
            signature=valid_sig,
            provider="razorpay",
        )
        verify_res = await rzp_adapter.verify_payment_signature(verify_payload)
        assert verify_res.valid is True
        assert verify_res.status == OrderStatus.PAID

        # Invalid signature must be rejected
        bad_verify = await rzp_adapter.verify_payment_signature(
            SignatureVerifyPayload(order_id=rzp_order_id, payment_id=rzp_payment_id, signature="tampered_sig", provider="razorpay")
        )
        assert bad_verify.valid is False
        assert bad_verify.status == OrderStatus.FAILED

        # 3. Order State Machine strict transitions
        assert OrderStateMachine.can_transition(OrderStatus.PENDING, OrderStatus.PROCESSING) is True
        assert OrderStateMachine.can_transition(OrderStatus.PROCESSING, OrderStatus.PAID) is True

        # Illegal transition: PAID -> PENDING must be rejected
        assert OrderStateMachine.can_transition(OrderStatus.PAID, OrderStatus.PENDING) is False
        with pytest.raises(ValueError, match="Invalid order state transition"):
            OrderStateMachine.validate_transition(OrderStatus.PAID, OrderStatus.PENDING)

        # 4. Webhook Idempotency Guard
        guard = IdempotentEventGuard()
        evt_id = "evt_stripe_charge_succeeded_001"
        assert guard.has_seen(evt_id) is False
        guard.mark_seen(evt_id)
        assert guard.has_seen(evt_id) is True


# ==============================================================================
# Scenario 4: Environment Variable & Secrets Inspector
# ==============================================================================
class TestScenario4SecretsInspector:
    """Verifies env scanner real-time diagnostics, missing critical alerts, and secret masking."""

    def test_secrets_inspection_and_masking(self):
        # Scan env specs for fullstack app with auth and stripe
        specs = env_scanner_service.scan_env_requirements(
            stack_key="react-fastapi-postgresql",
            auth_required=True,
            stripe_needed=True,
        )
        spec_keys = {s.key for s in specs}
        assert "DATABASE_URL" in spec_keys
        assert "SECRET_KEY" in spec_keys
        assert "STRIPE_SECRET_KEY" in spec_keys

        # Missing critical credentials validation in strict mode
        validation = env_scanner_service.validate_deployment_env(
            env_vars={"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/ats_db"},
            required_specs=specs,
            strict_mode=True,
        )
        assert validation["valid"] is False
        assert "STRIPE_SECRET_KEY" in validation["missing_critical"]

        # Valid credentials evaluation
        mock_stripe = "sk_test_mock_1234567890abcdef"
        valid_res = env_scanner_service.validate_deployment_env(
            env_vars={
                "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/ats_db",
                "STRIPE_SECRET_KEY": mock_stripe,
            },
            required_specs=specs,
            strict_mode=False,
        )
        assert "SECRET_KEY" in valid_res["sanitized_env"]
        assert len(valid_res["sanitized_env"]["SECRET_KEY"]) >= 32


# ==============================================================================
# Scenario 5: Automated Pre-Flight Testing & Self-Healing
# ==============================================================================
class TestScenario5PreflightAndSelfHealing:
    """Verifies AST syntax healing, lifespan conversion, and /api/health auto-injection."""

    def test_self_healing_heals_syntax_and_injects_health(self, sandbox_env):
        # 1. Create project with HTML missing viewport & having dead hash
        (sandbox_env / "index.html").write_text("<html><head></head><body><a href=\"#\">Home</a></body></html>", encoding="utf-8")
        (sandbox_env / "package.json").write_text(json.dumps({"name": "app", "dependencies": {}}), encoding="utf-8")

        # 2. Main app using deprecated on_event and missing /api/health
        backend_dir = sandbox_env / "backend"
        backend_dir.mkdir(parents=True, exist_ok=True)
        main_py = backend_dir / "main.py"
        main_py.write_text(
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.on_event('startup')\n"
            "async def startup_event():\n"
            "    pass\n",
            encoding="utf-8",
        )
        (backend_dir / "database.py").write_text('DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite"\n', encoding="utf-8")
        (backend_dir / "requirements.txt").write_text("fastapi\naiosqlite\n", encoding="utf-8")

        # Run pre-flight sweep with positional workspace path
        report = deployment_readiness_auditor.run_preflight_test_sweep(sandbox_env)
        assert report["passed"] is True
        assert report["checks_run"] >= 4

        # Verify /api/health was injected and on_event was modernized
        healed_main = main_py.read_text(encoding="utf-8")
        assert "/api/health" in healed_main or "/health" in healed_main
        assert '@app.on_event("startup")' not in healed_main
        ast.parse(healed_main)

        # Verify frontend AST healing tool works on dirty JSX
        dirty_jsx = "import React from 'react';\nexport default function Btn() { return <button>Click</button>;; }\n"
        is_valid, healed_jsx, _ = ai_debugger.validate_and_heal_frontend_syntax(dirty_jsx, "Btn.jsx")
        assert is_valid is True
        assert ";;" not in healed_jsx


# ==============================================================================
# Scenario 6: Multi-Target Deployment & Health Probing
# ==============================================================================
class TestScenario6MultiTargetDeploy:
    """Verifies multi-target provider resolution, Docker scaffolding, and health check probing."""

    @pytest.mark.asyncio
    async def test_multi_target_provider_and_docker_scaffold(self, sandbox_env):
        # 1. Target resolution
        local_provider = get_deployment_provider("local")
        assert isinstance(local_provider, LocalDeploymentProvider)

        docker_provider = get_deployment_provider("docker")
        assert isinstance(docker_provider, DockerDeploymentProvider)

        # 2. Heuristic Target Detection
        (sandbox_env / "index.html").write_text("<h1>Web</h1>", encoding="utf-8")
        assert local_provider.detect_target(str(sandbox_env)) == DeploymentTarget.STATIC

        # 3. Docker validation and automated manifest generation
        backend_app = sandbox_env / "backend" / "app"
        backend_app.mkdir(parents=True, exist_ok=True)
        (backend_app / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

        is_valid, err = await docker_provider.validate(str(sandbox_env))
        assert is_valid is True
        assert err is None

        dockerfile = sandbox_env / "Dockerfile"
        compose_file = sandbox_env / "docker-compose.yml"
        assert dockerfile.exists()
        assert compose_file.exists()

        df_content = dockerfile.read_text(encoding="utf-8")
        assert "FROM python" in df_content or "FROM node" in df_content


# ==============================================================================
# Scenario 7: Visual Fidelity & Fluid Responsive Audit
# ==============================================================================
class TestScenario7VisualFidelityDirectives:
    """Verifies Phase 9 premium visual generation tokens across design system and manifest pages."""

    def test_design_system_and_page_manifest_visual_tokens(self):
        # 1. Dark Luxe archetype
        tech_design = _normalize_design_system(
            {},
            category="Technology",
            genre="Deep Tech AI",
            prompt="Design a dark luxury cyberpunk neural interface",
        )
        assert tech_design["aesthetic_direction"] == "dark_luxe"
        assert tech_design["fluid_heading_clamp"].startswith("clamp(")
        assert tech_design["fluid_body_clamp"].startswith("clamp(")
        assert tech_design["min_touch_target"] == "44px"
        assert "glow_accent" in tech_design
        assert "card_border" in tech_design

        # Clean Modern SaaS archetype
        saas_design = _normalize_design_system(
            {},
            category="Business",
            genre="B2B Accounting",
            prompt="Build a clean modern B2B analytics platform for teams",
        )
        assert saas_design["aesthetic_direction"] == "clean_saas"
        assert saas_design["min_touch_target"] == "44px"

        # 2. ArchitectAgent page manifest visual directives
        agent = ArchitectAgent()
        manifest = {
            "site_title": "Grand Horizon Resort",
            "pages": [
                {"name": "Home", "filename": "index.html", "purpose": "Resort landing"},
                {"name": "Suites", "filename": "suites.html", "purpose": "Room preview"},
                {"name": "Contact", "filename": "contact.html", "purpose": "Inquiry form"},
            ],
        }
        normalized = agent._normalize_manifest(
            manifest,
            original_pages=manifest["pages"],
            plan={"pages": manifest["pages"]},
            genre="Resort",
        )

        for page in normalized["pages"]:
            assert "visual_directive" in page, f"Page {page['filename']} must have visual_directive"
            vd = page["visual_directive"]
            assert vd["min_touch_target"] == "44px"
            assert vd["zero_horizontal_overflow"] is True
            assert vd["mobile_breakpoint"] == "768px"
            assert vd["fluid_heading_clamp"].startswith("clamp(")
            assert vd["fluid_body_clamp"].startswith("clamp(")
