"""
Test Suite for Phase 8 Automated Testing & Self-Repair Engine.
Tests:
- Frontend JSX/TSX AST syntax healing & export normalization
- Backend Python AST compilation & syntax repair (missing colons, brackets, fences)
- Route Lifespan conversion & /api/health auto-injection
- Database schema & CRUD query modernization (SQLAlchemy 2.0 async)
- Closed-loop pre-flight test sweep & build failure auto-repair
"""

import ast
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from app.services.debugger_service import ai_debugger
from app.services.deployment_readiness_auditor import deployment_readiness_auditor


@pytest.fixture
def temp_workspace():
    """Isolated temporary workspace for testing pre-flight sweeps and self-repairs."""
    d = tempfile.mkdtemp(prefix="test_self_repair_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class TestFrontendASTHealing:
    """Verifies frontend AST syntax healing and normalization."""

    def test_stray_semicolons_and_unclosed_braces_healed(self):
        broken_jsx = """
        import React from 'react';

        export default function Card({ title, children }) {
            return (
                <div className="card">
                    <h2>{title}</h2>;
                    <div>{children}</div>
                </div>;
            );
        """
        is_valid, healed, msg = ai_debugger.validate_and_heal_frontend_syntax(
            broken_jsx,
            filename="Card.jsx",
            framework="react"
        )
        assert is_valid is True
        # Stray semicolons before closing JSX tags should be stripped
        assert "</h2>;" not in healed
        # Missing closing brace for function should be auto-balanced
        assert healed.count("{") == healed.count("}")

    def test_duplicate_export_default_normalized(self):
        multi_export_jsx = """
        import React from 'react';
        function Header() { return <header>Header</header>; }
        function MainApp() { return <main>Main</main>; }
        export default Header;
        export default MainApp;
        """
        is_valid, healed, msg = ai_debugger.validate_and_heal_frontend_syntax(
            multi_export_jsx,
            filename="App.jsx",
            framework="react"
        )
        assert is_valid is True
        # Should only have one export default at the bottom pointing to the last component
        export_count = healed.count("export default")
        assert export_count == 1
        assert "export default MainApp;" in healed


class TestBackendASTHealing:
    """Verifies Python AST validation and deterministic syntax repair."""

    def test_markdown_fence_stripped_and_ast_parses(self):
        code_with_fences = """```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}
```"""
        is_valid, healed, msg = ai_debugger.validate_and_heal_python_syntax(
            code_with_fences,
            filename="main.py"
        )
        assert is_valid is True
        assert "```" not in healed
        parsed = ast.parse(healed)
        assert parsed is not None

    def test_missing_colons_and_unclosed_brackets_healed(self):
        broken_python = """
def calculate_metrics(values)
    if len(values) > 0
        total = sum(values
        return total
    else
        return 0
"""
        is_valid, healed, msg = ai_debugger.validate_and_heal_python_syntax(
            broken_python,
            filename="metrics.py"
        )
        assert is_valid is True
        # Should parse cleanly without raising SyntaxError
        parsed = ast.parse(healed)
        assert parsed is not None
        assert "def calculate_metrics(values):" in healed
        assert "if len(values) > 0:" in healed
        assert "else:" in healed


class TestRouteLifespanAndHealthSweep:
    """Verifies route and lifespan integrity sweep."""

    def test_startup_event_converted_to_lifespan_and_health_injected(self, temp_workspace):
        backend_dir = temp_workspace / "backend"
        backend_dir.mkdir(parents=True)
        main_py = backend_dir / "main.py"
        main_py.write_text(
            """from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Database connected")

@app.get("/items")
async def get_items():
    return []
""",
            encoding="utf-8"
        )

        report = deployment_readiness_auditor.run_preflight_test_sweep(temp_workspace)
        assert report["passed"] is True

        healed_main = main_py.read_text(encoding="utf-8")
        # Should contain lifespan context manager
        assert "lifespan" in healed_main
        assert "asynccontextmanager" in healed_main
        assert "FastAPI(" in healed_main
        # Should contain mandatory /api/health endpoint
        assert "/api/health" in healed_main
        # Legacy startup event should be removed
        assert '@app.on_event("startup")' not in healed_main


class TestClosedLoopPreflightSweep:
    """End-to-end test of the complete automated pre-flight testing and self-repair sweep."""

    def test_full_project_preflight_sweep_heals_all_layers(self, temp_workspace):
        # 1. Frontend layer with missing viewport, stray hash href, and unclosed tag
        (temp_workspace / "index.html").write_text(
            "<html><head></head><body><a href=\"#\">Link</a></body></html>",
            encoding="utf-8"
        )
        (temp_workspace / "package.json").write_text(
            json.dumps({"name": "demo-app", "dependencies": {}}),
            encoding="utf-8"
        )
        src_dir = temp_workspace / "src"
        src_dir.mkdir()
        (src_dir / "App.jsx").write_text(
            """import React from 'react';
import { Sparkles } from 'lucide-react';

export default function App() {
    return (
        <div>
            <h1>Demo</h1>;
            <Sparkles />;
        </div>
    );
""",
            encoding="utf-8"
        )

        # 2. Backend layer with SQLite database and legacy db.query
        backend_dir = temp_workspace / "backend"
        backend_dir.mkdir()
        (backend_dir / "database.py").write_text(
            'DATABASE_URL = "sqlite+aiosqlite:///./test.db"\n',
            encoding="utf-8"
        )
        (backend_dir / "requirements.txt").write_text(
            "aiosqlite\nfastapi\n",
            encoding="utf-8"
        )

        report = deployment_readiness_auditor.run_preflight_test_sweep(temp_workspace)
        assert report["passed"] is True
        assert report["checks_run"] >= 5
        assert len(report["healed_files"]) >= 3

        # Verify HTML healed
        html_out = (temp_workspace / "index.html").read_text(encoding="utf-8")
        assert '<meta name="viewport"' in html_out
        assert 'href="javascript:void(0)"' in html_out

        # Verify package.json auto-injected lucide-react and build script
        pkg_out = json.loads((temp_workspace / "package.json").read_text(encoding="utf-8"))
        assert "lucide-react" in pkg_out["dependencies"]
        assert "build" in pkg_out["scripts"]

        # Verify database.py converted to PostgreSQL asyncpg
        db_out = (backend_dir / "database.py").read_text(encoding="utf-8")
        assert 'os.environ["DATABASE_URL"]' in db_out

        # Verify requirements.txt converted to asyncpg
        req_out = (backend_dir / "requirements.txt").read_text(encoding="utf-8")
        assert "asyncpg" in req_out
        assert "aiosqlite" not in req_out


class TestCompilerBuildFailureHealing:
    """Tests compiler failure extraction and automated file patching."""

    def test_extract_and_patch_failing_files_from_build_logs(self, temp_workspace):
        src_dir = temp_workspace / "src"
        src_dir.mkdir()
        utils_file = src_dir / "utils.js"
        utils_file.write_text("console.log('utils');\n", encoding="utf-8")

        mock_logs = f"""
        [vite] Internal server error: Failed to resolve import "clsx" from "{utils_file}".
        Error: Cannot find module 'clsx'
        """
        (temp_workspace / "package.json").write_text(
            json.dumps({"dependencies": {}}),
            encoding="utf-8"
        )

        heal_res = deployment_readiness_auditor.diagnose_and_heal_build_failure(
            temp_workspace,
            mock_logs
        )
        assert heal_res["healed"] is True
        pkg_out = json.loads((temp_workspace / "package.json").read_text(encoding="utf-8"))
        assert "clsx" in pkg_out["dependencies"]
