"""
Routes for managing deployments.
"""

import uuid
import asyncio
import platform
import os
import shutil
import zipfile
import io
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Resolve static directory relative to this file (backend/app/api/v1/routes/ → backend/static/)
_STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
_DEPLOYMENTS_ROOT = _STATIC_ROOT / "deployments"

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.deployment import Deployment
from app.schemas.deployment import DeploymentCreate, DeploymentResponse


router = APIRouter()


async def real_deploy_task(deployment_id: uuid.UUID):
    """Background task that runs a real Node build and serve pipeline."""
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    
    async with AsyncSessionLocal() as db:
        stmt = select(Deployment).where(Deployment.id == deployment_id)
        res = await db.execute(stmt)
        deployment = res.scalar_one_or_none()
        if not deployment:
            return

        project_name = deployment.project_name
        provider = deployment.provider
        template_id = deployment.template_id

        # Target directory where we extract and compile files
        deploy_dir = str(_DEPLOYMENTS_ROOT / str(deployment_id))
        os.makedirs(deploy_dir, exist_ok=True)
        
        deployment.logs = "🕛 [1/4] Initializing deployment workspace...\n"
        deployment.status = "building"
        await db.commit()

        # Step 1: Extract or Create files
        try:
            if not template_id or str(template_id) == "mock-project-id":
                # Create a beautiful mock index.html
                mock_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <style>
        body {{
            background: radial-gradient(circle at center, #1e1b4b, #090514);
            color: #ffffff;
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 3rem;
            border-radius: 1.5rem;
            text-align: center;
            max-width: 500px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #a78bfa, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p {{
            color: #94a3b8;
            font-size: 1.1rem;
            line-height: 1.6;
        }}
        .badge {{
            display: inline-block;
            margin-top: 1.5rem;
            padding: 0.5rem 1rem;
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{project_name}</h1>
        <p>This is your fully functional AI generated landing page, deployed on the local CDN gateway.</p>
        <div class="badge">Live & Secure via {provider.upper()}</div>
    </div>
</body>
</html>"""
                with open(os.path.join(deploy_dir, "index.html"), "w", encoding="utf-8") as f:
                    f.write(mock_html)
                
                deployment.logs += "✓ Generated clean HTML static assets.\n"
                deployment.logs += "📦 Deploying static files to local CDN gateway...\n"
                await db.commit()
                await asyncio.sleep(1.5)
                
                deployment.status = "success"
                deployment.live_url = f"http://localhost:8000/static/deployments/{deployment_id}/index.html"
                deployment.logs += "✅ Deployment completed successfully!\n"
                deployment.logs += f"🌐 Live URL: {deployment.live_url}\n"
                await db.commit()
                return

            else:
                # Real template
                from app.models.template import Template as DBTemplate
                t_stmt = select(DBTemplate).where(DBTemplate.id == template_id)
                t_res = await db.execute(t_stmt)
                template = t_res.scalar_one_or_none()
                if not template:
                    raise Exception("Template not found in database.")

                download_assets = template.download_assets or {}
                zip_url = download_assets.get("zip")
                if not zip_url:
                    raise Exception("Template source archive ZIP not configured.")

                deployment.logs += "📥 Downloading template source code ZIP...\n"
                await db.commit()

                file_id_str = zip_url.split("/")[-1]
                is_external = False
                file_uuid = None
                try:
                    file_uuid = uuid.UUID(file_id_str)
                except ValueError:
                    is_external = True

                if is_external:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(zip_url, follow_redirects=True, timeout=60.0)
                        if resp.status_code != 200:
                            raise Exception(f"Failed to fetch external ZIP: HTTP status {resp.status_code}")
                        zip_data = resp.content
                else:
                    from app.models import StoredFile
                    sf_stmt = select(StoredFile).where(StoredFile.id == file_uuid)
                    sf_res = await db.execute(sf_stmt)
                    stored_file = sf_res.scalar_one_or_none()
                    if not stored_file:
                        raise Exception("Source ZIP archive not found in local store.")
                    zip_data = stored_file.data

                deployment.logs += "✓ Download complete. Extracting package files...\n"
                await db.commit()

                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                    for member in zip_ref.infolist():
                        clean_path = os.path.normpath(member.filename).replace("..", "")
                        if clean_path.startswith("/") or clean_path.startswith("\\"):
                            clean_path = clean_path[1:]
                        target_path = os.path.join(deploy_dir, clean_path)
                        if member.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(zip_ref.read(member.filename))

                deployment.logs += "✓ Package extracted successfully.\n"
                await db.commit()

        except Exception as e:
            deployment.status = "failed"
            deployment.logs += f"❌ Error during extraction: {str(e)}\n"
            await db.commit()
            return

        # Step 2: Build / Compile project if required
        build_command = deployment.build_command
        output_dir = deployment.output_dir

        if not build_command or build_command.lower() == "none":
            # Pure static HTML
            deployment.logs += "📦 Deploying static files to local CDN gateway...\n"
            await db.commit()
            await asyncio.sleep(1.0)
            
            target_index = "index.html"
            for r, d, files in os.walk(deploy_dir):
                if "index.html" in files:
                    target_index = os.path.relpath(os.path.join(r, "index.html"), deploy_dir).replace("\\", "/")
                    break

            deployment.status = "success"
            deployment.live_url = f"http://localhost:8000/static/deployments/{deployment_id}/{target_index}"
            deployment.logs += "✅ Deployment completed successfully!\n"
            deployment.logs += f"🌐 Live URL: {deployment.live_url}\n"
            await db.commit()
            return

        try:
            # Locate package.json
            project_root = deploy_dir
            for r, d, files in os.walk(deploy_dir):
                if "package.json" in files:
                    project_root = r
                    break

            deployment.logs += "🛠️ Initializing Node build pipeline...\n"
            deployment.logs += "📥 Running: npm install\n"
            await db.commit()

            # Async subprocess for npm install
            proc_install = await asyncio.create_subprocess_exec(
                npm_cmd, "install", "--no-audit", "--no-fund",
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Stream npm install output
            while True:
                line = await proc_install.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8", errors="ignore")
                deployment.logs += "  " + decoded_line
                await db.commit()

            await proc_install.wait()
            if proc_install.returncode != 0:
                raise Exception(f"npm install failed with exit code {proc_install.returncode}")

            deployment.logs += "✓ Dependencies installed successfully.\n"
            deployment.logs += f"🚀 Running build script: {build_command}\n"
            await db.commit()

            cmd_parts = build_command.split(" ")
            if cmd_parts[0] == "npm" and cmd_parts[1] == "run":
                proc_build = await asyncio.create_subprocess_exec(
                    npm_cmd, "run", cmd_parts[2],
                    cwd=project_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            else:
                cmd_exec = cmd_parts[0] + (".cmd" if platform.system() == "Windows" and not cmd_parts[0].endswith(".cmd") else "")
                proc_build = await asyncio.create_subprocess_exec(
                    cmd_exec, *cmd_parts[1:],
                    cwd=project_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

            # Stream build output
            while True:
                line = await proc_build.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8", errors="ignore")
                deployment.logs += "  " + decoded_line
                await db.commit()

            await proc_build.wait()
            if proc_build.returncode != 0:
                raise Exception(f"Build command failed with exit code {proc_build.returncode}")

            deployment.logs += "✓ Build compilation completed successfully.\n"
            deployment.logs += "📦 Registering assets in local static CDN gateway...\n"
            await db.commit()
            await asyncio.sleep(1.0)

            # Locate build outputs
            build_folders = [output_dir, "dist", "out", "build", ".output/public", "public"]
            build_dir_path = None
            for d in build_folders:
                candidate = os.path.join(project_root, d)
                if os.path.isdir(candidate):
                    for br, bd, bfiles in os.walk(candidate):
                        if "index.html" in bfiles:
                            build_dir_path = br
                            break
                    if build_dir_path:
                        break

            if not build_dir_path:
                for br, bd, bfiles in os.walk(project_root):
                    if "index.html" in bfiles:
                        build_dir_path = br
                        break

            if not build_dir_path:
                raise Exception("Build completed but could not locate 'index.html' entry point in output files.")

            rel_build_path = os.path.relpath(build_dir_path, deploy_dir).replace("\\", "/")
            deployment.status = "success"
            deployment.live_url = f"http://localhost:8000/static/deployments/{deployment_id}/{rel_build_path}/index.html"
            deployment.logs += "✅ Deployment completed successfully!\n"
            deployment.logs += f"🌐 Live URL: {deployment.live_url}\n"
            await db.commit()

        except Exception as e:
            deployment.status = "failed"
            deployment.logs += f"\n❌ Build failed: {str(e)}\n"
            await db.commit()


@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new deployment and start the real build in the background."""
    clean_name = "".join(c for c in payload.project_name.lower() if c.isalnum() or c in (" ", "-", "_"))
    subdomain_slug = clean_name.replace(" ", "-")
    subdomain = f"{subdomain_slug}.aisitestudio.com"

    deployment = Deployment(
        user_id=current_user.id,
        template_id=payload.template_id,
        project_name=payload.project_name,
        provider=payload.provider,
        status="building",
        subdomain=subdomain,
        branch=payload.branch,
        build_command=payload.build_command,
        output_dir=payload.output_dir,
        logs="🕛 Initializing deployment pipeline...\n",
    )
    
    db.add(deployment)
    await db.flush()
    await db.commit()
    await db.refresh(deployment)

    background_tasks.add_task(real_deploy_task, deployment.id)

    return deployment


@router.get("/", response_model=List[DeploymentResponse])
async def list_deployments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all deployments belonging to the logged-in user."""
    stmt = select(Deployment).where(Deployment.user_id == current_user.id).order_by(Deployment.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{id}", response_model=DeploymentResponse)
async def get_deployment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get status and logs for a specific deployment."""
    stmt = select(Deployment).where(Deployment.id == id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return deployment


@router.post("/{id}/redeploy", response_model=DeploymentResponse)
async def redeploy(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeploy an existing project configuration."""
    stmt = select(Deployment).where(Deployment.id == id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Reset deployment details
    deployment.status = "building"
    deployment.created_at = datetime.now(timezone.utc)
    deployment.logs = "🕛 Initializing redeployment...\n"
    deployment.live_url = None

    await db.commit()
    await db.refresh(deployment)

    background_tasks.add_task(real_deploy_task, deployment.id)

    return deployment


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a deployment config and clean up local build directory."""
    stmt = select(Deployment).where(Deployment.id == id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Clean up static files directory
    deploy_dir = str(_DEPLOYMENTS_ROOT / str(id))
    if os.path.exists(deploy_dir):
        shutil.rmtree(deploy_dir, ignore_errors=True)

    await db.delete(deployment)
    await db.commit()
    return


@router.patch("/{id}/domain", response_model=DeploymentResponse)
async def update_custom_domain(
    id: uuid.UUID,
    custom_domain: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link or unlink a custom domain to/from an existing deployment."""
    stmt = select(Deployment).where(Deployment.id == id, Deployment.user_id == current_user.id)
    res = await db.execute(stmt)
    deployment = res.scalar_one_or_none()

    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if custom_domain:
        domain_clean = custom_domain.strip().lower()
        if not domain_clean or "." not in domain_clean or len(domain_clean) < 4:
            raise HTTPException(status_code=400, detail="Invalid custom domain format")
        
        deployment.custom_domain = domain_clean
        # Update live_url to point to custom domain (ensuring http/https prefix)
        if not (domain_clean.startswith("http://") or domain_clean.startswith("https://")):
            deployment.live_url = f"http://{domain_clean}"
        else:
            deployment.live_url = domain_clean
    else:
        deployment.custom_domain = None
        # Revert live_url to default subdomain
        deployment.live_url = f"http://{deployment.subdomain}"

    await db.commit()
    await db.refresh(deployment)
    return deployment
