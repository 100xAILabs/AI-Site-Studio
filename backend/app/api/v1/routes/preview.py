"""
Preview routes — create preview sessions and serve watermarked previews.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.models.user import User
from app.services.preview_service import PreviewService
from app.services.ai_service import ai_service
from app.repositories.template_repo import TemplateRepository
from pydantic import BaseModel

router = APIRouter()


class PreviewRequest(BaseModel):
    template_id: uuid.UUID
    business_name: str
    industry: str
    primary_color: Optional[str] = "#6366f1"
    secondary_color: Optional[str] = "#8b5cf6"
    about: Optional[str] = None
    services: Optional[list] = None
    contact: Optional[dict] = None
    location: Optional[str] = None
    social_links: Optional[dict] = None
    logo_url: Optional[str] = None
    ai_fill: bool = False  # If True, auto-generate content via AI


class PreviewResponse(BaseModel):
    session_id: uuid.UUID
    preview_image_url: Optional[str] = None
    business_data: dict
    generated_content: Optional[dict] = None
    template_id: uuid.UUID


@router.post("", response_model=PreviewResponse)
async def create_preview(
    request: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a watermarked live preview session.

    If `ai_fill=true`, AI generates the business content automatically.
    Returns a watermarked preview image URL + session ID.
    """
    service = PreviewService(db)
    template_repo = TemplateRepository(db)

    template = await template_repo.get_by_id(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    business_data = {
        "business_name": request.business_name,
        "industry": request.industry,
        "primary_color": request.primary_color,
        "secondary_color": request.secondary_color,
        "about": request.about,
        "services": request.services or [],
        "contact": request.contact or {},
        "location": request.location,
        "social_links": request.social_links or {},
        "logo_url": request.logo_url,
    }

    generated_content = None
    if request.ai_fill and ai_service.client:
        try:
            generated_content = await ai_service.generate_business_content(
                business_name=request.business_name,
                industry=request.industry,
                template_type=template.category.name if template.category else "business",
            )
            # Merge AI content into business_data
            business_data.update(generated_content)
        except Exception:
            pass  # AI fill optional — continue without it

    user_email = current_user.email if current_user else None

    session = await service.create_session(
        template_id=request.template_id,
        business_data=business_data,
        user_email=user_email,
        is_ai_filled=request.ai_fill,
    )

    # Generate watermarked preview
    preview_url = None
    try:
        preview_url = await service.generate_preview_screenshot(
            session_id=session.id,
            template_thumbnail_url=template.thumbnail_url,
            user_email=user_email,
        )
        session.preview_image_url = preview_url
        session.generated_content = generated_content
        await db.flush()
    except Exception:
        pass  # Preview image is optional — session is still created

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=preview_url,
        business_data=business_data,
        generated_content=generated_content,
        template_id=request.template_id,
    )


@router.get("/{session_id}", response_model=PreviewResponse)
async def get_preview_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an existing preview session by ID."""
    from sqlalchemy import select
    from app.models.preview_session import PreviewSession

    result = await db.execute(
        select(PreviewSession).where(PreviewSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Preview session not found")

    return PreviewResponse(
        session_id=session.id,
        preview_image_url=session.preview_image_url,
        business_data=session.business_data or {},
        generated_content=session.generated_content,
        template_id=session.template_id,
    )


# Global locks to prevent parallel builds of the same template
_build_locks = {}


@router.get("/live/{template_id}", response_class=Response)
@router.get("/live/{template_id}/{filepath:path}", response_class=Response)
async def serve_live_preview(
    template_id: uuid.UUID,
    request: Request,
    filepath: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Redirect to URL with trailing slash to ensure relative assets load correctly in browser
    if not filepath and not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=str(request.url) + "/")
    """
    Dynamically extract, compile (if needed), and serve the template's actual frontend code in the browser as a running live demo.
    """
    import os
    import zipfile
    import io
    import mimetypes
    import asyncio
    import platform
    import subprocess
    import tempfile
    from fastapi.responses import Response
    from sqlalchemy import select
    from app.repositories.template_repo import TemplateRepository
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    file_id_str = zip_url.split("/")[-1]
    is_external = False
    file_id = None
    try:
        file_id = uuid.UUID(file_id_str)
    except ValueError:
        is_external = True
        
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    os.makedirs(preview_dir, exist_ok=True)
    
    # If the folder has package.json but lacks a completed build folder (dist/out/etc. containing index.html),
    # it means a previous compilation failed. Clear the directory to trigger a fresh extraction and self-healing build.
    package_json_exists = False
    build_folder_exists = False
    for root, dirs, files in os.walk(preview_dir):
        if "package.json" in files:
            package_json_exists = True
            for d in ["dist", "out", "build", ".output", "public"]:
                candidate = os.path.join(root, d)
                if os.path.isdir(candidate):
                    for b_root, b_dirs, b_files in os.walk(candidate):
                        if "index.html" in b_files:
                            build_folder_exists = True
                            break
                    if build_folder_exists:
                        break
            break

    if package_json_exists and not build_folder_exists:
        try:
            import shutil
            shutil.rmtree(preview_dir, ignore_errors=True)
            os.makedirs(preview_dir, exist_ok=True)
        except Exception:
            pass

    # Extract files if preview_dir is empty (first-time extract)
    if not os.listdir(preview_dir):
        if is_external:
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(zip_url, follow_redirects=True, timeout=30.0)
                    if response.status_code != 200:
                        raise HTTPException(status_code=400, detail=f"Failed to fetch external ZIP assets: status {response.status_code}")
                    zip_data = response.content
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to download external template ZIP: {str(e)}")
        else:
            from app.models import StoredFile
            result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            stored_file = result.scalar_one_or_none()
            if not stored_file:
                raise HTTPException(status_code=404, detail="Source template archive file not found")
            zip_data = stored_file.data
            
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
            for member in zip_ref.infolist():
                clean_path = os.path.normpath(member.filename).replace("..", "")
                if clean_path.startswith("/") or clean_path.startswith("\\"):
                    clean_path = clean_path[1:]
                    
                target_path = os.path.join(preview_dir, clean_path)
                if member.is_dir():
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    content_bytes = zip_ref.read(member.filename)
                    # Self-heal previously generated files if they are truncated
                    if target_path.endswith(".jsx") or target_path.endswith(".js"):
                        try:
                            from app.services.ai_service import repair_truncated_jsx
                            code_str = content_bytes.decode("utf-8", errors="ignore")
                            repaired_code = repair_truncated_jsx(code_str)
                            content_bytes = repaired_code.encode("utf-8")
                        except Exception as e:
                            print(f"[On-the-fly Self Heal] Failed to repair {target_path}: {e}")
                    elif target_path.endswith(".html"):
                        try:
                            from app.services.ai_service import repair_truncated_html
                            code_str = content_bytes.decode("utf-8", errors="ignore")
                            repaired_code = repair_truncated_html(code_str)
                            content_bytes = repaired_code.encode("utf-8")
                        except Exception as e:
                            print(f"[On-the-fly Self Heal] Failed to repair {target_path}: {e}")
                    with open(target_path, "wb") as f:
                        f.write(content_bytes)

    # Detect package.json to see if this is a Node.js project requiring compilation
    import json
    package_json_path = None
    # 1. Prioritize package.json that contains a "build" script
    for root, dirs, files in os.walk(preview_dir):
        if "package.json" in files:
            candidate_path = os.path.join(root, "package.json")
            try:
                with open(candidate_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    if "scripts" in pkg_data and "build" in pkg_data["scripts"]:
                        package_json_path = candidate_path
                        break
            except Exception:
                pass
                
    # 2. Fallback to the first package.json if none have a build script
    if not package_json_path:
        for root, dirs, files in os.walk(preview_dir):
            if "package.json" in files:
                package_json_path = os.path.join(root, "package.json")
                break

    serve_root = preview_dir
    build_dir = None

    if package_json_path:
        project_root = os.path.dirname(package_json_path)
        build_folders = ["dist", "out", "build", ".output", "public"]
        
        # Check if project is already compiled
        for d in build_folders:
            candidate = os.path.join(project_root, d)
            if os.path.isdir(candidate):
                # Search for index.html recursively inside build folder (e.g. dist/index.html)
                for b_root, b_dirs, b_files in os.walk(candidate):
                    if "index.html" in b_files:
                        build_dir = b_root
                        break
                if build_dir:
                    break

        # If not compiled, trigger compilation
        if not build_dir:
            lock = _build_locks.setdefault(template_id, asyncio.Lock())
            async with lock:
                # Check again under lock in case another request compiled it
                for d in build_folders:
                    candidate = os.path.join(project_root, d)
                    if os.path.isdir(candidate):
                        for b_root, b_dirs, b_files in os.walk(candidate):
                            if "index.html" in b_files:
                                build_dir = b_root
                                break
                        if build_dir:
                            break
                
                if not build_dir:
                    # Run compilation
                    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                    loop = asyncio.get_running_loop()
                    
                    # 1. npm install
                    def run_npm_install():
                        return subprocess.run(
                            [npm_cmd, "install", "--no-audit", "--no-fund"],
                            cwd=project_root,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                    
                    install_res = await loop.run_in_executor(None, run_npm_install)
                    if install_res.returncode != 0:
                        print(f"npm install failed for {template_id}: {install_res.stderr.decode('utf-8', errors='ignore')}")
                    
                    # Detect framework characteristics
                    is_next = False
                    is_nuxt = False
                    has_generate_script = False
                    has_export_script = False
                    
                    try:
                        with open(package_json_path, "r", encoding="utf-8") as f:
                            pkg_data = json.load(f)
                            all_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                            is_next = "next" in all_deps
                            is_nuxt = "nuxt" in all_deps
                            has_generate_script = "generate" in pkg_data.get("scripts", {})
                            has_export_script = "export" in pkg_data.get("scripts", {})
                    except Exception:
                        pass

                    # Framework-specific configuration tuning (e.g., forcing static export for Next.js)
                    if is_next:
                        next_cfg_js = os.path.join(project_root, "next.config.js")
                        next_cfg_mjs = os.path.join(project_root, "next.config.mjs")
                        
                        if not os.path.exists(next_cfg_js) and not os.path.exists(next_cfg_mjs):
                            try:
                                with open(next_cfg_js, "w", encoding="utf-8") as f:
                                    f.write("module.exports = { output: 'export', images: { unoptimized: true } };\n")
                            except Exception:
                                pass
                        else:
                            cfg_path = next_cfg_js if os.path.exists(next_cfg_js) else next_cfg_mjs
                            try:
                                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                                    cfg_content = f.read()
                                if "output:" not in cfg_content and "output :" not in cfg_content:
                                    for pattern in ["const nextConfig = {", "module.exports = {", "export default {", "nextConfig = {"]:
                                        if pattern in cfg_content:
                                            cfg_content = cfg_content.replace(pattern, f"{pattern}\n  output: 'export',\n  images: {{ unoptimized: true }},", 1)
                                            break
                                    with open(cfg_path, "w", encoding="utf-8") as f:
                                        f.write(cfg_content)
                            except Exception:
                                pass

                    # Determine optimal build/generate command
                    build_cmd = [npm_cmd, "run", "build"]
                    if is_nuxt:
                        if has_generate_script:
                            build_cmd = [npm_cmd, "run", "generate"]
                        else:
                            npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
                            build_cmd = [npx_cmd, "nuxt", "generate"]

                    # 2. Compile/build template project
                    def run_npm_build():
                        res = subprocess.run(
                            build_cmd,
                            cwd=project_root,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        if res.returncode == 0 and is_next and has_export_script:
                            subprocess.run(
                                [npm_cmd, "run", "export"],
                                cwd=project_root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                            )
                        return res
                        
                    build_res = await loop.run_in_executor(None, run_npm_build)
                    if build_res.returncode != 0:
                        print(f"npm run build failed for {template_id}: {build_res.stderr.decode('utf-8', errors='ignore')}")
                        
                    # Locate build dir again after build
                    for d in build_folders:
                        candidate = os.path.join(project_root, d)
                        if os.path.isdir(candidate):
                            for b_root, b_dirs, b_files in os.walk(candidate):
                                if "index.html" in b_files:
                                    build_dir = b_root
                                    break
                            if build_dir:
                                break

        if build_dir:
            serve_root = build_dir
        else:
            serve_root = project_root

    # Locate index.html
    index_file_path = os.path.join(serve_root, "index.html")
    if not os.path.exists(index_file_path):
        for root, dirs, files in os.walk(serve_root):
            if "index.html" in files:
                index_file_path = os.path.join(root, "index.html")
                serve_root = root
                break

    # Determine file to serve
    if not filepath or filepath == "/":
        full_path = index_file_path
    else:
        safe_path = os.path.normpath(filepath).replace("..", "")
        if safe_path.startswith("/") or safe_path.startswith("\\"):
            safe_path = safe_path[1:]
        full_path = os.path.join(serve_root, safe_path)
        
        # Fallback for nested layouts if not found directly
        if not os.path.exists(full_path):
            subdirs = [d for d in os.listdir(serve_root) if os.path.isdir(os.path.join(serve_root, d)) and d not in ["__MACOSX"]]
            if len(subdirs) == 1:
                nested_path = os.path.join(serve_root, subdirs[0], safe_path)
                if os.path.exists(nested_path):
                    full_path = nested_path

    if not os.path.exists(full_path) or os.path.isdir(full_path):
        # Fallback to index.html if file not found (e.g. client side routing)
        if os.path.exists(index_file_path):
            full_path = index_file_path
        else:
            raise HTTPException(status_code=404, detail="Requested file not found in template")
            
    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    with open(full_path, "rb") as f:
        content = f.read()

    # Rewrite absolute references to relative on all HTML preview pages
    if mime_type == "text/html":
        try:
            html_content = content.decode("utf-8", errors="ignore")
            
            # 1. Rewrite absolute resources (e.g. /vite.svg, /assets/index.js) to relative FIRST
            import re
            html_content = re.sub(r'src="/(?![/])', 'src="./', html_content)
            html_content = re.sub(r'href="/(?![/])', 'href="./', html_content)
            
            # 2. Inject client-side routing and location sandboxing script (including absolute <base> tag)
            sandbox_script = f"""<base href="/api/v1/preview/live/{template_id}/" />
<script>
  (function() {{
    const basePrefix = "/api/v1/preview/live/{template_id}";
    
    // 1. Instantly rewrite history state to relative path so client-side routers match the root route
    try {{
      if (window.location.pathname.startsWith(basePrefix)) {{
        let targetPath = window.location.pathname.slice(basePrefix.length);
        if (!targetPath.startsWith('/')) {{
          targetPath = '/' + targetPath;
        }}
        window.history.replaceState(null, '', targetPath);
      }}
    }} catch (e) {{
      console.error("[Live Preview Sandbox] Failed to replace initial state:", e);
    }}

    // 2. Intercept click events on absolute links to keep them inside the sandbox
    document.addEventListener('click', function(e) {{
      const link = e.target.closest('a');
      if (link) {{
        const rawHref = link.getAttribute('href');
        if (rawHref && rawHref.startsWith('#')) {{
          e.preventDefault();
          window.location.hash = rawHref;
          return;
        }}
        if (rawHref && rawHref.startsWith('javascript:')) {{
          return;
        }}
        if (link.href) {{
          try {{
            const url = new URL(link.href);
            if (url.origin === window.location.origin) {{
              let path = url.pathname;
              if (path.startsWith('/') && !path.startsWith(basePrefix)) {{
                link.href = url.origin + basePrefix + path + url.search + url.hash;
              }}
            }}
          }} catch (err) {{}}
        }}
      }}
    }}, true);
  }})();
</script>"""
            
            if "<head>" in html_content:
                html_content = html_content.replace("<head>", f"<head>\n  {sandbox_script}", 1)
            elif "<html>" in html_content:
                html_content = html_content.replace("<html>", f"<html>\n  {sandbox_script}", 1)
            else:
                html_content = sandbox_script + "\n" + html_content

            # Inject Watermarks & Copy/Inspect/Print Restrictions before </body>
            watermark_payload = """
<!-- Injected Watermark Grid Overlay -->
<div class="preview-watermark-grid"></div>

<!-- Injected Purchase Footer Banner -->
<div class="preview-purchase-footer-banner">
  <span>🔒 Watermarked Draft Preview. Purchase this template to download clean project assets.</span>
  <a href="/marketplace" target="_parent">Purchase Template &rarr;</a>
</div>

<style>
  /* Disable text selection across all elements */
  * {
    user-select: none !important;
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
  }

  /* Watermark grid covering full page with pointer-events disabled */
  .preview-watermark-grid {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    pointer-events: none !important;
    z-index: 999999 !important;
    opacity: 0.65 !important;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(15, 23, 42, 0.035)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>AI SITE STUDIO PREVIEW</text></svg>") !important;
    background-repeat: repeat !important;
  }

  /* Bottom floating warning banner */
  .preview-purchase-footer-banner {
    position: fixed !important;
    bottom: 1.5rem !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    background: rgba(15, 23, 42, 0.96) !important;
    backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    color: #ffffff !important;
    padding: 0.625rem 1.25rem !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    border-radius: 9999px !important;
    display: flex !important;
    align-items: center !important;
    gap: 1rem !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4) !important;
    z-index: 999998 !important;
    white-space: nowrap !important;
    font-family: system-ui, -apple-system, sans-serif !important;
  }

  .preview-purchase-footer-banner a {
    color: #38bdf8 !important;
    text-decoration: none !important;
    font-weight: 800 !important;
    border-left: 1px solid rgba(255, 255, 255, 0.2) !important;
    padding-left: 1rem !important;
    transition: color 0.2s ease !important;
  }

  .preview-purchase-footer-banner a:hover {
    color: #0ea5e9 !important;
  }

  /* Block PDF printing */
  @media print {
    body {
      display: none !important;
    }
  }
</style>

<script>
  (function() {
    // 1. Disable Right-Click Context Menu
    document.addEventListener('contextmenu', function(e) {
      e.preventDefault();
    }, true);

    // 2. Intercept Inspector, View-Source, Copy and Save keys
    document.addEventListener('keydown', function(e) {
      if (
        e.key === 'F12' ||
        (e.ctrlKey && e.shiftKey && e.key === 'I') ||
        (e.ctrlKey && e.shiftKey && e.key === 'C') ||
        (e.ctrlKey && e.shiftKey && e.key === 'J') ||
        (e.ctrlKey && e.key === 'u') ||
        (e.ctrlKey && e.key === 'c') ||
        (e.ctrlKey && e.key === 's')
      ) {
        e.preventDefault();
        e.stopPropagation();
        return false;
      }
    }, true);
  })();
</script>
"""
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{watermark_payload}\n</body>", 1)
            else:
                html_content = html_content + "\n" + watermark_payload

            content = html_content.encode("utf-8")
        except Exception:
            pass
        
    return Response(content=content, media_type=mime_type)


class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class AIEditRequest(BaseModel):
    prompt: str


@router.post("/live/{template_id}/edit-manual")
async def edit_live_preview_manual(
    template_id: uuid.UUID,
    request: ManualEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # If the template is PUBLISHED, clone it so the user modifies their own private DRAFT copy
    if template.status == TemplateStatus.PUBLISHED:
        new_template = Template(
            title=f"Customized {template.title}",
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            developer_id=current_user.id if current_user else template.developer_id,
            thumbnail_url=template.thumbnail_url,
            demo_url=template.demo_url,
            features=template.features,
            tags=template.tags,
            framework=template.framework,
            download_assets=template.download_assets.copy() if template.download_assets else {}
        )
        db.add(new_template)
        await db.flush()
        template = new_template
        template_id = new_template.id

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    file_id_str = zip_url.split("/")[-1]
    try:
        file_id = uuid.UUID(file_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
        
    from app.models.stored_file import StoredFile
    from sqlalchemy import select
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")
        
    zip_data = stored_file.data
    
    # 1. Inspect the ZIP content to find the main code file
    target_file = None
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        namelist = z_in.namelist()
        if "src/App.jsx" in namelist:
            target_file = "src/App.jsx"
        elif "index.html" in namelist:
            target_file = "index.html"
        else:
            for name in namelist:
                if name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js"):
                    target_file = name
                    break
                    
    if not target_file:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")
        
    # 2. Extract target file content
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        original_code = z_in.read(target_file).decode("utf-8", errors="ignore")
        
    # 3. Use Gemini to do simple content/styling updates
    edit_prompt = f"""You are a specialized React/HTML code refactoring tool.
Your task is to take the provided code and replace specific business fields and styles with these new values:
- Business Name: {request.business_name}
- About Description: {request.about}
- Primary Theme Color Accent: {request.primary_color}
- Secondary Theme Color Accent: {request.secondary_color}
- Contact Email: {request.contact_email or ""}
- Contact Phone: {request.contact_phone or ""}

Rules:
1. Preserve all page layouts, logic, hooks, routing, icons, and components exactly.
2. Only replace text labels, headers, descriptions, contact details, and theme color Hex codes/Tailwind colors.
3. Return ONLY the complete modified source code. Do not include markdown code block syntax (like ```jsx or ```html) or explanations.

Here is the source code:
{original_code}
"""
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    try:
        raw_code = await ai_service._generate_content(edit_prompt, response_mime_type="text/plain", feature_name="code_assistant")
        updated_code = clean_code_response(raw_code, "jsx")
        updated_code = clean_code_response(updated_code, "javascript")
        updated_code = clean_code_response(updated_code, "html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refactor template code: {str(e)}")
        
    # 4. Overwrite file in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename == target_file:
                    content = updated_code.encode("utf-8")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 5. Save the updated ZIP back to the database
    stored_file.data = new_zip_bytes
    stored_file.size = len(new_zip_bytes)
    db.add(stored_file)
    await db.flush()
    
    # 6. Clear local preview directory cache to force a rebuild on the next preview request
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id)}


@router.post("/live/{template_id}/edit-ai")
async def edit_live_preview_ai(
    template_id: uuid.UUID,
    request: AIEditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    import zipfile
    import io
    import shutil
    import tempfile
    from app.models.template import Template, TemplateStatus
    from app.core.storage import storage
    
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # If the template is PUBLISHED, clone it so the user modifies their own private DRAFT copy
    if template.status == TemplateStatus.PUBLISHED:
        new_template = Template(
            title=f"Customized {template.title}",
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            developer_id=current_user.id if current_user else template.developer_id,
            thumbnail_url=template.thumbnail_url,
            demo_url=template.demo_url,
            features=template.features,
            tags=template.tags,
            framework=template.framework,
            download_assets=template.download_assets.copy() if template.download_assets else {}
        )
        db.add(new_template)
        await db.flush()
        template = new_template
        template_id = new_template.id

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP assets")
        
    file_id_str = zip_url.split("/")[-1]
    try:
        file_id = uuid.UUID(file_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="External/Invalid zip storage format")
        
    from app.models.stored_file import StoredFile
    from sqlalchemy import select
    result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
    stored_file = result.scalar_one_or_none()
    if not stored_file:
        raise HTTPException(status_code=404, detail="Source template archive file not found")
        
    zip_data = stored_file.data
    
    # 1. Inspect the ZIP content to find the main code file
    target_file = None
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        namelist = z_in.namelist()
        if "src/App.jsx" in namelist:
            target_file = "src/App.jsx"
        elif "index.html" in namelist:
            target_file = "index.html"
        else:
            for name in namelist:
                if name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js"):
                    target_file = name
                    break
                    
    if not target_file:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")
        
    # 2. Extract target file content
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        original_code = z_in.read(target_file).decode("utf-8", errors="ignore")
        
    # 3. Use Gemini to do AI editing/refinement
    ai_prompt = f"""You are a senior lead web developer.
Refine the provided code according to this user request: "{request.prompt}".

Rules:
1. Fully implement the modifications requested by the user.
2. Ensure the code compiles and remains valid React/HTML. Keep all existing styles/utilities unless explicitly requested to change.
3. Return ONLY the complete modified source code. Do not include markdown code block syntax (like ```jsx or ```html) or explanations.

Here is the source code:
{original_code}
"""
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    try:
        raw_code = await ai_service._generate_content(ai_prompt, response_mime_type="text/plain", feature_name="code_assistant")
        updated_code = clean_code_response(raw_code, "jsx")
        updated_code = clean_code_response(updated_code, "javascript")
        updated_code = clean_code_response(updated_code, "html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine template code via AI: {str(e)}")
        
    # 4. Overwrite file in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename == target_file:
                    content = updated_code.encode("utf-8")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 5. Save the updated ZIP back to the database
    stored_file.data = new_zip_bytes
    stored_file.size = len(new_zip_bytes)
    db.add(stored_file)
    await db.flush()
    
    # 6. Clear local preview directory cache to force a rebuild on the next preview request
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id)}

