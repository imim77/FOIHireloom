"""create initial schema

Revision ID: 1981498b73b5
Revises:
Create Date: 2026-10-29 11:38:47.544571
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '1981498b73b5'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('counties',
        sa.Column('id', sa.SmallInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.CheckConstraint('length(btrim(code)) > 0', name=op.f('ck_counties_code_not_blank')),
        sa.CheckConstraint('length(btrim(name)) > 0', name=op.f('ck_counties_name_not_blank')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_counties')),
        sa.UniqueConstraint('code', name=op.f('uq_counties_code')),
        sa.UniqueConstraint('name', name=op.f('uq_counties_name'))
    )
    op.create_table('employers',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('website_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('created_at <= updated_at', name=op.f('ck_employers_timestamps_ordered')),
        sa.CheckConstraint('length(btrim(name)) > 0', name=op.f('ck_employers_name_not_blank')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_employers'))
    )
    op.create_table('web_documents',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('canonical_url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('retrieval_provider', sa.Text(), nullable=False),
        sa.Column('first_retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("retrieval_provider IN ('tavily', 'direct')", name=op.f('ck_web_documents_provider_valid')),
        sa.CheckConstraint('first_retrieved_at <= last_verified_at', name=op.f('ck_web_documents_timestamps_ordered')),
        sa.CheckConstraint('length(btrim(canonical_url)) > 0', name=op.f('ck_web_documents_url_not_blank')),
        sa.CheckConstraint('length(btrim(content_hash)) > 0', name=op.f('ck_web_documents_hash_not_blank')),
        sa.CheckConstraint('length(btrim(content_text)) > 0', name=op.f('ck_web_documents_content_not_blank')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_web_documents')),
        sa.UniqueConstraint('canonical_url', 'content_hash', name=op.f('uq_web_documents_canonical_url_content_hash'))
    )
    op.create_table('employer_web_documents',
        sa.Column('employer_id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('relation_kind', sa.Text(), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("relation_kind IN ('official_site', 'careers', 'company_context')", name=op.f('ck_employer_web_documents_relation_kind_valid')),
        sa.ForeignKeyConstraint(['document_id'], ['web_documents.id'], name=op.f('fk_employer_web_documents_document_id_web_documents'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['employer_id'], ['employers.id'], name=op.f('fk_employer_web_documents_employer_id_employers'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('employer_id', 'document_id', name=op.f('pk_employer_web_documents'))
    )
    op.create_index(op.f('ix_employer_web_documents_document_id'), 'employer_web_documents', ['document_id'], unique=False)
    op.create_table('jobs',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('employer_id', sa.BigInteger(), nullable=True),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('source_job_id', sa.Text(), nullable=True),
        sa.Column('source_guid', sa.Text(), nullable=True),
        sa.Column('canonical_url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('description_raw', sa.Text(), nullable=True),
        sa.Column('description_text', sa.Text(), nullable=True),
        sa.Column('published_on', sa.Date(), nullable=True),
        sa.Column('deadline_on', sa.Date(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('location_text', sa.Text(), nullable=True),
        sa.Column('availability_status', sa.Text(), server_default='unknown', nullable=False),
        sa.Column('availability_evidence_url', sa.Text(), nullable=True),
        sa.Column('availability_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('quality_flags', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('content_changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("(availability_status = 'unknown' AND availability_evidence_url IS NULL AND availability_checked_at IS NULL) OR (availability_status IN ('confirmed_open', 'confirmed_closed') AND availability_evidence_url IS NOT NULL AND length(btrim(availability_evidence_url)) > 0 AND availability_checked_at IS NOT NULL)", name=op.f('ck_jobs_availability_has_evidence')),
        sa.CheckConstraint('content_changed_at BETWEEN first_seen_at AND last_seen_at', name=op.f('ck_jobs_content_change_within_observation')),
        sa.CheckConstraint('first_seen_at <= last_seen_at', name=op.f('ck_jobs_observation_times_ordered')),
        sa.CheckConstraint('length(btrim(canonical_url)) > 0', name=op.f('ck_jobs_url_not_blank')),
        sa.CheckConstraint('length(btrim(content_hash)) > 0', name=op.f('ck_jobs_hash_not_blank')),
        sa.CheckConstraint('length(btrim(provider)) > 0', name=op.f('ck_jobs_provider_not_blank')),
        sa.ForeignKeyConstraint(['employer_id'], ['employers.id'], name=op.f('fk_jobs_employer_id_employers'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
        sa.UniqueConstraint('provider', 'canonical_url', name=op.f('uq_jobs_provider_canonical_url')),
        sa.UniqueConstraint('provider', 'source_job_id', name=op.f('uq_jobs_provider_source_job_id'))
    )
    op.create_index(op.f('ix_jobs_deadline_on'), 'jobs', ['deadline_on'], unique=False)
    op.create_index(op.f('ix_jobs_employer_id'), 'jobs', ['employer_id'], unique=False)
    op.create_index(op.f('ix_jobs_published_on'), 'jobs', ['published_on'], unique=False)
    op.create_table('source_feeds',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('county_id', sa.SmallInteger(), nullable=True),
        sa.Column('ckan_resource_id', sa.Uuid(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('feed_url', sa.Text(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('etag', sa.Text(), nullable=True),
        sa.Column('source_last_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_content_change_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(scope = 'county' AND county_id IS NOT NULL) OR (scope = 'eu' AND county_id IS NULL)", name=op.f('ck_source_feeds_scope_matches_county')),
        sa.CheckConstraint('last_success_at IS NULL OR (last_checked_at IS NOT NULL AND last_success_at <= last_checked_at)', name=op.f('ck_source_feeds_success_not_after_check')),
        sa.CheckConstraint('length(btrim(feed_url)) > 0', name=op.f('ck_source_feeds_url_not_blank')),
        sa.CheckConstraint('length(btrim(label)) > 0', name=op.f('ck_source_feeds_label_not_blank')),
        sa.ForeignKeyConstraint(['county_id'], ['counties.id'], name=op.f('fk_source_feeds_county_id_counties'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_source_feeds')),
        sa.UniqueConstraint('ckan_resource_id', name=op.f('uq_source_feeds_ckan_resource_id')),
        sa.UniqueConstraint('feed_url', name=op.f('uq_source_feeds_feed_url'))
    )
    op.create_index(op.f('ix_source_feeds_county_id'), 'source_feeds', ['county_id'], unique=False)
    op.create_table('job_feed_memberships',
        sa.Column('job_id', sa.BigInteger(), nullable=False),
        sa.Column('feed_id', sa.BigInteger(), nullable=False),
        sa.Column('source_item', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=False),
        sa.Column('presence_status', sa.Text(), server_default='present', nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('missing_since_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(presence_status = 'present' AND missing_since_at IS NULL) OR (presence_status = 'missing' AND missing_since_at IS NOT NULL AND missing_since_at >= last_seen_at)", name=op.f('ck_job_feed_memberships_presence_matches_missing_time')),
        sa.CheckConstraint("jsonb_typeof(source_item) = 'object'", name=op.f('ck_job_feed_memberships_source_item_is_object')),
        sa.CheckConstraint('first_seen_at <= last_seen_at', name=op.f('ck_job_feed_memberships_timestamps_ordered')),
        sa.ForeignKeyConstraint(['feed_id'], ['source_feeds.id'], name=op.f('fk_job_feed_memberships_feed_id_source_feeds'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name=op.f('fk_job_feed_memberships_job_id_jobs'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('job_id', 'feed_id', name=op.f('pk_job_feed_memberships'))
    )
    op.create_index('ix_job_feed_memberships_feed_presence_job', 'job_feed_memberships', ['feed_id', 'presence_status', 'job_id'], unique=False)
    op.create_table('job_web_documents',
        sa.Column('job_id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('relation_kind', sa.Text(), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("relation_kind IN ('job_detail', 'supporting_context')", name=op.f('ck_job_web_documents_relation_kind_valid')),
        sa.ForeignKeyConstraint(['document_id'], ['web_documents.id'], name=op.f('fk_job_web_documents_document_id_web_documents'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name=op.f('fk_job_web_documents_job_id_jobs'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('job_id', 'document_id', name=op.f('pk_job_web_documents'))
    )
    op.create_index(op.f('ix_job_web_documents_document_id'), 'job_web_documents', ['document_id'], unique=False)
    op.create_table('sync_runs',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('feed_id', sa.BigInteger(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Text(), server_default='running', nullable=False),
        sa.Column('http_status', sa.SmallInteger(), nullable=True),
        sa.Column('items_seen', sa.Integer(), nullable=True),
        sa.Column('items_added', sa.Integer(), nullable=True),
        sa.Column('items_updated', sa.Integer(), nullable=True),
        sa.Column('items_invalid', sa.Integer(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.CheckConstraint("(status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL AND finished_at >= started_at)", name=op.f('ck_sync_runs_completion_matches_status')),
        sa.CheckConstraint("status <> 'not_modified' OR (http_status IS NOT NULL AND http_status = 304)", name=op.f('ck_sync_runs_not_modified_requires_http_304')),
        sa.CheckConstraint("status <> 'succeeded' OR (http_status IS NOT NULL AND http_status = 200)", name=op.f('ck_sync_runs_success_requires_http_200')),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'not_modified', 'failed', 'rejected')", name=op.f('ck_sync_runs_status_valid')),
        sa.CheckConstraint('http_status IS NULL OR http_status BETWEEN 100 AND 599', name=op.f('ck_sync_runs_http_status_valid')),
        sa.CheckConstraint('items_added IS NULL OR items_added >= 0', name=op.f('ck_sync_runs_items_added_nonnegative')),
        sa.CheckConstraint('items_invalid IS NULL OR items_invalid >= 0', name=op.f('ck_sync_runs_items_invalid_nonnegative')),
        sa.CheckConstraint('items_seen IS NULL OR items_seen >= 0', name=op.f('ck_sync_runs_items_seen_nonnegative')),
        sa.CheckConstraint('items_updated IS NULL OR items_updated >= 0', name=op.f('ck_sync_runs_items_updated_nonnegative')),
        sa.ForeignKeyConstraint(['feed_id'], ['source_feeds.id'], name=op.f('fk_sync_runs_feed_id_source_feeds'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_sync_runs'))
    )
    op.create_index('ix_sync_runs_feed_id_started_at', 'sync_runs', ['feed_id', sa.literal_column('started_at DESC')], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sync_runs_feed_id_started_at', table_name='sync_runs')
    op.drop_table('sync_runs')
    op.drop_index(op.f('ix_job_web_documents_document_id'), table_name='job_web_documents')
    op.drop_table('job_web_documents')
    op.drop_index('ix_job_feed_memberships_feed_presence_job', table_name='job_feed_memberships')
    op.drop_table('job_feed_memberships')
    op.drop_index(op.f('ix_source_feeds_county_id'), table_name='source_feeds')
    op.drop_table('source_feeds')
    op.drop_index(op.f('ix_jobs_published_on'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_employer_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_deadline_on'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_employer_web_documents_document_id'), table_name='employer_web_documents')
    op.drop_table('employer_web_documents')
    op.drop_table('web_documents')
    op.drop_table('employers')
    op.drop_table('counties')
