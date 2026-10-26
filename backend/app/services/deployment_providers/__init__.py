"""
Deployment Providers Package.
"""

from app.services.deployment_providers.base import DeploymentProvider
from app.services.deployment_providers.local_provider import LocalDeploymentProvider, local_deployment_provider
from app.services.deployment_providers.vercel_provider import VercelDeploymentProvider, vercel_deployment_provider


def get_deployment_provider(provider: str):
    provider = (provider or "local").strip().lower()
    if provider == "local":
        return local_deployment_provider
    if provider == "vercel":
        return vercel_deployment_provider
    raise ValueError(f"Unsupported deployment provider '{provider}'. Choose 'local' or 'vercel'.")

__all__ = [
    "DeploymentProvider",
    "LocalDeploymentProvider",
    "local_deployment_provider",
    "VercelDeploymentProvider",
    "vercel_deployment_provider",
    "get_deployment_provider",
]
