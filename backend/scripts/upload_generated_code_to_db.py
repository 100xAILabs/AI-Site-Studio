import asyncio
import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.core.database import AsyncSessionLocal
from app.core.storage import storage
from app.models.template import Template, TemplateStatus
from sqlalchemy import select

PROJECT_SRC = Path(backend_root.parent) / "generated_projects" / "rr-residency-website-plan-90bce052" / "latest"

async def main():
    if not PROJECT_SRC.exists():
        raise FileNotFoundError(f"Project source folder not found at: {PROJECT_SRC}")

    print(f"[1/6] Building ZIP archive from: {PROJECT_SRC}")
    zip_buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_SRC):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(PROJECT_SRC)
                zf.write(full_path, arcname=str(rel_path).replace("\\", "/"))
                file_count += 1
                print(f"  + Added: {rel_path}")

    zip_bytes = zip_buffer.getvalue()
    print(f"Total files packaged: {file_count} (Archive size: {len(zip_bytes)} bytes)")

    async with AsyncSessionLocal() as db:
        print("[2/6] Uploading ZIP archive to Studio storage...")
        zip_url = await storage.upload_file(
            db=db,
            file_content=zip_bytes,
            folder="templates",
            original_filename="rr-residency-luxury-hotel.zip",
            content_type="application/zip",
        )
        print(f"Uploaded successfully! Asset URL: {zip_url}")

        # Update templates
        target_ids = [
            "e07e9089-9a48-4e9c-80d2-39ac564d655f",  # Luxury Hotel - Exclusive Accommodations (previous)
            "4f91805b-8a5b-4757-9a1c-962705c6bbb1",  # RR Residency Website Plan (current studio project)
        ]

        hero_thumb = "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80"
        pages = ["Home", "Rooms & Suites", "Dining & Restaurant", "Amenities", "Contact & Location"]

        print("[3/6] Updating template records in database...")
        for tid in target_ids:
            template = await db.get(Template, tid)
            if not template:
                print(f"  Warning: Template with ID {tid} not found.")
                continue

            print(f"  Updating template: '{template.title}' (ID: {template.id})")
            template.download_assets = {"html": zip_url, "zip": zip_url}
            template.pages_count = 5
            template.included_pages = pages
            template.thumbnail_url = hero_thumb
            template.status = TemplateStatus.PUBLISHED

            if tid == "e07e9089-9a48-4e9c-80d2-39ac564d655f":
                template.title = "Luxury Hotel - RR Residency Exclusive Accommodations"
                template.short_description = "A premium 5-page luxury hotel and resort website featuring unified navigation, dining reservations, suites, and tranquil amenities."

        await db.commit()
        print("[4/6] Database transaction committed successfully!")

    # Write pointer files in generated_projects
    gen_dir = PROJECT_SRC.parent.parent
    print(f"[5/6] Creating local project pointer files in: {gen_dir}")
    pointers = [
        gen_dir / ".id_e07e9089-9a48-4e9c-80d2-39ac564d655f.txt",
        gen_dir / ".id_luxury-hotel-exclusive-accommodations.txt",
        gen_dir / ".id_4f91805b-8a5b-4757-9a1c-962705c6bbb1.txt",
        gen_dir / ".id_rr-residency-website-plan-90bce052.txt",
    ]
    for p in pointers:
        p.write_text("rr-residency-website-plan-90bce052", encoding="utf-8")
        print(f"  + Pointer created: {p.name} -> rr-residency-website-plan-90bce052")

    # Clear preview temp cache
    print("[6/6] Clearing cached live preview temporary directories...")
    temp_preview_base = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews"
    if temp_preview_base.exists():
        for tid in target_ids:
            p_dir = temp_preview_base / tid
            if p_dir.exists():
                shutil.rmtree(p_dir, ignore_errors=True)
                print(f"  Cleared temp cache for {tid}")

    # Invalidate fast_catalog cache
    try:
        from app.services.fast_catalog import fast_catalog
        fast_catalog.invalidate()
        print("  Fast catalog cache invalidated.")
    except Exception as e:
        print(f"  Fast catalog invalidation note: {e}")

    print("\nAll tasks completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

