"""
Preview service — generates watermarked preview images using Pillow.
"""

import io
import uuid
import textwrap
from datetime import datetime, timezone, timedelta
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import storage
from app.models.preview_session import PreviewSession
from app.repositories.template_repo import TemplateRepository


class PreviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.template_repo = TemplateRepository(db)

    async def create_session(
        self,
        template_id: uuid.UUID,
        business_data: dict,
        user_email: Optional[str] = None,
        is_ai_filled: bool = False,
    ) -> PreviewSession:
        """Create a preview session record."""
        template = await self.template_repo.get_by_id(template_id)
        if not template:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Template not found")

        session = PreviewSession(
            template_id=template_id,
            user_email=user_email,
            business_data=business_data,
            is_ai_filled=is_ai_filled,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    def apply_watermark(
        self,
        image_bytes: bytes,
        user_email: Optional[str] = None,
        opacity: int = 38,  # ~15% of 255
    ) -> bytes:
        """
        Apply a diagonal tiled watermark to a preview image.

        Watermark text: "SITE STUDIO  PREVIEW ONLY  <email>"
        Opacity: ~15% (38/255)
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        width, height = img.size

        # Create a transparent watermark layer
        watermark_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)

        # Try to load a font, fall back to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 36)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        watermark_lines = ["SITE STUDIO", "PREVIEW ONLY"]
        if user_email:
            watermark_lines.append(user_email)

        watermark_text = "\n".join(watermark_lines)

        # Tile the watermark diagonally
        tile_size = 400
        for x in range(-tile_size, width + tile_size, tile_size):
            for y in range(-tile_size, height + tile_size, tile_size):
                # Create a small rotated tile
                tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                tile_draw = ImageDraw.Draw(tile)
                tile_draw.text(
                    (10, tile_size // 3),
                    watermark_text,
                    font=font_large,
                    fill=(200, 200, 200, opacity),
                    align="center",
                )
                rotated = tile.rotate(45, expand=False)
                watermark_layer.paste(rotated, (x, y), rotated)

        # Composite onto original
        result = Image.alpha_composite(img, watermark_layer).convert("RGB")

        # Return as bytes
        output = io.BytesIO()
        result.save(output, format="JPEG", quality=90)
        return output.getvalue()

    async def generate_preview_screenshot(
        self,
        session_id: uuid.UUID,
        template_thumbnail_url: str,
        user_email: Optional[str] = None,
    ) -> str:
        """
        For Phase 1: applies watermark to the template thumbnail.
        Phase 2 will use headless browser screenshot of actual rendered template.
        """
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(template_thumbnail_url)
            resp.raise_for_status()
            image_bytes = resp.content

        watermarked = self.apply_watermark(image_bytes, user_email=user_email)
        url = await storage.upload_file(
            self.db,
            watermarked,
            folder=f"previews/{session_id}",
            original_filename="preview.jpg",
            content_type="image/jpeg",
        )
        return url
