"""
Abstract Base Class for Multi-Tenant Website Deployment Providers.
Defines standard lifecycle operations for isolated customer workloads across
Static, Serverless Hybrid, and Full-Stack Container targets.
"""

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Tuple, Optional, List


class DeploymentTarget(str, Enum):
    STATIC = "static"
    SERVERLESS_HYBRID = "hybrid_serverless"
    FULLSTACK_CONTAINER = "fullstack_container"


class DeploymentProvider(ABC):
    """
    Abstract interface for hosting and building isolated tenant websites.
    Implementations: LocalDeploymentProvider, DockerDeploymentProvider, VercelDeploymentProvider.
    """

    def detect_target(self, source_path: str) -> DeploymentTarget:
        """
        Inspects project codebase and determines the optimal deployment target:
        - FULLSTACK_CONTAINER: Dockerfile, docker-compose.yml, or backend/app/main.py
        - SERVERLESS_HYBRID: backend/api or api/ directory with serverless handlers
        - STATIC: Pure client HTML/CSS/JS or Vite/React static SPA
        """
        if not os.path.exists(source_path):
            return DeploymentTarget.STATIC

        # 1. Full-stack container indicators
        if (
            os.path.exists(os.path.join(source_path, "docker-compose.yml"))
            or os.path.exists(os.path.join(source_path, "Dockerfile"))
            or os.path.exists(os.path.join(source_path, "backend", "app", "main.py"))
            or os.path.exists(os.path.join(source_path, "backend", "main.py"))
        ):
            return DeploymentTarget.FULLSTACK_CONTAINER

        # 2. Serverless hybrid indicators
        if (
            os.path.isdir(os.path.join(source_path, "backend", "api"))
            or os.path.isdir(os.path.join(source_path, "api"))
        ):
            return DeploymentTarget.SERVERLESS_HYBRID

        return DeploymentTarget.STATIC

    @abstractmethod
    async def validate(self, source_path: str) -> Tuple[bool, Optional[str]]:
        """Validate project source structure before compilation."""
        pass

    @abstractmethod
    async def build(
        self,
        source_path: str,
        build_command: str,
        output_dir: str,
        env_vars: Dict[str, str],
        deployment_id: str,
    ) -> Tuple[bool, str, str]:
        """
        Runs isolated compilation.
        Returns: (success: bool, logs: str, artifact_path: str)
        """
        pass

    @abstractmethod
    async def deploy(
        self,
        artifact_path: str,
        site_id: str,
        version: str,
        build_command: Optional[str] = None,
        output_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """
        Deploys the compiled artifact to the tenant's isolated workload storage.
        Returns: (success: bool, live_url: str)
        """
        pass

    @abstractmethod
    async def health_check(
        self,
        live_url: str,
        site_id: Optional[str] = None,
        check_path: str = "/api/health",
    ) -> Tuple[bool, int, str]:
        """
        Verifies HTTP 200 availability and integrity of the deployed workload.
        Returns: (is_healthy: bool, status_code: int, message: str)
        """
        pass

    @abstractmethod
    async def rollback(self, site_id: str, target_version: str) -> Tuple[bool, str]:
        """
        Atomic zero-downtime traffic switch to a previous deployment version.
        Returns: (success: bool, live_url: str)
        """
        pass

    @abstractmethod
    async def stop(self, site_id: str) -> bool:
        """Suspends or stops the tenant workload."""
        pass

    @abstractmethod
    async def remove(self, site_id: str) -> bool:
        """Deletes all artifacts associated with the tenant site."""
        pass
