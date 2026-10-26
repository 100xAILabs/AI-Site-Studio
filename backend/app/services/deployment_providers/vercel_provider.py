"""Deploy prebuilt static sites to Vercel using its file and deployment APIs."""

import asyncio
import hashlib
import logging
import os
import re
from pathlib import PurePosixPath, PureWindowsPath
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx

from app.core.config import settings
from app.services.deployment_providers.base import DeploymentProvider
from app.services.deployment_providers.local_provider import LocalDeploymentProvider

logger = logging.getLogger(__name__)


class VercelDeploymentProvider(DeploymentProvider):
    """Build locally, upload the compiled static artifact, and wait for Vercel readiness."""

    api_base = "https://api.vercel.com"
    max_files = 5000
    max_total_bytes = 100 * 1024 * 1024

    def __init__(self):
        self.validator = LocalDeploymentProvider()

    def _auth_headers(self):
        if not settings.VERCEL_TOKEN:
            raise RuntimeError("Vercel deployment is not configured. Set VERCEL_TOKEN in the backend environment.")
        return {"Authorization": f"Bearer {settings.VERCEL_TOKEN}"}

    def _params(self):
        return {"teamId": settings.VERCEL_TEAM_ID} if settings.VERCEL_TEAM_ID else {}

    async def validate(self, source_path: str):
        return await self.validator.validate(source_path)

    async def build(self, source_path: str, build_command: str = "npm run build", output_dir: str = "dist", env_vars: Optional[Dict[str, str]] = None, deployment_id: str = "temp"):
        # Build user code remotely on Vercel; never execute uploaded package scripts on the API host.
        return True, "Source validated. Vercel will install dependencies and build this project remotely.", source_path

    async def deploy(self, artifact_path: str, site_id: str, version: str = "v1.0", build_command: Optional[str] = None, output_dir: Optional[str] = None, env_vars: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        root = Path(artifact_path).resolve()
        if not root.is_dir():
            return False, "Build artifact directory is missing."
        output_dir = output_dir or "dist"
        output_path = PurePosixPath(output_dir)
        if output_path.is_absolute() or PureWindowsPath(output_dir).is_absolute() or ".." in output_path.parts or ".." in PureWindowsPath(output_dir).parts:
            return False, "Output directory must be a safe relative path inside the project."

        files = []
        total_bytes = 0
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            if any(part in {".git", "node_modules", ".venv", "venv", "__pycache__"} for part in path.relative_to(root).parts):
                continue
            if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example") or path.name == ".npmrc":
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith("../"):
                return False, "Build artifact contains a path outside its output directory."
            content = await asyncio.to_thread(path.read_bytes)
            total_bytes += len(content)
            if len(files) >= self.max_files or total_bytes > self.max_total_bytes:
                return False, "Static build exceeds Vercel upload limits for this service (5,000 files / 100 MB)."
            digest = hashlib.sha1(content).hexdigest()
            files.append((relative, content, digest))

        if not files or not any(name.lower() == "index.html" for name, _, _ in files):
            return False, "Build output must include an index.html file."

        headers = self._auth_headers()
        params = self._params()
        timeout = httpx.Timeout(30.0, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for name, content, digest in files:
                    response = await client.post(
                        f"{self.api_base}/v2/files",
                        params=params,
                        headers={**headers, "Content-Type": "application/octet-stream", "Content-Length": str(len(content)), "x-vercel-digest": digest},
                        content=content,
                    )
                    if response.is_error:
                        return False, f"Vercel file upload failed ({response.status_code}): {response.text[:1000]}"

                project_name = re.sub(r"[^a-z0-9-]+", "-", site_id.lower()).strip("-")[:52] or "site"
                has_package_json = (root / "package.json").is_file()
                payload = {
                    "name": project_name,
                    "target": "production",
                    "files": [{"file": name, "sha": digest, "size": len(content)} for name, content, digest in files],
                    "projectSettings": {
                        "framework": None,
                        "buildCommand": (build_command or "npm run build") if has_package_json else None,
                        "devCommand": None,
                        "installCommand": "npm install" if has_package_json else None,
                        "outputDirectory": (output_dir or "dist") if has_package_json else ".",
                    },
                }
                response = await client.post(
                    f"{self.api_base}/v13/deployments",
                    params={**params, "skipAutoDetectionConfirmation": "1"},
                    headers={**headers, "Content-Type": "application/json"},
                    json=payload,
                )
                if response.is_error:
                    return False, f"Vercel rejected deployment ({response.status_code}): {response.text[:1500]}"
                deployment = response.json()
                deployment_id = deployment.get("id")
                deployment_url = deployment.get("url")
                if not deployment_id or not deployment_url:
                    return False, "Vercel returned an incomplete deployment response."

                deadline = asyncio.get_running_loop().time() + 300
                while asyncio.get_running_loop().time() < deadline:
                    state = deployment.get("readyState")
                    if state == "READY":
                        return True, f"https://{deployment_url}"
                    if state in {"ERROR", "CANCELED"}:
                        return False, f"Vercel deployment {state.lower()}: {deployment.get('errorMessage') or deployment.get('errorCode') or 'build failed'}"
                    await asyncio.sleep(3)
                    status_response = await client.get(
                        f"{self.api_base}/v13/deployments/{deployment_id}",
                        params=params,
                        headers=headers,
                    )
                    if status_response.is_error:
                        return False, f"Could not read Vercel deployment status ({status_response.status_code}): {status_response.text[:1000]}"
                    deployment = status_response.json()
                return False, "Vercel deployment timed out before reaching READY. Check the deployment in your Vercel dashboard."
        except httpx.HTTPError as exc:
            logger.warning("Vercel API request failed: %s", exc)
            return False, f"Could not reach Vercel API: {type(exc).__name__}"
        except Exception as exc:
            logger.exception("Vercel deployment failed")
            return False, f"Vercel deployment failed: {exc}"

    async def health_check(self, live_url: str, site_id: Optional[str] = None):
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(live_url)
            return response.status_code == 200, response.status_code, f"Vercel deployment returned HTTP {response.status_code}."
        except httpx.HTTPError as exc:
            return False, 0, f"Could not verify Vercel deployment: {type(exc).__name__}"

    async def rollback(self, site_id: str, target_version: str):
        return False, "Vercel rollback requires selecting a Vercel deployment in the provider dashboard."

    async def stop(self, site_id: str) -> bool:
        return False

    async def remove(self, site_id: str) -> bool:
        return False

    async def remove_by_url(self, deployment_url: str) -> bool:
        if not deployment_url:
            return False
        identifier = deployment_url.removeprefix("https://").removeprefix("http://").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.delete(
                    f"{self.api_base}/v13/deployments/{identifier}",
                    params=self._params(),
                    headers=self._auth_headers(),
                )
            return response.is_success or response.status_code == 404
        except httpx.HTTPError:
            logger.exception("Failed to remove Vercel deployment")
            return False


vercel_deployment_provider = VercelDeploymentProvider()
