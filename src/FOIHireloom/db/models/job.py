from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
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
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Searchable text with Croatian letters folded to ASCII, so "cistacica" finds
# "ČISTAČICA". "/" and "." become spaces: the parser would otherwise read
# "KUHAR/KUHARICA" as a file path and "68.STRUČNI" as a host name. Queries
# must apply the same translate(); unaccent() is not immutable and cannot be
# used in a generated column.
SEARCH_FOLD_FROM, SEARCH_FOLD_TO = "ČĆŽŠĐčćžšđ/.", "CCZSDcczsd  "
# Title words get weight A, so a query restricted to it (kuhar:*A) tells
# whether the title matched; everything else keeps the default weight D. The
# job page's values replace the feed's truncated title and description once
# read, and add the employer, place of work and education.
SEARCH_TITLE_WEIGHT = "A"
SEARCH_DOCUMENT = (
    "setweight(to_tsvector('simple'::regconfig, translate("
    f"coalesce(page_title, title, ''), '{SEARCH_FOLD_FROM}', '{SEARCH_FOLD_TO}')), '{SEARCH_TITLE_WEIGHT}') || "
    "to_tsvector('simple'::regconfig, translate("
    "coalesce(page_description_text, description_text, '') || ' ' || coalesce(page_employer_name, '') || ' ' || "
    "coalesce(page_work_place, '') || ' ' || coalesce(page_education, ''), "
    f"'{SEARCH_FOLD_FROM}', '{SEARCH_FOLD_TO}'))"
)

if TYPE_CHECKING:
    from .employer import Employer
    from .job_feed_membership import JobFeedMembership
    from .job_web_document import JobWebDocument


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
        Index("ix_jobs_search_vector", "search_vector", postgresql_using="gin"),
        CheckConstraint(
            "page_status IN ('pending', 'fetched', 'unavailable', 'failed')", name="page_status_known"
        ),
        CheckConstraint("(page_status = 'pending') = (page_checked_at IS NULL)", name="page_check_recorded"),
        CheckConstraint(
            "page_status <> 'fetched' OR (page_fetched_at IS NOT NULL AND page_source_hash IS NOT NULL)",
            name="page_fetch_recorded",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    employer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("employers.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(Text)
    source_job_id: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description_raw: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)
    published_on: Mapped[date | None] = mapped_column(Date, index=True)
    deadline_on: Mapped[date | None] = mapped_column(Date, index=True)
    category: Mapped[str | None] = mapped_column(Text, index=True)
    location_text: Mapped[str | None] = mapped_column(Text)
    municipality: Mapped[str | None] = mapped_column(Text)
    availability_status: Mapped[str] = mapped_column(
        Text, default="unknown", server_default="unknown"
    )
    availability_evidence_url: Mapped[str | None] = mapped_column(Text)
    availability_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_flags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ARRAY(Text)), default=list, server_default=text("'{}'::text[]")
    )
    content_hash: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(SEARCH_DOCUMENT, persisted=True), deferred=True
    )
    # Fields from the job's HZZ detail page, kept apart from the feed's values.
    # A later failed check keeps the last fetched values; page_source_hash is
    # the feed content hash they were fetched for.
    page_status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
    page_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page_source_hash: Mapped[str | None] = mapped_column(Text)
    page_error: Mapped[str | None] = mapped_column(Text)
    page_title: Mapped[str | None] = mapped_column(Text)
    page_work_place: Mapped[str | None] = mapped_column(Text)
    page_workers_needed: Mapped[int | None] = mapped_column(Integer)
    page_employment_type: Mapped[str | None] = mapped_column(Text)
    page_working_hours: Mapped[str | None] = mapped_column(Text)
    page_work_schedule: Mapped[str | None] = mapped_column(Text)
    page_accommodation: Mapped[str | None] = mapped_column(Text)
    page_transport_allowance: Mapped[str | None] = mapped_column(Text)
    page_valid_from: Mapped[date | None] = mapped_column(Date)
    page_valid_until: Mapped[date | None] = mapped_column(Date)
    page_education: Mapped[str | None] = mapped_column(Text)
    page_experience: Mapped[str | None] = mapped_column(Text)
    page_description_text: Mapped[str | None] = mapped_column(Text)
    page_employer_name: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    employer: Mapped["Employer | None"] = relationship(back_populates="jobs", lazy="raise")
    feed_memberships: Mapped[list["JobFeedMembership"]] = relationship(
        back_populates="job",
        cascade="save-update, merge, delete, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    web_document_links: Mapped[list["JobWebDocument"]] = relationship(
        back_populates="job",
        cascade="save-update, merge, delete, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
