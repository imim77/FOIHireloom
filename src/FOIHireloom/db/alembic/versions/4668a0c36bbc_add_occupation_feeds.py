"""add occupation feeds

Revision ID: 4668a0c36bbc
Revises: 9acbc4dd1c66
Create Date: 2026-10-31 12:00:00.000000
"""

from typing import Sequence

from alembic import op

revision: str = '4668a0c36bbc'
down_revision: str | Sequence[str] | None = '9acbc4dd1c66'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = 'ck_source_feeds_scope_matches_county'


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), 'source_feeds', type_='check')
    op.create_check_constraint(
        op.f(CONSTRAINT), 'source_feeds',
        "(scope = 'county' AND county_id IS NOT NULL) OR (scope IN ('occupation', 'eu') AND county_id IS NULL)",
    )


def downgrade() -> None:
    # The old constraint has no occupation scope, so their feeds and history go.
    occupation_feeds = "SELECT id FROM source_feeds WHERE scope = 'occupation'"
    op.execute(f"DELETE FROM job_feed_memberships WHERE feed_id IN ({occupation_feeds})")
    op.execute(f"DELETE FROM sync_runs WHERE feed_id IN ({occupation_feeds})")
    op.execute("DELETE FROM source_feeds WHERE scope = 'occupation'")
    op.drop_constraint(op.f(CONSTRAINT), 'source_feeds', type_='check')
    op.create_check_constraint(
        op.f(CONSTRAINT), 'source_feeds',
        "(scope = 'county' AND county_id IS NOT NULL) OR (scope = 'eu' AND county_id IS NULL)",
    )
