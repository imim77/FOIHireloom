"""add job page details

Revision ID: adc0c83dfede
Revises: 76fe07c71f7f
Create Date: 2026-10-30 11:20:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'adc0c83dfede'
down_revision: str | Sequence[str] | None = '76fe07c71f7f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAGE_TEXT_COLUMNS = (
    'page_title', 'page_work_place', 'page_employment_type', 'page_working_hours', 'page_work_schedule',
    'page_accommodation', 'page_transport_allowance', 'page_education', 'page_experience',
    'page_description_text', 'page_employer_name', 'page_source_hash', 'page_error',
)


def upgrade() -> None:
    op.add_column('jobs', sa.Column('page_status', sa.Text(), server_default='pending', nullable=False))
    op.add_column('jobs', sa.Column('page_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('page_fetched_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('page_workers_needed', sa.Integer(), nullable=True))
    op.add_column('jobs', sa.Column('page_valid_from', sa.Date(), nullable=True))
    op.add_column('jobs', sa.Column('page_valid_until', sa.Date(), nullable=True))
    for name in PAGE_TEXT_COLUMNS:
        op.add_column('jobs', sa.Column(name, sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f('ck_jobs_page_status_known'), 'jobs',
        "page_status IN ('pending', 'fetched', 'unavailable', 'failed')",
    )
    op.create_check_constraint(
        op.f('ck_jobs_page_check_recorded'), 'jobs',
        "(page_status = 'pending') = (page_checked_at IS NULL)",
    )
    op.create_check_constraint(
        op.f('ck_jobs_page_fetch_recorded'), 'jobs',
        "page_status <> 'fetched' OR (page_fetched_at IS NOT NULL AND page_source_hash IS NOT NULL)",
    )


def downgrade() -> None:
    for name in ('page_fetch_recorded', 'page_check_recorded', 'page_status_known'):
        op.drop_constraint(op.f(f'ck_jobs_{name}'), 'jobs', type_='check')
    for name in reversed(PAGE_TEXT_COLUMNS):
        op.drop_column('jobs', name)
    for name in ('page_valid_until', 'page_valid_from', 'page_workers_needed', 'page_fetched_at',
                 'page_checked_at', 'page_status'):
        op.drop_column('jobs', name)
