"""Enable Row Level Security (RLS) on all public tables

Revision ID: f9b8a7c6d5e4
Revises: 084c2fa81110
Create Date: 2026-08-06 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9b8a7c6d5e4'
down_revision: Union[str, None] = '084c2fa81110'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'users',
    'categories',
    'templates',
    'orders',
    'order_items',
    'payments',
    'reviews',
    'wishlist_items',
    'favorites',
    'downloads',
    'ai_history',
    'analytics_events',
    'licenses',
    'follows',
    'preview_sessions',
    'stored_files',
    'deployments',
    'withdrawal_requests',
    'alembic_version',
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;')
    
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'public' AND p.proname = 'handle_updated_at'
            ) THEN
                EXECUTE 'ALTER FUNCTION public.handle_updated_at() SET search_path = public, pg_temp;';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY;')
 