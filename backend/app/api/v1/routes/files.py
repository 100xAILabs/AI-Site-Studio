import uuid
import io
import os
import mimetypes
from typing import Optional
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Query, Request
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
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> Response:
    """
    Stream a file from PostgreSQL storage.
    Requires authentication via token or a valid HMAC URL signature.
    """
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")

    result = await storage.get_file(db, file_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")

    data, content_type, original_filename = result

    # 1. Authorize: check for valid URL signature first
    authorized = False
    if expires is not None and signature is not None:
        if verify_file_signature(file_id, expires, signature):
            authorized = True

    # 2. Fall back to current_user depending on file type sensitivity
    if not authorized:
        if content_type == "application/zip":
            # ZIP files (paid template assets) require a valid signature URL, Admin, Owner seller, Buyer purchase, or Free template
            if current_user is not None:
                role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
                if str(role_val).lower() in ("admin", "super_admin"):
                    authorized = True
                else:
                    try:
                        from app.models.template import Template
                        from sqlalchemy import select
                        # 2a. Check if seller created/uploaded this template
                        tmpl_res = await db.execute(
                            select(Template).where(Template.seller_id == current_user.id)
                        )
                        for t in tmpl_res.scalars().all():
                            d_assets = t.download_assets or {}
                            if t.source_file_id == file_uuid or str(file_uuid) in str(list(d_assets.values())):
                                authorized = True
                                break
                    except Exception:
                        pass

                    # 2b. Check if buyer purchased this template or template is free
                    if not authorized:
                        try:
                            from app.models.order import Order, OrderItem, OrderStatus
                            from app.models.template import Template
                            from sqlalchemy import or_
                            ord_res = await db.execute(
                                select(Template.id)
                                .outerjoin(OrderItem, OrderItem.template_id == Template.id)
                                .outerjoin(Order, OrderItem.order_id == Order.id)
                                .where(
                                    (Template.source_file_id == file_uuid) | (Template.id == file_uuid),
                                    or_(
                                        settings.TEMPLATE_DOWNLOADS_FREE,
                                        Template.is_free == True,
                                        (Order.user_id == current_user.id) & (Order.status == OrderStatus.COMPLETED)
                                    )
                                )
                                .limit(1)
                            )
                            if ord_res.scalar_one_or_none():
                                authorized = True
                        except Exception:
                            pass
        else:
            # Non-zip files (thumbnails, preview images, developer avatars, etc.) are public
            authorized = True

    if not authorized:
        raise HTTPException(
            status_code=403 if current_user is not None else 401,
            detail="Unauthorized: Access requires a valid token or URL signature."
        )

    headers = {}
    
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

    return Response(content=data, media_type=content_type, headers=headers)



@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store an uploaded file, validate it using Pillow, and return its signed public URL."""
    # 1. Early check using content length / metadata if available
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # 2. Read in chunks to prevent loading huge files into memory (OOM safety)
    content_buffer = bytearray()
    chunk_size = 1024 * 1024  # 1MB chunks
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            content_buffer.extend(chunk)
            if len(content_buffer) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
    finally:
        await file.close()

    content = bytes(content_buffer)

    # 3. Security: Check if file is a video, ZIP template, or image
    filename_lower = (file.filename or "").lower()
    video_exts = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".ogg": "video/ogg"}
    detected_mime = None

    for ext, v_mime in video_exts.items():
        if filename_lower.endswith(ext):
            detected_mime = v_mime
            break

    if detected_mime:
        # Valid video upload — bypass image Pillow parser
        pass
    elif filename_lower.endswith(".zip") and ("seller" in str(getattr(current_user, "role", "")).lower() or "admin" in str(getattr(current_user, "role", "")).lower()):
        detected_mime = "application/zip"
    else:
        # Validate image bytes using Pillow
        try:
            image = Image.open(io.BytesIO(content))
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
    url = await storage.upload_file(
        db=db,
        file_content=content,
        folder="uploads",
        original_filename=file.filename,
        content_type=detected_mime,
    )
    
    file_id = url.split("/")[-1]
    
    # Ensure public domain is used when accessed through production proxy
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    if forwarded_host and "localhost" not in forwarded_host and "127.0.0.1" not in forwarded_host:
        url = f"{forwarded_proto}://{forwarded_host}/api/v1/files/{file_id}"
    elif "localhost" in url and (str(settings.ENVIRONMENT).lower() in ("production", "prod") or os.getenv("RENDER")):
        url = f"https://ai-site-studio.onrender.com/api/v1/files/{file_id}"

    # Non-zip assets (avatars, thumbnails, screenshots, videos) are public
    if detected_mime != "application/zip":
        return {"url": url}

    # ZIP template packages use signed URLs valid for 7 days
    expires = int(datetime.now(timezone.utc).timestamp()) + 86400 * 7
    signature = generate_file_signature(file_id, expires)
    signed_url = f"{url}?expires={expires}&signature={signature}"

    return {"url": signed_url}
