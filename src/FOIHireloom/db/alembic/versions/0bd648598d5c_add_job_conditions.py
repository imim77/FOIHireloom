"""add job conditions

Revision ID: 0bd648598d5c
Revises: c4e8a2f6b1d3
Create Date: 2026-10-31 22:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0bd648598d5c'
down_revision: str | Sequence[str] | None = 'c4e8a2f6b1d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Rows stay unknown until foihireloom-normalize-job-conditions fills them in.
CONDITION_COLUMNS = (
    ('experience_months', sa.Integer()), ('trainee', sa.Boolean()), ('contract', sa.Text()),
    ('employment_tags', postgresql.ARRAY(sa.Text())), ('full_time', sa.Boolean()), ('weekly_hours', sa.Integer()),
    ('education_levels', postgresql.ARRAY(sa.Text())), ('accommodation', sa.Text()),
    ('schedule_tags', postgresql.ARRAY(sa.Text())), ('transport_allowance', sa.Text()),
)
CHECKS = {
    'conditions_known': (
        "contract IN ('permanent', 'fixed_term', 'other') "
        "AND employment_tags <@ ARRAY['new_position', 'vacancy', 'replacement', 'increased_workload', 'seasonal', "
        "'reappointment', 'trainee', 'retirees', 'disability']::text[] "
        "AND education_levels <@ ARRAY['primary_lower', 'primary', 'secondary_3', 'secondary_4', 'college', "
        "'university']::text[] "
        "AND accommodation IN ('none', 'shared', 'single', 'family') "
        "AND schedule_tags <@ ARRAY['morning', 'afternoon', 'two_shifts', 'three_shifts', 'split', 'night', "
        "'weekends_holidays']::text[] "
        "AND transport_allowance IN ('full', 'partial', 'none') "
        "AND conditions_unrecognised <@ ARRAY['experience', 'employment_type', 'working_hours', 'education', "
        "'accommodation', 'work_schedule', 'transport_allowance']::text[]"
    ),
    'experience_consistent': (
        "(experience_months IS NULL) = (trainee IS NULL) AND experience_months >= 0 "
        "AND (NOT trainee OR experience_months = 0)"
    ),
    'weekly_hours_positive': "weekly_hours > 0",
    'conditions_need_page': (
        "page_fetched_at IS NOT NULL OR (num_nonnulls(experience_months, trainee, contract, employment_tags, "
        "full_time, weekly_hours, education_levels, accommodation, schedule_tags, transport_allowance) = 0 "
        "AND conditions_unrecognised = '{}')"
    ),
}


def upgrade() -> None:
    for name, type_ in CONDITION_COLUMNS:
        op.add_column('jobs', sa.Column(name, type_, nullable=True))
    op.add_column('jobs', sa.Column(
        'conditions_unrecognised', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"),
        nullable=False,
    ))
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f'ck_jobs_{name}'), 'jobs', condition)


def downgrade() -> None:
    for name in reversed(CHECKS):
        op.drop_constraint(op.f(f'ck_jobs_{name}'), 'jobs', type_='check')
    op.drop_column('jobs', 'conditions_unrecognised')
    for name, _ in reversed(CONDITION_COLUMNS):
        op.drop_column('jobs', name)
