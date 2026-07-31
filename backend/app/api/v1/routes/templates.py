"""
Templates routes — public browsing and admin CRUD.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user_optional, require_admin, require_seller_or_admin, get_current_user
from app.models.user import User
from app.services.template_service import TemplateService
from app.services.project_analyzer import project_analyzer
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateListResponse, TemplateFilterParams, TemplateCardResponse,
)
from app.models.template import TemplateFramework, TemplateLicense, TemplateStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.core.config import settings
from app.core.security import generate_file_signature
from decimal import Decimal
from datetime import datetime, timezone

router = APIRouter()


import httpx

class GitAnalyzeRequest(BaseModel):
    git_url: str
    token: Optional[str] = None


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    # Search
    q: Optional[str] = Query(None, description="Text search query"),
    # Category
    category: Optional[str] = Query(None, description="Category slug or name"),
    # Price
    min_price: Optional[Decimal] = Query(None, ge=0),
    max_price: Optional[Decimal] = Query(None, ge=0),
    # Rating
    rating: Optional[float] = Query(None, ge=1, le=5),
    # Boolean flags
    is_free: Optional[bool] = Query(None),
    is_on_sale: Optional[bool] = Query(None),
    has_dark_mode: Optional[bool] = Query(None),
    is_ai_ready: Optional[bool] = Query(None),
    is_featured: Optional[bool] = Query(None),
    # Taxonomy
    framework: Optional[TemplateFramework] = Query(None),
    industry: Optional[str] = Query(None),
    color_scheme: Optional[str] = Query(None),
    license_type: Optional[TemplateLicense] = Query(None),
    # Theme Forest specific filters
    sales: Optional[str] = Query(None, description="Sales count tier filter"),
    compatibility: Optional[str] = Query(None, description="Compatibility filter"),
    language: Optional[str] = Query(None, description="Programming language filter"),
    date_added: Optional[str] = Query(None, description="Date added range filter"),
    # Sorting & Pagination
    sort: str = Query("newest", description="Sort field"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    semantic: bool = Query(False, description="Use AI semantic search"),
    developer: Optional[str] = Query(None, description="Developer/seller name"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Browse marketplace templates with filtering, sorting, and pagination.
    All filter params are optional and combinable.
    """
    filters = TemplateFilterParams(
        q=q, category=category, min_price=min_price, max_price=max_price,
        rating=rating, is_free=is_free, is_on_sale=is_on_sale,
        has_dark_mode=has_dark_mode, is_ai_ready=is_ai_ready, is_featured=is_featured,
        framework=framework, industry=industry, color_scheme=color_scheme,
        license_type=license_type, sales=sales, compatibility=compatibility, language=language,
        date_added=date_added,
        sort=sort, page=page, page_size=page_size, semantic=semantic,
        developer=developer,
    )

    service = TemplateService(db)
    return await service.list_templates(filters, current_user)


@router.get("/featured", response_model=list[TemplateCardResponse])
async def get_featured_templates(
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Return featured templates for the landing page."""
    service = TemplateService(db)
    return await service.get_featured_templates(limit)


@router.get("/my-templates", response_model=list[TemplateResponse])
async def list_my_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all templates permanently linked to the current seller's account.
    Queries by seller_id FK — accurate regardless of name changes.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.template import Template
    from app.models.category import Category

    query = (
        select(Template)
        .options(selectinload(Template.category).selectinload(Category.children))
        .where(Template.seller_id == current_user.id)
        .order_by(Template.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/git-repos")
async def list_git_repos(
    username: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Fetch repository list for a GitHub user (using username or token, or stored user token).
    """
    auth_token = token
    if not auth_token and current_user.github_access_token:
        auth_token = current_user.github_access_token

    if not username and not auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either GitHub username, Personal Access Token, or connected GitHub account is required"
        )
    
    headers = {"Accept": "application/vnd.github+json"}
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"
        url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    else:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                detail = "Failed to fetch repositories from GitHub"
                try:
                    detail = response.json().get("message", detail)
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)
            
            repos = response.json()
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "clone_url": r.get("clone_url"),
                    "description": r.get("description"),
                    "private": r.get("private"),
                    "language": r.get("language"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "updated_at": r.get("updated_at"),
                }
                for r in repos if isinstance(r, dict)
            ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to GitHub: {str(e)}"
        )


@router.get("/{slug}", response_model=TemplateResponse)
async def get_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get full template details by slug."""
    service = TemplateService(db)
    return await service.get_template(slug, current_user)


@router.post("/analyze-zip")
async def analyze_project_zip(
    file: UploadFile = File(...),
    _user: User = Depends(require_seller_or_admin),
):
    """
    Upload a project ZIP file, extract it, analyze the code and assets,
    and generate visual/SEO/code suggestions and meta parameters via Gemini.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP archives are supported"
        )
    content = await file.read()
    return await project_analyzer.analyze_zip(content, file.filename)


@router.post("/analyze-git")
async def analyze_git_repo(
    request_data: GitAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """
    Provide a Git repository URL, clone it, package it into a clean ZIP,
    analyze the code and assets, save the clean ZIP to database storage,
    and return the analysis results along with the public file URL.
    """
    git_url = request_data.git_url.strip()
    token = request_data.token.strip() if request_data.token else None
    if not token and current_user.github_access_token:
        token = current_user.github_access_token

    if not git_url.startswith(("http://", "https://", "git@")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Git URL format. Must start with http://, https:// or git@"
        )

    # Inject personal access token into HTTPS URL for private repositories
    if token and git_url.startswith("https://github.com/"):
        git_url = git_url.replace("https://github.com/", f"https://{token}@github.com/")

    try:
        result = await project_analyzer.analyze_git_repo(git_url)
        zip_bytes = result.pop("_zip_bytes")
        filename = result.pop("_filename")

        from app.core.storage import storage
        stored_zip_url = await storage.upload_file(
            db=db,
            file_content=zip_bytes,
            folder="uploads",
            original_filename=filename,
            content_type="application/zip",
        )

        result["stored_zip_url"] = stored_zip_url
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import and analyze Git repository: {str(e)}"
        )


# ── Admin Endpoints ───────────────────────────────────────────────────────────

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """Create a new template and permanently link it to the uploading seller's account."""
    data.status = TemplateStatus.PUBLISHED
    service = TemplateService(db)
    return await service.create_template(data, seller_id=current_user.id)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """Update an existing template."""
    service = TemplateService(db)
    return await service.update_template(template_id, data, current_user)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_seller_or_admin),
):
    """Delete a template. Admins can delete any template; sellers can only delete their own."""
    service = TemplateService(db)
    await service.delete_template(template_id, current_user)


@router.post("/{template_id}/download")
async def download_template(
    template_id: uuid.UUID,
    format: Optional[str] = "zip",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate secure download URL for a purchased template.
    """
    from app.repositories.template_repo import TemplateRepository
    template_repo = TemplateRepository(db)
    template = await template_repo.get_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    is_owner = template.seller_id == current_user.id
    if not template.is_free and not is_owner:
        purchase = await db.execute(
            select(OrderItem.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == current_user.id,
                Order.status == OrderStatus.COMPLETED,
                OrderItem.template_id == template_id,
            )
            .limit(1)
        )
        if purchase.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Purchase required to download this template")

    await template_repo.increment_downloads(template_id)
    
    from app.models.download import Download
    download_log = Download(
        user_id=current_user.id,
        template_id=template_id,
    )
    db.add(download_log)
    await db.flush()
    await db.commit()
    
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip")
    if not zip_url:
        raise HTTPException(status_code=400, detail="Source zip file not configured for this template")
        
    # Stored files require a short-lived signature. External URLs retain their
    # provider-managed access controls.
    if zip_url.startswith(settings.STORAGE_BASE_URL.rstrip("/") + "/"):
        file_id = zip_url.rsplit("/", 1)[-1]
        expires = int(datetime.now(timezone.utc).timestamp()) + 3600
        signature = generate_file_signature(file_id, expires)
        zip_url = f"{zip_url}?expires={expires}&signature={signature}"

    return {"download_url": zip_url}


class TemplatePrepareRequest(BaseModel):
    prompt: str


class TemplateQuestion(BaseModel):
    id: str
    question: str
    options: list[str]


class TemplatePageItem(BaseModel):
    name: str
    filename: str


class TemplatePrepareResponse(BaseModel):
    questions: list[TemplateQuestion]
    suggested_pages: list[TemplatePageItem]


class TemplateGenerateRequest(BaseModel):
    prompt: str
    framework: str = "html"  # html | react
    answers: Optional[dict] = None
    pages: Optional[list[dict]] = None


@router.post("/generate/prepare", response_model=TemplatePrepareResponse)
async def prepare_template_generation(
    request: TemplatePrepareRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate tailored clarifying questions and pages structure matching the user's template prompt.
    """
    from app.services.ai_service import ai_service
    import json
    from app.services.ai_service import fix_truncated_json
    
    prompt = request.prompt.strip()
    
    prepare_prompt = f"""
    Analyze this website template request: "{prompt}".
    Generate a JSON response containing:
    1. A list of 3-4 specific clarifying questions to help customize the styling, colors, and layout (e.g. style tone, color scheme, special elements) with a few options.
    2. A list of suggested HTML pages (index.html is required, plus up to 4 other pages, e.g. about.html, features.html, contact.html, portal.html) appropriate for this template concept.
    
    You MUST return JSON matching this exact structure:
    {{
      "questions": [
        {{
          "id": "q1",
          "question": "What primary color scheme do you prefer?",
          "options": ["Dark Neon Blue", "Professional Crimson", "Modern Teal & White", "Vibrant Gold"]
        }}
      ],
      "suggested_pages": [
        {{"name": "Home Page", "filename": "index.html"}},
        {{"name": "About Us", "filename": "about.html"}}
      ]
    }}
    """
    
    try:
        raw_response = await ai_service._generate_content(prepare_prompt, response_mime_type="application/json", feature_name="website_content_generation")
        fixed_json = fix_truncated_json(raw_response)
        data = json.loads(fixed_json)
        # Ensure index.html is present
        if "suggested_pages" not in data or not data["suggested_pages"]:
            data["suggested_pages"] = [
                {"name": "Home Page", "filename": "index.html"},
                {"name": "About Details", "filename": "about.html"}
            ]
        elif not any(p.get("filename") == "index.html" for p in data["suggested_pages"]):
            data["suggested_pages"].insert(0, {"name": "Home Page", "filename": "index.html"})
        return data
    except Exception:
        return {
            "questions": [
                {
                    "id": "color_scheme",
                    "question": "Which color scheme matches your brand best?",
                    "options": ["Modern Slate & Teal", "Vibrant Electric Blue", "Sleek Dark Cyberpunk", "Warm Minimalist Coral"]
                },
                {
                    "id": "layout_style",
                    "question": "What layout style do you prefer?",
                    "options": ["Clean & Corporate", "Glassmorphic & Futuristic", "Playful & Vibrant", "Minimalist & Spaced"]
                }
            ],
            "suggested_pages": [
                {"name": "Home Page", "filename": "index.html"},
                {"name": "About Details", "filename": "about.html"},
                {"name": "Contact Page", "filename": "contact.html"}
            ]
        }


@router.post("/generate", response_model=TemplateResponse)
async def generate_template_by_prompt(
    request: TemplateGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a website template dynamically using Gemini and Pollinations AI images.
    """
    import urllib.parse
    import json
    import decimal
    import re
    import io
    import zipfile
    from app.repositories.category_repo import CategoryRepository
    from app.repositories.template_repo import TemplateRepository
    from app.services.search_service import SearchService
    from app.services.ai_service import ai_service, robust_json_loads, repair_truncated_jsx, repair_truncated_html
    from app.core.storage import storage
    from app.schemas.template import TemplateResponse
    import logging
    logger = logging.getLogger(__name__)

    # Force framework to always be HTML as requested by the user
    framework_lower = "html"
    
    # 1. Fetch available categories
    category_repo = CategoryRepository(db)
    categories = await category_repo.get_all_active()
    if not categories:
        raise HTTPException(status_code=400, detail="No active categories found in database to link the generated template.")
        
    categories_list = [{"id": str(c.id), "name": c.name, "slug": c.slug} for c in categories]
    
    # 2. Query Gemini to structure the template metadata
    gemini_prompt = f"""You are a professional website template developer.
A user wants to create a template matching this request: "{request.prompt}"
The framework requested is: "{framework_lower}"

Here are the available category options in the database:
{json.dumps(categories_list)}

Analyze the prompt and choose the most suitable category.
Then, generate a high-fidelity website template configuration.

Return a JSON object matching this exact structure:
{{
  "title": "A highly creative, premium title for the template listing",
  "short_description": "A catchy, persuasive 1-2 sentence description of the template for the marketplace grid card.",
  "description": "A comprehensive, beautifully formatted description outlining the design system, target industries, page layouts, components, and responsive details.",
  "price": 49.00,
  "category_id": "the chosen UUID category_id from the options list",
  "tags": ["3-5 matching tags like 'portfolio', 'creative', 'dark-mode'"],
  "industry": "e.g. Design, Real Estate, E-commerce, Restaurant",
  "color_scheme": "e.g. Elegant Gold & Charcoal, Minimal Neon Cyan",
  "pages_count": 5,
  "has_dark_mode": true,
  "included_pages": ["A comprehensive list of all page names required to build a fully featured website for this type of business (e.g., Home, About, Services, Products, Team, Portfolio, Blog, Testimonials, FAQ, Contact, Careers, Reviews). Choose the best 5 to 8 pages that make sense for this specific business type."],
  "seo_keywords": ["portfolio", "agency", "creative"],
  "logo_prompt": "A prompt describing a clean, minimalist developer brand avatar logo customized specifically for the target business theme (DO NOT copy template studio templates; e.g. if request is coffee shop, describe a coffee cup badge logo).",
  "thumbnail_prompt": "A detailed layout prompt for generating the template's landing page screenshot, reflecting the exact design aesthetics, colorful palettes, theme, and layouts matching this business category (DO NOT copy the dashboard example; write a custom screenshot prompt tailored to the request).",
  "gallery_prompts": [
    "A screenshot prompt for the services/products section of this specific business type",
    "A screenshot prompt for the contact/about section of this specific business type"
  ]
}}

Ensure price is a number.
Return ONLY valid JSON. Do not include markdown code block notation (```json) or explanations."""

    try:
        response_text = await ai_service._generate_content(gemini_prompt, response_mime_type="application/json", feature_name="website_content_generation")
        data = robust_json_loads(response_text)
    except Exception as e:
        logger.error(f"Gemini template generator prompt failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate template properties using AI: {str(e)}")

    # Extract chosen category UUID and other attributes
    category_uuid = None
    try:
        parsed_uuid = uuid.UUID(data.get("category_id"))
        if any(c.id == parsed_uuid for c in categories):
            category_uuid = parsed_uuid
    except Exception:
        pass

    if not category_uuid:
        # Fallback to first category if invalid or nonexistent UUID returned
        category_uuid = categories[0].id

    # Find the chosen category name for search indexing metadata
    chosen_cat_name = categories[0].name
    for c in categories:
        if c.id == category_uuid:
            chosen_cat_name = c.name
            break

    # Safe Slicing of string fields to prevent DB length constraint truncation failures
    title = data.get("title", "AI Generated Template")[:255]
    short_desc = data.get("short_description", "Premium AI-generated website template.")[:500]
    desc = data.get("description", "A stunning template built by AI.")
    price = data.get("price", 49.00)
    tags = data.get("tags", ["ai-generated", "premium"])
    
    industry_raw = data.get("industry", "Business")
    industry = industry_raw[:100] if industry_raw else None
    
    color_scheme_raw = data.get("color_scheme", "Modern Dark")
    color_scheme = color_scheme_raw[:50] if color_scheme_raw else None

    pages_count = data.get("pages_count", 5)
    has_dark_mode = data.get("has_dark_mode", True)
    included_pages = data.get("included_pages", ["Home"])
    seo_keywords = data.get("seo_keywords", ["website"])
    
    # Pollinations AI generation prompts
    logo_prompt = data.get("logo_prompt", f"minimalist developer avatar for {title} template creator")
    thumb_prompt = data.get("thumbnail_prompt", f"premium template homepage website screenshot of {title}")
    g_prompts = data.get("gallery_prompts", [
        f"screenshot of about section for {title} website template",
        f"screenshot of contact section for {title} website template"
    ])

    # 3. Create Pollinations AI URLs
    thumbnail_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(thumb_prompt[:120])}?width=1024&height=768&nologo=true&seed=42"
    gallery_images = [
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p[:120])}?width=1024&height=768&nologo=true&seed={i}"
        for i, p in enumerate(g_prompts)
    ]
    developer_avatar = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(logo_prompt[:120])}?width=250&height=250&nologo=true&seed=88"

    # Compile custom user answers
    answers_str = ""
    if request.answers:
        answers_list = []
        for q_id, val in request.answers.items():
            answers_list.append(f"- {q_id}: {val}")
        answers_str = "\n".join(answers_list)

    # Ensure the list of pages is clean and contains strings
    if request.pages:
        raw_pages = [p.get("name") for p in request.pages if p.get("name")]
    else:
        raw_pages = data.get("included_pages", ["Home", "About", "Services", "Contact"])
        
    pages = [p.strip() for p in raw_pages if isinstance(p, str) and p.strip()]
    # Normalize: Ensure "Home" exists
    has_home = False
    for i, p in enumerate(pages):
        if p.lower() in ["home", "homepage"]:
            pages[i] = "Home"
            has_home = True
            break
    if not has_home:
        pages.insert(0, "Home")
    pages_count = len(pages)

    # Format dynamic pages structures for HTML prompts
    html_pages_desc = []
    json_structure_template = {}
    for idx, p in enumerate(pages):
        # Determine filename
        if p == "Home":
            fname = "index.html"
        else:
            fname = request.pages[idx].get("filename") if (request.pages and idx < len(request.pages) and request.pages[idx].get("filename")) else f"{re.sub(r'[^a-zA-Z0-9]+', '-', p.lower()).strip('-')}.html"
        html_pages_desc.append(f"{idx+1}. {fname} (The complete page layout for the '{p}' section)")
        json_structure_template[fname] = f"<!DOCTYPE html>... (complete styled HTML5 code for {p} page)"

    html_pages_list_str = "\n".join(html_pages_desc)
    json_struct_str = json.dumps(json_structure_template, indent=2)

    # Format dynamic pages structures for React prompts
    react_pages_list_str = ", ".join(pages)
    react_pages_states_str = ", ".join([f"'{p.lower().replace(' ', '-')}'" for p in pages])

    # Helper function to clean markdown code snippets
    def clean_code_response(text: str, language: str) -> str:
        text = text.strip()
        if text.startswith(f"```{language}"):
            text = text.replace(f"```{language}", "", 1)
        elif text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    # 4. Generate the actual Code using Gemini Pro
    print(f"Generating custom {framework_lower} code...")
    if framework_lower == "html":
        code_prompt = f"""You are an elite, world-class lead frontend designer.
Create a complete, responsive, multi-page HTML website matching this user description: "{request.prompt}".

SPECIFIC USER DESIGN PREFERENCES:
{answers_str if answers_str else "No custom design questions answered."}

THE METADATA AND VISUAL DESIGN SPECS YOU MUST MATCH EXACTLY:
- Website Title: "{title}"
- Target Industry: "{industry}"
- Color Scheme & Styling Palette: "{color_scheme}" (Use this exact color scheme for background gradients, buttons, card borders, active navigations, and glow states).
- Visual Mockup Description: "{thumb_prompt}"
- Overall Design System & Aesthetic: "{desc}"
- Custom Tags: {json.dumps(tags)}
- Exact Pages to Generate: {html_pages_list_str}

Ensure all pages are fully styled with Tailwind CSS via CDN. 
You can implement the multi-page structure in one of two ways based on content size and completeness:
1. Multi-File Site: Map each filename to its complete HTML code, linking pages together using standard hrefs (e.g. index.html, about.html).
2. Single-Page Application (SPA): If the codebase is complex, you can write a single unified "index.html" file that contains all pages as distinct sections, using an inline client-side router/JavaScript tab toggler (matching navbar link clicks) to switch between them with smooth transition effects. This keeps all views fully detailed, responsive, and prevents truncation issues. If you choose this SPA approach, make sure all navigation links, buttons, and call-to-actions use hash anchors (e.g. href="#home", href="#request-blood") to toggle the display views dynamically, rather than linking to separate .html files, to prevent browser 404 page navigation errors. The other files in the JSON mapping can contain smaller templates or simply be left as minimal stubs, while index.html hosts the complete interactive site application.
Use professional layouts, modern color palettes, and beautiful fonts.

CRITICAL STRUCTURAL CODE REQUIREMENTS (DO NOT SKIP ANY SECTION):
1. NO SHORTCUTS: Write the complete, production-ready HTML code. Do not use placeholders, shorthand snippets, or ellipses. Every single layout component, form input, image, and text block must be fully written out.
2. RICH COMPONENTS & GRID LAYOUTS FOR EACH DYNAMIC VIEW:
   - Main landing/home view: MUST include a high-impact Hero banner (split two-column layout on desktop), a detailed multi-card Features Grid, a visual Showcase/Gallery container, a Statistics/Numbers section, and a professional Footer with social links and subscription newsletter.
   - "About" or "Process" or "Story" view: MUST include a story intro, an interactive vertical/horizontal Timeline layout, and a Team/Profile grid featuring styled avatar cards.
   - "Services" or "Products" or "Portfolio" or "Gallery" view: MUST include detailed pricing tables or item grids with checklist elements, styled checklist cards, and prominent CTA cards.
   - "Contact" or "Booking" view: MUST include a double-column layout with visual contact cards (SVG icons for phone/email/map location) on one side, and a fully styled contact form on the other side.

CRITICAL VISUAL DESIGN & IMAGES:
- Navbar brand logo image URL: '{developer_avatar}'
- Home page hero section background image URL: '{thumbnail_url}'
- Section background or showcase image URLs:
  - First Showcase Image: '{gallery_images[0] if len(gallery_images) > 0 else ""}'
  - Second Showcase Image: '{gallery_images[1] if len(gallery_images) > 1 else ""}'
  - Third Showcase Image: '{gallery_images[2] if len(gallery_images) > 2 else ""}'
If you need additional images, illustrations, or profile photos, use the Pollinations AI image service directly in the img src tags:
`https://image.pollinations.ai/prompt/{{{{description_of_desired_image}}}}?width=600&height=400&nologo=true`
(Ensure the description is short, descriptive, and safely URL-encoded).

CRITICAL ANIMATIONS & EFFECTS:
1. DESIGN STYLE: Make the design extremely attractive, vibrant, and colorful! Use rich background gradients (e.g. `bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900`), glowing glassmorphic cards (`bg-slate-900/40 backdrop-blur-xl border border-white/10 hover:border-primary/50`), colored border accents (`border-t-2 border-primary`), and gradient text (`text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-pink-500 to-amber-400`).
2. CSS KEYFRAME ANIMATIONS: Inside the <head> of EACH page, inject a <style> block containing custom CSS @keyframes:
   - fadeInUp: smooth entry from bottom (opacity 0, translateY 20px -> opacity 1, translateY 0).
   - fadeIn: simple fade entry.
   - pulseGlow: subtle glow pulse effect for CTA buttons and badges.
   Apply helper classes like .animate-fade-in-up {{{{ animation: fadeInUp 0.8s ease-out forwards; }}}} to headers, cards, and sections.
3. PAGE TRANSITIONS: Implement smooth multi-page transitions. Inject a fullscreen transition overlay and a simple JavaScript handler that intercepts page link clicks (preventing default instant load), animates a smooth fade/wipe effect, and then completes the redirect, ensuring a premium, seamless feeling between pages. Any loading spinner/transition overlay must have an inline self-destruct script immediately following its HTML markup that automatically hides the overlay after 1 second to prevent it from getting stuck.
4. Tailwind hover transition classes (e.g., transition-all duration-300 transform hover:-translate-y-1 hover:scale-[1.02] hover:shadow-2xl) to all cards, grid items, buttons, and navigation elements.

Return ONLY a valid JSON object mapping filenames to their complete file content string, matching this structure:
{json_struct_str}
Do not include markdown code block syntax (like ```json) or explanations."""
        
        try:
            raw_code = await ai_service._generate_content(code_prompt, response_mime_type="application/json", feature_name="code_assistant")
            files_dict = robust_json_loads(raw_code)
        except Exception as e:
            logger.error(f"Gemini HTML code generation or JSON parse failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate template HTML codebase: {str(e)}")

        # Package ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for fname, fcontent in files_dict.items():
                if fname.endswith(".html"):
                    fcontent = repair_truncated_html(fcontent)
                zip_file.writestr(fname, fcontent)
        zip_bytes = zip_buffer.getvalue()

    else:  # react
        code_prompt = f"""You are a senior lead React developer.
Generate the complete source code for a single-file React component `src/App.jsx` matching this user description: "{request.prompt}".

THE METADATA AND VISUAL DESIGN SPECS YOU MUST MATCH EXACTLY:
- Website Title: "{title}"
- Target Industry: "{industry}"
- Color Scheme & Styling Palette: "{color_scheme}" (Use this exact color scheme for background gradients, buttons, card borders, active navigations, and glow states).
- Visual Mockup Description: "{thumb_prompt}"
- Overall Design System & Aesthetic: "{desc}"
- Custom Tags: {json.dumps(tags)}
- Exact Pages to Toggle: {react_pages_list_str} (possible state values: {react_pages_states_str})

The file must export a default App component. It must use Tailwind CSS utility classes and Lucide React icons.
To support a multi-page experience, implement a state-driven client-side router inside App.jsx using state hooks (e.g. `const [currentPage, setCurrentPage] = useState('home')`) to toggle between these exact pages.

Ensure the navigation bar links change the current page state dynamically, and the website has premium layouts, micro-interactions, and beautiful copywriting.
Import lucide icons at the top: `import {{ Sparkles, ArrowRight, Check, ... }} from 'lucide-react';`

CRITICAL STRUCTURAL CODE REQUIREMENTS (DO NOT SKIP ANY SECTION):
1. NO SHORTCUTS: Write the complete, production-ready React JSX code for `src/App.jsx`. Do not use placeholders, shorthand snippets, or comments like `/* other sections here */`. Every single layout component, form input, image, and text block must be fully written out.
2. RICH COMPONENTS & GRID LAYOUTS FOR EACH DYNAMIC VIEW:
   - Navigation Header: Glassmorphic background with backdrop-blur-md, brand logo, links with active underlines, and a responsive mobile navbar toggler.
   - Whichever page is the main landing/home view: MUST include a high-impact Hero banner (split two-column layout on desktop), a detailed multi-card Features Grid, a visual Showcase/Gallery container, a Statistics/Numbers section, and a professional Footer with social links and subscription newsletter.
   - Whichever page represents the "About" or "Process" or "Story" view: MUST include a story intro, an interactive vertical/horizontal Timeline layout, and a Team/Profile grid featuring styled avatar cards.
   - Whichever page represents the "Services" or "Products" or "Portfolio" or "Gallery" view: MUST include detailed pricing comparison cards with checklist elements and active checklist icons, a detailed service process/flow section, and prominent CTA cards.
   - Whichever page represents the "Contact" or "Booking" view: MUST include a double-column layout with visual contact cards (Lucide icons for phone/email/map location) on the left, and a styled contact form on the right.
   - 
CRITICAL VISUAL DESIGN & IMAGES:
- Navbar brand logo image URL: '{developer_avatar}'
- Home page hero section background image URL: '{thumbnail_url}'
- Section background or showcase image URLs:
  - First Showcase Image: '{gallery_images[0] if len(gallery_images) > 0 else ""}'
  - Second Showcase Image: '{gallery_images[1] if len(gallery_images) > 1 else ""}'
  - Third Showcase Image: '{gallery_images[2] if len(gallery_images) > 2 else ""}'
If you need additional images, illustrations, or profile photos, use the Pollinations AI image service directly in the img src tags:
`https://image.pollinations.ai/prompt/{{{{description_of_desired_image}}}}?width=600&height=400&nologo=true`
(Ensure the description is short, descriptive, and safely URL-encoded).

CRITICAL ANIMATIONS & EFFECTS:
1. DESIGN STYLE: Make the design extremely attractive, vibrant, and colorful! Use rich background gradients (e.g. `bg-gradient-to-br from-slate-950 via-purple-950 to-slate-900`), glowing glassmorphic cards (`bg-slate-900/40 backdrop-blur-xl border border-white/10 hover:border-primary/50`), colored border accents, and gradient text (`text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-pink-500 to-amber-400`).
2. CSS KEYFRAME ANIMATIONS: Inject a `<style>` element inside the App component return JSX containing custom keyframe animations:
   - fadeInUp (smooth entry from bottom: opacity 0, translateY 20px -> opacity 1, translateY 0).
   - fadeIn (simple fade entry).
   Assign class names like `animate-fade-in-up` to structural elements.
3. PAGE TRANSITIONS: Wrap each page component in a transition container that triggers a smooth fade-in and scale-up animation whenever `currentPage` changes, providing a seamless page change effect.
4. Apply Tailwind hover transition classes (e.g. `transition-all duration-300 transform hover:-translate-y-1 hover:scale-[1.02] hover:shadow-2xl`) to buttons, navigation elements, and service cards.

Return ONLY the complete React ES6 Javascript code. Do not include markdown code block syntax (like ```javascript) or explanation."""

        try:
            raw_code = await ai_service._generate_content(code_prompt, response_mime_type="text/plain", feature_name="code_assistant")
            generated_code = clean_code_response(raw_code, "jsx")
            # If generated code still starts with js/jsx block, strip it
            generated_code = clean_code_response(generated_code, "javascript")
            # Auto-repair truncated JSX markup and brackets
            generated_code = repair_truncated_jsx(generated_code)
        except Exception as e:
            logger.error(f"Gemini React code generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate template React codebase: {str(e)}")

        # Construct standard React Vite project
        package_json = {
            "name": "ai-generated-template",
            "private": True,
            "version": "1.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "lucide-react": "^0.344.0"
            },
            "devDependencies": {
                "@types/react": "^18.2.66",
                "@types/react-dom": "^18.2.22",
                "@vitejs/plugin-react": "^4.2.1",
                "vite": "^5.1.6"
            }
        }
        
        vite_config = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
"""

        index_html = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Generated Template</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              primary: '#6366f1',
              secondary: '#8b5cf6',
            }
          }
        }
      }
    </script>
  </head>
  <body class="bg-slate-900 text-slate-100">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

        main_jsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""

        index_css = """/* Custom style */
body {
  margin: 0;
  background-color: #0f172a;
}
"""

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            zip_file.writestr("package.json", json.dumps(package_json, indent=2))
            zip_file.writestr("vite.config.js", vite_config)
            zip_file.writestr("index.html", index_html)
            zip_file.writestr("src/main.jsx", main_jsx)
            zip_file.writestr("src/App.jsx", generated_code)
            zip_file.writestr("src/index.css", index_css)
        zip_bytes = zip_buffer.getvalue()

    # Helper function to generate slug
    base_slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    base_slug = re.sub(r"[-\s]+", "-", base_slug)
    slug = base_slug
    counter = 1
    template_repo = TemplateRepository(db)
    while True:
        existing = await template_repo.get_by_slug(slug)
        if not existing:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    # 5. Upload Codebase ZIP to DB Storage
    zip_url = await storage.upload_file(
        db=db,
        file_content=zip_bytes,
        folder="templates",
        original_filename=f"{slug}.zip",
        content_type="application/zip"
    )

    download_assets = {
        "react": zip_url if framework_lower == "react" else "",
        "html": zip_url if framework_lower == "html" else "",
        "zip": zip_url
    }

    # 6. Create Template in DB
    from app.models.template import Template, TemplateStatus, TemplateLicense, TemplateFramework
    new_template = Template(
        title=title,
        slug=slug,
        short_description=short_desc,
        description=desc,
        price=price,
        original_price=decimal.Decimal(str(price)) * decimal.Decimal("1.25") if price else None,
        is_free=False,
        is_on_sale=True,
        thumbnail_url=thumbnail_url,
        preview_url=f"https://example.com/preview/{slug}",
        video_url=None,
        gallery_images=gallery_images,
        category_id=category_uuid,
        tags=tags,
        industry=industry,
        color_scheme=color_scheme,
        framework=TemplateFramework(framework_lower),
        pages_count=pages_count,
        has_dark_mode=has_dark_mode,
        is_responsive=True,
        is_rtl_supported=False,
        is_ai_ready=True,
        compatibility=["Chrome", "Safari", "Edge"],
        version="1.0.0",
        license_type=TemplateLicense.REGULAR,
        status=TemplateStatus.PUBLISHED,
        is_featured=False,
        is_bestseller=False,
        is_new=True,
        developer_name="AI Studio",
        developer_avatar=developer_avatar,
        seller_id=current_user.id,
        download_assets=download_assets,
        changelog={"1.0.0": "Initial AI generation"},
        included_pages=included_pages,
        seo_keywords=seo_keywords
    )
    
    db.add(new_template)
    await db.flush()
    await db.commit()
    await db.refresh(new_template)

    # 7. Index in Qdrant Vector search
    try:
        search_service = SearchService(db)
        await search_service.index_template(
            template_id=new_template.id,
            text=f"{new_template.title} {new_template.short_description} {new_template.description}",
            metadata={
                "title": new_template.title,
                "category": chosen_cat_name,
                "industry": new_template.industry,
                "tags": new_template.tags,
                "features": new_template.included_pages,
                "framework": new_template.framework,
                "style": "Modern",
                "color_scheme": new_template.color_scheme,
                "seo_keywords": new_template.seo_keywords
            }
        )
    except Exception as e:
        logger.error(f"Failed to index generated template in Qdrant: {e}")

    # Return template detail
    return await template_repo.get_by_id(new_template.id)
