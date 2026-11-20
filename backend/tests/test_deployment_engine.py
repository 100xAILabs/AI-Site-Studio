"""
Test Suite for Phase 7 Deployment Engine Upgrade.
Tests:
- Architecture Target Detection (Static, Serverless Hybrid, Fullstack Container)
- Provider Factory Resolution ('local', 'docker', 'container', 'fullstack')
- Docker Deployment Provider Multi-stage Dockerfile and docker-compose.yml generation
- Build and Staging Pipelines
- Multi-probe Health Checking with retry backoff
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.deployment_providers.base import (
    DeploymentTarget,
    DeploymentProvider,
)
from app.services.deployment_providers import (
    get_deployment_provider,
    DockerDeploymentProvider,
    LocalDeploymentProvider,
)
from app.services.deployment_service import DeploymentService


@pytest.fixture
def temp_project():
    """Creates a temporary sandbox folder for testing target detection and build."""
    d = tempfile.mkdtemp(prefix="test_deploy_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class TestTargetDetection:
    """Tests heuristic detection of Static, Serverless Hybrid, and Fullstack Container architectures."""

    def test_detect_static_project(self, temp_project):
        provider = LocalDeploymentProvider()
        # Pure HTML/JS files
        (temp_project / "index.html").write_text("<!DOCTYPE html><html><body>Test</body></html>")
        (temp_project / "style.css").write_text("body { color: red; }")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.STATIC
        assert target.value == "static"

    def test_detect_serverless_hybrid_project(self, temp_project):
        provider = LocalDeploymentProvider()
        (temp_project / "index.html").write_text("<!DOCTYPE html><html><body>Test</body></html>")
        # backend/api directory present
        api_dir = temp_project / "backend" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "contact.py").write_text("def handler(req): return {'ok': True}")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.SERVERLESS_HYBRID
        assert target.value == "hybrid_serverless"

    def test_detect_serverless_hybrid_root_api(self, temp_project):
        provider = LocalDeploymentProvider()
        api_dir = temp_project / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "newsletter.py").write_text("def handler(): pass")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.SERVERLESS_HYBRID

    def test_detect_fullstack_container_with_compose(self, temp_project):
        provider = LocalDeploymentProvider()
        (temp_project / "docker-compose.yml").write_text("services:\n  web:\n    image: node:20")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.FULLSTACK_CONTAINER
        assert target.value == "fullstack_container"

    def test_detect_fullstack_container_with_dockerfile(self, temp_project):
        provider = LocalDeploymentProvider()
        (temp_project / "Dockerfile").write_text("FROM python:3.12-slim")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.FULLSTACK_CONTAINER

    def test_detect_fullstack_container_with_backend_main(self, temp_project):
        provider = LocalDeploymentProvider()
        backend_main = temp_project / "backend" / "app" / "main.py"
        backend_main.parent.mkdir(parents=True)
        backend_main.write_text("from fastapi import FastAPI\napp = FastAPI()")

        target = provider.detect_target(str(temp_project))
        assert target == DeploymentTarget.FULLSTACK_CONTAINER


class TestProviderFactory:
    """Tests provider factory lookup."""

    def test_get_local_provider(self):
        prov = get_deployment_provider("local")
        assert isinstance(prov, LocalDeploymentProvider)

    def test_get_docker_provider_aliases(self):
        for alias in ("docker", "container", "fullstack", "DOCKER", "Container"):
            prov = get_deployment_provider(alias)
            assert isinstance(prov, DockerDeploymentProvider)

    def test_unknown_provider_fallback(self):
        with pytest.raises(ValueError, match="Unsupported deployment provider"):
            get_deployment_provider("nonexistent_provider")


@pytest.mark.asyncio
class TestDockerDeploymentProvider:
    """Tests DockerDeploymentProvider validation, multi-stage file generation, and staging."""

    async def test_validate_and_auto_generate_docker_manifests(self, temp_project):
        provider = DockerDeploymentProvider()
        (temp_project / "index.html").write_text("<h1>App</h1>")
        backend_app = temp_project / "backend" / "app"
        backend_app.mkdir(parents=True)
        (backend_app / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")

        assert not (temp_project / "Dockerfile").exists()
        assert not (temp_project / "docker-compose.yml").exists()

        is_valid, err = await provider.validate(str(temp_project))
        assert is_valid is True
        assert err is None

        # Dockerfile and docker-compose.yml should be generated automatically
        dockerfile = temp_project / "Dockerfile"
        compose_file = temp_project / "docker-compose.yml"
        assert dockerfile.exists()
        assert compose_file.exists()

        df_content = dockerfile.read_text(encoding="utf-8")
        assert "FROM node:20-alpine AS frontend-builder" in df_content
        assert "FROM python:3.12-slim AS runner" in df_content
        assert "HEALTHCHECK" in df_content
        assert "/api/health" in df_content

        compose_content = compose_file.read_text(encoding="utf-8")
        assert "services:" in compose_content
        assert "ports:" in compose_content
        assert "healthcheck:" in compose_content

    async def test_build_and_stage_static_dist(self, temp_project):
        provider = DockerDeploymentProvider()
        dist_dir = temp_project / "dist"
        dist_dir.mkdir()
        (dist_dir / "index.html").write_text("<h1>Built SPA</h1>")
        (dist_dir / "assets.js").write_text("console.log('test');")

        success, logs, artifact_path = await provider.build(
            source_path=str(temp_project),
            build_command="static",
            output_dir="dist",
            env_vars={"NODE_ENV": "production"},
            deployment_id="dep-12345",
        )
        assert success is True
        assert Path(artifact_path).exists()
        assert (Path(artifact_path) / "index.html").exists()


@pytest.mark.asyncio
class TestHealthCheckEngine:
    """Tests multi-probe live URL health checking with retry logic."""

    async def test_local_health_check_missing_index_fails(self, temp_project):
        provider = LocalDeploymentProvider()
        # When site_id is given but no files exist on disk
        is_healthy, status_code, msg = await provider.health_check(
            "http://localhost:8000/sites/SITE-UNKNOWN/",
            site_id="SITE-UNKNOWN",
            retries=1,
        )
        assert is_healthy is False
        assert status_code == 404
        assert "missing or corrupted" in msg

    async def test_health_check_success_with_mock_client(self):
        provider = LocalDeploymentProvider()

        mock_root_resp = MagicMock()
        mock_root_resp.status_code = 200

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200

        async def mock_get(url):
            if "/api/health" in url:
                return mock_api_resp
            return mock_root_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=mock_get)
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            is_healthy, status_code, msg = await provider.health_check(
                "http://localhost:8000/sites/SITE-123/",
                site_id=None,
                check_path="/api/health",
                retries=2,
            )
            assert is_healthy is True
            assert status_code == 200
            assert "verified healthy" in msg

    async def test_docker_health_check_retry_failure(self):
        provider = DockerDeploymentProvider()

        mock_err_resp = MagicMock()
        mock_err_resp.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_err_resp)
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            is_healthy, status_code, msg = await provider.health_check(
                "http://localhost:8000/sites/SITE-FAIL/",
                site_id=None,
                check_path="/api/health",
                retries=2,
                retry_delay=0.01,
            )
            assert is_healthy is False
            assert status_code == 503
            assert "Health check failed after 2 attempts" in msg
