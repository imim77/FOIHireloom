"""search job page text

Revision ID: 9acbc4dd1c66
Revises: adc0c83dfede
Create Date: 2026-10-30 14:10:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9acbc4dd1c66'
down_revision: str | Sequence[str] | None = 'adc0c83dfede'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of Job.search_vector's expression after and before this
# revision. Title words get weight A, so a query restricted to them tells
# whether the title matched.
SEARCH_DOCUMENT = (
    "setweight(to_tsvector('simple'::regconfig, translate("
    "coalesce(page_title, title, ''), 'ČĆŽŠĐčćžšđ/.', 'CCZSDcczsd  ')), 'A') || "
    "to_tsvector('simple'::regconfig, translate("
    "coalesce(page_description_text, description_text, '') || ' ' || coalesce(page_employer_name, '') || ' ' || "
    "coalesce(page_work_place, '') || ' ' || coalesce(page_education, ''), "
    "'ČĆŽŠĐčćžšđ/.', 'CCZSDcczsd  '))"
)
PREVIOUS_SEARCH_DOCUMENT = (
    "to_tsvector('simple'::regconfig, translate("
    "coalesce(title, '') || ' ' || coalesce(description_text, ''), "
    "'ČĆŽŠĐčćžšđ/.', 'CCZSDcczsd  '))"
)


def _replace_search_vector(expression: str) -> None:
    # SET EXPRESSION needs PostgreSQL 17, so the column is rebuilt instead.
    op.drop_index('ix_jobs_search_vector', table_name='jobs', postgresql_using='gin')
    op.drop_column('jobs', 'search_vector')
    op.add_column('jobs', sa.Column(
        'search_vector', postgresql.TSVECTOR(), sa.Computed(expression, persisted=True), nullable=True,
    ))
    op.create_index('ix_jobs_search_vector', 'jobs', ['search_vector'], unique=False, postgresql_using='gin')


def upgrade() -> None:
    _replace_search_vector(SEARCH_DOCUMENT)


def downgrade() -> None:
    _replace_search_vector(PREVIOUS_SEARCH_DOCUMENT)
