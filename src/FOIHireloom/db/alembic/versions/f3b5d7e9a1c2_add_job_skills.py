"""add job skills

Revision ID: f3b5d7e9a1c2
Revises: e2a4c6b8d0f1
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f3b5d7e9a1c2"
down_revision = "e2a4c6b8d0f1"
branch_labels = None
depends_on = None

# Frozen expression: later catalog edits must not change this migration.
SKILLS_DOCUMENT = (
    'array_remove(ARRAY['
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])(c#|c sharp)([^a-z0-9]|$)' THEN 'csharp' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])(asp[.]net|[.]net)([^a-z0-9]|$)' THEN 'dotnet' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])python([^a-z0-9]|$)' THEN 'python' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])java([^a-z0-9]|$)' THEN 'java' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])(javascript|typescript)([^a-z0-9]|$)' THEN 'javascript' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])sql([^a-z0-9]|$)' THEN 'sql' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])php([^a-z0-9]|$)' THEN 'php' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])excel(a|u|om)?([^a-z0-9]|$)' THEN 'excel' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])autocad(a|u|om)?([^a-z0-9]|$)' THEN 'autocad' END, "
    "CASE WHEN regexp_replace(lower(translate(coalesce(page_title, title, '') || ' ' || coalesce(page_description_text, description_text, ''), 'ČĆŽŠĐčćžšđ', 'CCZSDcczsd')), '(https?://|www[.])[^\\s<>]+', ' ', 'g') ~ '(^|[^a-z0-9])plc([^a-z0-9]|$)' THEN 'plc' END], NULL)"
)


def upgrade() -> None:
    op.add_column("jobs", sa.Column(
        "skills", postgresql.ARRAY(sa.Text()), sa.Computed(SKILLS_DOCUMENT, persisted=True), nullable=False,
    ))
    op.create_index("ix_jobs_skills", "jobs", ["skills"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_jobs_skills", table_name="jobs", postgresql_using="gin")
    op.drop_column("jobs", "skills")
