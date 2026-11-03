"""add dzs indicator values

Revision ID: e2a4c6b8d0f1
Revises: d1f3a5c7e9b2
Create Date: 2026-11-02 15:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e2a4c6b8d0f1'
down_revision: str | Sequence[str] | None = 'd1f3a5c7e9b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('dzs_imports',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Text(), server_default='running', nullable=False),
        sa.Column('values_inserted', sa.Integer(), nullable=True),
        sa.Column('values_updated', sa.Integer(), nullable=True),
        sa.Column('values_unchanged', sa.Integer(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed', 'rejected')", name=op.f('ck_dzs_imports_status_valid')),
        sa.CheckConstraint("(status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL AND finished_at >= started_at)", name=op.f('ck_dzs_imports_completion_matches_status')),
        sa.CheckConstraint("status <> 'succeeded' OR num_nonnulls(values_inserted, values_updated, values_unchanged) = 3", name=op.f('ck_dzs_imports_success_has_counts')),
        sa.CheckConstraint("status NOT IN ('failed', 'rejected') OR error_summary IS NOT NULL", name=op.f('ck_dzs_imports_failure_has_error')),
        sa.CheckConstraint('values_inserted >= 0 AND values_updated >= 0 AND values_unchanged >= 0', name=op.f('ck_dzs_imports_counts_nonnegative')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dzs_imports'))
    )
    op.create_index('ix_dzs_imports_started_at', 'dzs_imports', [sa.literal_column('started_at DESC')], unique=False)
    op.create_table('dzs_import_files',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('import_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('location', sa.Text(), nullable=False),
        sa.Column('sheets', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('sha256', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('etag', sa.Text(), nullable=True),
        sa.Column('source_last_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('t1', 'workbook')", name=op.f('ck_dzs_import_files_role_valid')),
        sa.CheckConstraint('length(btrim(location)) > 0', name=op.f('ck_dzs_import_files_location_not_blank')),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f('ck_dzs_import_files_sha256_valid')),
        sa.CheckConstraint('size_bytes >= 0', name=op.f('ck_dzs_import_files_size_bytes_nonnegative')),
        sa.ForeignKeyConstraint(['import_id'], ['dzs_imports.id'], name=op.f('fk_dzs_import_files_import_id_dzs_imports'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dzs_import_files')),
        sa.UniqueConstraint('import_id', 'role', name=op.f('uq_dzs_import_files_import_id_role'))
    )
    op.create_table('dzs_indicator_values',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('county_id', sa.SmallInteger(), nullable=False),
        sa.Column('indicator', sa.Text(), nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('sex', sa.Text(), nullable=False),
        sa.Column('value', sa.Numeric(), nullable=True),
        sa.Column('missing_reason', sa.Text(), nullable=True),
        sa.Column('is_provisional', sa.Boolean(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('import_id', sa.BigInteger(), nullable=False),
        sa.Column('revised_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("indicator IN ('active_population', 'employed', 'unemployed', 'unemployment_rate')", name=op.f('ck_dzs_indicator_values_indicator_valid')),
        sa.CheckConstraint("sex IN ('total', 'women', 'men')", name=op.f('ck_dzs_indicator_values_sex_valid')),
        sa.CheckConstraint("period = date_trunc('month', period)::date", name=op.f('ck_dzs_indicator_values_period_is_month_start')),
        sa.CheckConstraint("missing_reason IN ('no_occurrence', 'not_available', 'empty')", name=op.f('ck_dzs_indicator_values_missing_reason_valid')),
        sa.CheckConstraint('(value IS NULL) = (missing_reason IS NOT NULL)', name=op.f('ck_dzs_indicator_values_value_or_missing_reason')),
        sa.CheckConstraint("value >= 0 AND CASE WHEN indicator = 'unemployment_rate' THEN value <= 100 AND value = round(value, 1) ELSE value = trunc(value) END", name=op.f('ck_dzs_indicator_values_value_in_unit')),
        sa.CheckConstraint("source = 't1' OR (source = 'workbook_9_4_13' AND indicator = 'active_population') OR (source = 'workbook_9_4_14' AND indicator = 'unemployment_rate')", name=op.f('ck_dzs_indicator_values_source_has_indicator')),
        sa.CheckConstraint('created_at <= updated_at', name=op.f('ck_dzs_indicator_values_timestamps_ordered')),
        sa.CheckConstraint('revised_at IS NULL OR revised_at BETWEEN created_at AND updated_at', name=op.f('ck_dzs_indicator_values_revised_in_lifetime')),
        sa.ForeignKeyConstraint(['county_id'], ['counties.id'], name=op.f('fk_dzs_indicator_values_county_id_counties'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['import_id'], ['dzs_imports.id'], name=op.f('fk_dzs_indicator_values_import_id_dzs_imports'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dzs_indicator_values')),
        sa.UniqueConstraint('county_id', 'indicator', 'period', 'sex', name=op.f('uq_dzs_indicator_values_county_id_indicator_period_sex'))
    )
    op.create_index(op.f('ix_dzs_indicator_values_import_id'), 'dzs_indicator_values', ['import_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dzs_indicator_values_import_id'), table_name='dzs_indicator_values')
    op.drop_table('dzs_indicator_values')
    op.drop_table('dzs_import_files')
    op.drop_index('ix_dzs_imports_started_at', table_name='dzs_imports')
    op.drop_table('dzs_imports')
