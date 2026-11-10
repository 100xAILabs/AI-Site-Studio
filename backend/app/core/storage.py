"""
Universal File Storage Service — supports PostgreSQL (Local Dev) and
Cloudflare R2 / AWS S3 (Production Object Storage) with signed URLs and CDN support.
"""

import io
import asyncio
import logging
import mimetypes
import uuid
import re
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Tuple
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.stored_file import StoredFile

logger = logging.getLogger("storage")


class StorageService:
    """
    Handles file upload, retrieval, deletion, and presigned URL generation.
    Switches between PostgreSQL BYTEA storage (default for zero-dependency dev)
    and Cloudflare R2 / AWS S3 (production enterprise storage).
    """

    def __init__(self):
        self._s3_client = None

    @property
    def is_cloud_storage(self) -> bool:
        backend = (settings.STORAGE_BACKEND or "postgres").lower()
        if backend in ("r2", "cloudflare_r2"):
            return bool(settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and settings.R2_ACCOUNT_ID)
        if backend in ("s3", "aws_s3"):
            return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.S3_BUCKET_NAME)
        return False

    @property
    def bucket_name(self) -> str:
        backend = (settings.STORAGE_BACKEND or "postgres").lower()
        if backend in ("r2", "cloudflare_r2"):
            return settings.R2_BUCKET_NAME or "ai-site-studio"
        return settings.S3_BUCKET_NAME or "ai-site-studio"

    def _get_s3_client(self):
        """Lazy-initialize boto3 S3 client with connection timeouts."""
        if self._s3_client is not None:
            return self._s3_client

        backend = (settings.STORAGE_BACKEND or "postgres").lower()
        boto_config = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=15,
        )

        if backend in ("r2", "cloudflare_r2"):
            endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=boto_config,
            )
        elif backend in ("s3", "aws_s3"):
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION or "us-east-1",
                config=boto_config,
            )
        return self._s3_client

    @property
    def public_url(self) -> str:
        return settings.RESOLVED_STORAGE_BASE_URL.rstrip("/")

    def build_url(self, file_id: uuid.UUID) -> str:
        return f"{self.public_url}/{file_id}"

    def _parse_file_id(self, url: str) -> Optional[uuid.UUID]:
        match = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", str(url))
        if match:
            try:
                return uuid.UUID(match.group(1))
            except ValueError:
                pass
        return None

    async def upload_file(
        self,
        db: AsyncSession,
        file_content: bytes,
        folder: str,
        original_filename: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Store a file. In cloud mode (R2/S3), uploads blob to bucket and stores
        lightweight metadata in PostgreSQL. In local mode, stores in DB BYTEA.
        """
        ext = Path(original_filename).suffix
        storage_key = f"{folder}/{uuid.uuid4().hex}{ext}"

        if not content_type:
            content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

        data_payload = file_content

        # Upload to cloud storage if configured
        if self.is_cloud_storage:
            try:
                s3 = self._get_s3_client()
                await asyncio.to_thread(
                    s3.put_object,
                    Bucket=self.bucket_name,
                    Key=storage_key,
                    Body=file_content,
                    ContentType=content_type,
                )
                logger.info(f"[Storage] Uploaded {storage_key} to cloud bucket {self.bucket_name}")
                # Store empty byte string in DB to avoid double-storage and save DB space
                data_payload = b""
            except Exception as e:
                logger.warning(f"[Storage] Cloud upload failed, falling back to database: {e}")
                data_payload = file_content

        stored_file = StoredFile(
            storage_key=storage_key,
            original_filename=original_filename,
            content_type=content_type,
            size=len(file_content),
            data=data_payload,
        )
        db.add(stored_file)
        await db.flush()

        return self.build_url(stored_file.id)

    def local_file_path(self, storage_key: str) -> Path:
        root = Path(settings.LOCAL_STORAGE_DIR).resolve()
        candidate = (root / storage_key).resolve()
        candidate.relative_to(root)
        return candidate

    async def upload_file_from_file(
        self,
        db: AsyncSession,
        file_obj: BinaryIO,
        size: int,
        folder: str,
        original_filename: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Stream an upload to object storage or local disk without holding it in RAM."""
        ext = Path(original_filename).suffix
        storage_key = f"{folder}/{uuid.uuid4().hex}{ext}"
        content_type = content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
        file_obj.seek(0)

        if self.is_cloud_storage:
            s3 = self._get_s3_client()
            await asyncio.to_thread(
                s3.upload_fileobj,
                file_obj,
                self.bucket_name,
                storage_key,
                ExtraArgs={"ContentType": content_type},
            )
        else:
            target = self.local_file_path(storage_key)
            target.parent.mkdir(parents=True, exist_ok=True)

            def copy_upload():
                file_obj.seek(0)
                with target.open("wb") as out:
                    shutil.copyfileobj(file_obj, out, length=8 * 1024 * 1024)

            await asyncio.to_thread(copy_upload)

        stored_file = StoredFile(
            storage_key=storage_key,
            original_filename=Path(original_filename).name[:255],
            content_type=content_type,
            size=size,
            data=b"",
        )
        db.add(stored_file)
        await db.flush()
        return self.build_url(stored_file.id)

    async def get_file_record(self, db: AsyncSession, file_id: uuid.UUID) -> Optional[StoredFile]:
        result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
        return result.scalar_one_or_none()

    async def copy_to_path(self, db: AsyncSession, file_id: uuid.UUID, destination: Path) -> Optional[StoredFile]:
        """Materialize a stored object on disk for streaming scans and previews."""
        stored_file = await self.get_file_record(db, file_id)
        if not stored_file:
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        if stored_file.data:
            await asyncio.to_thread(destination.write_bytes, stored_file.data)
        elif self.is_cloud_storage:
            s3 = self._get_s3_client()
            await asyncio.to_thread(s3.download_file, self.bucket_name, stored_file.storage_key, str(destination))
        else:
            source = self.local_file_path(stored_file.storage_key)
            if not source.is_file():
                return None
            await asyncio.to_thread(shutil.copyfile, source, destination)
        return stored_file

    async def get_file(
        self,
        db: AsyncSession,
        file_id: uuid.UUID,
    ) -> Optional[Tuple[bytes, str, Optional[str]]]:
        """
        Return (file_bytes, content_type, original_filename).
        Reads from PostgreSQL if data is present, or fetches from S3/R2 if stored in cloud.
        """
        try:
            result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
            stored_file = result.scalar_one_or_none()
        except Exception:
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as fresh_db:
                result = await fresh_db.execute(select(StoredFile).where(StoredFile.id == file_id))
                stored_file = result.scalar_one_or_none()

        if not stored_file:
            return None

        # 1. If stored directly in DB (local/fallback)
        if stored_file.data and len(stored_file.data) > 0:
            return stored_file.data, stored_file.content_type, stored_file.original_filename

        # 2. Fetch from Cloud Storage if stored remotely
        if self.is_cloud_storage:
            try:
                s3 = self._get_s3_client()
                response = await asyncio.to_thread(s3.get_object, Bucket=self.bucket_name, Key=stored_file.storage_key)
                file_bytes = await asyncio.to_thread(response["Body"].read)
                return file_bytes, stored_file.content_type, stored_file.original_filename
            except ClientError as e:
                logger.error(f"[Storage] Failed to retrieve {stored_file.storage_key} from cloud: {e}")
                return None

        # Large locally stored uploads live on disk; small legacy blobs remain in BYTEA.
        try:
            local_path = self.local_file_path(stored_file.storage_key)
            if local_path.is_file():
                file_bytes = await asyncio.to_thread(local_path.read_bytes)
                return file_bytes, stored_file.content_type, stored_file.original_filename
        except (OSError, ValueError):
            pass

        return None

    def generate_presigned_url(self, storage_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned GET download URL for direct cloud download.
        """
        if not self.is_cloud_storage:
            return None
        try:
            s3 = self._get_s3_client()
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": storage_key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error(f"[Storage] Failed to generate presigned URL for {storage_key}: {e}")
            return None

    async def delete_file(self, db: AsyncSession, url: str) -> bool:
        """Delete file from cloud storage and DB."""
        file_id = self._parse_file_id(url)
        if not file_id:
            return False

        result = await db.execute(select(StoredFile).where(StoredFile.id == file_id))
        stored_file = result.scalar_one_or_none()
        if not stored_file:
            return False

        if self.is_cloud_storage:
            try:
                s3 = self._get_s3_client()
                await asyncio.to_thread(s3.delete_object, Bucket=self.bucket_name, Key=stored_file.storage_key)
            except Exception as e:
                logger.warning(f"[Storage] Cloud delete failed for {stored_file.storage_key}: {e}")

        await db.delete(stored_file)
        await db.flush()
        return True


storage = StorageService()
