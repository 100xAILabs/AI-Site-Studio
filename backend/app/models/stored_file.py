"""
StoredFile ORM model — binary file storage in PostgreSQL.
"""

import uuid
from typing import Optional

from sqlalchemy import BigInteger, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class StoredFile(UUIDMixin, TimestampMixin, Base):
    """File blob stored in PostgreSQL instead of external object storage."""

    __tablename__ = "stored_files"

    storage_key: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    def __repr__(self) -> str:
        return f"<StoredFile {self.storage_key} ({self.size} bytes)>"
