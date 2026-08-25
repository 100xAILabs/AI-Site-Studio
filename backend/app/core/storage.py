"""
PostgreSQL-backed file storage.

Uploaded files are stored in the `stored_files` table and served via the
`/api/v1/files/{file_id}` endpoint.
"""

import mimetypes
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stored_file import StoredFile


class StorageService:
    """Handles file upload, retrieval, and deletion using PostgreSQL."""

    @property
    def public_url(self) -> str:
        return settings.STORAGE_BASE_URL.rstrip("/")

    def build_url(self, file_id: uuid.UUID) -> str:
        return f"{self.public_url}/{file_id}"

    def _parse_file_id(self, url: str) -> Optional[uuid.UUID]:
        if url.startswith(self.public_url):
            path = url[len(self.public_url) :].lstrip("/")
        else:
            path = urlparse(url).path.rstrip("/").split("/")[-1]

        if not path:
            return None

        try:
            return uuid.UUID(path)
        except ValueError:
            return None

    async def upload_file(
        self,
        db: AsyncSession,
        file_content: bytes,
        folder: str,
        original_filename: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Store a file in PostgreSQL and return its public URL."""
        ext = Path(original_filename).suffix
        storage_key = f"{folder}/{uuid.uuid4().hex}{ext}"

        if not content_type:
            content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

        stored_file = StoredFile(
            storage_key=storage_key,
            original_filename=original_filename,
            content_type=content_type,
            size=len(file_content),
            data=file_content,
        )
        db.add(stored_file)
        await db.flush()

        return self.build_url(stored_file.id)

    async def get_file(
        self,
        db: AsyncSession,
        file_id: uuid.UUID,
    ) -> Optional[tuple[bytes, str, Optional[str]]]:
        """Return file bytes, content type, and original filename with auto-retry on connection reset."""
        try:
            result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            stored_file = result.scalar_one_or_none()
        except Exception:
            # Fallback to fresh session if existing connection was closed / stale
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as fresh_db:
                result = await fresh_db.execute(select(StoredFile).where(StoredFile.id == file_id))
                stored_file = result.scalar_one_or_none()

        if not stored_file:
            return None

        return stored_file.data, stored_file.content_type, stored_file.original_filename

    async def delete_file(self, db: AsyncSession, url: str) -> bool:
        """Delete a stored file by its public URL."""
        file_id = self._parse_file_id(url)
        if not file_id:
            return False

        result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
        stored_file = result.scalar_one_or_none()
        if not stored_file:
            return False

        await db.delete(stored_file)
        await db.flush()
        return True


storage = StorageService()
