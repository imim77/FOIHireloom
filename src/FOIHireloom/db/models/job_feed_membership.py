from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .job import Job
    from .source_feed import SourceFeed


class JobFeedMembership(Base):
    __tablename__ = "job_feed_memberships"
    __table_args__ = (
        CheckConstraint("first_seen_at <= last_seen_at", name="timestamps_ordered"),
        CheckConstraint(
            "(presence_status = 'present' AND missing_since_at IS NULL) OR "
            "(presence_status = 'missing' AND missing_since_at IS NOT NULL "
            "AND missing_since_at >= last_seen_at)",
            name="presence_matches_missing_time",
        ),
        Index("ix_job_feed_memberships_feed_presence_job", "feed_id", "presence_status", "job_id"),
    )

    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    feed_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("source_feeds.id", ondelete="RESTRICT"), primary_key=True
    )
    presence_status: Mapped[str] = mapped_column(Text, default="present", server_default="present")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    missing_since_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped["Job"] = relationship(back_populates="feed_memberships", lazy="raise")
    feed: Mapped["SourceFeed"] = relationship(back_populates="job_memberships", lazy="raise")
