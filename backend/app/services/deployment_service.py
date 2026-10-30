"""
Multi-Tenant Deployment Orchestration Service.
Coordinates asynchronous build jobs, secret-masked logs, tenant authorization,
multi-version management, automated health checking, and zero-downtime rollbacks.
"""

import os
import re
import uuid
import io
import zipfile
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.storage import storage
from app.models.deployment import Deployment, DeploymentVersion, Domain, DeploymentLog
from app.models.template import Template
from app.models.user import User
from app.services.deployment_providers import get_deployment_provider, local_deployment_provider

logger = logging.getLogger(__name__)

# List of patterns to mask in deployment logs to prevent any secret leakages
SECRET_MASK_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9_-]{20,})"),
    re.compile(r"(AIzaSy[a-zA-Z0-9_-]{33})"),
    re.compile(r"(postgresql\+asyncpg://[^@]+@)"),
    re.compile(r"(password=[\'\"][^\'\"]+[\'\"])", re.IGNORECASE),
    re.compile(r"(secret=[\'\"][^\'\"]+[\'\"])", re.IGNORECASE),
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{25,})", re.IGNORECASE),
]


def mask_sensitive_logs(text: str) -> str:
    """Masks API keys, JWT tokens, and DB connection credentials from logs."""
    if not text:
        return ""
    masked = text
    for pattern in SECRET_MASK_PATTERNS:
        masked = pattern.sub("[REDACTED_SECRET]", masked)
    return masked


class DeploymentService:
    """Core business logic service for multi-tenant website deployments."""

    def __init__(self, db: AsyncSession, provider_type: str = "local"):
        self.db = db
        self.provider = get_deployment_provider(provider_type)

    async def log_event(self, deployment_id: uuid.UUID, level: str, message: str):
        """Appends a structured log event with automated secret masking."""
        safe_msg = mask_sensitive_logs(message)
        log_entry = DeploymentLog(
            deployment_id=deployment_id,
            level=level.upper(),
            message=safe_msg,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(log_entry)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()

    async def create_deployment(
        self,
        user: User,
        project_name: str,
        template_id: Optional[uuid.UUID] = None,
        provider_type: str = "local",
        build_command: str = "npm run build",
        output_dir: str = "dist",
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Deployment:
        """
        Creates a new tenant deployment record in `QUEUED` state.
        Generates unique stable `site_id` (e.g. `SITE-A8F2E`).
        """
        provider_type = (provider_type or "local").strip().lower()
        self.provider = get_deployment_provider(provider_type)
        local_deployments_enabled = settings.LOCAL_DEPLOYMENT_ENABLED or settings.ENVIRONMENT in {"development", "local", "test"}
        if provider_type == "local" and not local_deployments_enabled:
            raise ValueError("Local server deployments are disabled. Configure Vercel or explicitly enable trusted local builds.")
        if provider_type == "vercel" and not settings.VERCEL_TOKEN:
            raise ValueError("Vercel deployment is unavailable until VERCEL_TOKEN is configured on the backend.")
        clean_name = "".join(c for c in project_name.lower() if c.isalnum() or c in (" ", "-", "_")).strip()
        subdomain_slug = clean_name.replace(" ", "-")
        rand_suffix = uuid.uuid4().hex[:4].lower()
        subdomain = f"{subdomain_slug}-{rand_suffix}.aisitestudio.com"
        site_id = f"SITE-{uuid.uuid4().hex[:6].upper()}"

        deployment = Deployment(
            user_id=user.id,
            template_id=template_id,
            site_id=site_id,
            project_name=project_name,
            provider=provider_type,
            status="queued",
            current_version="v1.0",
            deployment_type="static",
            health_status="healthy",
            subdomain=subdomain,
            branch="main",
            commit_message="Initial deployment",
            build_command=build_command,
            output_dir=output_dir,
            env_vars=env_vars or {},
            logs=f"[{datetime.now().strftime('%H:%M:%S')}] [QUEUED] Deployment initialized in queue for {project_name} ({site_id}). Preparing sandbox...\n",
        )

        self.db.add(deployment)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(deployment)

        # Record initial domain mapping
        try:
            domain_record = Domain(
                deployment_id=deployment.id,
                user_id=user.id,
                domain=subdomain,
                domain_type="subdomain",
                verification_status="pending_verification",
                ssl_status="pending",
            )
            self.db.add(domain_record)
            await self.db.commit()
        except Exception:
            await self.db.rollback()

        # Add initial log event
        await self.log_event(deployment.id, "INFO", f"Deployment {deployment.site_id} created and queued.")

        return deployment

    @staticmethod
    async def run_deployment_pipeline(deployment_id: uuid.UUID, version_str: str = "v1.0"):
        """
        Background worker pipeline that executes compilation, testing, health checking,
        and atomic deployment for an isolated tenant workload.
        """
        async with AsyncSessionLocal() as db:
            service = DeploymentService(db)
            res = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
            deployment = res.scalar_one_or_none()
            if not deployment:
                return
            service = DeploymentService(db, deployment.provider)

            site_id = deployment.site_id or f"SITE-{deployment.id.hex[:6].upper()}"
            deployment.status = "building"

            # 1. Prepare isolated workspace directory
            temp_dir = Path(tempfile.gettempdir()) / "ai_site_studio" / "tenant_builds" / deployment.id.hex
            temp_dir.mkdir(parents=True, exist_ok=True)
            source_dir = temp_dir / "source"
            source_dir.mkdir(exist_ok=True)

            t_now = datetime.now().strftime('%H:%M:%S')
            deployment.logs = (deployment.logs or "") + f"[{t_now}] [INFO] Starting build pipeline for version {version_str}...\n"
            deployment.logs += f"[{t_now}] [INFO] Initializing sandboxed workspace environment ({temp_dir.name})...\n"
            await db.commit()
            await service.log_event(deployment.id, "INFO", f"Build started for version {version_str}.")

            try:
                # 2. Extract template source code from database StoredFile or local static template directories
                template_title = deployment.project_name
                template_desc = f"Welcome to {deployment.project_name}. Powered by AI Site Studio."
                if deployment.template_id:
                    t_res = await db.execute(select(Template).where(Template.id == deployment.template_id))
                    template = t_res.scalar_one_or_none()
                    if template:
                        if template.title:
                            template_title = template.title
                        if template.short_description or template.description:
                            template_desc = template.short_description or template.description[:180]
                        
                        # Helper to extract UUID from string or URL
                        def _extract_uuid(val: Any) -> Optional[uuid.UUID]:
                            if not val:
                                return None
                            match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(val))
                            if match:
                                try:
                                    return uuid.UUID(match.group(1))
                                except ValueError:
                                    return None
                            return None

                        # 2a. Check database StoredFile zip blob if linked
                        source_file_uuid = _extract_uuid(getattr(template, "source_file_id", None))
                        if not source_file_uuid and isinstance(getattr(template, "download_assets", None), dict):
                            d_assets = template.download_assets
                            source_file_uuid = _extract_uuid(d_assets.get("source_file_id")) or _extract_uuid(d_assets.get("zip")) or _extract_uuid(d_assets.get("html"))

                        if source_file_uuid:
                            try:
                                stored_file = await storage.get_file(db, source_file_uuid)
                                if stored_file:
                                    file_bytes = stored_file[0]
                                    from app.services.security_scanner import security_scanner
                                    security_scanner.sanitize_extract_zip(file_bytes, source_dir)
                                    logger.info(f"Successfully extracted template source zip ({len(file_bytes)} bytes) for {template.title}")
                                else:
                                    logger.warning("Template source archive is missing from configured storage")
                            except Exception as zip_err:
                                logger.warning(f"Failed to extract stored template file: {zip_err}")

                        # 2b. Check generated_projects for customized code
                        from app.core.local_project_manager import local_project_manager
                        candidate_idents = [str(template.id), template.slug or "", deployment.project_name]
                        for c_id in candidate_idents:
                            if not c_id:
                                continue
                            p_dir = local_project_manager._resolve_project_dir(c_id)
                            if p_dir.exists() and (p_dir / "latest").exists():
                                latest_files = list((p_dir / "latest").iterdir())
                                if latest_files:
                                    shutil.copytree(p_dir / "latest", source_dir, dirs_exist_ok=True)
                                    logger.info(f"Loaded customized project code from generated_projects/{p_dir.name}/latest")
                                    break

                        # 2c. Check local static template directory on disk
                        if not os.listdir(source_dir):
                            base_dir = Path(__file__).resolve().parents[2]
                            possible_paths = [
                                base_dir / "static" / "templates" / str(template.id),
                                base_dir / "static" / "templates" / (template.slug or ""),
                                base_dir / "static" / "previews" / str(template.id),
                            ]
                            for p in possible_paths:
                                if p.exists() and p.is_dir() and any(p.iterdir()):
                                    shutil.copytree(p, source_dir, dirs_exist_ok=True)
                                    break

                        # 2c. Flatten single subfolder if ZIP extracted into a root subfolder (e.g., GrowMark/index.html)
                        if os.listdir(source_dir):
                            subitems = [item for item in source_dir.iterdir() if not item.name.startswith(".")]
                            if len(subitems) == 1 and subitems[0].is_dir():
                                inner_dir = subitems[0]
                                for sub_file in inner_dir.iterdir():
                                    shutil.move(str(sub_file), str(source_dir / sub_file.name))
                                try:
                                    inner_dir.rmdir()
                                except Exception:
                                    pass

                # A deployment must contain the user's actual source. Never report a generated placeholder as their live site.
                if not os.listdir(source_dir):
                    raise RuntimeError("No deployable source files were found. Re-upload the template archive or select a project with source files.")

                mounted_count = len(list(source_dir.iterdir()))
                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Mounted project codebase ({mounted_count} items ready in sandbox).\n"
                await db.commit()

                # -------------------------------------------------------------
                # 3. Pre-Flight Production Readiness Audit & Permanent Auto-Healing
                # -------------------------------------------------------------
                from app.services.deployment_readiness_auditor import deployment_readiness_auditor

                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [AUDIT] 🔍 Commencing pre-flight Production Readiness Audit...\n"
                await db.commit()
                await service.log_event(deployment.id, "AUDIT", "Pre-flight Production Readiness Audit started.")

                target_identifier = (template.slug if (template and template.slug) else None) or deployment.project_name
                audit_res = deployment_readiness_auditor.audit_and_heal_source(
                    source_path=source_dir,
                    template_identifier=target_identifier,
                )

                for finding in audit_res.get("findings", []):
                    lvl = "HEAL" if any(w in finding.lower() for w in ("heal", "added", "fixed", "injected", "configured", "persisted")) else "AUDIT"
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [{lvl}] {finding}\n"
                    await service.log_event(deployment.id, lvl, finding)

                for warning in audit_res.get("warnings", []):
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] {warning}\n"
                    await service.log_event(deployment.id, "WARN", warning)

                if audit_res.get("healed_files"):
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [HEAL] ✨ Permanently persisted {len(audit_res['healed_files'])} auto-healed files into project codebase.\n"
                    await service.log_event(deployment.id, "HEAL", f"Permanently persisted {len(audit_res['healed_files'])} healed files.")
                await db.commit()

                # Validate source structure
                is_valid, val_err = await service.provider.validate(str(source_dir))
                if not is_valid:
                    raise Exception(val_err or "Project source validation failed.")

                # -------------------------------------------------------------
                # 4. Execute Sandboxed Build with Autonomous Build Self-Healing
                # -------------------------------------------------------------
                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Executing sandboxed build ({deployment.build_command})...\n"
                await db.commit()

                build_success, build_logs, artifact_path = await service.provider.build(
                    source_path=str(source_dir),
                    build_command=deployment.build_command,
                    output_dir=deployment.output_dir,
                    env_vars=deployment.env_vars,
                    deployment_id=str(deployment.id),
                )
                deployment.logs += mask_sensitive_logs(build_logs) + "\n"
                await db.commit()

                # Autonomous Self-Healing on Build Failure
                if not build_success or not artifact_path:
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] Initial build failed. Activating Autonomous Build Self-Healing Engine...\n"
                    await db.commit()
                    await service.log_event(deployment.id, "WARN", "Initial build failed. Activating Autonomous Build Self-Healing Engine.")

                    heal_diagnostics = deployment_readiness_auditor.diagnose_and_heal_build_failure(
                        source_path=source_dir,
                        build_logs=build_logs,
                        template_identifier=target_identifier,
                    )

                    if heal_diagnostics.get("healed"):
                        for fix_msg in heal_diagnostics.get("fixes_applied", []):
                            deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [SELF-HEAL] 🩺 {fix_msg}\n"
                            await service.log_event(deployment.id, "SELF-HEAL", fix_msg)
                        await db.commit()

                        # Re-run build with healed files (Pass 2)
                        deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Re-running build pipeline with healed code (Pass 2)...\n"
                        await db.commit()

                        build_success, build_logs_p2, artifact_path = await service.provider.build(
                            source_path=str(source_dir),
                            build_command=deployment.build_command,
                            output_dir=deployment.output_dir,
                            env_vars=deployment.env_vars,
                            deployment_id=str(deployment.id),
                        )
                        deployment.logs += mask_sensitive_logs(build_logs_p2) + "\n"
                        await db.commit()

                        if build_success and artifact_path:
                            deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [SELF-HEAL] ✅ Build successfully self-healed on Pass 2! Continuing to deployment.\n"
                            await service.log_event(deployment.id, "SELF-HEAL", "Build successfully self-healed on Pass 2.")
                        else:
                            raise Exception("Compilation failed even after self-healing pass.")
                    else:
                        raise Exception("Compilation failed during build step.")

                # -------------------------------------------------------------
                # 5. Deploy Artifact to Production Tenant Storage
                # -------------------------------------------------------------
                deployment.status = "deploying"
                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Registering versioned artifact in tenant storage...\n"
                await db.commit()

                deploy_success, live_url = await service.provider.deploy(
                    artifact_path=artifact_path,
                    site_id=site_id,
                    version=version_str,
                    build_command=deployment.build_command,
                    output_dir=deployment.output_dir,
                    env_vars=deployment.env_vars,
                )
                if not deploy_success:
                    raise Exception(f"Failed to register artifact: {live_url}")

                # -------------------------------------------------------------
                # 6. Execute Automated Health Check & Runtime Self-Healing
                # -------------------------------------------------------------
                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Performing automated health check on {live_url}...\n"
                await db.commit()

                is_healthy, h_status, h_msg = await service.provider.health_check(live_url, site_id=site_id)
                if not is_healthy:
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] Health check warning: {h_msg}. Attempting runtime entrypoint repair...\n"
                    await db.commit()
                    # Check if artifact has a nested single subfolder
                    art_dir = Path(artifact_path)
                    sub_dirs = [d for d in art_dir.iterdir() if d.is_dir()]
                    if len(sub_dirs) == 1 and (sub_dirs[0] / "index.html").exists():
                        for item in sub_dirs[0].iterdir():
                            shutil.move(str(item), str(art_dir / item.name))
                        try:
                            sub_dirs[0].rmdir()
                        except Exception:
                            pass
                        # Re-deploy flattened
                        await service.provider.deploy(
                            artifact_path=artifact_path,
                            site_id=site_id,
                            version=version_str,
                        )
                        is_healthy, h_status, h_msg = await service.provider.health_check(live_url, site_id=site_id)

                if is_healthy:
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Health check passed 100% OK.\n"
                else:
                    deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [WARN] Site deployed with degraded health: {h_msg}\n"
                await db.commit()

                # 7. Record Version & Transition to LIVE
                deployment.status = "live"
                deployment.current_version = version_str
                deployment.health_status = "healthy"
                deployment.live_url = live_url
                deployment.deployment_path = artifact_path
                deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Deployment is LIVE: {live_url}\n"
                await db.commit()

                # Record DeploymentVersion entry
                dep_version = DeploymentVersion(
                    deployment_id=deployment.id,
                    version=version_str,
                    build_reference=artifact_path,
                    status="live",
                    commit_message=deployment.commit_message or "Production deploy",
                    build_logs=deployment.logs,
                )
                db.add(dep_version)
                await db.commit()

                await service.log_event(deployment.id, "SUCCESS", f"Deployment version {version_str} is LIVE at {live_url}")

            except Exception as e:
                logger.error(f"Deployment {deployment_id} failed: {e}")
                deployment.status = "failed"
                deployment.health_status = "down"
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Deployment failed: {str(e)}\n"
                deployment.logs = (deployment.logs or "") + error_msg
                await db.commit()
                await service.log_event(deployment.id, "ERROR", f"Deployment failed: {str(e)}")

            finally:
                # Clean up temporary build files
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def redeploy(self, user: User, deployment_id: uuid.UUID) -> Deployment:
        """Triggers a fresh deployment pipeline, incrementing the version."""
        stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == user.id)
        res = await self.db.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            raise Exception("Deployment not found or access denied.")
        self.provider = get_deployment_provider(deployment.provider)

        # Calculate next version (e.g. v1.0 -> v1.1)
        curr_ver = deployment.current_version or "v1.0"
        match = re.search(r"v?(\d+)\.(\d+)", curr_ver)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            next_ver = f"v{major}.{minor + 1}"
        else:
            next_ver = "v1.1"

        deployment.status = "queued"
        deployment.logs = f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] Redeployment queued for {next_ver}...\n"
        await self.db.commit()
        await self.db.refresh(deployment)

        await self.log_event(deployment.id, "INFO", f"Redeployment queued for version {next_ver}.")
        return deployment

    async def rollback_to_version(self, user: User, deployment_id: uuid.UUID, target_version: str) -> Tuple[bool, str]:
        """Performs atomic zero-downtime rollback to a previous version."""
        stmt = select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == user.id)
        res = await self.db.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            return False, "Deployment not found or access denied."

        self.provider = get_deployment_provider(deployment.provider)

        site_id = deployment.site_id
        success, live_url = await self.provider.rollback(site_id, target_version)
        if not success:
            return False, live_url

        deployment.current_version = target_version
        deployment.status = "live"
        deployment.health_status = "healthy"
        deployment.logs += f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] Atomic rollback to {target_version} completed.\n"
        await self.db.commit()

        await self.log_event(deployment.id, "SUCCESS", f"Rolled back to version {target_version}.")
        return True, live_url
