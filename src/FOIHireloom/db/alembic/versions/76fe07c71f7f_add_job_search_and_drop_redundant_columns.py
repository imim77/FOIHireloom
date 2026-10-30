"""add job search and drop redundant columns

Revision ID: 76fe07c71f7f
Revises: 1981498b73b5
Create Date: 2026-10-29 18:02:35.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Frozen copy of Job.search_vector's expression at this revision. translate()
# folds Croatian letters to ASCII and splits words joined by "/" or ".";
# unaccent() is not immutable, so it cannot appear in a generated column.
SEARCH_DOCUMENT = (
    "to_tsvector('simple'::regconfig, translate("
    "coalesce(title, '') || ' ' || coalesce(description_text, ''), "
    "'ČĆŽŠĐčćžšđ/.', 'CCZSDcczsd  '))"
)

revision: str = '76fe07c71f7f'
down_revision: str | Sequence[str] | None = '1981498b73b5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('municipality', sa.Text(), nullable=True))
    # Existing rows keep their content hash, so sync would never rewrite them.
    op.execute(
        "UPDATE jobs SET municipality = "
        "nullif(btrim(substring(description_raw FROM ', Općina: (.*?), Županija: ')), '')"
    )
    op.add_column('jobs', sa.Column(
        'search_vector', postgresql.TSVECTOR(), sa.Computed(SEARCH_DOCUMENT, persisted=True), nullable=True,
    ))
    op.create_index('ix_jobs_search_vector', 'jobs', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_jobs_category'), 'jobs', ['category'], unique=False)
    op.drop_column('jobs', 'subject')
    op.drop_column('jobs', 'source_guid')
    op.drop_constraint(
        op.f('ck_job_feed_memberships_source_item_is_object'), 'job_feed_memberships', type_='check'
    )
    op.drop_column('job_feed_memberships', 'source_item')


def downgrade() -> None:
    op.add_column('job_feed_memberships', sa.Column(
        'source_item', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"), nullable=False,
    ))
    op.alter_column('job_feed_memberships', 'source_item', server_default=None)
    op.create_check_constraint(
        op.f('ck_job_feed_memberships_source_item_is_object'), 'job_feed_memberships',
        "jsonb_typeof(source_item) = 'object'",
    )
    op.add_column('jobs', sa.Column('source_guid', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('subject', sa.Text(), nullable=True))
    op.execute(
        "UPDATE jobs SET subject = title, "
        "source_guid = regexp_replace(canonical_url, '^https://', 'http://')"
    )
    op.drop_index(op.f('ix_jobs_category'), table_name='jobs')
    op.drop_index('ix_jobs_search_vector', table_name='jobs', postgresql_using='gin')
    op.drop_column('jobs', 'search_vector')
    op.drop_column('jobs', 'municipality')
