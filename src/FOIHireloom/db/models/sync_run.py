from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .source_feed import SourceFeed


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'not_modified', 'failed', 'rejected')",
            name="status_valid",
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status <> 'running' AND finished_at IS NOT NULL AND finished_at >= started_at)",
            name="completion_matches_status",
        ),
        CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599", name="http_status_valid"
        ),
        CheckConstraint(
            "status <> 'succeeded' OR (http_status IS NOT NULL AND http_status = 200)",
            name="success_requires_http_200",
        ),
        CheckConstraint(
            "status <> 'not_modified' OR (http_status IS NOT NULL AND http_status = 304)",
            name="not_modified_requires_http_304",
        ),
        CheckConstraint("items_seen IS NULL OR items_seen >= 0", name="items_seen_nonnegative"),
        CheckConstraint("items_added IS NULL OR items_added >= 0", name="items_added_nonnegative"),
        CheckConstraint("items_updated IS NULL OR items_updated >= 0", name="items_updated_nonnegative"),
        CheckConstraint("items_invalid IS NULL OR items_invalid >= 0", name="items_invalid_nonnegative"),
        Index("ix_sync_runs_feed_id_started_at", "feed_id", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    feed_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("source_feeds.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="running", server_default="running")
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    items_seen: Mapped[int | None] = mapped_column(Integer)
    items_added: Mapped[int | None] = mapped_column(Integer)
    items_updated: Mapped[int | None] = mapped_column(Integer)
    items_invalid: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)

    feed: Mapped["SourceFeed"] = relationship(back_populates="sync_runs", lazy="raise")
