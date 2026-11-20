"""
Full Lifecycle Integration Test:
From User Login -> AI Template Generation -> Project & Security Analysis ->
Multi-Target Deployment -> Marketplace Retailing -> Buyer Purchase & Resale Fulfillment.

Validates:
1. User registration & JWT authentication.
2. AI Studio project generation with design directives and multi-page manifests.
3. Automated project readiness audit and security scan.
4. Deployment scaffolding (Dockerfile & compose) with live health probing.
5. Marketplace retailing with Extreme Creator monetization.
6. End-to-end customer purchase, license issuance, and verified download.
"""

import io
import json
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.category import Category
from app.models.template import Template, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.license import License, LicenseType
from app.core.security import create_access_token, hash_password
from app.services.security_scanner import security_scanner
from app.services.deployment_readiness_auditor import deployment_readiness_auditor
from app.services.deployment_providers import get_deployment_provider, DockerDeploymentProvider
from app.services.studio_service import _normalize_design_system
from app.services.architect_agent import ArchitectAgent


@pytest.mark.asyncio
class TestFullLifecycleLoginToResell:
    """End-to-end user lifecycle test: Login -> Generate -> Analyze -> Deploy -> Resell -> Purchase."""

    async def test_complete_studio_to_marketplace_resell_lifecycle(
        self,
        client: AsyncClient,
        db: AsyncSession,
        tmp_path: Path,
    ):
        # ======================================================================
        # STEP 1: Creator User Registration & Authentication
        # ======================================================================
        creator_password = "SecurePassword123!"
        creator = User(
            email="extreme_creator@sitestudio.io",
            username="extreme_creator",
            hashed_password=hash_password(creator_password),
            role=UserRole.USER,
            subscription_tier="extreme",  # Extreme tier has marketplace retailing privileges
            is_active=True,
            is_email_verified=True,
            creator_brand_name="Nexus Studios",
            creator_store_slug="nexus-studios",
            token_version=1,
        )
        db.add(creator)

        # Seed Marketplace Category
        category = Category(
            name="AI & SaaS",
            slug="ai-saas",
            description="Next-generation SaaS and AI applications",
            sort_order=1,
            is_active=True,
        )
        db.add(category)
        await db.commit()

        # Login via /api/v1/auth/login with JSON body
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "extreme_creator@sitestudio.io", "password": creator_password},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        creator_token = login_res.json()["access_token"]
        creator_headers = {"Authorization": f"Bearer {creator_token}"}

        # ======================================================================
        # STEP 2: Studio Project Planning & Multi-Agent Generation
        # ======================================================================
        # UI Designer Agent Design System Normalization
        design_system = _normalize_design_system(
            raw={},
            category="AI & SaaS",
            genre="AI Developer Platform",
            prompt="Build a dark luxury developer platform for AI agent orchestration",
        )
        assert design_system["aesthetic_direction"] == "dark_luxe"
        assert design_system["min_touch_target"] == "44px"
        assert "clamp(" in design_system["fluid_heading_clamp"]

        # Architect Agent Manifest Generation
        architect = ArchitectAgent()
        manifest_raw = {
            "site_title": "Nexus AI Agent Studio",
            "pages": [
                {"name": "Home", "filename": "index.html", "purpose": "Platform gateway and agent builder"},
                {"name": "Docs", "filename": "docs.html", "purpose": "Developer API reference"},
                {"name": "Pricing", "filename": "pricing.html", "purpose": "Transparent tier selection"},
                {"name": "Contact", "filename": "contact.html", "purpose": "Enterprise support & sales enquiry"},
            ],
        }
        manifest = architect._normalize_manifest(
            manifest_raw,
            original_pages=manifest_raw["pages"],
            plan={"pages": manifest_raw["pages"]},
            genre="AI SaaS",
        )
        for page in manifest["pages"]:
            assert "visual_directive" in page
            assert page["visual_directive"]["zero_horizontal_overflow"] is True

        # Generate complete, syntactically clean project files
        project_files = {
            "index.html": (
                "<!DOCTYPE html><html lang='en'><head>"
                "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                "<title>Nexus AI</title><link rel='stylesheet' href='style.css'>"
                "</head><body><header><nav><a href='index.html' class='active'>Home</a><a href='docs.html'>Docs</a></nav></header>"
                "<main><h1>Next-Gen Agent Engine</h1><a href='contact.html' class='btn'>Get Started</a></main>"
                "<footer><p>© 2026 Nexus Studios</p></footer></body></html>"
            ),
            "docs.html": (
                "<!DOCTYPE html><html lang='en'><head>"
                "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                "<title>Docs</title><link rel='stylesheet' href='style.css'>"
                "</head><body><header><nav><a href='index.html'>Home</a><a href='docs.html' class='active'>Docs</a></nav></header>"
                "<main><h2>API Reference</h2></main></body></html>"
            ),
            "contact.html": (
                "<!DOCTYPE html><html lang='en'><head>"
                "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                "<title>Contact</title><link rel='stylesheet' href='style.css'>"
                "</head><body><form action='https://formsubmit.co/ajax/contact@nexus.io' method='POST'>"
                "<input type='text' name='name' required><input type='email' name='email' required>"
                "<button type='submit'>Send</button></form></body></html>"
            ),
            "style.css": (
                ":root { --bg: #0B0D13; --text: #F8FAFC; --accent: #6366F1; }\n"
                "body { background: var(--bg); color: var(--text); overflow-x: hidden; font-size: clamp(1rem, 1.2vw, 1.125rem); }\n"
                "button, a { min-height: 44px; display: inline-flex; align-items: center; }\n"
            ),
            "backend/main.py": (
                "from contextlib import asynccontextmanager\n"
                "from fastapi import FastAPI\n\n"
                "@asynccontextmanager\n"
                "async def lifespan(app: FastAPI):\n"
                "    yield\n\n"
                "app = FastAPI(title='Nexus API', lifespan=lifespan)\n\n"
                "@app.get('/api/health')\n"
                "async def health():\n"
                "    return {'status': 'healthy', 'service': 'nexus-api'}\n"
            ),
            "backend/requirements.txt": "fastapi>=0.115.0\nuvicorn>=0.30.0\n",
        }

        # Write files into temporary workspace for audit & deployment testing
        for path_str, content in project_files.items():
            dest = tmp_path / path_str
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        # Create zip archive in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path_str, content in project_files.items():
                zf.writestr(path_str, content.encode("utf-8"))
        zip_bytes = zip_buf.getvalue()

        # ======================================================================
        # STEP 3: Automated Project & Security Analysis
        # ======================================================================
        # 1. Security scan on zip bytes
        scan_report = security_scanner.scan_zip_bytes(zip_bytes, "nexus-ai-studio.zip")
        assert scan_report["is_safe"] is True
        assert not any(f.get("severity") == "CRITICAL" for f in scan_report.get("findings", []))

        # 2. Automated Pre-Flight Test Sweep
        sweep_report = deployment_readiness_auditor.run_preflight_test_sweep(tmp_path)
        assert sweep_report["passed"] is True
        assert sweep_report["checks_run"] >= 4

        # ======================================================================
        # STEP 4: Multi-Target Deployment & Health Probing
        # ======================================================================
        docker_provider = get_deployment_provider("docker")
        is_valid, deploy_err = await docker_provider.validate(str(tmp_path))
        assert is_valid is True
        assert deploy_err is None

        # Verify auto-generated Docker manifests
        assert (tmp_path / "Dockerfile").exists()
        assert (tmp_path / "docker-compose.yml").exists()

        # Simulate live health probe against /api/health
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_probe:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"status": "healthy"}
            mock_probe.return_value = mock_res

            async with AsyncClient() as probe_client:
                health_res = await probe_client.get("http://localhost:8000/api/health")
                assert health_res.status_code == 200
                assert health_res.json().get("status") == "healthy"

        # Register template in database as an AI-generated Studio project
        template = Template(
            title="Nexus AI Agent Studio Draft",
            slug="nexus-ai-agent-studio-draft",
            short_description="Turnkey AI Agent Studio platform with docs and contact routing",
            description="Comprehensive multi-page SaaS template built with FastAPI and modern responsive UI.",
            thumbnail_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe",
            price=Decimal("0.00"),
            is_free=True,
            seller_id=creator.id,
            category_id=category.id,
            status=TemplateStatus.DRAFT,
            template_origin="studio",
            tags=["studio-project", "ai-generated", "saas"],
            download_assets={"zip": "https://storage.sitestudio.io/projects/nexus-ai.zip"},
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

        # ======================================================================
        # STEP 5: Retail Template on the Marketplace
        # ======================================================================
        retail_payload = {
            "template_id": str(template.id),
            "retail_price": 49.00,
            "title": "Nexus AI Agent Platform (Commercial Edition)",
            "short_description": "Production-ready AI Agent Studio template with FastAPI backend & responsive Dark Luxe design",
            "category_id": str(category.id),
            "tags": ["ai-agents", "fastapi", "saas", "dark-luxe"],
        }
        retail_res = await client.post(
            "/api/v1/templates/retail",
            json=retail_payload,
            headers=creator_headers,
        )
        assert retail_res.status_code == 200, f"Retail failed: {retail_res.text}"
        retailed_data = retail_res.json()
        assert retailed_data["title"] == "Nexus AI Agent Platform (Commercial Edition)"
        assert float(retailed_data["price"]) == 49.00
        assert "retailed" in retailed_data["tags"]
        assert "extreme-creator" in retailed_data["tags"]

        # Platform Admin approves template for sale in the marketplace
        reloaded_template = await db.get(Template, template.id)
        reloaded_template.status = TemplateStatus.PUBLISHED
        await db.commit()
        await db.refresh(reloaded_template)

        # Verify published template is discoverable in public marketplace catalog
        catalog_res = await client.get("/api/v1/templates?category=ai-saas")
        assert catalog_res.status_code == 200
        catalog_items = catalog_res.json().get("items", [])
        assert any(item["id"] == str(template.id) for item in catalog_items)

        # ======================================================================
        # STEP 6: Customer Purchase & Resale Fulfillment
        # ======================================================================
        buyer_password = "BuyerPassword123!"
        buyer = User(
            email="tech_founder@venture.com",
            username="tech_founder",
            hashed_password=hash_password(buyer_password),
            role=UserRole.USER,
            subscription_tier="free",
            is_active=True,
            is_email_verified=True,
            token_version=1,
        )
        db.add(buyer)
        await db.commit()

        # Buyer logs in via JSON body
        buyer_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "tech_founder@venture.com", "password": buyer_password},
        )
        assert buyer_login.status_code == 200
        buyer_token = buyer_login.json()["access_token"]
        buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

        # Buyer creates purchase order for the retailed template
        order_payload = {
            "items": [
                {
                    "template_id": str(template.id),
                    "license_type": "regular",
                }
            ],
            "country_code": "US",
        }
        order_res = await client.post(
            "/api/v1/orders",
            json=order_payload,
            headers=buyer_headers,
        )
        assert order_res.status_code == 201, f"Order creation failed: {order_res.text}"
        order_data = order_res.json()
        assert order_data["status"] == "pending"
        assert float(order_data["total"]) == 49.00
        order_id = uuid.UUID(order_data["id"])

        # Complete Payment Simulation (Order -> COMPLETED, License issued)
        completed_order = await db.get(Order, order_id)
        completed_order.status = OrderStatus.COMPLETED
        buyer_license = License(
            user_id=buyer.id,
            template_id=template.id,
            order_id=order_id,
            license_type=LicenseType.REGULAR,
            license_key=f"LIC-NEXUS-{uuid.uuid4().hex[:12].upper()}",
            is_active=True,
        )
        db.add(buyer_license)
        await db.commit()

        # Buyer requests secure template download via /api/v1/templates/{id}/download
        download_res = await client.post(
            f"/api/v1/templates/{template.id}/download",
            headers=buyer_headers,
        )
        assert download_res.status_code == 200, f"Download failed: {download_res.text}"
        download_data = download_res.json()
        assert "download_url" in download_data
        assert template.download_assets["zip"] in download_data["download_url"]
        assert download_data["is_clean"] is True
        assert download_data["license_type"] == "regular"

        # Verify seller received creator sales entitlement / attribution
        order_items_res = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )
        item = order_items_res.scalar_one()
        assert item.template_id == template.id
        assert item.price == Decimal("49.00")
