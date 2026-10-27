"""Authenticated endpoints for planning and generating private Studio projects."""

import json
import re
from typing import Any, Literal
from uuid import UUID
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.request_limits import enforce_user_limit
from app.models.user import User
from app.services.studio_service import studio_service

router = APIRouter()


def _is_allowed_image_asset_url(value: str) -> bool:
    """Allow HTTPS image URLs and the app's local uploaded-file URLs in development."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() == "https":
            return bool(parsed.hostname and not parsed.username and not parsed.password)
        if parsed.scheme.lower() != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return False
        # Plain HTTP is allowed only for UUID-backed files served by this app.
        return bool(re.fullmatch(r"/api/v1/files/[0-9a-fA-F-]{36}", parsed.path))
    except (TypeError, ValueError):
        return False


class StudioPlanRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=100000)
    category: str = Field(min_length=1, max_length=100)
    genre: str = Field(min_length=1, max_length=100)
    page_structure: Literal["single_page", "multi_page"]


class StudioImageAsset(BaseModel):
    role: Literal["portrait", "skills", "project", "team", "equipment", "general"]
    url: str = Field(min_length=1, max_length=2048)
    alt: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        if not _is_allowed_image_asset_url(value):
            raise ValueError("Image assets must use HTTPS URLs, or a local Studio uploaded-file URL during development.")
        return value


class StudioGenerateRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=100000)
    category_id: UUID
    category: str = Field(min_length=1, max_length=100)
    genre: str = Field(min_length=1, max_length=100)
    build_prompt: str = Field(min_length=100, max_length=60000)
    plan: dict[str, Any]
    answers: dict[str, Any] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list, max_length=16)
    image_assets: list[StudioImageAsset] = Field(default_factory=list, max_length=16)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values):
        for url in values:
            if len(url) > 2048 or not re.match(r"^https://[^\s]+$", url, re.IGNORECASE):
                raise ValueError("Images must be direct HTTPS URLs selected by you.")
        return values


class StudioPromptRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=100000)
    category: str = Field(min_length=1, max_length=100)
    genre: str = Field(min_length=1, max_length=100)
    page_structure: Literal["single_page", "multi_page"]
    plan: dict[str, Any]
    answers: dict[str, Any] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list, max_length=16)
    image_assets: list[StudioImageAsset] = Field(default_factory=list, max_length=16)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values):
        for url in values:
            if len(url) > 2048 or not re.match(r"^https://[^\s]+$", url, re.IGNORECASE):
                raise ValueError("Images must be direct HTTPS URLs selected by you.")
        return values


@router.post("/plan")
async def create_studio_plan(
    request: StudioPlanRequest,
    current_user: User = Depends(get_current_user),
):
    await enforce_user_limit(str(current_user.id), "studio-plan", limit=10, window_seconds=3600)
    try:
        plan = await studio_service.plan(request.prompt, request.category, request.genre, request.page_structure)
        return {"agent": "Planning Agent", "plan": plan}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Planning Agent failed: {exc}")


@router.post("/prompt")
async def create_studio_build_prompt(
    request: StudioPromptRequest,
    current_user: User = Depends(get_current_user),
):
    await enforce_user_limit(str(current_user.id), "studio-prompt", limit=10, window_seconds=3600)
    try:
        build_prompt = await studio_service.create_build_prompt(
            prompt=request.prompt,
            category=request.category,
            genre=request.genre,
            page_structure=request.page_structure,
            plan=request.plan,
            answers=request.answers,
            image_urls=request.image_urls,
            image_assets=[asset.model_dump() for asset in request.image_assets],
        )
        return {"agent": "Planning Agent", "build_prompt": build_prompt}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Build prompt generation failed: {exc}")


@router.post("/generate")
async def generate_studio_project(
    request: StudioGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await enforce_user_limit(str(current_user.id), "studio-generate", limit=3, window_seconds=3600)

    async def stream_events():
        try:
            async for event in studio_service.generate(
                db=db,
                user=current_user,
                prompt=request.prompt,
                category_id=request.category_id,
                category_name=request.category,
                genre=request.genre,
                plan=request.plan,
                answers=request.answers,
                build_prompt=request.build_prompt,
                image_urls=request.image_urls,
                image_assets=[asset.model_dump() for asset in request.image_assets],
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:500]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
