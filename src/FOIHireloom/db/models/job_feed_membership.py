from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .job import Job
    from .source_feed import SourceFeed


class JobFeedMembership(Base):
    __tablename__ = "pripadnosti_oglasa_kanalima"
    __table_args__ = (
        CheckConstraint("vrijeme_prvog_opazanja <= vrijeme_zadnjeg_opazanja", name="vremena_opazanja_redom"),
        CheckConstraint(
            "(stanje_prisutnosti = 'present' AND vrijeme_nestanka IS NULL) OR "
            "(stanje_prisutnosti = 'missing' AND vrijeme_nestanka IS NOT NULL "
            "AND vrijeme_nestanka >= vrijeme_zadnjeg_opazanja)",
            name="prisutnost_prema_nestanku",
        ),
        Index("ix_pripadnosti_kanal_prisutnost_oglas", "feed_id", "presence_status", "job_id"),
    )

    job_id: Mapped[int] = mapped_column(
        "id_oglasa", BigInteger, ForeignKey("oglasi.id", ondelete="CASCADE"), primary_key=True,
        key="job_id",
    )
    feed_id: Mapped[int] = mapped_column(
        "id_kanala", BigInteger, ForeignKey("izvorni_kanali.id", ondelete="RESTRICT"),
        primary_key=True, key="feed_id",
    )
    presence_status: Mapped[str] = mapped_column(
        "stanje_prisutnosti", Text, default="present", server_default="present", key="presence_status",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        "vrijeme_prvog_opazanja", DateTime(timezone=True), server_default=func.now(),
        key="first_seen_at",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        "vrijeme_zadnjeg_opazanja", DateTime(timezone=True), server_default=func.now(),
        key="last_seen_at",
    )
    missing_since_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_nestanka", DateTime(timezone=True), key="missing_since_at",
    )

    job: Mapped["Job"] = relationship(back_populates="feed_memberships", lazy="raise")
    feed: Mapped["SourceFeed"] = relationship(back_populates="job_memberships", lazy="raise")
