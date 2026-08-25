"""
Abstract Base Class for Multi-Tenant Website Deployment Providers.
Defines standard lifecycle operations for isolated customer workloads.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List


class DeploymentProvider(ABC):
    """
    Abstract interface for hosting and building isolated tenant websites.
    Implementations: LocalDeploymentProvider, DockerDeploymentProvider, CloudDeploymentProvider.
    """

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
    ) -> Tuple[bool, str]:
        """
        Deploys the compiled artifact to the tenant's isolated workload storage.
        Returns: (success: bool, live_url: str)
        """
        pass

    @abstractmethod
    async def health_check(self, live_url: str) -> Tuple[bool, int, str]:
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
