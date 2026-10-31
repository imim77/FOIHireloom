"""add job category source

Revision ID: c4e8a2f6b1d3
Revises: b7d2e5a1c3f9
Create Date: 2026-10-31 20:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4e8a2f6b1d3'
down_revision: str | Sequence[str] | None = 'b7d2e5a1c3f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('category_source', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('category_feed_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f('fk_jobs_category_feed_id_source_feeds'), 'jobs', 'source_feeds',
        ['category_feed_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index(op.f('ix_jobs_category_feed_id'), 'jobs', ['category_feed_id'])
    # Every stored category so far was parsed from the job's description.
    op.execute("UPDATE jobs SET category_source = 'description' WHERE category IS NOT NULL")
    op.create_check_constraint(
        op.f('ck_jobs_category_source_recorded'), 'jobs',
        "(category IS NULL) = (category_source IS NULL) "
        "AND (coalesce(category_source, '') = 'feed') = (category_feed_id IS NOT NULL) "
        "AND coalesce(category_source, 'description') IN ('description', 'feed')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_jobs_category_source_recorded'), 'jobs', type_='check')
    # The old schema cannot tell a filled-in category from a parsed one.
    op.execute("UPDATE jobs SET category = NULL WHERE category_source = 'feed'")
    op.drop_index(op.f('ix_jobs_category_feed_id'), table_name='jobs')
    op.drop_constraint(op.f('fk_jobs_category_feed_id_source_feeds'), 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'category_feed_id')
    op.drop_column('jobs', 'category_source')
