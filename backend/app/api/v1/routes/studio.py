"""Authenticated endpoints for planning and generating private Studio projects."""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import get_current_user
from app.core.request_limits import enforce_user_limit
from app.models.user import User
from app.models.studio_build import StudioBuild, StudioBuildEvent, StudioBuildMessage
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
    stack: str = Field(default="html-css-js", max_length=80)


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
    stack: str = Field(default="html-css-js", max_length=80)

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
    stack: str = Field(default="html-css-js", max_length=80)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values):
        for url in values:
            if len(url) > 2048 or not re.match(r"^https://[^\s]+$", url, re.IGNORECASE):
                raise ValueError("Images must be direct HTTPS URLs selected by you.")
        return values


class StudioMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)
    message_type: Literal["chat", "clarification", "answer", "build_summary", "error"] = "chat"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 5000:
            raise ValueError("Message metadata must be 5 KB or smaller.")
        return value


@router.post("/plan")
async def create_studio_plan(
    request: StudioPlanRequest,
    current_user: User = Depends(get_current_user),
):
    limit = 200 if settings.DEBUG else 50
    await enforce_user_limit(str(current_user.id), "studio-plan", limit=limit, window_seconds=3600)
    try:
        plan = await studio_service.plan(
            request.prompt,
            request.category,
            request.genre,
            request.page_structure,
            stack=request.stack,
        )
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
    limit = 200 if settings.DEBUG else 50
    await enforce_user_limit(str(current_user.id), "studio-prompt", limit=limit, window_seconds=3600)
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
            stack=request.stack,
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
    limit = 100 if settings.DEBUG else 30
    await enforce_user_limit(str(current_user.id), "studio-generate", limit=limit, window_seconds=3600)

    build = StudioBuild(
        user_id=current_user.id,
        title=str(request.plan.get("title") or request.genre)[:255],
        initial_prompt=request.prompt,
        category=request.category,
        site_type=request.genre,
        stack=request.stack or "html-css-js",
        status="running",
        current_phase="planning",
        plan=request.plan,
        answers=request.answers,
        approved_prompt=request.build_prompt,
        started_at=datetime.now(timezone.utc),
    )
    db.add(build)
    await db.flush()
    build_id = build.id
    message_sequence = 1
    db.add(StudioBuildMessage(build_id=build.id, sequence=message_sequence, role="user", content=request.prompt, message_type="request"))
    for index, question in enumerate(request.plan.get("questions", []) if isinstance(request.plan.get("questions"), list) else []):
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("id") or f"q-{index}")
        answer = str(request.answers.get(question_id) or "").strip()
        if not answer:
            continue
        message_sequence += 1
        db.add(StudioBuildMessage(build_id=build.id, sequence=message_sequence, role="assistant", content=str(question.get("question") or "")[:2000], message_type="clarification"))
        message_sequence += 1
        db.add(StudioBuildMessage(build_id=build.id, sequence=message_sequence, role="user", content=answer[:10000], message_type="answer", metadata_json={"question_id": question_id}))
    message_sequence += 1
    db.add(StudioBuildMessage(build_id=build.id, sequence=message_sequence, role="assistant", content=request.build_prompt, message_type="build_brief"))
    await db.commit()
    await db.refresh(build)

    async def stream_events():
        sequence = 0
        last_message_sequence = message_sequence
        yield f"data: {json.dumps({'type': 'session', 'build_id': str(build_id)}, ensure_ascii=False)}\n\n"
        service_db = AsyncSessionLocal()
        try:
            gen = studio_service.generate(
                db=service_db,
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
                stack=request.stack,
            )
            next_task = asyncio.create_task(gen.__anext__())
            while True:
                done, _ = await asyncio.wait({next_task}, timeout=15.0)
                if not done:
                    # SSE comment line keeps HTTP streaming connection warm during heavy generation steps without cancelling
                    yield ": keep-alive\n\n"
                    continue
                try:
                    event = next_task.result()
                except StopAsyncIteration:
                    break

                sequence += 1
                try:
                    async with AsyncSessionLocal() as ev_db:
                        ev_db.add(StudioBuildEvent(build_id=build_id, sequence=sequence, event_type=str(event.get("type") or "progress"), payload=event))
                        b = await ev_db.get(StudioBuild, build_id)
                        if b:
                            if event.get("type") in {"agent", "page"}:
                                b.current_phase = str(event.get("agent") or event.get("name") or event.get("filename") or b.current_phase)[:80]
                            if event.get("type") == "complete":
                                project = event.get("project") or {}
                                b.status = "completed"
                                b.current_phase = "completed"
                                b.template_id = UUID(str(project["id"]))
                                b.result_summary = f"Created {project.get('title') or b.title} with {project.get('pages_count') or 1} page(s)."
                                b.finished_at = datetime.now(timezone.utc)
                                last_message_sequence += 1
                                ev_db.add(StudioBuildMessage(build_id=build_id, sequence=last_message_sequence, role="assistant", content=b.result_summary, message_type="build_summary"))
                        await ev_db.commit()
                except Exception as log_exc:
                    logger.warning("Could not persist build event %s: %s", sequence, log_exc)

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                # Schedule next iteration only after this event is fully processed and yielded
                next_task = asyncio.create_task(gen.__anext__())
        except asyncio.CancelledError:
            if "next_task" in locals() and next_task and not next_task.done():
                next_task.cancel()
            try:
                async with AsyncSessionLocal() as c_db:
                    cancelled_build = await c_db.get(StudioBuild, build_id)
                    if cancelled_build:
                        cancelled_build.status = "cancelled"
                        cancelled_build.current_phase = "cancelled"
                        cancelled_build.error_message = "Build stream was interrupted before completion."
                        cancelled_build.finished_at = datetime.now(timezone.utc)
                        c_db.add(StudioBuildEvent(build_id=build_id, sequence=sequence + 1, event_type="cancelled", payload={"type": "cancelled", "reason": "client_disconnected"}))
                        await c_db.commit()
            except Exception:
                pass
            raise
        except Exception as exc:
            try:
                async with AsyncSessionLocal() as f_db:
                    failed_build = await f_db.get(StudioBuild, build_id)
                    if failed_build:
                        failed_build.status = "failed"
                        failed_build.current_phase = "failed"
                        failed_build.error_message = str(exc)[:2000]
                        failed_build.finished_at = datetime.now(timezone.utc)
                        max_message_sequence = await f_db.scalar(select(func.max(StudioBuildMessage.sequence)).where(StudioBuildMessage.build_id == build_id)) or 0
                        f_db.add(StudioBuildMessage(build_id=build_id, sequence=max_message_sequence + 1, role="assistant", content=f"Build failed: {str(exc)[:1800]}", message_type="error"))
                        await f_db.commit()
            except Exception:
                pass
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:500]}, ensure_ascii=False)}\n\n"
        finally:
            try:
                await service_db.close()
            except Exception as close_err:
                logger.debug("service_db closed safely: %s", close_err)

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/builds")
async def list_studio_builds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StudioBuild).where(StudioBuild.user_id == current_user.id).order_by(StudioBuild.created_at.desc()).limit(100)
    )
    builds = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "status": item.status,
            "current_phase": item.current_phase,
            "template_id": str(item.template_id) if item.template_id else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "result_summary": item.result_summary,
            "error_message": item.error_message,
        }
        for item in builds
    ]


@router.get("/builds/{build_id}")
async def get_studio_build(
    build_id: UUID,
    after_event: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    build = await db.get(StudioBuild, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Studio build not found.")
    messages_result = await db.execute(
        select(StudioBuildMessage).where(StudioBuildMessage.build_id == build_id).order_by(StudioBuildMessage.sequence.asc())
    )
    events_result = await db.execute(
        select(StudioBuildEvent).where(StudioBuildEvent.build_id == build_id, StudioBuildEvent.sequence > max(0, after_event)).order_by(StudioBuildEvent.sequence.asc()).limit(500)
    )
    return {
        "id": str(build.id),
        "title": build.title,
        "status": build.status,
        "current_phase": build.current_phase,
        "template_id": str(build.template_id) if build.template_id else None,
        "created_at": build.created_at.isoformat() if build.created_at else None,
        "updated_at": build.updated_at.isoformat() if build.updated_at else None,
        "result_summary": build.result_summary,
        "error_message": build.error_message,
        "messages": [
            {"id": str(item.id), "role": item.role, "content": item.content, "type": item.message_type, "metadata": item.metadata_json or {}, "created_at": item.created_at.isoformat() if item.created_at else None}
            for item in messages_result.scalars().all()
        ],
        "events": [
            {"sequence": item.sequence, "type": item.event_type, "payload": item.payload, "created_at": item.created_at.isoformat() if item.created_at else None}
            for item in events_result.scalars().all()
        ],
    }


@router.post("/builds/{build_id}/messages", status_code=201)
async def append_studio_build_message(
    build_id: UUID,
    request: StudioMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await enforce_user_limit(str(current_user.id), "studio-build-message", limit=60, window_seconds=3600)
    build_result = await db.execute(select(StudioBuild).where(StudioBuild.id == build_id).with_for_update())
    build = build_result.scalar_one_or_none()
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Studio build not found.")
    max_message_sequence = await db.scalar(select(func.max(StudioBuildMessage.sequence)).where(StudioBuildMessage.build_id == build_id)) or 0
    message = StudioBuildMessage(
        build_id=build.id,
        sequence=max_message_sequence + 1,
        role=request.role,
        content=request.content,
        message_type=request.message_type,
        metadata_json=request.metadata,
    )
    build.updated_at = datetime.now(timezone.utc)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "type": message.message_type,
        "metadata": message.metadata_json or {},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }



class StudioIterateRequest(BaseModel):
    """Request to apply a conversational change instruction to an existing build."""
    instruction: str = Field(min_length=3, max_length=8000, description="Natural-language change instruction, e.g. 'Change the hero background to dark navy and add a pricing section'")


@router.post("/builds/{build_id}/iterate")
async def iterate_studio_build(
    build_id: UUID,
    request: StudioIterateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Conversational post-build iteration.

    Applies a natural-language change instruction to the files of an existing
    completed Studio build and streams back a modified ZIP package.

    The AI reads the current generated files, applies the instruction, and
    re-packages the updated project.
    """
    from app.services.backend_generator import backend_generator
    from app.models.template import Template
    from sqlalchemy import select as sa_select
    import io, zipfile

    await enforce_user_limit(str(current_user.id), "studio-iterate", limit=20, window_seconds=3600)

    # Load the build
    build = await db.get(StudioBuild, build_id)
    if not build or build.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Studio build not found.")
    if build.status not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail="Build must be completed before iterating.")
    if not build.template_id:
        raise HTTPException(status_code=409, detail="No generated project found for this build.")

    # Load the associated template to get the download ZIP URL
    template = await db.get(Template, build.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Generated project template not found.")

    # Load conversation history for context
    messages_result = await db.execute(
        select(StudioBuildMessage)
        .where(StudioBuildMessage.build_id == build_id)
        .order_by(StudioBuildMessage.sequence.asc())
        .limit(30)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in messages_result.scalars().all()
    ]

    # Reconstruct the current files from the stored ZIP
    from app.core.storage import storage
    current_files: dict[str, str] = {}
    download_assets = template.download_assets or {}
    zip_url = download_assets.get("zip") or download_assets.get("html") or ""

    if zip_url:
        try:
            import re as _re
            # Try to load from storage if it's a local storage UUID URL
            file_id_match = _re.search(r"/files/([0-9a-fA-F-]{36})$", zip_url)
            if file_id_match:
                from uuid import UUID as _UUID
                stored = await storage.get_file(db, _UUID(file_id_match.group(1)))
                if stored:
                    zip_bytes, _, _ = stored
                    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                        for name in zf.namelist():
                            if any(name.endswith(ext) for ext in (
                                ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
                                ".py", ".md", ".json", ".txt", ".env",
                                ".toml", ".yaml", ".yml", ".ini",
                            )):
                                try:
                                    current_files[name] = zf.read(name).decode("utf-8", errors="replace")
                                except Exception:
                                    pass
        except Exception as load_exc:
            raise HTTPException(status_code=500, detail=f"Could not load existing project files: {load_exc}")

    if not current_files:
        raise HTTPException(status_code=422, detail="Could not read source files from the existing build. The ZIP may use an external storage URL.")

    architecture = {}
    try:
        changelog = template.changelog or {}
        architecture = changelog.get("architecture", {})
    except Exception:
        pass

    stack = build.stack or "html-css-js"

    async def stream_iteration():
        import json as _json
        nonlocal current_files

        yield f"data: {_json.dumps({'type': 'iterate_start', 'instruction': request.instruction[:200]}, ensure_ascii=False)}\n\n"

        changed_count = 0
        try:
            async for action, fpath, new_content in backend_generator.apply_chat_instruction(
                instruction=request.instruction,
                current_files=current_files,
                architecture=architecture,
                stack_key=stack,
                build_history=history,
            ):
                if action == "update":
                    current_files[fpath] = new_content
                    changed_count += 1
                    yield f"data: {_json.dumps({'type': 'file_updated', 'path': fpath, 'chars': len(new_content)}, ensure_ascii=False)}\n\n"
                elif action == "delete":
                    current_files.pop(fpath, None)
                    yield f"data: {_json.dumps({'type': 'file_deleted', 'path': fpath}, ensure_ascii=False)}\n\n"
        except Exception as iter_exc:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(iter_exc)[:400]}, ensure_ascii=False)}\n\n"
            return

        if changed_count == 0:
            yield f"data: {_json.dumps({'type': 'error', 'message': 'The AI did not generate any file changes for this instruction. Please rephrase or be more specific.'}, ensure_ascii=False)}\n\n"
            return

        # Re-package the updated project into a new ZIP
        from app.services.security_scanner import security_scanner
        try:
            new_archive = io.BytesIO()
            with zipfile.ZipFile(new_archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for fpath, content in current_files.items():
                    bundle.writestr(fpath, content.encode("utf-8", errors="replace"))
            new_zip_bytes = new_archive.getvalue()

            scan = security_scanner.scan_zip_bytes(new_zip_bytes, "studio-iteration.zip")
            if not scan.get("is_safe", False):
                yield f"data: {_json.dumps({'type': 'error', 'message': 'The updated project did not pass the security scan.'}, ensure_ascii=False)}\n\n"
                return

            new_zip_url = await storage.upload_file(
                db, new_zip_bytes, "studio-projects",
                f"{build_id.hex}-iter.zip", "application/zip"
            )

            # Persist updated revision locally (keeps before_edit untouched, updates latest and revisions/)
            try:
                from app.core.local_project_manager import local_project_manager
                local_project_manager.unpack_zip_bytes_to_local(
                    template_id=build.template_id,
                    slug=template.slug or str(build.template_id),
                    zip_bytes=new_zip_bytes,
                    title=template.title,
                    is_initial=False,
                    instruction=request.instruction,
                )
            except Exception as loc_exc:
                pass

            # Update the template's download URL
            template.download_assets = {**(template.download_assets or {}), "zip": new_zip_url, "html": new_zip_url}
            db.add(template)

            # Save the iteration as a message
            max_seq = await db.scalar(
                select(func.max(StudioBuildMessage.sequence)).where(StudioBuildMessage.build_id == build_id)
            ) or 0
            db.add(StudioBuildMessage(
                build_id=build_id,
                sequence=max_seq + 1,
                role="user",
                content=request.instruction,
                message_type="chat",
            ))
            db.add(StudioBuildMessage(
                build_id=build_id,
                sequence=max_seq + 2,
                role="assistant",
                content=f"Applied: {request.instruction[:200]}. Modified {changed_count} file(s). New package ready.",
                message_type="chat",
                metadata_json={"changed_files": changed_count, "zip_url": new_zip_url},
            ))
            await db.commit()

            yield f"data: {_json.dumps({'type': 'iterate_complete', 'changed_files': changed_count, 'zip_url': new_zip_url}, ensure_ascii=False)}\n\n"
        except Exception as pack_exc:
            await db.rollback()
            yield f"data: {_json.dumps({'type': 'error', 'message': f'Failed to repackage project: {str(pack_exc)[:300]}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_iteration(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
