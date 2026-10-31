"""add feed category mapping

Revision ID: b7d2e5a1c3f9
Revises: 4668a0c36bbc
Create Date: 2026-10-31 18:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7d2e5a1c3f9'
down_revision: str | Sequence[str] | None = '4668a0c36bbc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('source_feeds', sa.Column('mapped_category', sa.Text(), nullable=True))
    op.add_column('source_feeds', sa.Column('mapping_status', sa.Text(), nullable=True))
    op.add_column('source_feeds', sa.Column('mapping_matching_examples', sa.Integer(), nullable=True))
    op.add_column('source_feeds', sa.Column('mapping_contradicting_examples', sa.Integer(), nullable=True))
    op.add_column('source_feeds', sa.Column('mapping_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f('ck_source_feeds_mapping_verified_for_occupation'), 'source_feeds',
        "(mapping_status IS NULL AND mapped_category IS NULL AND mapping_matching_examples IS NULL "
        "AND mapping_contradicting_examples IS NULL AND mapping_verified_at IS NULL) OR "
        "(scope = 'occupation' AND mapping_status IS NOT NULL AND mapping_matching_examples IS NOT NULL "
        "AND mapping_contradicting_examples IS NOT NULL AND mapping_verified_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f('ck_source_feeds_mapping_evidence_consistent'), 'source_feeds',
        "mapping_status IN ('confirmed', 'too_few_examples', 'contradicted') "
        "AND mapping_matching_examples >= 0 AND mapping_contradicting_examples >= 0 "
        "AND (mapped_category IS NULL) = (mapping_matching_examples = 0) "
        "AND (mapping_status = 'contradicted') = (mapping_contradicting_examples > 0) "
        "AND (mapping_status <> 'confirmed' OR mapping_matching_examples > 0)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_source_feeds_mapping_evidence_consistent'), 'source_feeds', type_='check')
    op.drop_constraint(op.f('ck_source_feeds_mapping_verified_for_occupation'), 'source_feeds', type_='check')
    op.drop_column('source_feeds', 'mapping_verified_at')
    op.drop_column('source_feeds', 'mapping_contradicting_examples')
    op.drop_column('source_feeds', 'mapping_matching_examples')
    op.drop_column('source_feeds', 'mapping_status')
    op.drop_column('source_feeds', 'mapped_category')
