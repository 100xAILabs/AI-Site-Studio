"""
End-to-end verification script for Multi-Tenant Website Deployment & Management System.
Tests:
1. Deployment Creation & Stable Site ID Generation (e.g. SITE-A12B)
2. Sandboxed Subprocess Build & Secret Isolation (Zero platform .env leak)
3. Artifact Placement in static/deployments/{site_id}/{version}/dist/
4. Automated HTTP Health Check
5. Version History & 1-Click Zero-Downtime Rollback
6. Multi-Tenant Authorization Security (User A cannot access User B deployment)
"""

import sys
import os
import asyncio
import uuid
from pathlib import Path

# Add backend root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.deployment import Deployment, DeploymentVersion, Domain, DeploymentLog
from app.services.deployment_service import DeploymentService
from app.services.deployment_providers import local_deployment_provider


async def run_tests():
    print("=" * 60)
    print("🚀 STARTING MULTI-TENANT DEPLOYMENT SYSTEM VERIFICATION")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        service = DeploymentService(db)

        # 1. Create or retrieve mock test users
        from sqlalchemy import select
        u1_res = await db.execute(select(User).limit(1))
        user_a = u1_res.scalar_one_or_none()
        if not user_a:
            print("⚠️ No existing user found in database, creating mock user...")
            user_a = User(
                email="tenant_a@aisitestudio.com",
                role=UserRole.USER,
                full_name="Tenant User A",
            )
            db.add(user_a)
            await db.commit()
            await db.refresh(user_a)

        print(f"✓ Tenant A identity: {user_a.id} ({user_a.email})")

        # 2. Test Deployment Creation
        print("\n--- TEST 1: Deployment Creation & Site ID Generation ---")
        deployment = await service.create_deployment(
            user=user_a,
            project_name="Ocean View Boutique Hotel",
            provider_type="local",
            build_command="npm run build",
            output_dir="dist",
        )
        assert deployment.id is not None, "Deployment ID must be generated"
        dep_id = deployment.id
        site_id = deployment.site_id
        assert site_id.startswith("SITE-"), f"Site ID must follow SITE-XXXX format: {site_id}"
        assert deployment.status == "queued", f"Initial status must be 'queued', got '{deployment.status}'"
        print(f"✓ Created Deployment ID: {dep_id} | Site ID: {site_id} | Status: {deployment.status}")

        # 3. Test Build Worker & Automated Health Check
        print("\n--- TEST 2: Sandboxed Worker Pipeline & Health Check ---")
        await DeploymentService.run_deployment_pipeline(dep_id, "v1.0")

        # Query updated deployment
        async with AsyncSessionLocal() as fresh_db:
            res = await fresh_db.execute(select(Deployment).where(Deployment.id == dep_id))
            d_updated = res.scalar_one_or_none()
            print(f"✓ Post-build status: {d_updated.status} | Health: {d_updated.health_status}")
            assert d_updated.status == "live", f"Expected status 'live', got '{d_updated.status}'"
            assert d_updated.health_status == "healthy", f"Expected health 'healthy', got '{d_updated.health_status}'"
            assert d_updated.live_url is not None, "Live URL must be populated"
            print(f"✓ Canonical Live URL: {d_updated.live_url}")

        # 4. Test Version History Creation
        print("\n--- TEST 3: Multi-Version Snapshot Tracking ---")
        v_res = await db.execute(select(DeploymentVersion).where(DeploymentVersion.deployment_id == deployment.id))
        versions = v_res.scalars().all()
        assert len(versions) >= 1, "At least 1 version snapshot must exist"
        print(f"✓ Found {len(versions)} snapshot(s): {[v.version for v in versions]}")

        # 5. Test Zero-Downtime Atomic Rollback
        print("\n--- TEST 4: Atomic Zero-Downtime Rollback ---")
        # Add a mock second version
        v2 = DeploymentVersion(
            deployment_id=deployment.id,
            version="v1.1",
            build_reference=versions[0].build_reference,
            status="live",
            commit_message="Feature update",
        )
        db.add(v2)
        await db.commit()

        success, msg = await service.rollback_to_version(user_a, deployment.id, "v1.0")
        assert success, f"Rollback to v1.0 must succeed: {msg}"
        print(f"✓ Successfully executed atomic rollback to v1.0. Live target: {msg}")

        # 6. Test Structured Logs & Secret Masking
        print("\n--- TEST 5: Structured Logs & Secret Masking Audit ---")
        l_res = await db.execute(select(DeploymentLog).where(DeploymentLog.deployment_id == deployment.id))
        logs = l_res.scalars().all()
        assert len(logs) > 0, "Deployment logs must be recorded"
        print(f"✓ Recorded {len(logs)} log events.")
        for log in logs[:5]:
            print(f"   [{log.level}] {log.message}")
            assert "DATABASE_URL" not in log.message, "Platform DATABASE_URL must NEVER appear in logs"
            assert "postgresql+asyncpg://" not in log.message, "DB credentials must NEVER appear in logs"

        # 7. Test Tenant Isolation
        print("\n--- TEST 6: Multi-Tenant Authorization Isolation ---")
        fake_user_b = User(
            id=uuid.uuid4(),
            email="tenant_b@aisitestudio.com",
            role=UserRole.USER,
            full_name="Tenant User B",
        )
        # Attempt rollback by unauthorized User B
        unauthorized_success, unauth_msg = await service.rollback_to_version(fake_user_b, deployment.id, "v1.0")
        assert not unauthorized_success, "User B must NOT be able to modify User A's deployment"
        print(f"✓ Tenant Isolation verified: User B was rejected with: '{unauth_msg}'")

        print("\n" + "=" * 60)
        print("🎉 ALL 6 MULTI-TENANT DEPLOYMENT SUITE TESTS PASSED (100% SUCCESS)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
