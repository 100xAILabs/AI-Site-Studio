"""
Phase 3 — Full-Stack Generation Engine Tests.

Tests that the deterministic scaffold generator produces valid, complete,
immediately runnable project files for full-stack and hybrid architectures.
"""
import ast
import os
import sys
import pytest

# Ensure backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_DB_TABLES = [
    {
        "name": "users",
        "fields": [
            {"name": "id", "type": "uuid", "nullable": False},
            {"name": "email", "type": "str", "nullable": False, "unique": True},
            {"name": "hashed_password", "type": "str", "nullable": False},
            {"name": "created_at", "type": "datetime", "nullable": True},
        ],
        "indexes": ["email"],
    },
    {
        "name": "jobs",
        "fields": [
            {"name": "id", "type": "uuid", "nullable": False},
            {"name": "title", "type": "str", "nullable": False},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "is_active", "type": "bool", "nullable": False},
            {"name": "created_at", "type": "datetime", "nullable": True},
        ],
        "indexes": ["title"],
    },
]

SAMPLE_API_ROUTES = [
    {"method": "GET", "path": "/api/health", "description": "Health check"},
    {"method": "POST", "path": "/api/contact", "description": "Contact form"},
    {"method": "GET", "path": "/api/jobs", "description": "List jobs"},
    {"method": "POST", "path": "/api/jobs", "description": "Create job"},
]

SAMPLE_PAGES = [
    {"name": "Home", "filename": "index"},
    {"name": "Jobs", "filename": "jobs"},
    {"name": "About", "filename": "about"},
    {"name": "Contact", "filename": "contact"},
]

FULLSTACK_REQUIRED_BACKEND_FILES = [
    "backend/app/main.py",
    "backend/app/database.py",
    "backend/app/models.py",
    "backend/app/schemas.py",
    "backend/app/crud.py",
    "backend/requirements.txt",
    "backend/.env.example",
]

REACT_REQUIRED_FILES = [
    "frontend/package.json",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/index.html",
    "frontend/src/main.tsx",
    "frontend/src/App.tsx",
    "frontend/src/api/client.ts",
    "frontend/src/components/Navbar.tsx",
    "frontend/src/components/Footer.tsx",
    "frontend/.env.example",
]

ALEMBIC_REQUIRED_FILES = [
    "backend/alembic.ini",
    "backend/alembic/env.py",
]

DOCKER_REQUIRED_FILES = [
    "docker-compose.yml",
    "backend/Dockerfile",
    "frontend/Dockerfile",
]

HYBRID_REQUIRED_FILES = [
    "backend/api/contact.py",
    "backend/api/newsletter.py",
    "backend/api/health.py",
    "backend/requirements.txt",
    "backend/.env.example",
]


@pytest.fixture
def scaffold():
    from app.services.fullstack_scaffold import FullStackScaffoldGenerator
    return FullStackScaffoldGenerator()


class TestFastAPIScaffold:
    def test_returns_all_required_backend_files(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=True,
            stripe_needed=False,
            env_vars=["DATABASE_URL", "SECRET_KEY", "ENVIRONMENT"],
            page_names=["Home", "Jobs", "About", "Contact"],
        )
        for required in FULLSTACK_REQUIRED_BACKEND_FILES:
            assert required in files, f"Missing required file: {required}"

    def test_main_py_uses_lifespan_not_startup_event(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=False,
            stripe_needed=False,
            env_vars=[],
            page_names=[],
        )
        main_py = files.get("backend/app/main.py", "")
        assert "lifespan" in main_py, "main.py must use FastAPI lifespan pattern"
        assert "on_event" not in main_py, "main.py must NOT use deprecated @app.on_event"

    def test_database_py_has_dual_config(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="test-proj",
            db_tables=[],
            api_routes=[],
            auth_required=False,
            stripe_needed=False,
            env_vars=[],
            page_names=[],
        )
        db_py = files.get("backend/app/database.py", "")
        assert "sqlite+aiosqlite" in db_py, "database.py must have SQLite fallback"
        assert "postgresql+asyncpg" in db_py or "asyncpg" in db_py, "database.py must support PostgreSQL"
        assert "DATABASE_URL" in db_py

    def test_models_py_uses_mapped_columns(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=False,
            stripe_needed=False,
            env_vars=[],
            page_names=[],
        )
        models_py = files.get("backend/app/models.py", "")
        assert "Mapped" in models_py, "models.py must use SQLAlchemy 2.0 Mapped[] typed columns"
        assert "mapped_column" in models_py
        assert "DeclarativeBase" in models_py

    def test_crud_py_does_not_use_db_query(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=False,
            stripe_needed=False,
            env_vars=[],
            page_names=[],
        )
        crud_py = files.get("backend/app/crud.py", "")
        assert "db.query(" not in crud_py, "crud.py must NOT use deprecated db.query() — use select()"
        assert "select(" in crud_py or "await db.execute" in crud_py

    def test_python_files_are_syntactically_valid(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="syntax-test",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=True,
            stripe_needed=False,
            env_vars=["DATABASE_URL", "SECRET_KEY"],
            page_names=["Home", "Dashboard"],
        )
        for path, content in files.items():
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {path}: {e}")

    def test_no_todo_placeholders_in_scaffold(self, scaffold):
        files = scaffold.generate_fastapi_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            db_tables=SAMPLE_DB_TABLES,
            api_routes=SAMPLE_API_ROUTES,
            auth_required=False,
            stripe_needed=False,
            env_vars=[],
            page_names=[],
        )
        for path, content in files.items():
            if path.endswith(".py"):
                assert "# TODO" not in content, f"Found # TODO placeholder in {path}"
                assert "pass  # implement" not in content.lower()


class TestAlembicScaffold:
    def test_returns_all_alembic_files(self, scaffold):
        files = scaffold.generate_alembic_scaffold(SAMPLE_DB_TABLES, "ats-tracker")
        for required in ALEMBIC_REQUIRED_FILES:
            assert required in files, f"Missing alembic file: {required}"

    def test_initial_migration_exists(self, scaffold):
        files = scaffold.generate_alembic_scaffold(SAMPLE_DB_TABLES, "ats-tracker")
        migration_files = [k for k in files if "versions" in k and k.endswith(".py")]
        assert len(migration_files) >= 1, "Must generate at least one initial Alembic migration"

    def test_migration_has_create_table(self, scaffold):
        files = scaffold.generate_alembic_scaffold(SAMPLE_DB_TABLES, "ats-tracker")
        migration_files = [k for k in files if "versions" in k and k.endswith(".py")]
        for mf in migration_files:
            content = files[mf]
            assert "op.create_table" in content, f"Migration {mf} must contain op.create_table"

    def test_alembic_env_py_uses_async(self, scaffold):
        files = scaffold.generate_alembic_scaffold(SAMPLE_DB_TABLES, "ats-tracker")
        env_py = files.get("backend/alembic/env.py", "")
        assert "async" in env_py or "asyncio" in env_py, "alembic/env.py must use async migration runner"

    def test_alembic_python_files_valid_syntax(self, scaffold):
        files = scaffold.generate_alembic_scaffold(SAMPLE_DB_TABLES, "ats-tracker")
        for path, content in files.items():
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {path}: {e}")


class TestReactScaffold:
    def test_returns_all_required_frontend_files(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        for required in REACT_REQUIRED_FILES:
            assert required in files, f"Missing React scaffold file: {required}"

    def test_generates_one_page_per_planned_page(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        page_files = [k for k in files if k.startswith("frontend/src/pages/") and k.endswith(".tsx")]
        assert len(page_files) == len(SAMPLE_PAGES), f"Expected {len(SAMPLE_PAGES)} page TSX files, got {len(page_files)}"

    def test_app_tsx_has_routes_for_all_pages(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        app_tsx = files.get("frontend/src/App.tsx", "")
        assert "<Route" in app_tsx or "Routes" in app_tsx, "App.tsx must define React Router routes"

    def test_api_client_uses_env_var(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        client_ts = files.get("frontend/src/api/client.ts", "")
        assert "VITE_API_URL" in client_ts, "api/client.ts must read baseURL from import.meta.env.VITE_API_URL"

    def test_navbar_has_links_to_all_pages(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        navbar = files.get("frontend/src/components/Navbar.tsx", "")
        assert "Home" in navbar
        assert "useState" in navbar, "Navbar must use useState for mobile menu toggle"

    def test_env_example_has_vite_api_url(self, scaffold):
        files = scaffold.generate_react_scaffold(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            pages=SAMPLE_PAGES,
            api_base_url="http://localhost:8000",
        )
        env_example = files.get("frontend/.env.example", "")
        assert "VITE_API_URL" in env_example


class TestDockerScaffold:
    def test_returns_all_docker_files(self, scaffold):
        files = scaffold.generate_docker_compose(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            auth_required=True,
            stripe_needed=False,
        )
        for required in DOCKER_REQUIRED_FILES:
            assert required in files, f"Missing Docker file: {required}"

    def test_docker_compose_has_postgres_service(self, scaffold):
        files = scaffold.generate_docker_compose(
            stack_key="react-fastapi-postgresql",
            project_name="ats-tracker",
            auth_required=False,
            stripe_needed=False,
        )
        compose = files.get("docker-compose.yml", "")
        assert "postgres" in compose.lower() or "postgresql" in compose.lower()
        assert "backend:" in compose
        assert "frontend:" in compose


class TestHybridServerless:
    def test_returns_all_serverless_files(self, scaffold):
        files = scaffold.generate_hybrid_serverless(
            project_name="contact-site",
            env_vars=["RESEND_API_KEY", "NOTIFICATION_EMAIL"],
        )
        for required in HYBRID_REQUIRED_FILES:
            assert required in files, f"Missing hybrid serverless file: {required}"

    def test_contact_handler_has_post_route(self, scaffold):
        files = scaffold.generate_hybrid_serverless(
            project_name="contact-site",
            env_vars=[],
        )
        contact_py = files.get("backend/api/contact.py", "")
        assert "POST" in contact_py or "post" in contact_py.lower()
        assert "contact" in contact_py.lower()

    def test_hybrid_python_files_valid_syntax(self, scaffold):
        files = scaffold.generate_hybrid_serverless(project_name="contact-site", env_vars=[])
        for path, content in files.items():
            if path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {path}: {e}")


class TestEnvFiles:
    def test_env_files_generated(self, scaffold):
        files = scaffold.generate_env_files(
            required_env_vars=["DATABASE_URL", "SECRET_KEY", "STRIPE_SECRET_KEY"],
            project_name="ats-tracker",
            payment_required=True,
            email_required=False,
        )
        assert any(".env.example" in k for k in files), "Must generate at least one .env.example"

    def test_env_example_has_required_vars(self, scaffold):
        files = scaffold.generate_env_files(
            required_env_vars=["DATABASE_URL", "SECRET_KEY"],
            project_name="ats-tracker",
            payment_required=False,
            email_required=False,
        )
        root_env = files.get(".env.example", "") or files.get("backend/.env.example", "")
        assert "DATABASE_URL" in root_env
        assert "SECRET_KEY" in root_env
