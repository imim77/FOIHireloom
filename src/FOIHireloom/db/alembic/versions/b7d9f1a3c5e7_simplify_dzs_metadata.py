"""Remove unused DZS file metadata and per-value audit timestamps.

Revision ID: b7d9f1a3c5e7
Revises: a6c8e0f2b4d6

Downgrade restores structure only: sizes become zero and created/updated
times become the downgrade time. Restore the backup for original metadata.
"""

from alembic import op
import sqlalchemy as sa

revision = "b7d9f1a3c5e7"
down_revision = "a6c8e0f2b4d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_dzs_import_files_size_bytes_nonnegative"), "dzs_import_files", type_="check")
    op.drop_column("dzs_import_files", "etag")
    op.drop_column("dzs_import_files", "size_bytes")
    op.drop_constraint(op.f("ck_dzs_indicator_values_timestamps_ordered"), "dzs_indicator_values", type_="check")
    op.drop_constraint(op.f("ck_dzs_indicator_values_revised_in_lifetime"), "dzs_indicator_values", type_="check")
    for column in ("revised_at", "created_at", "updated_at"):
        op.drop_column("dzs_indicator_values", column)


def downgrade() -> None:
    op.add_column("dzs_import_files", sa.Column("etag", sa.Text(), nullable=True))
    op.add_column("dzs_import_files", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("dzs_import_files", "size_bytes", server_default=None)
    op.create_check_constraint(op.f("ck_dzs_import_files_size_bytes_nonnegative"), "dzs_import_files", "size_bytes >= 0")
    op.add_column("dzs_indicator_values", sa.Column("revised_at", sa.DateTime(timezone=True), nullable=True))
    for column in ("created_at", "updated_at"):
        op.add_column("dzs_indicator_values", sa.Column(
            column, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"),
        ))
    op.create_check_constraint(
        op.f("ck_dzs_indicator_values_timestamps_ordered"), "dzs_indicator_values", "created_at <= updated_at",
    )
    op.create_check_constraint(
        op.f("ck_dzs_indicator_values_revised_in_lifetime"), "dzs_indicator_values",
        "revised_at IS NULL OR revised_at BETWEEN created_at AND updated_at",
    )
