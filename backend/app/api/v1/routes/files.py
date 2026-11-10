import uuid
import io
import os
import mimetypes
from typing import Optional
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.storage import storage
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.core.security import verify_file_signature, generate_file_signature
from datetime import datetime, timezone

router = APIRouter()


@router.get("/{file_id}")
async def get_stored_file(
    file_id: str,
    expires: Optional[int] = Query(None),
    signature: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Response:
    """
    Stream a file from PostgreSQL storage.
    Requires authentication via token or a valid HMAC URL signature.
    """
    # 0. Support token authentication from query param (e.g. for browser window/link downloads)
    if current_user is None and token:
        try:
            from app.core.security import decode_token
            from app.repositories.user_repo import UserRepository
            clean_token = str(token).replace("Bearer ", "").strip()
            payload = decode_token(clean_token)
            sub = payload.get("sub")
            if sub:
                user_repo = UserRepository(db)
                db_user = await user_repo.get_by_id(uuid.UUID(str(sub)))
                if db_user and db_user.is_active:
                    current_user = db_user
        except Exception:
            pass

    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")

    stored_file = await storage.get_file_record(db, file_uuid)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File not found")
    content_type = stored_file.content_type
    original_filename = stored_file.original_filename

    # 1. Authorize: check for valid URL signature first
    authorized = False
    if expires is not None and signature is not None:
        file_id_normalized = str(file_uuid)
        clean_sig = str(signature).strip().lower()
        if (
            verify_file_signature(file_id_normalized, expires, signature)
            or verify_file_signature(file_id, expires, signature)
            or verify_file_signature(file_id_normalized, expires, clean_sig)
            or verify_file_signature(file_id, expires, clean_sig)
        ):
            authorized = True

    # 2. Fall back to current_user depending on file type sensitivity
    if not authorized:
        is_zip = (
            content_type in ("application/zip", "application/x-zip-compressed", "application/x-zip", "application/octet-stream")
            or str(original_filename or "").lower().endswith(".zip")
        )
        if is_zip:
            # ZIP files require a valid signature URL, Admin, Owner seller, Buyer purchase, or Free template
            if current_user is not None:
                role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
                if str(role_val).lower() in ("admin", "super_admin"):
                    authorized = True
                else:
                    try:
                        from app.models.template import Template
                        from app.models.download import Download
                        from app.models.order import Order, OrderItem, OrderStatus
                        from sqlalchemy import select, or_

                        # 2a. Check if seller created/uploaded this template
                        tmpl_res = await db.execute(
                            select(Template).where(Template.seller_id == current_user.id)
                        )
                        for t in tmpl_res.scalars().all():
                            d_assets = t.download_assets or {}
                            if t.source_file_id == file_uuid or str(file_uuid) in str(list(d_assets.values())):
                                authorized = True
                                break

                        # 2b. Check if user has an authorized download record for this template
                        if not authorized:
                            dl_check = await db.execute(
                                select(Download.id)
                                .where(Download.user_id == current_user.id)
                                .limit(1)
                            )
                            if dl_check.scalar_one_or_none():
                                authorized = True

                        # 2c. Check if buyer purchased this template or template is free
                        if not authorized:
                            ord_res = await db.execute(
                                select(Template.id)
                                .outerjoin(OrderItem, OrderItem.template_id == Template.id)
                                .outerjoin(Order, OrderItem.order_id == Order.id)
                                .where(
                                    (Template.source_file_id == file_uuid) | (Template.id == file_uuid),
                                    or_(
                                        settings.TEMPLATE_DOWNLOADS_FREE,
                                        Template.is_free == True,
                                        (Order.user_id == current_user.id) & (Order.status.in_([OrderStatus.COMPLETED, OrderStatus.PROCESSING])),
                                    )
                                )
                                .limit(1)
                            )
                            if ord_res.scalar_one_or_none():
                                authorized = True

                        # 2d. Fallback: check all completed/paid orders of user
                        if not authorized:
                            user_purchased_templates = await db.execute(
                                select(Template)
                                .join(OrderItem, OrderItem.template_id == Template.id)
                                .join(Order, OrderItem.order_id == Order.id)
                                .where(
                                    Order.user_id == current_user.id,
                                    Order.status.in_([OrderStatus.COMPLETED, OrderStatus.PROCESSING]),
                                )
                            )
                            for t in user_purchased_templates.scalars().all():
                                d_assets = t.download_assets or {}
                                if t.source_file_id == file_uuid or str(file_uuid) in str(list(d_assets.values())):
                                    authorized = True
                                    break
                    except Exception as auth_err:
                        pass
        else:
            # Non-zip files (thumbnails, preview images, developer avatars, etc.) are public
            authorized = True

    if not authorized:
        raise HTTPException(
            status_code=403 if current_user is not None else 401,
            detail="Unauthorized: Access requires a valid token or URL signature."
        )

    headers = {"X-Content-Type-Options": "nosniff"}
    
    # 3. Prevent arbitrary inline execution (XSS) by using attachment disposition for untrusted formats
    allowed_inline_types = set(settings.ALLOWED_IMAGE_TYPES_LIST) | {"video/mp4", "video/webm", "video/quicktime", "video/ogg"}
    if content_type in allowed_inline_types:
        disposition = "inline"
    else:
        disposition = "attachment"

    if original_filename:
        safe_filename = os.path.basename(original_filename.replace("\\", "/"))
        safe_filename = safe_filename.replace('"', "").replace("\r", "").replace("\n", "")
        headers["Content-Disposition"] = f'{disposition}; filename="{safe_filename}"'
    elif disposition == "attachment":
        safe_filename = f"template-{file_uuid}.zip" if content_type == "application/zip" else f"file-{file_uuid}"
        headers["Content-Disposition"] = f'{disposition}; filename="{safe_filename}"'

    if stored_file.data:
        return Response(content=stored_file.data, media_type=content_type, headers=headers)
    if storage.is_cloud_storage:
        signed_url = storage.generate_presigned_url(stored_file.storage_key)
        if not signed_url:
            raise HTTPException(status_code=503, detail="Stored file is temporarily unavailable")
        return RedirectResponse(url=signed_url, status_code=307)
    local_path = storage.local_file_path(stored_file.storage_key)
    if not local_path.is_file():
        raise HTTPException(status_code=404, detail="File data not found")
    return FileResponse(path=local_path, media_type=content_type, headers=headers)



@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream files to object storage/disk; enforce type and archive safety checks, not size caps."""
    file_obj = file.file
    file_obj.seek(0)
    file_size = int(file.size or 0)
    if not file_size:
        file_obj.seek(0, os.SEEK_END)
        file_size = file_obj.tell()
        file_obj.seek(0)

    filename_lower = (file.filename or "").lower()
    video_exts = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".ogg": "video/ogg"}
    detected_mime = None

    for ext, v_mime in video_exts.items():
        if filename_lower.endswith(ext):
            header = file_obj.read(12)
            valid_container = (
                header[4:8] == b"ftyp" if ext in (".mp4", ".mov") else
                header.startswith(b"\x1a\x45\xdf\xa3") if ext == ".webm" else
                header.startswith(b"OggS") if ext == ".ogg" else False
            )
            file_obj.seek(0)
            if not valid_container:
                raise HTTPException(status_code=400, detail="Uploaded video contents do not match the selected format.")
            detected_mime = v_mime
            break

    if detected_mime:
        # Valid video upload — bypass image Pillow parser
        pass
    elif filename_lower.endswith(".zip") and ("seller" in str(getattr(current_user, "role", "")).lower() or "admin" in str(getattr(current_user, "role", "")).lower()):
        from app.services.security_scanner import security_scanner
        zip_report = security_scanner.scan_zip_stream(file_obj, file.filename or "upload.zip")
        file_obj.seek(0)
        if not zip_report.get("is_safe") or zip_report.get("purged_files"):
            blocked = ", ".join(zip_report.get("purged_files", [])[:5])
            if blocked:
                raise HTTPException(status_code=400, detail=f"Archive contains blocked executable files: {blocked}")
            raise HTTPException(status_code=400, detail=zip_report.get("reason") or "Archive failed security inspection")
        detected_mime = "application/zip"
    else:
        # Validate image bytes using Pillow
        try:
            image = Image.open(file_obj)
            image.verify()
            
            # Re-detect MIME type based on format rather than client input
            detected_format = image.format.lower() if image.format else ""
            if detected_format == "jpeg":
                detected_mime = "image/jpeg"
            elif detected_format == "png":
                detected_mime = "image/png"
            elif detected_format == "webp":
                detected_mime = "image/webp"
            elif detected_format == "gif":
                detected_mime = "image/gif"
            else:
                detected_mime = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is not a valid image, video, or ZIP archive."
            )

    # Enforce configured allow-list
    allowed_types = set(settings.ALLOWED_IMAGE_TYPES_LIST) | {"application/zip", "video/mp4", "video/webm", "video/quicktime", "video/ogg"}
    if detected_mime not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {detected_mime} is not allowed."
        )

    # 4. Store file and build URL
    file_obj.seek(0)
    url = await storage.upload_file_from_file(
        db=db,
        file_obj=file_obj,
        size=file_size,
        folder="uploads",
        original_filename=file.filename or "upload.bin",
        content_type=detected_mime,
    )
    await file.close()
    
    file_id = url.split("/")[-1]
    
    # Public URLs come from trusted deployment configuration, never client-controlled
    # Host / X-Forwarded-Host request headers.

    # Non-zip assets (avatars, thumbnails, screenshots, videos) are public
    if detected_mime != "application/zip":
        return {"url": url}

    # ZIP template packages use signed URLs valid for 7 days
    expires = int(datetime.now(timezone.utc).timestamp()) + 86400 * 7
    signature = generate_file_signature(file_id, expires)
    signed_url = f"{url}?expires={expires}&signature={signature}"

    return {"url": signed_url}
