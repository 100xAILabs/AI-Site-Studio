"""
Preview routes — create preview sessions and serve watermarked previews.
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
            page_name_clean = page_name.replace(".html", "").replace(".jsx", "").replace(".js", "").replace(".tsx", "").replace(".ts", "")
            page_edits_str += f"- For page/file '{page_name}' (If the template is a single-page template/only has index.html, map these changes to the corresponding section like #{page_name_clean} or the '{page_name_clean}' area inside index.html):\n"
            if edits.get("title"):
                page_edits_str += f"  * Set main title/header/headline to: \"{edits['title']}\"\n"
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
5. If the template is a single-page template (index.html), apply all page/section overrides to the corresponding sections inside index.html.

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


class FindReplaceRequest(BaseModel):
    find_text: str
    replace_text: str


@router.post("/live/{template_id}/find-replace")
async def edit_live_preview_find_replace(
    template_id: uuid.UUID,
    request: FindReplaceRequest,
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
    
    # 1. Read files and do find-and-replace
    updated_filenames = set()
    new_zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z_in:
        with zipfile.ZipFile(new_zip_buffer, "w", zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                content = z_in.read(item.filename)
                is_build = any(d in item.filename.replace("\\", "/").split("/") for d in ["dist", "build", "out", "node_modules", ".output"])
                is_text = (item.filename.endswith(".html") or 
                           item.filename.endswith(".jsx") or 
                           item.filename.endswith(".js") or 
                           item.filename.endswith(".css") or 
                           item.filename.endswith(".tsx") or 
                           item.filename.endswith(".ts") or
                           item.filename.endswith(".json")) and not is_build
                           
                if is_text:
                    try:
                        text_content = content.decode("utf-8", errors="ignore")
                        if request.find_text in text_content:
                            text_content = text_content.replace(request.find_text, request.replace_text)
                            content = text_content.encode("utf-8")
                            updated_filenames.add(item.filename)
                            print(f"Replaced text in: {item.filename}")
                    except Exception:
                        pass
                z_out.writestr(item, content)
                
    if not updated_filenames:
        return {"status": "success", "template_id": str(template_id), "matches_found": 0}
        
    new_zip_bytes = new_zip_buffer.getvalue()
    
    # 2. Save the updated ZIP back to the database
    stored_file.data = new_zip_bytes
    stored_file.size = len(new_zip_bytes)
    db.add(stored_file)
    await db.flush()
    
    # 3. Clear local preview directory cache
    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    shutil.rmtree(preview_dir, ignore_errors=True)
    
    # Commit session changes
    await db.commit()
    
    return {"status": "success", "template_id": str(template_id), "matches_found": len(updated_filenames)}


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
        
    target_slug = template.slug if (template and template.slug) else str(template_id)
    purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

    watermark_payload = """
<!-- Injected Watermark Grid Overlay -->
<div class="preview-watermark-grid"></div>

<!-- Injected Purchase Footer Banner -->
<div class="preview-purchase-footer-banner">
  <span>🔒 Watermarked Draft Preview. Purchase this template to download clean project assets.</span>
  <a href="__PURCHASE_URL__" target="_top">Purchase Template &rarr;</a>
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
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
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
""".replace("__PURCHASE_URL__", purchase_url)
    async def serve_fallback(err_msg: str = "Preview compilation"):
        if filepath and not (filepath.endswith(".html") or filepath.endswith(".htm")):
            if filepath.endswith(".css"):
                return Response(content=b"", media_type="text/css")
            if filepath.endswith(".js"):
                return Response(content=b"", media_type="application/javascript")
            return Response(content=b"", media_type="application/octet-stream")

        # 1. First attempt: In-Browser Standalone React/Babel Runner for App.jsx
        app_jsx_content = None
        index_css_content = ""
        preview_dir_loc = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
        
        if os.path.isdir(preview_dir_loc):
            for root, _, files in os.walk(preview_dir_loc):
                if any(d in root.replace("\\", "/").split("/") for d in ["dist", "build", ".output"]):
                    continue
                if "App.jsx" in files:
                    try:
                        with open(os.path.join(root, "App.jsx"), "r", encoding="utf-8", errors="ignore") as f:
                            app_jsx_content = f.read()
                    except Exception:
                        pass
                if "index.css" in files:
                    try:
                        with open(os.path.join(root, "index.css"), "r", encoding="utf-8", errors="ignore") as f:
                            index_css_content = f.read()
                    except Exception:
                        pass

        if app_jsx_content:
            try:
                # Clean imports/exports for in-browser standalone execution
                cleaned_jsx = app_jsx_content
                cleaned_jsx = re.sub(r'import\s+.*?from\s+[\'"].*?[\'"];?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'import\s+[\'"].*?[\'"];?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'export\s+default\s+[A-Za-z0-9_]+\s*;?', '', cleaned_jsx)
                cleaned_jsx = re.sub(r'export\s+', '', cleaned_jsx)

                comp_name = "App"
                if "function App" not in cleaned_jsx and "const App" not in cleaned_jsx and "let App" not in cleaned_jsx:
                    func_m = re.search(r'function\s+([A-Za-z0-9_]+)', cleaned_jsx)
                    if func_m:
                        comp_name = func_m.group(1)

                react_runner_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{template.title} - Live Preview</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone@7.24.0/babel.min.js"></script>
  <script src="https://unpkg.com/lucide-react@0.344.0/dist/umd/lucide-react.js"></script>
  <style>
    body {{ margin: 0; background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }}
    {index_css_content}
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    const LucideIcons = window.lucide || window.LucideReact || {{}};
    const {{ 
      Sparkles = () => null, ArrowLeft = () => null, ArrowRight = () => null, 
      Loader2 = () => null, CheckCircle2 = () => null, CheckCircle = () => null, 
      Cpu = () => null, Globe = () => null, Layers = () => null, FileText = () => null, 
      Plus = () => null, Trash2 = () => null, Info = () => null, Building2 = () => null, 
      Palette = () => null, Phone = () => null, Mail = () => null, MapPin = () => null, 
      Share2 = () => null, Wand2 = () => null, Edit3 = () => null, Check = () => null, 
      RefreshCw = () => null, Eye = () => null, Upload = () => null, ShoppingBag = () => null, 
      ShoppingCart = () => null, Folder = () => null, ExternalLink = () => null, 
      Sliders = () => null, Bot = () => null, User = () => null, Zap = () => null, 
      Heart = () => null, Star = () => null, Code = () => null, Play = () => null, 
      AlertCircle = () => null, Shield = () => null, Award = () => null,
      TrendingUp = () => null, DollarSign = () => null, Database = () => null, 
      Server = () => null, Terminal = () => null, Lock = () => null, Key = () => null
    }} = LucideIcons;

    const useState = React.useState;
    const useEffect = React.useEffect;
    const useRef = React.useRef;
    const useMemo = React.useMemo;
    const useCallback = React.useCallback;

    {cleaned_jsx}

    try {{
      const container = document.getElementById('root');
      const root = ReactDOM.createRoot(container);
      root.render(React.createElement({comp_name}));
    }} catch (e) {{
      console.error("Mount error:", e);
      document.getElementById('root').innerHTML = '<div style="padding:2rem;color:#f87171;">Runtime Preview Error: ' + e.message + '</div>';
    }}
  </script>
</body>
</html>"""
                return Response(content=react_runner_html.encode("utf-8"), media_type="text/html")
            except Exception as e_runner:
                logger.warning(f"In-browser React runner fallback failed: {e_runner}")

        # 2. Visual rich landing page fallback

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
        import urllib.parse
        img_prompt = urllib.parse.quote(f"premium beautiful modern {c_title} website visual showcase photo")
        hero_bg_url = f"https://image.pollinations.ai/prompt/{img_prompt}?width=1200&height=800&nologo=true&seed=42"
        gallery_1 = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(c_title + ' product feature visual showcase')}?width=600&height=400&nologo=true&seed=1"
        gallery_2 = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(c_title + ' interior aesthetic atmosphere')}?width=600&height=400&nologo=true&seed=2"
        gallery_3 = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(c_title + ' artisanal craftsmanship experience')}?width=600&height=400&nologo=true&seed=3"
        
        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{b_name} - Live Preview</title>
  <style>
    :root {{
      --primary: {custom_color};
      --primary-rgb: {primary_rgb};
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
      background: rgba(15, 23, 42, 0.75);
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
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(var(--primary-rgb), 0.4);
    }}
    
    .nav-btn:hover {{
      opacity: 0.9;
    }}
    
    .hero-container {{
      position: relative;
      padding: 5rem 2rem;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3rem;
      align-items: center;
      max-width: 1200px;
      margin: 0 auto;
    }}

    .hero-image-wrapper {{
      position: relative;
      border-radius: 1.5rem;
      overflow: hidden;
      border: 1px solid var(--border);
      box-shadow: 0 20px 40px -15px rgba(0,0,0,0.5);
    }}

    .hero-image-wrapper img {{
      width: 100%;
      height: 380px;
      object-fit: cover;
      display: block;
      transition: transform 0.5s ease;
    }}

    .hero-image-wrapper:hover img {{
      transform: scale(1.05);
    }}
    
    .category-badge {{
      display: inline-block;
      padding: 0.25rem 0.75rem;
      background: rgba(var(--primary-rgb), 0.15);
      color: var(--primary);
      border: 1px solid rgba(var(--primary-rgb), 0.3);
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
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 2rem;
    }}
    
    .feature-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      overflow: hidden;
      transition: transform 0.3s ease, border-color 0.3s ease;
    }}
    
    .feature-card:hover {{
      transform: translateY(-6px);
      border-color: rgba(var(--primary-rgb), 0.5);
    }}

    .feature-card img {{
      width: 100%;
      height: 180px;
      object-fit: cover;
      display: block;
    }}

    .feature-card-content {{
      padding: 1.5rem;
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
      margin-bottom: 1rem;
    }}
    
    .feature-card h3 {{
      font-size: 1.125rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
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
      <span>{b_name}</span>
    </div>
    <nav>
      <a href="#" class="active">Home</a>
      <a href="#">Products & Services</a>
      <a href="#">About Us</a>
      <a href="#">Contact</a>
    </nav>
    <a href="#" class="nav-btn">Get Started</a>
  </header>
  
  <main class="hero-container">
    <div>
      <div class="category-badge">{(template.framework or 'HTML').upper()} Template</div>
      <h1>{c_title}</h1>
      <p class="desc">{c_sub}</p>
      <div class="cta-group">
        <a href="#" class="btn btn-primary">{c_cta}</a>
        <a href="#" class="btn btn-secondary">Explore Gallery</a>
      </div>
    </div>
    <div class="hero-image-wrapper">
      <img src="{hero_bg_url}" alt="Website Hero Visual" />
    </div>
  </main>
  
  <section class="features">
    <h2 class="section-title">Visual Showcase & Signature Features</h2>
    <div class="features-grid">
      <div class="feature-card">
        <img src="{gallery_1}" alt="Feature 1 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">✨</div>
          <h3>Crafted Experience</h3>
          <p>Curated visual layouts designed to elevate your brand presence and engage customers.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_2}" alt="Feature 2 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">⚡</div>
          <h3>Atmospheric Design</h3>
          <p>Modern aesthetics utilizing premium colors, glowing gradients, and responsive grids.</p>
        </div>
      </div>
      <div class="feature-card">
        <img src="{gallery_3}" alt="Feature 3 Showcase" />
        <div class="feature-card-content">
          <div class="feature-icon">🛡️</div>
          <h3>Artisanal Quality</h3>
          <p>Built with attention to detail across typography, spacing systems, and interactive cards.</p>
        </div>
      </div>
    </div>
  </section>
  
  <footer>
    <p>&copy; 2026 {b_name}. Powered by Site Studio.</p>
  </footer>
  {watermark_payload}
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

        import json
        import shutil
        from app.models.template import TemplateStatus

        def detect_project_ui_package_json(base_dir: str) -> Optional[str]:
            # Priority 1: Check standard UI locations
            for cand in [
                os.path.join(base_dir, "frontend", "package.json"),
                os.path.join(base_dir, "package.json"),
                os.path.join(base_dir, "client", "package.json"),
                os.path.join(base_dir, "web", "package.json"),
                os.path.join(base_dir, "ui", "package.json"),
            ]:
                if os.path.isfile(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            
            # Priority 2: Walk only safe non-vendor directories (NEVER descend into node_modules/backend/dist)
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", ".output", "vendor", "backend", ".venv", "env"]]
                if "package.json" in files:
                    cand = os.path.join(root, "package.json")
                    try:
                        with open(cand, "r", encoding="utf-8") as f:
                            p_data = json.load(f)
                            if "scripts" in p_data and ("build" in p_data["scripts"] or "dev" in p_data["scripts"]):
                                return cand
                    except Exception:
                        pass
            return None

        lock = _build_locks.setdefault(template_id, asyncio.Lock())
        async with lock:
            # 1. Detect package.json or check if source files exist
            package_json_path = detect_project_ui_package_json(preview_dir)

            # If directory is empty or source files / package.json missing, extract fresh from ZIP
            need_extract = not os.path.exists(preview_dir) or not os.listdir(preview_dir)
            if not need_extract and not package_json_path:
                has_html = any(f.endswith(".html") for r, d, files in os.walk(preview_dir) for f in files)
                if not has_html:
                    need_extract = True

            if need_extract:
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

                # Re-detect package.json after extraction
                package_json_path = detect_project_ui_package_json(preview_dir)

            build_folders = ["dist", "out", "build", ".output"]
            serve_root = preview_dir
            build_dir = None

            if package_json_path:
                project_root = os.path.dirname(package_json_path)

                # Check if project is already compiled
                for d in build_folders:
                    candidate = os.path.join(project_root, d)
                    if os.path.isdir(candidate):
                        for b_root, b_dirs, b_files in os.walk(candidate):
                            if "index.html" in b_files:
                                build_dir = b_root
                                break
                        if build_dir:
                            break

                # If not compiled, trigger compilation
                if not build_dir:
                    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                    loop = asyncio.get_running_loop()

                    # 1. Verify that node_modules and Vite/framework binaries are present and functional
                    node_modules_dir = os.path.join(project_root, "node_modules")
                    vite_bin = os.path.join(node_modules_dir, "vite", "dist", "node", "cli.js")
                    vite_pkg = os.path.join(node_modules_dir, "vite", "package.json")
                    next_pkg = os.path.join(node_modules_dir, "next", "package.json")
                    is_modules_ready = (os.path.isfile(vite_bin) or os.path.isfile(vite_pkg) or os.path.isfile(next_pkg))

                    if not is_modules_ready:
                        logger.info(f"[Preview Runner] Clean node_modules install required for {template_id}...")
                        shutil.rmtree(node_modules_dir, ignore_errors=True)
                        try:
                            os.remove(os.path.join(project_root, "package-lock.json"))
                        except OSError:
                            pass
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

                    # Pre-build self-healing: sanitize all JSX/TSX/JS/HTML files in project to fix truncated code or syntax errors
                    try:
                        from app.services.ai_service import repair_truncated_jsx, repair_truncated_html
                        for s_root, _, s_files in os.walk(project_root):
                            if any(d in s_root.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", "out", ".output"]):
                                continue
                            for s_fname in s_files:
                                s_path = os.path.join(s_root, s_fname)
                                if s_fname.endswith(".jsx") or s_fname.endswith(".tsx") or s_fname.endswith(".js") or s_fname.endswith(".ts"):
                                    try:
                                        with open(s_path, "r", encoding="utf-8", errors="ignore") as sf:
                                            raw_c = sf.read()
                                        repaired_c = repair_truncated_jsx(raw_c)
                                        if repaired_c and repaired_c != raw_c:
                                            with open(s_path, "w", encoding="utf-8") as sf:
                                                sf.write(repaired_c)
                                    except Exception as e_heal:
                                        print(f"[Pre-Build Heal] Could not heal {s_fname}: {e_heal}")
                                elif s_fname.endswith(".html"):
                                    try:
                                        with open(s_path, "r", encoding="utf-8", errors="ignore") as sf:
                                            raw_c = sf.read()
                                        h_c = raw_c
                                        if "</html>" in h_c:
                                            h_c = h_c.split("</html>")[0] + "</html>\n"
                                        if "/src/main.tsx" in h_c and not os.path.exists(os.path.join(project_root, "src", "main.tsx")) and os.path.exists(os.path.join(project_root, "src", "main.jsx")):
                                            h_c = h_c.replace("/src/main.tsx", "/src/main.jsx")
                                        elif "/src/main.jsx" in h_c and not os.path.exists(os.path.join(project_root, "src", "main.jsx")) and os.path.exists(os.path.join(project_root, "src", "main.tsx")):
                                            h_c = h_c.replace("/src/main.jsx", "/src/main.tsx")
                                        repaired_c = repair_truncated_html(h_c)
                                        if repaired_c and repaired_c != raw_c:
                                            with open(s_path, "w", encoding="utf-8") as sf:
                                                sf.write(repaired_c)
                                    except Exception as e_heal:
                                        print(f"[Pre-Build Heal] Could not heal {s_fname}: {e_heal}")
                    except Exception as e_pre_heal:
                        print(f"[Pre-Build Heal Pass Failed]: {e_pre_heal}")

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
                        error_out = (build_res.stderr or build_res.stdout or b"").decode('utf-8', errors='ignore')
                        print(f"npm run build failed for {template_id}: {error_out}")

                        # 🤖 Trigger Autonomous AI Debugger Agent to inspect and repair syntax/compile errors
                        try:
                            from app.services.debugger_service import ai_debugger
                            print(f"[Autonomous AI Debugger] Activating compiler repair agent for template {template_id}...")
                            is_fixed, fix_log, repaired_map = await ai_debugger.debug_project_build(
                                project_root=project_root,
                                build_cmd=build_cmd,
                                initial_error_log=error_out,
                                max_attempts=3
                            )
                            if is_fixed:
                                print(f"[Autonomous AI Debugger] Successfully resolved build errors for {template_id}!")
                                # Also persist repaired files back into the template stored ZIP in database
                                if repaired_map and file_id and not is_external:
                                    try:
                                        from app.models import StoredFile
                                        sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
                                        stored_rec = sf_res.scalar_one_or_none()
                                        if stored_rec and stored_rec.data:
                                            in_mem_zip = io.BytesIO()
                                            with zipfile.ZipFile(io.BytesIO(stored_rec.data), 'r') as zin:
                                                with zipfile.ZipFile(in_mem_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
                                                    for item in zin.infolist():
                                                        item_content = zin.read(item.filename)
                                                        # Check if this file was repaired
                                                        norm_name = os.path.normpath(item.filename).replace("\\", "/")
                                                        for rep_rel, rep_content in repaired_map.items():
                                                            norm_rep = os.path.normpath(rep_rel).replace("\\", "/")
                                                            if norm_name.endswith(norm_rep) or norm_rep.endswith(norm_name):
                                                                item_content = rep_content.encode("utf-8")
                                                                break
                                                        zout.writestr(item, item_content)
                                            stored_rec.data = in_mem_zip.getvalue()
                                            await db.commit()
                                            print(f"[Autonomous AI Debugger] Updated stored ZIP with repaired files in database for {template_id}")
                                    except Exception as e_zip_up:
                                        print(f"[Autonomous AI Debugger] Could not update stored ZIP: {e_zip_up}")
                        except Exception as e_ai_debug:
                            print(f"[Autonomous AI Debugger] Automated repair pass encountered an error: {e_ai_debug}")

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
            elif package_json_path:
                return await serve_fallback("Preview compilation fallback")
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
    
        // 2. Intercept click events on links to keep them inside the live preview sandbox
        document.addEventListener('click', function(e) {{
          const link = e.target.closest('a');
          if (link) {{
            const rawHref = link.getAttribute('href');
            if (!rawHref) return;
            if (rawHref.includes('/marketplace') || link.closest('.preview-purchase-footer-banner')) {{
              e.preventDefault();
              window.top.location.href = "{settings.FRONTEND_URL}/marketplace/{template.slug if template and template.slug else template_id}";
              return;
            }}
            if (rawHref.startsWith('#')) {{
              e.preventDefault();
              window.location.hash = rawHref;
              return;
            }}
            if (rawHref.startsWith('javascript:')) {{
              return;
            }}
            // Ensure relative page links (e.g. "about.html", "contact.html", "./menu.html") remain inside the sandbox route
            if (link.href) {{
              try {{
                const url = new URL(link.href, window.location.href);
                if (url.origin === window.location.origin) {{
                  let path = url.pathname;
                  if (!path.startsWith(basePrefix)) {{
                    if (path.startsWith('/')) {{
                      path = path.slice(1);
                    }}
                    link.href = window.location.origin + basePrefix + '/' + path + url.search + url.hash;
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
                target_slug = template.slug if (template and template.slug) else str(template_id)
                purchase_url = f"{settings.FRONTEND_URL}/marketplace/{target_slug}?buy=1"

                watermark_payload = """
    <!-- Injected Watermark Grid Overlay -->
    <div class="preview-watermark-grid"></div>
    
    <!-- Injected Purchase Footer Banner -->
    <div class="preview-purchase-footer-banner">
      <span>🔒 Watermarked Draft Preview. Purchase this template to download clean project assets.</span>
      <a href="__PURCHASE_URL__" target="_top">Purchase Template &rarr;</a>
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
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'><text x='20' y='150' fill='rgba(128, 128, 128, 0.16)' font-size='13' font-weight='800' font-family='sans-serif' transform='rotate(-30 20 150)'>SITE STUDIO PREVIEW</text></svg>") !important;
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
    """.replace("__PURCHASE_URL__", purchase_url)
                if "</body>" in html_content:
                    html_content = html_content.replace("</body>", f"{watermark_payload}\n</body>", 1)
                else:
                    html_content = html_content + "\n" + watermark_payload

                # Ensure all /marketplace links point to the React frontend application
                html_content = html_content.replace('href="/marketplace"', f'href="{purchase_url}"')
                html_content = html_content.replace("href='/marketplace'", f"href='{purchase_url}'")
    
                content = html_content.encode("utf-8")
            except Exception:
                pass
        from app.services.security_scanner import security_scanner
        return Response(content=content, media_type=mime_type, headers=security_scanner.get_secure_preview_headers())
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


@router.post("/live/{template_id}/ai-debug")
async def ai_debug_template_code(
    template_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand AI Debugger endpoint:
    Scans the template codebase, detects any broken JSX/TSX/HTML or syntax defects,
    invokes Gemini AI Debugger to fix them, rebuilds the project, and persists the fixes.
    """
    import shutil
    import tempfile
    import zipfile
    import io
    from sqlalchemy import select
    from app.services.debugger_service import ai_debugger
    from app.models.template import Template
    from app.models.stored_file import StoredFile

    preview_dir = os.path.join(tempfile.gettempdir(), "ai_site_studio", "live_previews", str(template_id))
    
    # 1. Fetch template from DB
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Template does not have source ZIP archive")

    file_id_str = zip_url.split("/")[-1]
    stored_file = None
    try:
        file_id = uuid.UUID(file_id_str)
        sf_res = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
        stored_file = sf_res.scalar_one_or_none()
    except Exception:
        pass

    if not stored_file or not stored_file.data:
        raise HTTPException(status_code=404, detail="Source archive data not found")

    # 2. Extract to preview_dir
    os.makedirs(preview_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as z:
        z.extractall(preview_dir)

    # 3. Locate package.json and scan all source files
    fixed_files_count = 0
    repaired_map = {}

    for root, _, files in os.walk(preview_dir):
        if any(d in root.replace("\\", "/").split("/") for d in ["dist", "node_modules", "build", ".output"]):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".jsx", ".tsx", ".js", ".ts", ".html"]:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()

                    # Sanitize heuristics first
                    healed = ai_debugger.sanitize_code_heuristics(code, ext)
                    
                    # If suspect syntax or defects detected, invoke Gemini AI Debugger
                    if ");</" in code or ";</" in code or "export default" not in code or code.count("{") != code.count("}") or code.count("<div") != code.count("</div"):
                        rel_path = os.path.relpath(fpath, preview_dir)
                        healed = await ai_debugger.debug_code_with_ai(
                            code=code,
                            filename=rel_path,
                            error_message="Fix unbalanced tags, stray semicolons, missing brackets, and broken exports."
                        )

                    if healed and healed != code:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(healed)
                        rel_p = os.path.relpath(fpath, preview_dir)
                        repaired_map[rel_p] = healed
                        fixed_files_count += 1
                except Exception as e_file:
                    logger.warning(f"AI Debugger skipped {fname}: {e_file}")

    # 4. If files were fixed, re-package the ZIP and save to DB
    if repaired_map and stored_file:
        in_mem = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(stored_file.data), "r") as zin:
            with zipfile.ZipFile(in_mem, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    item_data = zin.read(item.filename)
                    norm_name = os.path.normpath(item.filename).replace("\\", "/")
                    for rep_rel, rep_content in repaired_map.items():
                        norm_rep = os.path.normpath(rep_rel).replace("\\", "/")
                        if norm_name.endswith(norm_rep) or norm_rep.endswith(norm_name):
                            item_data = rep_content.encode("utf-8")
                            break
                    zout.writestr(item, item_data)
        stored_file.data = in_mem.getvalue()
        await db.commit()

    # 5. Clear compiled dist/build directories in preview_dir to trigger fresh build
    for b_dir in ["dist", "out", "build", ".output"]:
        for root, dirs, _ in os.walk(preview_dir):
            if b_dir in dirs:
                shutil.rmtree(os.path.join(root, b_dir), ignore_errors=True)

    return {
        "status": "success",
        "message": f"AI Debugger analyzed project and successfully fixed {fixed_files_count} file(s).",
        "fixed_files": list(repaired_map.keys()),
        "fixed_count": fixed_files_count
    }


