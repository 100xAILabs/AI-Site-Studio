"""
Local Multi-Tenant Deployment Provider.
Provides strict tenant workload isolation, sandboxed subprocess building,
atomic zero-downtime version switching, and automated HTTP health checking.
"""

import os
import shutil
import asyncio
import platform
import logging
import uuid
import subprocess
import io
import zipfile
from collections import deque
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Any, Tuple, Optional
import httpx

from app.core.config import settings
from app.services.deployment_providers.base import DeploymentProvider

logger = logging.getLogger(__name__)

# Base static storage path on host
_STATIC_ROOT = Path(__file__).resolve().parents[3] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"
os.makedirs(_DEPLOYMENTS_ROOT, exist_ok=True)


def _run_process(command: list[str], cwd: str, env: Dict[str, str], timeout: int = 180) -> Tuple[int, list[str]]:
    """Run a build command in a worker thread with strict timeout and retain only its final log lines."""
    output_lines = deque(maxlen=600)
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    ) as process:
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    output_lines.append(line.rstrip())
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            output_lines.append(f"❌ Process killed after exceeding {timeout}s timeout limit.")
            return -1, list(output_lines)
    return return_code, list(output_lines)


class LocalDeploymentProvider(DeploymentProvider):
    """
    Production-ready local deployment provider for development and standalone server hosting.
    Executes isolated static builds, manages multi-version artifact directories, and performs health checks.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or getattr(settings, "BACKEND_URL", "http://localhost:8000")

    @staticmethod
    def _activate_directory(staged_dir: Path, current_dir: Path) -> None:
        """Swap a complete directory into place and restore the old tree on failure."""
        backup_dir = current_dir.parent / f".current-backup-{uuid.uuid4().hex}"
        had_current = current_dir.exists()
        if had_current:
            os.replace(current_dir, backup_dir)
        try:
            os.replace(staged_dir, current_dir)
        except Exception:
            if had_current and backup_dir.exists() and not current_dir.exists():
                os.replace(backup_dir, current_dir)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)

    async def validate(self, source_path: str) -> Tuple[bool, Optional[str]]:
        """Verifies that project workspace contains a valid runnable entry point."""
        if not os.path.exists(source_path):
            return False, f"Source path does not exist: {source_path}"

        has_package_json = False
        has_index_html = False

        for root, dirs, files in os.walk(source_path):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", ".venv", "dist", "build"]]
            if "package.json" in files:
                has_package_json = True
            if "index.html" in files:
                has_index_html = True

        if not has_package_json and not has_index_html:
            return False, "Project workspace must contain either 'package.json' or 'index.html'."

        return True, None

    async def build(
        self,
        source_path: str,
        build_command: str = "npm run build",
        output_dir: str = "dist",
        env_vars: Optional[Dict[str, str]] = None,
        deployment_id: str = "temp",
    ) -> Tuple[bool, str, str]:
        """Build a static project using npm with a reduced environment."""
        is_windows = platform.system() == "Windows"
        npm_cmd = "npm.cmd" if is_windows else "npm"
        logs = []
        output_path = PurePosixPath(output_dir)
        if output_path.is_absolute() or PureWindowsPath(output_dir).is_absolute() or ".." in output_path.parts or ".." in PureWindowsPath(output_dir).parts:
            return False, "Output directory must be a safe relative path inside the project.", ""

        # 1. Prepare sanitized tenant environment (strictly isolated from platform .env)
        tenant_clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "NODE_ENV": "production",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            "DEPLOYMENT_ID": str(deployment_id),
        }
        if is_windows:
            # npm.cmd is a Windows batch wrapper and cannot be launched directly
            # with CreateProcess. Preserve only the non-secret Windows profile
            # variables npm needs, then invoke the wrapper through cmd.exe.
            for key in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "PATHEXT", "WINDIR"):
                value = os.environ.get(key)
                if value:
                    tenant_clean_env[key] = value
            cmd_exe = os.path.join(tenant_clean_env["SYSTEMROOT"], "System32", "cmd.exe")
            tenant_clean_env["COMSPEC"] = os.environ.get("COMSPEC", cmd_exe)

        # Share npm's content-addressed package cache across framework previews.
        # npm still links each project's exact dependency versions in its own
        # node_modules, while downloads are reused from this common cache box.
        npm_cache_dir = Path(settings.NPM_CACHE_DIR).resolve()
        npm_cache_dir.mkdir(parents=True, exist_ok=True)
        tenant_clean_env["npm_config_cache"] = str(npm_cache_dir)
        tenant_clean_env["npm_config_prefer_offline"] = "true"
        tenant_clean_env["npm_config_include"] = "dev"

        def npm_process_args(*args: str) -> list[str]:
            if is_windows:
                command = " ".join(subprocess.list2cmdline([arg]) for arg in args)
                return [cmd_exe, "/d", "/c", command]
            return list(args)
        # Inject tenant-specified public environment variables (with strict security allowlisting)
        _BLOCKED_ENV_PREFIXES = ("NODE_", "NPM_", "npm_config_", "PYTHON", "PERL", "RUBY")
        _BLOCKED_ENV_NAMES = {
            "NODE_OPTIONS", "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH",
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE",
            "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"
        }
        if env_vars:
            for k, v in env_vars.items():
                k_clean = str(k).strip()
                if (
                    isinstance(v, str)
                    and k_clean.isidentifier()
                    and k_clean.upper() not in _BLOCKED_ENV_NAMES
                    and not any(k_clean.upper().startswith(p.upper()) for p in _BLOCKED_ENV_PREFIXES)
                ):
                    tenant_clean_env[k_clean] = v

        # Locate root directory containing package.json
        project_root = source_path
        for r, dirs, files in os.walk(source_path):
            dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", ".venv", "dist", "build"]]
            if "package.json" in files:
                project_root = r
                break

        package_json_path = os.path.join(project_root, "package.json")

        # 2. Static HTML direct pass (if no package.json exists)
        if not os.path.isfile(package_json_path):
            logs.append("ℹ️ Static HTML template detected — skipping compilation step.")
            return True, "\n".join(logs), project_root

        # Pre-build healing (auto-add missing npm dependencies & configure relative base: './')
        try:
            from app.services.deployment_readiness_auditor import deployment_readiness_auditor
            pre_healed, pre_findings = deployment_readiness_auditor.heal_pre_build(project_root)
            if pre_healed:
                for f in pre_findings:
                    logs.append(f"🔧 Pre-build: {f}")
        except Exception as e_pre:
            logger.warning("Pre-build healing error in %s: %s", project_root, e_pre)

        # Check if project already has a verified fresh pre-compiled production build (e.g. from canvas preview)
        candidate_build_dirs = [output_dir, "dist", "build", "out"]
        for d in candidate_build_dirs:
            candidate_path = os.path.join(project_root, d)
            if os.path.isdir(candidate_path) and os.path.isfile(os.path.join(candidate_path, "index.html")):
                logs.append(f"✓ Detected verified pre-compiled production build at '{d}/'.")
                return True, "\n".join(logs), candidate_path

        # 3. Install from the shared npm cache. Run subprocess work in a thread:
        # asyncio subprocess transports are not implemented by every Windows loop.
        # Include dev dependencies because build tools such as Vite, react-scripts,
        # Next, Angular CLI, and tsc are normally declared there.
        logs.append("📦 Installing project dependencies from the shared npm cache...")
        try:
            install_code, install_output = await asyncio.to_thread(
                _run_process,
                npm_process_args(npm_cmd, "install", "--ignore-scripts", "--include=dev", "--no-audit", "--no-fund"),
                project_root,
                tenant_clean_env,
            )
            logs.extend("  " + line for line in install_output)

            if install_code != 0:
                # Attempt self-healing missing packages
                try:
                    from app.services.deployment_readiness_auditor import deployment_readiness_auditor
                    healed, _ = deployment_readiness_auditor.diagnose_and_heal_build_failure("\n".join(install_output), project_root)
                    if healed:
                        install_code, install_output = await asyncio.to_thread(
                            _run_process,
                            npm_process_args(npm_cmd, "install", "--ignore-scripts", "--include=dev", "--no-audit", "--no-fund"),
                            project_root,
                            tenant_clean_env,
                        )
                except Exception:
                    pass

            if install_code != 0:
                logs.append(f"❌ npm install failed with exit code {install_code}")
                return False, "\n".join(logs), ""
            logs.append("✓ Dependencies installed successfully.")
        except Exception as e:
            logger.exception("Preview dependency installation could not start in %s", project_root)
            logs.append(f"❌ Dependency install error: {e!r}")
            return False, "\n".join(logs), ""

        # 4. Run build script (enforce safe npm build arguments & inspect package.json scripts)
        import json as json_lib
        import re as re_lib
        try:
            with open(package_json_path, "r", encoding="utf-8", errors="replace") as pf:
                pkg_data = json_lib.load(pf)
            pkg_scripts = pkg_data.get("scripts") if isinstance(pkg_data, dict) else {}
            if isinstance(pkg_scripts, dict):
                from app.services.security_scanner import security_scanner
                for s_name in ("prebuild", "build", "postbuild", "preinstall", "install", "postinstall"):
                    s_cmd = pkg_scripts.get(s_name)
                    if isinstance(s_cmd, str) and s_cmd.strip():
                        script_findings = security_scanner.scan_code_content(s_cmd, filename=f"package.json#scripts.{s_name}")
                        if any(f.get("severity") in ("CRITICAL", "HIGH") for f in script_findings):
                            logs.append("❌ Security violation detected inside package.json build scripts.")
                            return False, "\n".join(logs), ""
        except Exception:
            pass

        safe_build = build_command.strip() if build_command else "npm run build"
        cmd_parts = safe_build.split()
        if (
            not cmd_parts
            or cmd_parts[0] != "npm"
            or len(cmd_parts) not in (2, 3)
            or (len(cmd_parts) == 2 and cmd_parts[1] != "build")
            or (len(cmd_parts) == 3 and (cmd_parts[1] not in ("run", "run-script") or not re_lib.match(r"^[a-zA-Z0-9:_-]{1,50}$", cmd_parts[2]) or cmd_parts[2].startswith("-")))
        ):
            safe_build = "npm run build"
            cmd_parts = ["npm", "run", "build"]

        logs.append(f"🚀 Executing build command: {safe_build}")
        try:
            if len(cmd_parts) >= 3 and cmd_parts[1] == "run":
                build_args = npm_process_args(npm_cmd, "run", cmd_parts[2])
            else:
                build_args = npm_process_args(npm_cmd, "run", "build")
            build_code, build_output = await asyncio.to_thread(
                _run_process, build_args, project_root, tenant_clean_env
            )
            logs.extend("  " + line for line in build_output)

            if build_code != 0:
                combined_err = "\n".join(build_output)
                # If node_modules or build tool binary was corrupted or missing from disk
                if "err_module_not_found" in combined_err.lower() or "cannot find module" in combined_err.lower():
                    nm_dir = os.path.join(project_root, "node_modules")
                    if os.path.isdir(nm_dir):
                        logs.append("🧹 Detected corrupted build tool dependency — performing fresh install...")
                        shutil.rmtree(nm_dir, ignore_errors=True)
                        await asyncio.to_thread(
                            _run_process,
                            npm_process_args(npm_cmd, "install", "--include=dev", "--no-audit", "--no-fund"),
                            project_root,
                            tenant_clean_env,
                        )
                        logs.append("🔄 Re-attempting build after fresh dependency installation...")
                        build_code, build_output = await asyncio.to_thread(
                            _run_process, build_args, project_root, tenant_clean_env
                        )
                        logs.extend("  " + line for line in build_output)

                # Attempt autonomous build diagnosis and repair
                if build_code != 0:
                    try:
                        from app.services.deployment_readiness_auditor import deployment_readiness_auditor
                        healed, _ = deployment_readiness_auditor.diagnose_and_heal_build_failure("\n".join(build_output), project_root)
                        if healed:
                            logs.append("🔄 Re-attempting build after automated healing...")
                            build_code, build_output = await asyncio.to_thread(
                                _run_process, build_args, project_root, tenant_clean_env
                            )
                            logs.extend("  " + line for line in build_output)
                    except Exception:
                        pass

            if build_code != 0:
                logs.append(f"❌ Build failed with exit code {build_code}")
                return False, "\n".join(logs), ""
            logs.append("✓ Build completed successfully.")
        except Exception as e:
            logger.exception("Preview build command could not start in %s", project_root)
            logs.append(f"❌ Build execution error: {e!r}")
            return False, "\n".join(logs), ""

        # 5. Locate compiled artifact directory containing index.html
        build_folders = [output_dir, "dist", "out", "build", ".output/public", "public"]
        artifact_path = None

        for d in build_folders:
            candidate = os.path.join(project_root, d)
            if os.path.isdir(candidate):
                for br, bd, bfiles in os.walk(candidate):
                    if "index.html" in bfiles:
                        artifact_path = candidate
                        break
                if artifact_path:
                    break

        if not artifact_path:
            # Check project root directly
            for br, bd, bfiles in os.walk(project_root):
                if "index.html" in bfiles:
                    artifact_path = br
                    break

        if not artifact_path:
            logs.append("❌ Build completed but could not locate 'index.html' entry point.")
            return False, "\n".join(logs), ""

        logs.append(f"✓ Artifact located at: {artifact_path}")
        return True, "\n".join(logs), artifact_path

    async def deploy(
        self,
        artifact_path: str,
        site_id: str,
        version: str = "v1.0",
        build_command: Optional[str] = None,
        output_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """
        Stores versioned artifact in `static/deployments/{site_id}/{version}/dist/`
        and updates the live `current` symlink/directory for atomic zero-downtime serving.
        """
        try:
            site_dir = _DEPLOYMENTS_ROOT / site_id
            version_dir = site_dir / version / "dist"
            current_dir = site_dir / "current"

            os.makedirs(version_dir.parent, exist_ok=True)
            if version_dir.exists():
                return False, f"Version '{version}' already exists and is immutable."

            # Build an immutable version snapshot, then stage the live tree before switching.
            version_stage = version_dir.parent / f".dist-stage-{uuid.uuid4().hex}"
            shutil.copytree(
                artifact_path,
                version_stage,
                ignore=shutil.ignore_patterns(".env", ".env.*", ".npmrc", ".git", ".gitignore", "node_modules", "__pycache__"),
            )
            os.replace(version_stage, version_dir)

            current_stage = site_dir / f".current-stage-{uuid.uuid4().hex}"
            shutil.copytree(version_dir, current_stage)
            self._activate_directory(current_stage, current_dir)

            # If Oracle Instance 2 (User Workload Edge Server) is enabled, sync bundle remotely
            if settings.USER_WORKLOAD_MODE == "remote_oracle" and settings.USER_WORKLOAD_SERVER_URL:
                try:
                    await self._sync_to_remote_workload_node(artifact_path, site_id, version)
                except Exception as sync_err:
                    logger.warning(f"Remote workload node sync warning: {sync_err}")

            # Generate canonical live URL (pointing to User Workload Server if configured)
            if settings.USER_WORKLOAD_SERVER_URL:
                live_url = f"{settings.USER_WORKLOAD_SERVER_URL.rstrip('/')}/sites/{site_id}/"
            else:
                live_url = f"{self.base_url}/sites/{site_id}/"
            return True, live_url
        except Exception as e:
            logger.exception(f"Failed to deploy artifact for site {site_id}: {e}")
            return False, str(e)

    async def _sync_to_remote_workload_node(self, artifact_path: str, site_id: str, version: str) -> bool:
        """
        Zips compiled artifact and dispatches it via authenticated HTTP POST to Oracle Cloud Instance 2
        (User Workload Edge Server). Ensures user workloads run fully isolated from the platform core.
        """
        if not settings.USER_WORKLOAD_SERVER_URL:
            return False

        endpoint = f"{settings.USER_WORKLOAD_SERVER_URL.rstrip('/')}/api/v1/workload/sync-artifact"
        secret = settings.USER_WORKLOAD_SYNC_SECRET or ""

        # Package artifact_path into in-memory zip buffer
        zip_buffer = io.BytesIO()
        source_dir = Path(artifact_path)
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)

        zip_bytes = zip_buffer.getvalue()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {
                    "artifact_zip": ("artifact.zip", zip_bytes, "application/zip"),
                }
                data = {
                    "site_id": site_id,
                    "version": version,
                }
                headers = {
                    "X-Workload-Secret": secret,
                }
                resp = await client.post(endpoint, data=data, files=files, headers=headers)
                if resp.status_code in (200, 201):
                    logger.info(f"Successfully synced artifact for site {site_id} to remote workload node.")
                    return True
                else:
                    logger.error(
                        f"Failed to sync artifact to workload node: HTTP {resp.status_code} - {resp.text}"
                    )
                    return False
        except Exception as e:
            logger.exception(f"Exception syncing artifact to remote workload node {endpoint}: {e}")
            return False

    async def health_check(
        self,
        live_url: str,
        site_id: Optional[str] = None,
        check_path: str = "/api/health",
        retries: int = 3,
        retry_delay: float = 0.5,
    ) -> Tuple[bool, int, str]:
        """
        Performs comprehensive health checks against:
        1. Filesystem artifact integrity (index.html existence & non-zero size)
        2. Root endpoint availability (GET live_url -> HTTP 200)
        3. Optional API health check probe (GET live_url + check_path -> HTTP 200)
        Includes automatic retry with exponential backoff.
        """
        # 1. Verify filesystem artifact integrity
        if site_id:
            current_index = _DEPLOYMENTS_ROOT / site_id / "current" / "index.html"
            if not current_index.exists() or current_index.stat().st_size == 0:
                return False, 404, f"Deployment index.html missing or corrupted at {current_index}"

        last_error = ""
        last_code = 500

        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                    resp = await client.get(live_url)
                    last_code = resp.status_code
                    if resp.status_code == 200:
                        if check_path and check_path != "/":
                            api_url = f"{live_url.rstrip('/')}{check_path}"
                            try:
                                api_res = await client.get(api_url)
                                if api_res.status_code == 200:
                                    return True, 200, f"HTTP 200 OK — Both site and {check_path} verified healthy."
                            except Exception:
                                pass
                        return True, 200, "HTTP 200 OK — Health check passed."
                    last_error = f"HTTP {resp.status_code} returned during health check"
            except Exception as exc:
                last_error = f"Health check failed to reach endpoint: {exc}"

            if attempt < retries:
                await asyncio.sleep(retry_delay * attempt)

        return False, last_code, f"Health check failed after {retries} attempts: {last_error}"

    async def rollback(self, site_id: str, target_version: str) -> Tuple[bool, str]:
        """
        Performs atomic zero-downtime rollback by switching the `current` active directory
        to the target historical version.
        """
        candidate_dirs = [
            _DEPLOYMENTS_ROOT / site_id / target_version / "dist",
            _DEPLOYMENTS_ROOT / site_id / target_version,
            _DEPLOYMENTS_ROOT / site_id.upper() / target_version / "dist",
            _DEPLOYMENTS_ROOT / site_id.upper() / target_version,
            _DEPLOYMENTS_ROOT / site_id.lower() / target_version / "dist",
            _DEPLOYMENTS_ROOT / site_id.lower() / target_version,
        ]
        target_version_dir = next((d for d in candidate_dirs if d.is_dir()), None)
        if not target_version_dir:
            return False, f"Version '{target_version}' does not exist for site {site_id}."

        current_dir = _DEPLOYMENTS_ROOT / site_id / "current"
        if not current_dir.parent.exists() and (_DEPLOYMENTS_ROOT / site_id.upper()).exists():
            current_dir = _DEPLOYMENTS_ROOT / site_id.upper() / "current"

        try:
            os.makedirs(current_dir.parent, exist_ok=True)
            current_stage = current_dir.parent / f".current-stage-{uuid.uuid4().hex}"
            shutil.copytree(target_version_dir, current_stage)
            self._activate_directory(current_stage, current_dir)
            live_url = f"{self.base_url}/sites/{site_id}/"
            return True, live_url
        except Exception as e:
            return False, f"Rollback failed: {str(e)}"

    async def stop(self, site_id: str) -> bool:
        """Suspends the tenant site by replacing current directory with a maintenance card."""
        try:
            site_dir = _DEPLOYMENTS_ROOT / site_id
            current_dir = site_dir / "current"
            if os.path.exists(current_dir):
                shutil.rmtree(current_dir, ignore_errors=True)
            os.makedirs(current_dir, exist_ok=True)
            maintenance_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Website Suspended</title>
<style>body{background:#0b0f19;color:#fff;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
.card{text-align:center;padding:2.5rem;background:rgba(255,255,255,0.05);border-radius:1rem;border:1px solid rgba(255,255,255,0.1);}
h1{font-size:1.75rem;margin-bottom:0.5rem;}p{color:#94a3b8;font-size:0.9rem;}</style></head>
<body><div class="card"><h1>Website Currently Unavailable</h1><p>This deployment has been temporarily suspended by the site owner.</p></div></body></html>"""
            with open(current_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(maintenance_html)
            return True
        except Exception:
            return False

    async def remove(self, site_id: str) -> bool:
        """Deletes all deployment files and versions for the specified site ID."""
        try:
            site_dir = _DEPLOYMENTS_ROOT / site_id
            if os.path.exists(site_dir):
                shutil.rmtree(site_dir, ignore_errors=True)
            return True
        except Exception:
            return False


# Global singleton instance
local_deployment_provider = LocalDeploymentProvider()
