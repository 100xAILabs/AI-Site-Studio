"""
Preview routes — create preview sessions and serve watermarked previews.
"""

import os
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
class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None


class AIEditRequest(BaseModel):
    prompt: str




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


@router.post("/live/{template_id}/edit-manual")
async def edit_live_preview_manual(
    template_id: uuid.UUID,
    request: ManualEditRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
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
            short_description=template.short_description,
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            original_price=template.original_price,
            is_free=template.is_free,
            is_on_sale=template.is_on_sale,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            seller_id=current_user.id if current_user else template.seller_id,
            thumbnail_url=template.thumbnail_url,
            preview_url=template.preview_url,
            tags=template.tags,
            framework=template.framework,
            pages_count=template.pages_count,
            has_dark_mode=template.has_dark_mode,
            is_responsive=template.is_responsive,
            is_rtl_supported=template.is_rtl_supported,
            is_ai_ready=template.is_ai_ready,
            compatibility=template.compatibility,
            version=template.version,
            license_type=template.license_type,
            industry=template.industry,
            color_scheme=template.color_scheme,
            seo_keywords=template.seo_keywords,
            included_pages=template.included_pages,
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
    
    # 1. Read all editable files in the ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        for name in z_in.namelist():
            is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
            if (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".css") or name.endswith(".tsx") or name.endswith(".ts")) and not is_build:
                try:
                    files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")
        
    # 2. Use Gemini to do simple content/styling updates across all files
    files_str = ""
    for name, content in files_dict.items():
        files_str += f"\n--- FILE: {name} ---\n{content}\n"

    page_edits_str = ""
    if request.page_edits:
        page_edits_str = "\nAlso apply these page-specific content overrides:\n"
        for page_name, edits in request.page_edits.items():
            page_edits_str += f"- For file '{page_name}':\n"
            if edits.get("title"):
                page_edits_str += f"  * Set main page title/header/headline to: \"{edits['title']}\"\n"
            if edits.get("description"):
                page_edits_str += f"  * Set main body content/description/story to: \"{edits['description']}\"\n"
            if edits.get("cta_text"):
                page_edits_str += f"  * Set primary Call to Action (CTA) button text to: \"{edits['cta_text']}\"\n"
            if edits.get("cta_link"):
                page_edits_str += f"  * Set primary Call to Action (CTA) button link/href/action to: \"{edits['cta_link']}\"\n"

    edit_prompt = f"""You are a specialized React/HTML code refactoring tool.
Your task is to take the provided website template files and replace specific business fields and styles with these new values:
- Business Name: {request.business_name}
- About Description: {request.about}
- Primary Theme Color Accent: {request.primary_color}
- Secondary Theme Color Accent: {request.secondary_color}
- Contact Email: {request.contact_email or ""}
- Contact Phone: {request.contact_phone or ""}
{page_edits_str}

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code exactly, including leading spaces and indentation.
3. The "replace" string must contain the updated code to replace it.
4. Replace all occurrences of old business names, descriptions, accent colors, and contact info in the code.

Format the JSON response exactly like this:
[
  {{
    "filename": "src/App.tsx",
    "find": "const [title, setTitle] = useState('Old Title');",
    "replace": "const [title, setTitle] = useState('New Title');"
  }}
]

Here are the codebase files:
{files_str}
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
        import json
        raw_code = await ai_service._generate_content(edit_prompt, response_mime_type="application/json", feature_name="code_assistant")
        chunks = json.loads(clean_code_response(raw_code, "json"))
        if not isinstance(chunks, list):
            if isinstance(chunks, dict):
                chunks = [{"filename": k, "find": files_dict.get(k, ""), "replace": v} for k, v in chunks.items()]
            else:
                chunks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refactor template code: {str(e)}")
        
    # Apply chunks to files_dict
    updated_filenames = set()
    for chunk in chunks:
        filename = chunk.get("filename")
        find_str = chunk.get("find")
        replace_str = chunk.get("replace")
        if not filename or find_str is None or replace_str is None:
            continue
        matched_name = None
        for name in files_dict:
            if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                matched_name = name
                break
        if matched_name:
            if find_str in files_dict[matched_name]:
                files_dict[matched_name] = files_dict[matched_name].replace(find_str, replace_str)
                updated_filenames.add(matched_name)
                print(f"Applied manual replacement chunk for {matched_name}")
            else:
                # Try simple replacement if exact match failed due to spacing
                cleaned_find = find_str.strip()
                if cleaned_find and cleaned_find in files_dict[matched_name]:
                    files_dict[matched_name] = files_dict[matched_name].replace(cleaned_find, replace_str.strip())
                    updated_filenames.add(matched_name)
                    print(f"Applied fuzzy-spaced manual replacement chunk for {matched_name}")

    # 3. Overwrite files in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename in updated_filenames:
                    content = files_dict[item.filename].encode("utf-8")
                    print(f"Saved manual edited file to ZIP: {item.filename}")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 4. Save the updated ZIP back to the database
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
            short_description=template.short_description,
            description=template.description,
            slug=f"{template.slug}-custom-{uuid.uuid4().hex[:6]}",
            price=template.price,
            original_price=template.original_price,
            is_free=template.is_free,
            is_on_sale=template.is_on_sale,
            category_id=template.category_id,
            status=TemplateStatus.DRAFT,
            seller_id=current_user.id if current_user else template.seller_id,
            thumbnail_url=template.thumbnail_url,
            preview_url=template.preview_url,
            tags=template.tags,
            framework=template.framework,
            pages_count=template.pages_count,
            has_dark_mode=template.has_dark_mode,
            is_responsive=template.is_responsive,
            is_rtl_supported=template.is_rtl_supported,
            is_ai_ready=template.is_ai_ready,
            compatibility=template.compatibility,
            version=template.version,
            license_type=template.license_type,
            industry=template.industry,
            color_scheme=template.color_scheme,
            seo_keywords=template.seo_keywords,
            included_pages=template.included_pages,
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
    
    # 1. Read all editable files in the ZIP (HTML, JS, JSX, CSS)
    files_dict = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        for name in z_in.namelist():
            is_build = any(d in name.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
            if (name.endswith(".html") or name.endswith(".jsx") or name.endswith(".js") or name.endswith(".css") or name.endswith(".tsx") or name.endswith(".ts")) and not is_build:
                try:
                    files_dict[name] = z_in.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    pass

    if not files_dict:
        raise HTTPException(status_code=400, detail="Could not locate code files in template archive")
        
    # 2. Use Gemini to do AI editing/refinement across the codebase
    files_str = ""
    for name, content in files_dict.items():
        files_str += f"\n--- FILE: {name} ---\n{content}\n"

    ai_prompt = f"""You are a senior lead web developer.
Refine the provided website template files according to this user request: "{request.prompt}".

Rules:
1. Return a JSON list of search-and-replace blocks. Do NOT return the entire file content.
2. The "find" string must match the target code exactly, including leading spaces and indentation.
3. The "replace" string must contain the updated code to replace it.
4. Keep the search blocks as small and precise as possible to avoid mistakes.

Format the JSON response exactly like this:
[
  {{
    "filename": "src/App.tsx",
    "find": "const [title, setTitle] = useState('Old Title');",
    "replace": "const [title, setTitle] = useState('New Title');"
  }}
]

Here are the codebase files:
{files_str}
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
        import json
        raw_code = await ai_service._generate_content(ai_prompt, response_mime_type="application/json", feature_name="code_assistant")
        chunks = json.loads(clean_code_response(raw_code, "json"))
        if not isinstance(chunks, list):
            if isinstance(chunks, dict):
                chunks = [{"filename": k, "find": files_dict.get(k, ""), "replace": v} for k, v in chunks.items()]
            else:
                chunks = []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine template code via AI: {str(e)}")
        
    # Apply chunks to files_dict
    updated_filenames = set()
    for chunk in chunks:
        filename = chunk.get("filename")
        find_str = chunk.get("find")
        replace_str = chunk.get("replace")
        if not filename or find_str is None or replace_str is None:
            continue
        matched_name = None
        for name in files_dict:
            if name == filename or name.endswith("/" + filename) or name.endswith("\\" + filename) or os.path.basename(name) == filename:
                matched_name = name
                break
        if matched_name:
            if find_str in files_dict[matched_name]:
                files_dict[matched_name] = files_dict[matched_name].replace(find_str, replace_str)
                updated_filenames.add(matched_name)
                print(f"Applied AI replacement chunk for {matched_name}")
            else:
                # Try simple replacement if exact match failed due to spacing
                cleaned_find = find_str.strip()
                if cleaned_find and cleaned_find in files_dict[matched_name]:
                    files_dict[matched_name] = files_dict[matched_name].replace(cleaned_find, replace_str.strip())
                    updated_filenames.add(matched_name)
                    print(f"Applied fuzzy-spaced AI replacement chunk for {matched_name}")

    # 3. Overwrite files in ZIP
    new_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                if item.filename in updated_filenames:
                    content = files_dict[item.filename].encode("utf-8")
                    print(f"Saved AI edited file to ZIP: {item.filename}")
                z_out.writestr(item, content)
                
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 4. Save the updated ZIP back to the database
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

@router.api_route("/live/{template_id}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
@router.api_route("/live/{template_id}/{filepath:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"], response_class=Response)
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
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>AI SITE STUDIO PREVIEW</text></svg>") !important;
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
    async def serve_fallback(err_msg: str = "Preview compilation"):
        if filepath and not (filepath.endswith(".html") or filepath.endswith(".htm")):
            if filepath.endswith(".css"):
                return Response(content=b"", media_type="text/css")
            if filepath.endswith(".js"):
                return Response(content=b"", media_type="application/javascript")
            return Response(content=b"", media_type="application/octet-stream")

        custom_color = request.query_params.get("primaryColor") or "#6366f1"
        try:
            hex_color = custom_color.lstrip("#")
            if len(hex_color) == 3:
                hex_color = "".join(c*2 for c in hex_color)
            primary_rgb = f"{int(hex_color[0:2], 16)}, {int(hex_color[2:4], 16)}, {int(hex_color[4:6], 16)}"
        except Exception:
            primary_rgb = "99, 102, 241"

        b_name = request.query_params.get("businessName") or template.title
        c_title = request.query_params.get("title") or template.title
        c_sub = request.query_params.get("subtitle") or template.short_description
        c_cta = request.query_params.get("ctaText") or "Get Started"
        
        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{b_name}} - Live Preview</title>
  <style>
    :root {{
      --primary: {{custom_color}};
      --primary-rgb: {{primary_rgb}};
      --bg: #0f172a;
      --card: rgba(30, 41, 59, 0.7);
      --border: rgba(255, 255, 255, 0.1);
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, sans-serif;
    }}
    
    body {{
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }}
    
    .bg-grid {{
      position: fixed;
      inset: 0;
      z-index: -1;
      background-image: radial-gradient(circle at 50% 50%, rgba(var(--primary-rgb), 0.15) 0%, transparent 60%),
                        linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 100% 100%, 24px 24px, 24px 24px;
      pointer-events: none;
    }}
    
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1.5rem 2rem;
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(12px);
      background: rgba(15, 23, 42, 0.6);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    
    .logo {{
      font-size: 1.25rem;
      font-weight: 800;
      background: linear-gradient(135deg, #ffffff 0%, var(--primary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    
    nav {{
      display: flex;
      gap: 1.5rem;
    }}
    
    nav a {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      transition: color 0.2s;
    }}
    
    nav a:hover, nav a.active {{
      color: var(--text);
    }}
    
    .nav-btn {{
      background: var(--primary);
      color: #fff;
      padding: 0.5rem 1rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      text-decoration: none;
      transition: opacity 0.2s;
    }}
    
    .nav-btn:hover {{
      opacity: 0.9;
    }}
    
    .hero {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      text-align: center;
      padding: 6rem 2rem;
      max-w: 800px;
      margin: 0 auto;
      position: relative;
    }}
    
    .category-badge {{
      background: rgba(var(--primary-rgb), 0.15);
      border: 1px solid rgba(var(--primary-rgb), 0.3);
      color: var(--primary);
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 1.5rem;
    }}
    
    h1 {{
      font-size: 3rem;
      font-weight: 850;
      line-height: 1.15;
      margin-bottom: 1.5rem;
      letter-spacing: -0.03em;
    }}
    
    .desc {{
      color: var(--text-muted);
      font-size: 1.125rem;
      line-height: 1.6;
      margin-bottom: 2rem;
    }}
    
    .cta-group {{
      display: flex;
      gap: 1rem;
    }}
    
    .btn {{
      padding: 0.75rem 1.75rem;
      border-radius: 0.75rem;
      font-size: 0.875rem;
      font-weight: 700;
      text-decoration: none;
      transition: all 0.2s;
    }}
    
    .btn-primary {{
      background: var(--primary);
      color: #fff;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(var(--primary-rgb), 0.5);
    }}
    
    .btn-secondary {{
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }}
    
    .btn-secondary:hover {{
      background: rgba(255,255,255,0.05);
      transform: translateY(-2px);
    }}
    
    .features {{
      padding: 4rem 2rem;
      background: rgba(30, 41, 59, 0.3);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      width: 100%;
    }}
    
    .section-title {{
      text-align: center;
      font-size: 1.75rem;
      font-weight: 800;
      margin-bottom: 3rem;
    }}
    
    .features-grid {{
      max-w: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 2rem;
    }}
    
    .feature-card {{
      background: var(--card);
      border: 1px solid var(--border);
      padding: 2rem;
      border-radius: 1rem;
      transition: transform 0.2s;
    }}
    
    .feature-card:hover {{
      transform: translateY(-4px);
    }}
    
    .feature-icon {{
      width: 2.5rem;
      height: 2.5rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 0.5rem;
      font-size: 1.25rem;
      font-weight: bold;
      margin-bottom: 1.25rem;
    }}
    
    .feature-card h3 {{
      font-size: 1.125rem;
      font-weight: 700;
      margin-bottom: 0.75rem;
    }}
    
    .feature-card p {{
      color: var(--text-muted);
      font-size: 0.875rem;
      line-height: 1.5;
    }}
    
    footer {{
      padding: 3rem 2rem 6rem 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.875rem;
      border-top: 1px solid var(--border);
      width: 100%;
    }}
  </style>
</head>
<body>
  <div class="bg-grid"></div>
  
  <header>
    <div class="logo">
      <span>✦</span>
      <span>{{b_name}}</span>
    </div>
    <nav>
      <a href="#" class="active">Home</a>
      <a href="#">Services</a>
      <a href="#">About</a>
      <a href="#">Contact</a>
    </nav>
    <a href="#" class="nav-btn">Get Started</a>
  </header>
  
  <main class="hero">
    <div class="category-badge">{{(template.framework or 'HTML').upper()}} Template</div>
    <h1>{{c_title}}</h1>
    <p class="desc">{{c_sub}}</p>
    <div class="cta-group">
      <a href="#" class="btn btn-primary">{{c_cta}}</a>
      <a href="#" class="btn btn-secondary">Learn More</a>
    </div>
  </main>
  
  <section class="features">
    <h2 class="section-title">Key Advantages</h2>
    <div class="features-grid">
      <div class="feature-card">
        <div class="feature-icon">⚡</div>
        <h3>High Performance</h3>
        <p>Pre-compiled assets configured to deliver optimized core web vitals and fast loading times.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">🛡️</div>
        <h3>Clean Design</h3>
        <p>Premium modern aesthetics utilizing curated typography, spacing systems, and components.</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📱</div>
        <h3>Fully Responsive</h3>
        <p>Adapts fluidly across mobile phones, tablets, laptops, and wide screen monitors.</p>
      </div>
    </div>
  </section>
  
  <footer>
    <p>&copy; 2026 {{b_name}}. Powered by AI Site Studio.</p>
  </footer>
  {{watermark_payload}}
</body>
</html>"""
        return Response(content=fallback_html.encode("utf-8"), media_type="text/html")
    try:
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
                        is_source = not any(d in target_path.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", "out", ".output"])
                        if (target_path.endswith(".jsx") or target_path.endswith(".js") or target_path.endswith(".tsx") or target_path.endswith(".ts")) and is_source:
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
            
            # If the template is a DRAFT, we force recompilation to reflect the user's edits
            from app.models.template import TemplateStatus
            if template.status == TemplateStatus.DRAFT:
                for d in build_folders:
                    candidate = os.path.join(project_root, d)
                    if os.path.isdir(candidate):
                        import shutil
                        shutil.rmtree(candidate, ignore_errors=True)
                        print(f"Force deleted build folder {d} for DRAFT template {template_id} to trigger recompilation.")
            
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
    
                        # Vite config base path adjustment to enable relative assets inside subfolders
                        vite_cfg_js = os.path.join(project_root, "vite.config.js")
                        vite_cfg_ts = os.path.join(project_root, "vite.config.ts")
                        cfg_file = vite_cfg_js if os.path.exists(vite_cfg_js) else (vite_cfg_ts if os.path.exists(vite_cfg_ts) else None)
                        if cfg_file:
                            try:
                                with open(cfg_file, "r", encoding="utf-8", errors="ignore") as f:
                                    cfg_content = f.read()
                                if "base:" not in cfg_content and "base :" not in cfg_content:
                                    if "defineConfig({" in cfg_content:
                                        cfg_content = cfg_content.replace("defineConfig({", "defineConfig({\n  base: './',", 1)
                                    elif "export default {" in cfg_content:
                                        cfg_content = cfg_content.replace("export default {", "export default {\n  base: './',", 1)
                                    with open(cfg_file, "w", encoding="utf-8") as f:
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
    
        # Intercept and forward API calls to the template's embedded sub-app
        if filepath and (filepath.startswith("api/") or filepath == "api"):
            backend_dir = os.path.join(project_root, "backend")
            main_py = os.path.join(backend_dir, "main.py")
            if os.path.exists(main_py):
                import sys
                import importlib.util
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                try:
                    spec = importlib.util.spec_from_file_location("template_backend", main_py)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    sub_app = module.app
                    
                    scope = dict(request.scope)
                    scope["path"] = "/" + filepath
                    scope["raw_path"] = ("/" + filepath).encode("ascii")
                    
                    response_body = bytearray()
                    response_status = 200
                    response_headers = []
                    
                    async def send(message):
                        nonlocal response_status, response_headers
                        if message["type"] == "http.response.start":
                            response_status = message["status"]
                            response_headers = message["headers"]
                        elif message["type"] == "http.response.body":
                            response_body.extend(message.get("body", b""))
                            
                    await sub_app(scope, request.receive, send)
                    
                    headers_dict = {}
                    for k, v in response_headers:
                        headers_dict[k.decode("ascii")] = v.decode("ascii")
                        
                    return Response(content=bytes(response_body), status_code=response_status, headers=headers_dict)
                except Exception as e:
                    print(f"Failed to route sub-app request for {template_id}: {e}")

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
                
                # 1. Rewrite absolute references to relative on all HTML preview pages
                import re
                html_content = re.sub(r'src="/(?![/])', 'src="./', html_content)
                html_content = re.sub(r'href="/(?![/])', 'href="./', html_content)
    
                # 1a. Ensure viewport meta tag exists for proper mobile/tablet responsiveness in iframe
                if "<meta name=\"viewport\"" not in html_content.lower() and "<meta name='viewport'" not in html_content.lower():
                    viewport_meta = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                    if "<head>" in html_content:
                        html_content = html_content.replace("<head>", f"<head>\n  {viewport_meta}", 1)
                    elif "<html>" in html_content:
                        html_content = html_content.replace("<html>", f"<html>\n  <head>{viewport_meta}</head>", 1)
                    else:
                        html_content = f"<head>{viewport_meta}</head>\n" + html_content
    
                # 1b. Inject dynamic query parameter customizations into HTML for live preview customization
                customized = request.query_params.get("customized") == "true"
                if customized:
                    business_name = request.query_params.get("businessName")
                    primary_color = request.query_params.get("primaryColor")
                    custom_title = request.query_params.get("title")
                    custom_subtitle = request.query_params.get("subtitle")
                    custom_cta = request.query_params.get("ctaText")
                    logo_text = request.query_params.get("logoText")
    
                    # Override primary theme colors in CSS variables dynamically
                    if primary_color:
                        color_override_style = f"""
                        <style>
                          :root {{
                            --primary: {primary_color} !important;
                            --primary-color: {primary_color} !important;
                            --theme-color: {primary_color} !important;
                            --accent: {primary_color} !important;
                            --accent-color: {primary_color} !important;
                            --cta-bg: {primary_color} !important;
                          }}
                          a, button, .btn-primary, .bg-primary {{
                            background-color: {primary_color} !important;
                            border-color: {primary_color} !important;
                          }}
                          .text-primary, a:hover {{
                            color: {primary_color} !important;
                          }}
                        </style>
                        """
                        if "</head>" in html_content:
                            html_content = html_content.replace("</head>", f"{color_override_style}\n</head>", 1)
    
                    # Simple text/copy replacements
                    if business_name:
                        html_content = re.sub(r'<title>.*?</title>', f'<title>{business_name} - Preview</title>', html_content, flags=re.IGNORECASE)
                    if custom_title and template.title:
                        html_content = html_content.replace(template.title, custom_title)
                
                from app.models.template import TemplateFramework
                should_rewrite_history = "true" if template.framework != TemplateFramework.HTML else "false"
                
                # 2. Inject client-side routing and location sandboxing script (including absolute <base> tag)
                sandbox_script = f"""<base href="/api/v1/preview/live/{template_id}/" />
    <script>
      (function() {{
        const basePrefix = "/api/v1/preview/live/{template_id}";
        
        // Intercept fetch calls to rewrite root-relative API calls
        const originalFetch = window.fetch;
        window.fetch = function(input, init) {{
          let url = typeof input === 'string' ? input : (input instanceof Request ? input.url : '');
          if (url.startsWith('/api/')) {{
            url = basePrefix + url;
            if (input instanceof Request) {{
              input = new Request(url, input);
            }} else {{
              input = url;
            }}
          }}
          return originalFetch(input, init);
        }};

        // Intercept XMLHttpRequest
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url, ...args) {{
          if (typeof url === 'string' && url.startsWith('/api/')) {{
            url = basePrefix + url;
          }}
          return originalOpen.apply(this, [method, url, ...args]);
        }};

        // 1. Instantly rewrite history state to relative path so client-side routers match the root route
        try {{
          if ({should_rewrite_history} && window.location.pathname.startsWith(basePrefix)) {{
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
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>AI SITE STUDIO PREVIEW</text></svg>") !important;
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
    except Exception as e:
        return await serve_fallback(str(e))


class ManualEditRequest(BaseModel):
    business_name: str
    about: str
    primary_color: str
    secondary_color: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    page_edits: Optional[dict] = None


class AIEditRequest(BaseModel):
    prompt: str


