"""
Local Project Manager — Persists generated and edited projects directly to the local filesystem.

Ensures that every project created or edited by Studio is saved locally on disk in the
workspace, keeping separate 'before_edit' (original) and 'after_edit' (revisions) folders.

Directory Layout:
  generated_projects/
    └── <slug_or_id>/
        ├── metadata.json
        ├── before_edit/          # Initial generated code (preserved permanently)
        ├── latest/               # Current working version (served by live preview)
        └── revisions/            # Snapshot saved on each conversational iteration
            ├── rev_001_<ts>/
            └── rev_002_<ts>/
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Root workspace directory: d:\Projects\Official\AI-Site-Studio-main\AI-Site-Studio-main
BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = BACKEND_DIR.parent
GENERATED_PROJECTS_DIR = WORKSPACE_ROOT / "generated_projects"


def _clean_rel_path(path: str) -> str:
    """Normalize and sanitize relative file paths."""
    clean = path.replace("\\", "/").lstrip("/")
    parts = [p for p in clean.split("/") if p and p not in (".", "..")]
    return "/".join(parts)


class LocalProjectManager:
    def __init__(self, base_dir: Path = GENERATED_PROJECTS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_project_dir(self, identifier: str) -> Path:
        """Find an existing folder by slug or template_id, or return the standard path."""
        clean_id = str(identifier).strip()
        direct = self.base_dir / clean_id
        if direct.exists() and direct.is_dir():
            return direct

        # Search for matching metadata
        for sub in self.base_dir.iterdir():
            if sub.is_dir():
                meta_file = sub / "metadata.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8-sig"))
                        if str(meta.get("template_id")) == clean_id or meta.get("slug") == clean_id:
                            return sub
                    except Exception:
                        pass
        return direct

    def save_initial_project(
        self,
        template_id: UUID | str,
        slug: str,
        files: dict[str, str | bytes],
        title: str = "",
        stack: str = "html-css-js",
        extra_meta: Optional[dict[str, Any]] = None,
    ) -> Path:
        """
        Store the initial generated project into 'before_edit/' and 'latest/'.
        """
        project_folder_name = slug or str(template_id)
        project_dir = self.base_dir / project_folder_name
        before_edit_dir = project_dir / "before_edit"
        latest_dir = project_dir / "latest"

        before_edit_dir.mkdir(parents=True, exist_ok=True)
        latest_dir.mkdir(parents=True, exist_ok=True)

        # Write files into both before_edit and latest
        for rel_path, content in files.items():
            safe_rel = _clean_rel_path(rel_path)
            if not safe_rel:
                continue

            for target_base in (before_edit_dir, latest_dir):
                dest = target_base / safe_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str):
                    dest.write_text(content, encoding="utf-8", errors="replace")
                else:
                    dest.write_bytes(content)

        # Also create a quick template_id pointer folder if slug was used
        if slug and str(template_id) != slug:
            id_alias_file = self.base_dir / f".id_{str(template_id)}.txt"
            try:
                id_alias_file.write_text(slug, encoding="utf-8")
            except Exception:
                pass

        # Write metadata.json
        meta = {
            "template_id": str(template_id),
            "slug": slug,
            "title": title or slug,
            "stack": stack,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "current_revision": 0,
            "revisions": [
                {
                    "revision": 0,
                    "type": "initial_generation",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_count": len(files),
                }
            ],
            **(extra_meta or {}),
        }
        (project_dir / "metadata.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[LocalProjectManager] Stored initial project '%s' (%d files) at %s", slug, len(files), project_dir)
        return project_dir

    def save_project_revision(
        self,
        template_id: UUID | str,
        files: dict[str, str | bytes],
        instruction: str = "",
        slug: str = "",
    ) -> Path:
        """
        Save an updated project snapshot to 'revisions/rev_XXX_<ts>/' and update 'latest/'.
        Preserves 'before_edit/' untouched.
        """
        project_dir = self._resolve_project_dir(slug or str(template_id))
        if not project_dir.exists():
            return self.save_initial_project(template_id, slug or str(template_id), files)

        meta_file = project_dir / "metadata.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            except Exception:
                pass

        rev_num = int(meta.get("current_revision", 0)) + 1
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rev_folder_name = f"rev_{rev_num:03d}_{ts_slug}"

        rev_dir = project_dir / "revisions" / rev_folder_name
        latest_dir = project_dir / "latest"
        rev_dir.mkdir(parents=True, exist_ok=True)
        latest_dir.mkdir(parents=True, exist_ok=True)

        # Write files into revision folder and update latest
        for rel_path, content in files.items():
            safe_rel = _clean_rel_path(rel_path)
            if not safe_rel:
                continue

            for target_base in (rev_dir, latest_dir):
                dest = target_base / safe_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str):
                    dest.write_text(content, encoding="utf-8", errors="replace")
                else:
                    dest.write_bytes(content)

        # Update metadata.json
        meta["current_revision"] = rev_num
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        rev_list = meta.setdefault("revisions", [])
        rev_list.append(
            {
                "revision": rev_num,
                "folder": rev_folder_name,
                "instruction": instruction[:300],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "file_count": len(files),
            }
        )
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("[LocalProjectManager] Saved revision %d (%s) for project '%s'", rev_num, rev_folder_name, project_dir.name)
        return project_dir

    def get_local_project_dir(
        self,
        identifier: UUID | str,
        version: str = "latest",
    ) -> Optional[Path]:
        """
        Return the directory Path for a project version:
          version="latest"      -> current working version (served in preview)
          version="before_edit" -> original untouched version
        """
        clean_id = str(identifier).strip()

        # Check for pointer file
        alias_file = self.base_dir / f".id_{clean_id}.txt"
        if alias_file.exists():
            try:
                clean_id = alias_file.read_text(encoding="utf-8-sig").strip()
            except Exception:
                pass

        project_dir = self._resolve_project_dir(clean_id)
        if not project_dir.exists():
            return None

        target = project_dir / version
        if target.exists() and target.is_dir():
            return target
        return project_dir if (project_dir / "index.html").exists() else None

    def unpack_zip_bytes_to_local(
        self,
        template_id: UUID | str,
        slug: str,
        zip_bytes: bytes,
        title: str = "",
        stack: str = "html-css-js",
        is_initial: bool = True,
        instruction: str = "",
    ) -> Path:
        """Helper to unpack an in-memory ZIP and save it to local storage."""
        files: dict[str, str | bytes] = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                data = zf.read(name)
                # Attempt utf-8 decoding for text files
                if any(name.endswith(ext) for ext in (
                    ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".json",
                    ".py", ".md", ".txt", ".env", ".yml", ".yaml", ".ini", ".toml"
                )):
                    try:
                        files[name] = data.decode("utf-8")
                    except UnicodeDecodeError:
                        files[name] = data
                else:
                    files[name] = data

        if is_initial:
            return self.save_initial_project(template_id, slug, files, title=title, stack=stack)
        return self.save_project_revision(template_id, files, instruction=instruction, slug=slug)

    def list_project_assets(self, identifier: UUID | str) -> list[dict[str, Any]]:
        """
        List all image/media assets located in the project's 'latest/' directory.
        Returns a list of asset descriptors with role, dimensions, and format guidance.
        """
        latest_dir = self.get_local_project_dir(identifier, version="latest")
        if not latest_dir or not latest_dir.exists():
            return []

        image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico"}
        assets: list[dict[str, Any]] = []

        for root, _, files in os.walk(latest_dir):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in image_extensions:
                    full_path = Path(root) / filename
                    rel_path = full_path.relative_to(latest_dir).as_posix()

                    # Ignore internal git or build artifacts
                    if any(part in rel_path.split("/") for part in (".git", "node_modules", "dist", "build")):
                        continue

                    size_bytes = full_path.stat().st_size
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                    stem_lower = full_path.stem.lower()
                    if any(k in stem_lower for k in ("profile", "portrait", "avatar", "person", "headshot", "owner")):
                        role = "Profile / Portrait Photo"
                        format_hint = "PNG, JPG, or WebP"
                        dim_hint = "Square (1:1, 800 × 800px)"
                    elif "logo" in stem_lower:
                        role = "Brand Logo"
                        format_hint = "PNG or SVG (Transparent)"
                        dim_hint = "Recommended 400 × 120px"
                    elif any(k in stem_lower for k in ("hero", "banner", "cover", "bg", "background")):
                        role = "Hero / Banner Image"
                        format_hint = "JPG, WebP, or PNG"
                        dim_hint = "Landscape (16:9, 1200 × 675px)"
                    elif any(k in stem_lower for k in ("project", "work", "portfolio", "item")):
                        role = "Portfolio / Showcase Image"
                        format_hint = "JPG, WebP, or PNG"
                        dim_hint = "Landscape (4:3 or 16:9)"
                    else:
                        role = "Content Image"
                        format_hint = "PNG, JPG, or WebP"
                        dim_hint = "Standard resolution"

                    assets.append({
                        "filename": filename,
                        "rel_path": rel_path,
                        "size_bytes": size_bytes,
                        "size_str": size_str,
                        "extension": ext,
                        "role": role,
                        "format_hint": format_hint,
                        "dim_hint": dim_hint,
                        "updated_at": datetime.fromtimestamp(full_path.stat().st_mtime, timezone.utc).isoformat(),
                    })

        def _sort_key(item: dict[str, Any]) -> int:
            r = item["role"]
            if "Profile" in r:
                return 0
            if "Logo" in r:
                return 1
            if "Hero" in r:
                return 2
            if "Portfolio" in r:
                return 3
            return 4

        assets.sort(key=_sort_key)
        return assets

    def replace_project_asset(
        self,
        identifier: UUID | str,
        rel_path: str,
        new_bytes: bytes,
    ) -> dict[str, Any]:
        """
        Overwrite an asset in-place in 'latest/' without modifying code.
        Preserves 'before_edit/' untouched and writes an entry into 'revisions/'.
        """
        clean_rel = _clean_rel_path(rel_path)
        project_dir = self._resolve_project_dir(str(identifier).strip())
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory for '{identifier}' not found")

        latest_dest = project_dir / "latest" / clean_rel
        latest_dest.parent.mkdir(parents=True, exist_ok=True)
        latest_dest.write_bytes(new_bytes)

        # Snapshot in revisions folder
        meta_file = project_dir / "metadata.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            except Exception:
                pass

        rev_num = int(meta.get("current_revision", 0)) + 1
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rev_folder_name = f"rev_{rev_num:03d}_{ts_slug}_asset_replace"
        rev_dest = project_dir / "revisions" / rev_folder_name / clean_rel
        rev_dest.parent.mkdir(parents=True, exist_ok=True)
        rev_dest.write_bytes(new_bytes)

        meta["current_revision"] = rev_num
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        rev_list = meta.setdefault("revisions", [])
        rev_list.append({
            "revision": rev_num,
            "folder": rev_folder_name,
            "instruction": f"Replaced photo asset '{clean_rel}' (zero code changes)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_count": 1,
        })
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # Also update any active temp preview cache
        import tempfile
        temp_dest = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews" / str(identifier) / clean_rel
        if temp_dest.parent.exists():
            try:
                temp_dest.write_bytes(new_bytes)
            except Exception:
                pass

        return {
            "success": True,
            "rel_path": clean_rel,
            "size_bytes": len(new_bytes),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


    def purge_demo_website_data(
        self,
        identifier,
        wipe_reason: str = "timeout_30m",
    ):
        """
        Permanently purge all data, user edits, uploaded assets, and revisions
        created during a live demo session on the generated website.

        Strictly resets 'latest/' back to the pristine 'before_edit/' state,
        deletes all 'revisions/', removes any database files created in the generated project,
        and purges temp live preview caches in tempfile.
        Ensures ONLY the generated website data is touched.
        """
        import tempfile
        clean_id = str(identifier).strip()
        project_dir = self._resolve_project_dir(clean_id)

        result = {
            "identifier": clean_id,
            "project_found": False,
            "revisions_deleted": 0,
            "restored_from_before_edit": False,
            "temp_cache_cleared": False,
            "wipe_reason": wipe_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if project_dir.exists() and project_dir.is_dir():
            result["project_found"] = True
            before_edit_dir = project_dir / "before_edit"
            latest_dir = project_dir / "latest"
            revisions_dir = project_dir / "revisions"

            # 1. Delete all revisions generated during the session
            if revisions_dir.exists() and revisions_dir.is_dir():
                try:
                    rev_count = len(list(revisions_dir.iterdir()))
                    shutil.rmtree(revisions_dir, ignore_errors=True)
                    revisions_dir.mkdir(parents=True, exist_ok=True)
                    result["revisions_deleted"] = rev_count
                    logger.info("[LocalProjectManager] Purged %d revisions for %s", rev_count, clean_id)
                except Exception as e:
                    logger.error("[LocalProjectManager] Failed to clear revisions: %s", e)

            # 2. Reset 'latest/' back to 'before_edit/' pristine snapshot
            if before_edit_dir.exists() and before_edit_dir.is_dir():
                try:
                    if latest_dir.exists():
                        shutil.rmtree(latest_dir, ignore_errors=True)
                    shutil.copytree(before_edit_dir, latest_dir)
                    result["restored_from_before_edit"] = True
                    logger.info("[LocalProjectManager] Restored latest/ from before_edit/ for %s", clean_id)
                except Exception as e:
                    logger.error("[LocalProjectManager] Failed to restore before_edit: %s", e)

            # 3. Clean up any db or sqlite files that might have been created inside the project
            if latest_dir.exists():
                for db_file in latest_dir.rglob("*.db"):
                    try:
                        db_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                for db_file in latest_dir.rglob("*.sqlite*"):
                    try:
                        db_file.unlink(missing_ok=True)
                    except Exception:
                        pass

            # 4. Reset metadata.json
            meta_file = project_dir / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8-sig"))
                    meta["current_revision"] = 0
                    meta["revisions"] = [r for r in meta.get("revisions", []) if r.get("revision") == 0]
                    meta["last_demo_wipe"] = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": wipe_reason,
                    }
                    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception as e:
                    logger.warning("[LocalProjectManager] Could not update metadata.json after wipe: %s", e)

        # 5. Clear temp live preview directories
        temp_preview_base = Path(tempfile.gettempdir()) / "ai_site_studio" / "live_previews"
        if temp_preview_base.exists():
            targets = [clean_id]
            if project_dir.exists():
                targets.append(project_dir.name)
            for target_name in targets:
                target_dir = temp_preview_base / target_name
                if target_dir.exists():
                    try:
                        shutil.rmtree(target_dir, ignore_errors=True)
                        result["temp_cache_cleared"] = True
                        logger.info("[LocalProjectManager] Purged temp preview cache at %s", target_dir)
                    except Exception as e:
                        logger.warning("[LocalProjectManager] Failed to clear temp preview cache: %s", e)

        return result


local_project_manager = LocalProjectManager()

