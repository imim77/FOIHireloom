"""Use HZZ job identity directly and remove the unused EU feed scope.

Revision ID: c8e0a2b4d6f8
Revises: b7d9f1a3c5e7
"""

from alembic import op
import sqlalchemy as sa

revision = "c8e0a2b4d6f8"
down_revision = "b7d9f1a3c5e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("LOCK TABLE jobs, source_feeds IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM jobs WHERE provider <> 'hzz')
                OR EXISTS (SELECT 1 FROM source_feeds WHERE scope = 'eu')
                OR EXISTS (SELECT source_job_id FROM jobs WHERE source_job_id IS NOT NULL
                    GROUP BY source_job_id HAVING count(*) > 1)
                OR EXISTS (SELECT canonical_url FROM jobs GROUP BY canonical_url HAVING count(*) > 1)
            THEN
                RAISE EXCEPTION 'HZZ-only migration requires HZZ jobs, no EU feeds and unique job identities';
            END IF;
        END $$
    """)
    op.drop_constraint("uq_jobs_provider_source_job_id", "jobs", type_="unique")
    op.drop_constraint("uq_jobs_provider_canonical_url", "jobs", type_="unique")
    op.drop_constraint(op.f("ck_jobs_provider_not_blank"), "jobs", type_="check")
    op.drop_column("jobs", "provider")
    op.create_unique_constraint("uq_jobs_source_job_id", "jobs", ["source_job_id"])
    op.create_unique_constraint("uq_jobs_canonical_url", "jobs", ["canonical_url"])
    op.drop_constraint(op.f("ck_source_feeds_scope_matches_county"), "source_feeds", type_="check")
    op.create_check_constraint(
        op.f("ck_source_feeds_scope_matches_county"), "source_feeds",
        "(scope = 'county' AND county_id IS NOT NULL) OR (scope = 'occupation' AND county_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_source_feeds_scope_matches_county"), "source_feeds", type_="check")
    op.create_check_constraint(
        op.f("ck_source_feeds_scope_matches_county"), "source_feeds",
        "(scope = 'county' AND county_id IS NOT NULL) OR (scope IN ('occupation', 'eu') AND county_id IS NULL)",
    )
    op.add_column("jobs", sa.Column("provider", sa.Text(), nullable=False, server_default="hzz"))
    op.alter_column("jobs", "provider", server_default=None)
    op.drop_constraint("uq_jobs_source_job_id", "jobs", type_="unique")
    op.drop_constraint("uq_jobs_canonical_url", "jobs", type_="unique")
    op.create_unique_constraint("uq_jobs_provider_source_job_id", "jobs", ["provider", "source_job_id"])
    op.create_unique_constraint("uq_jobs_provider_canonical_url", "jobs", ["provider", "canonical_url"])
    op.create_check_constraint(op.f("ck_jobs_provider_not_blank"), "jobs", "length(btrim(provider)) > 0")
