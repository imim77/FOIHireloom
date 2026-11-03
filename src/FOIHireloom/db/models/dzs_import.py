from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DzsImport(Base):
    """One run of foihireloom-import-dzs that was not a dry run.

    A failed or rejected run wrote no indicator values; its files record what
    was downloaded or read before it stopped.
    """

    __tablename__ = "dzs_imports"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed', 'rejected')", name="status_valid"),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status <> 'running' AND finished_at IS NOT NULL AND finished_at >= started_at)",
            name="completion_matches_status",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR num_nonnulls(values_inserted, values_updated, values_unchanged) = 3",
            name="success_has_counts",
        ),
        CheckConstraint(
            "status NOT IN ('failed', 'rejected') OR error_summary IS NOT NULL", name="failure_has_error"
        ),
        CheckConstraint(
            "values_inserted >= 0 AND values_updated >= 0 AND values_unchanged >= 0", name="counts_nonnegative"
        ),
        Index("ix_dzs_imports_started_at", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="running", server_default="running")
    values_inserted: Mapped[int | None] = mapped_column(Integer)
    values_updated: Mapped[int | None] = mapped_column(Integer)
    values_unchanged: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)

    files: Mapped[list["DzsImportFile"]] = relationship(
        back_populates="dzs_import", order_by="DzsImportFile.role", passive_deletes=True, lazy="raise"
    )


class DzsImportFile(Base):
    """Provenance of one source file of an import: the T1 release table or the county workbook."""

    __tablename__ = "dzs_import_files"
    __table_args__ = (
        UniqueConstraint("import_id", "role"),
        CheckConstraint("role IN ('t1', 'workbook')", name="role_valid"),
        CheckConstraint("length(btrim(location)) > 0", name="location_not_blank"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_valid"),
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dzs_imports.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)
    # The download URL, or the path of a local file as given to the command.
    location: Mapped[str] = mapped_column(Text)
    sheets: Mapped[list[str]] = mapped_column(ARRAY(Text))
    sha256: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    etag: Mapped[str | None] = mapped_column(Text)
    source_last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    dzs_import: Mapped[DzsImport] = relationship(back_populates="files", lazy="raise")
