"""add template status enum values

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-17 21:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to PostgreSQL templatestatus enum
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        status_values = [
            'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED', 'SUSPENDED', 'ARCHIVED',
            'draft', 'submitted', 'under_review', 'approved', 'rejected', 'published', 'suspended', 'archived',
        ]
        for val in status_values:
            try:
                op.execute(sa.text(f"ALTER TYPE templatestatus ADD VALUE IF NOT EXISTS '{val}';"))
            except Exception:
                pass


def downgrade() -> None:
    pass
