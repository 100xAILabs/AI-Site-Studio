"""
Database Schema Migration Script — Alters `deployments` table in PostgreSQL to ensure all multi-tenant columns exist.
"""

import sys
import os
import asyncio
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import engine, Base
import app.models


async def patch_schema():
    print("Migrating PostgreSQL deployments table...")
    async with engine.begin() as conn:
        # Create all new tables (deployment_versions, domains, deployment_logs, projects)
        await conn.run_sync(Base.metadata.create_all)

        columns = [
            ("site_id", "VARCHAR(50)"),
            ("current_version", "VARCHAR(50) DEFAULT 'v1.0'"),
            ("deployment_type", "VARCHAR(50) DEFAULT 'static'"),
            ("health_status", "VARCHAR(50) DEFAULT 'healthy'"),
            ("deployment_path", "VARCHAR(500)"),
            ("env_vars", "JSON"),
            ("is_suspended", "BOOLEAN DEFAULT FALSE"),
            ("custom_domain", "VARCHAR(255)"),
        ]

        for col_name, col_type in columns:
            try:
                sql = f"ALTER TABLE deployments ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                await conn.execute(text(sql))
                print(f"✓ Ensured column '{col_name}' exists in deployments table.")
            except Exception as e:
                print(f"⚠️ Column {col_name}: {e}")

    print("✅ Schema patch applied successfully.")


if __name__ == "__main__":
    asyncio.run(patch_schema())
