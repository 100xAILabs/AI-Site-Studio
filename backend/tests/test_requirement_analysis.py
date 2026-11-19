import pytest
from app.services.requirement_analyzer import (
    requirement_analyzer,
    ArchitectureType,
    ProjectSpecification,
)
from app.services.studio_service import detect_stack_from_prompt
from app.services.backend_generator import SUPPORTED_STACKS
from app.services.architect_agent import architect_agent


def test_ats_tracking_classification_fullstack():
    """ATS and recruitment portals must be classified as Full-Stack with PostgreSQL and Auth."""
    prompt = "Build an ATS tracking platform for our recruitment team with candidate pipelines, resume screening, and recruiter login."
    spec: ProjectSpecification = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="SaaS & Technology",
        genre="Applicant Tracking System",
    )

    assert spec.architecture_type == ArchitectureType.FULLSTACK
    assert spec.stack_key == "react-fastapi-postgresql"
    assert spec.frontend_framework == "react"
    assert spec.backend_required is True
    assert spec.backend_framework == "fastapi"
    assert spec.database_required is True
    assert spec.database_type == "postgresql"
    assert spec.auth_required is True
    assert spec.auth_type == "jwt_rbac"
    assert spec.deployment_target == "fullstack_container"
    assert "DATABASE_URL" in spec.required_env_vars
    assert "JWT_SECRET" in spec.required_env_vars
    assert any("ATS" in f or "Applicant" in f for f in spec.features_detected)

    # Check suggested pages
    page_names = [p.name for p in spec.suggested_pages]
    assert "Dashboard" in page_names
    assert "Jobs" in page_names
    assert "Candidates" in page_names
    assert "Pipeline" in page_names

    # Check studio_service stack detection matches
    detected_stack = detect_stack_from_prompt(prompt, "SaaS & Technology", "Applicant Tracking System")
    assert detected_stack == "react-fastapi-postgresql"


def test_ecommerce_store_classification_fullstack():
    """E-Commerce with cart and checkout must be Full-Stack with Stripe and PostgreSQL."""
    prompt = "Create an online store for luxury watches with shopping cart with stripe checkout and order management system."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="E-Commerce",
        genre="Storefront",
    )

    assert spec.architecture_type == ArchitectureType.FULLSTACK
    assert spec.stack_key == "react-fastapi-postgresql"
    assert spec.database_required is True
    assert spec.database_type == "postgresql"
    assert spec.payment_required is True
    assert spec.payment_gateway == "stripe"
    assert "STRIPE_SECRET_KEY" in spec.required_env_vars
    assert "DATABASE_URL" in spec.required_env_vars


def test_crm_admin_portal_classification_fullstack():
    """CRM or customer portal with database CRUD and user authentication must be Full-Stack."""
    prompt = "Build a real estate CRM system with client portal, user login system, and admin crud portal with database schema."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Business",
        genre="CRM Portal",
    )

    assert spec.architecture_type == ArchitectureType.FULLSTACK
    assert spec.stack_key == "react-fastapi-postgresql"
    assert spec.database_required is True
    assert spec.database_type == "postgresql"
    assert spec.auth_required is True


def test_hybrid_website_classification():
    """Content sites with contact form or email inquiries must be Hybrid with serverless API."""
    prompt = "Design a sleek corporate website for an architectural consulting agency with an interactive contact form and quote request form to send inquiries."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Business",
        genre="Consulting Agency",
    )

    assert spec.architecture_type == ArchitectureType.HYBRID
    assert spec.stack_key == "hybrid-serverless-api"
    assert spec.backend_required is True
    assert spec.backend_framework == "serverless"
    assert spec.database_required is False
    assert spec.email_required is True
    assert spec.email_service == "smtp_resend"
    assert "RESEND_API_KEY" in spec.required_env_vars
    assert spec.deployment_target == "hybrid_serverless"


def test_pure_static_website_classification():
    """Static presentation showcases with zero dynamic forms should be pure Static."""
    prompt = "Create a minimal showcase website displaying my photography gallery with external Instagram links."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Portfolio",
        genre="Photography",
    )

    assert spec.architecture_type == ArchitectureType.STATIC
    assert spec.stack_key == "html-css-js"
    assert spec.backend_required is False
    assert spec.database_required is False
    assert spec.auth_required is False


def test_developer_skills_scrubbing_preserves_portfolio():
    """
    When an author lists resume skills ('I am a full stack React, Python, PostgreSQL developer'),
    the analyzer scrubs the skills and does not mistakenly generate an enterprise SaaS backend for a personal portfolio.
    """
    prompt = "I am a full stack software engineer with 6 years experience in React, Python, PostgreSQL, and FastAPI. Build my personal developer portfolio showcasing my past work and projects."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Portfolio",
        genre="Developer Portfolio",
    )

    # Should NOT be classified as fullstack SaaS
    assert spec.architecture_type in {ArchitectureType.STATIC, ArchitectureType.HYBRID}
    assert spec.stack_key in {"html-css-js", "hybrid-serverless-api"}
    assert spec.database_required is False


def test_explicit_stack_override():
    """Explicit requested stack must always be honored."""
    prompt = "Build a local bakery menu website."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Restaurant",
        genre="Bakery",
        requested_stack="react-fastapi-postgresql",
    )
    assert spec.architecture_type == ArchitectureType.FULLSTACK
    assert spec.stack_key == "react-fastapi-postgresql"

    spec_static = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Restaurant",
        genre="Bakery",
        requested_stack="html-css-js",
    )
    assert spec_static.architecture_type == ArchitectureType.STATIC
    assert spec_static.stack_key == "html-css-js"


def test_explicit_framework_directive():
    """Explicit framework directive in prompt must be honored."""
    prompt = "Build a modern portfolio for a 3D designer using Vue.js."
    spec = requirement_analyzer.analyze_requirements(
        prompt=prompt,
        category="Portfolio",
        genre="3D Designer",
    )
    assert spec.architecture_type == ArchitectureType.FULLSTACK
    assert spec.stack_key == "vue-fastapi-postgresql"
    assert spec.frontend_framework == "vue"


def test_supported_stacks_integrity():
    """Ensure all stacks defined in requirement analyzer exist in backend generator SUPPORTED_STACKS."""
    for stack in ["html-css-js", "hybrid-serverless-api", "react-fastapi-postgresql", "vue-fastapi-postgresql", "angular-fastapi-postgresql"]:
        assert stack in SUPPORTED_STACKS
        assert "label" in SUPPORTED_STACKS[stack]
        assert "frontend" in SUPPORTED_STACKS[stack]


def test_architect_agent_embeds_project_specification():
    """Architect manifest must carry the authoritative project specification."""
    spec = requirement_analyzer.analyze_requirements(
        prompt="Build an ATS tracking platform for recruiters",
        category="SaaS & Technology",
        genre="ATS",
    )
    plan = {
        "title": "RecruitAI ATS",
        "pages": [
            {"name": "Dashboard", "filename": "index.html", "purpose": "Overview"},
            {"name": "Candidates", "filename": "candidates.html", "purpose": "Candidate List"},
        ],
        "project_specification": spec.model_dump(),
    }
    manifest = architect_agent._build_fallback_manifest(
        prompt="Build an ATS tracking platform for recruiters",
        category="SaaS & Technology",
        genre="ATS",
        plan=plan,
        answers={},
        stack=spec.stack_key,
    )
    assert "project_specification" in manifest
    assert manifest["project_specification"]["architecture_type"] == "fullstack"
    assert manifest["project_specification"]["stack_key"] == "react-fastapi-postgresql"
    assert manifest["project_specification"]["database_type"] == "postgresql"
