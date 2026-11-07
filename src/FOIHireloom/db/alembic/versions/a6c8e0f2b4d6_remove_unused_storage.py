"""Remove unused employer/document storage and redundant job columns.

Revision ID: a6c8e0f2b4d6
Revises: f3b5d7e9a1c2

Downgrade restores the schema, but cannot recover discarded RSS snippets.
The cleaned description, parsed fields and original content hash stay intact.
"""

from alembic import op
import sqlalchemy as sa

revision = "a6c8e0f2b4d6"
down_revision = "f3b5d7e9a1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stop if another installation used the legacy storage outside this app.
    # Lock first so a concurrent writer cannot bypass the check.
    op.execute(
        "LOCK TABLE jobs, employers, web_documents, employer_web_documents, "
        "job_web_documents IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM employers)
                OR EXISTS (SELECT 1 FROM web_documents)
                OR EXISTS (SELECT 1 FROM employer_web_documents)
                OR EXISTS (SELECT 1 FROM job_web_documents)
                OR EXISTS (SELECT 1 FROM jobs WHERE employer_id IS NOT NULL
                    OR availability_status <> 'unknown'
                    OR availability_evidence_url IS NOT NULL
                    OR availability_checked_at IS NOT NULL)
            THEN
                RAISE EXCEPTION 'Legacy employer/document or availability data exists; '
                    'export and review it before applying a6c8e0f2b4d6';
            END IF;
        END $$
    """)
    op.drop_table("job_web_documents")
    op.drop_table("employer_web_documents")
    op.drop_constraint(op.f("fk_jobs_employer_id_employers"), "jobs", type_="foreignkey")
    op.drop_index(op.f("ix_jobs_employer_id"), table_name="jobs")
    op.drop_column("jobs", "employer_id")
    op.drop_table("web_documents")
    op.drop_table("employers")
    op.drop_constraint(op.f("ck_jobs_availability_has_evidence"), "jobs", type_="check")
    op.drop_column("jobs", "availability_status")
    op.drop_column("jobs", "availability_evidence_url")
    op.drop_column("jobs", "availability_checked_at")
    op.drop_column("jobs", "description_raw")


def downgrade() -> None:
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
    op.add_column("jobs", sa.Column("employer_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_jobs_employer_id_employers"), "jobs", "employers", ["employer_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_jobs_employer_id"), "jobs", ["employer_id"])
    op.add_column("jobs", sa.Column("description_raw", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("availability_status", sa.Text(), server_default="unknown", nullable=False))
    op.add_column("jobs", sa.Column("availability_evidence_url", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("availability_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_jobs_availability_has_evidence"), "jobs",
        "(availability_status = 'unknown' AND availability_evidence_url IS NULL "
        "AND availability_checked_at IS NULL) OR "
        "(availability_status IN ('confirmed_open', 'confirmed_closed') "
        "AND availability_evidence_url IS NOT NULL "
        "AND length(btrim(availability_evidence_url)) > 0 "
        "AND availability_checked_at IS NOT NULL)",
    )
