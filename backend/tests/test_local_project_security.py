import io
import zipfile

import pytest

from app.core.local_project_manager import LocalProjectManager, _clean_rel_path


def test_project_paths_reject_traversal_and_windows_absolute_paths():
    assert _clean_rel_path("assets/logo.png") == "assets/logo.png"
    assert _clean_rel_path("../../outside.txt") == ""
    assert _clean_rel_path(r"..\outside.txt") == ""
    assert _clean_rel_path(r"C:\outside.txt") == ""
    assert _clean_rel_path("assets:stream.txt") == ""


def test_project_save_cannot_write_outside_project_root(tmp_path):
    manager = LocalProjectManager(tmp_path / "projects")
    manager.save_initial_project(
        "project-1",
        "safe-project",
        {"index.html": "ok", "../../outside.txt": "no", r"C:\outside.txt": "no"},
    )

    assert (tmp_path / "projects" / "safe-project" / "latest" / "index.html").read_text() == "ok"
    assert not (tmp_path / "outside.txt").exists()


def test_project_identifiers_cannot_escape_base_directory(tmp_path):
    manager = LocalProjectManager(tmp_path / "projects")
    result = manager._resolve_project_dir("../../outside")
    assert result.parent == manager.base_dir


def test_zip_unpack_rejects_traversal_before_writing(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../outside.txt", "no")

    manager = LocalProjectManager(tmp_path / "projects")
    with pytest.raises(ValueError, match="unsafe file path"):
        manager.unpack_zip_bytes_to_local("project-1", "safe-project", archive.getvalue())
    assert not (tmp_path / "outside.txt").exists()


def test_zip_unpack_rejects_expansion_bombs(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("large.txt", b"A" * (2 * 1024 * 1024))

    manager = LocalProjectManager(tmp_path / "projects")
    with pytest.raises(ValueError, match="compression ratio"):
        manager.unpack_zip_bytes_to_local("project-1", "safe-project", archive.getvalue())

