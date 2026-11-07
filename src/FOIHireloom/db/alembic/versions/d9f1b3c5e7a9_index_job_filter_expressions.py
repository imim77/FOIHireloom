"""Index the expressions that job filters compare instead of the raw columns.

Revision ID: d9f1b3c5e7a9
Revises: c8e0a2b4d6f8

Filters use upper(category) and coalesce(page_valid_until, deadline_on), so
the plain indexes on category and deadline_on could not serve them.
"""

from alembic import op
import sqlalchemy as sa

revision = "d9f1b3c5e7a9"
down_revision = "c8e0a2b4d6f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_jobs_category", table_name="jobs")
    op.drop_index("ix_jobs_deadline_on", table_name="jobs")
    op.create_index("ix_jobs_upper_category", "jobs", [sa.text("upper(category)")])
    op.create_index("ix_jobs_effective_deadline", "jobs", [sa.text("coalesce(page_valid_until, deadline_on)")])


def downgrade() -> None:
    op.drop_index("ix_jobs_effective_deadline", table_name="jobs")
    op.drop_index("ix_jobs_upper_category", table_name="jobs")
    op.create_index("ix_jobs_deadline_on", "jobs", ["deadline_on"])
    op.create_index("ix_jobs_category", "jobs", ["category"])
