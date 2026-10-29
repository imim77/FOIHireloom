from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .employer import Employer


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("provider", "source_job_id"),
        UniqueConstraint("provider", "canonical_url"),
        CheckConstraint("length(btrim(provider)) > 0", name="provider_not_blank"),
        CheckConstraint("length(btrim(canonical_url)) > 0", name="url_not_blank"),
        CheckConstraint("length(btrim(content_hash)) > 0", name="hash_not_blank"),
        CheckConstraint(
            "(availability_status = 'unknown' AND availability_evidence_url IS NULL "
            "AND availability_checked_at IS NULL) OR "
            "(availability_status IN ('confirmed_open', 'confirmed_closed') "
            "AND availability_evidence_url IS NOT NULL "
            "AND length(btrim(availability_evidence_url)) > 0 "
            "AND availability_checked_at IS NOT NULL)",
            name="availability_has_evidence",
        ),
        CheckConstraint("first_seen_at <= last_seen_at", name="observation_times_ordered"),
        CheckConstraint(
            "content_changed_at BETWEEN first_seen_at AND last_seen_at",
            name="content_change_within_observation",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    employer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("employers.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(Text)
    source_job_id: Mapped[str | None] = mapped_column(Text)
    source_guid: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    description_raw: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)
    published_on: Mapped[date | None] = mapped_column(Date, index=True)
    deadline_on: Mapped[date | None] = mapped_column(Date, index=True)
    category: Mapped[str | None] = mapped_column(Text)
    location_text: Mapped[str | None] = mapped_column(Text)
    availability_status: Mapped[str] = mapped_column(
        Text, default="unknown", server_default="unknown"
    )
    availability_evidence_url: Mapped[str | None] = mapped_column(Text)
    availability_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_flags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ARRAY(Text)), default=list, server_default=text("'{}'::text[]")
    )
    content_hash: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employer: Mapped["Employer | None"] = relationship(back_populates="jobs", lazy="raise")
