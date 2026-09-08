"""
Figma Import API Routes.
Exposes endpoints to validate Figma links, extract design tokens, and synthesize live studio templates.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.models.user import User
from app.services.figma_service import figma_service

logger = logging.getLogger(__name__)

router = APIRouter()


class FigmaImportRequest(BaseModel):
    figma_url: str
    framework: Optional[str] = "HTML"
    title: Optional[str] = None
    category: Optional[str] = "Technology"
    access_token: Optional[str] = None
    purpose: Optional[str] = "personal"  # "personal" (deploy live site) or "sell" (marketplace template)
    price: Optional[float] = 0.0
    original_price: Optional[float] = 0.0


class FigmaValidateRequest(BaseModel):
    figma_url: str


@router.post("/validate-url")
async def validate_figma_url(request: FigmaValidateRequest):
    """
    Validate a Figma URL and extract metadata (file key, title hint, node ID).
    """
    if not request.figma_url or "figma.com" not in request.figma_url:
        return {
            "valid": False,
            "message": "Please enter a valid Figma file or design URL (e.g. https://www.figma.com/file/...)",
        }

    parsed = figma_service.parse_figma_url(request.figma_url)
    if not parsed.get("file_key"):
        return {
            "valid": False,
            "message": "Could not identify a valid Figma file key from URL.",
        }

    return {
        "valid": True,
        "file_key": parsed["file_key"],
        "title_slug": parsed["title_slug"].title() if parsed.get("title_slug") else "Untitled Figma Design",
        "node_id": parsed.get("node_id"),
    }


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_from_figma(
    request: FigmaImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Import a design from Figma and convert it into an interactive, multi-page website template.
    Saves clean assets, generates snapshot preview, and mounts it into the Live Studio.
    """
    if not request.figma_url or "figma.com" not in request.figma_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Figma URL. Please provide a link in the format https://www.figma.com/file/..."
        )

    try:
        user_id = current_user.id if current_user else None
        
        # Enforce that marketplace selling is strictly for Sellers & Admins.
        # Buyers importing Figma designs are strictly created for private Studio projects and deployment.
        final_purpose = request.purpose or "personal"
        if final_purpose == "sell":
            if not current_user:
                final_purpose = "personal"
            else:
                user_role_str = str(getattr(current_user, "role", "")).lower()
                if "seller" not in user_role_str and "admin" not in user_role_str:
                    logger.info(f"User {current_user.id} with role '{user_role_str}' cannot sell templates on marketplace. Enforcing purpose to 'personal'.")
                    final_purpose = "personal"

        result = await figma_service.import_from_figma(
            db=db,
            figma_url=request.figma_url,
            framework=request.framework or "HTML",
            custom_title=request.title,
            category_name=request.category or "Technology",
            access_token=request.access_token,
            user_id=user_id,
            purpose=final_purpose,
            price=request.price if final_purpose == "sell" else 0.0,
            original_price=request.original_price if final_purpose == "sell" else 0.0,
        )
        return result
    except Exception as e:
        logger.error(f"Figma import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import from Figma: {str(e)}"
        )
