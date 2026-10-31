from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
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
# Codes JobConditionsNormalizer stores, by column; a new code needs a
# migration. conditions_unrecognised names RawJobConditionsDTO fields.
CONDITION_CODES = {
    "contract": ("permanent", "fixed_term", "other"),
    "employment_tags": ("new_position", "vacancy", "replacement", "increased_workload", "seasonal", "reappointment",
                        "trainee", "retirees", "disability"),
    "education_levels": ("primary_lower", "primary", "secondary_3", "secondary_4", "college", "university"),
    "accommodation": ("none", "shared", "single", "family"),
    "schedule_tags": ("morning", "afternoon", "two_shifts", "three_shifts", "split", "night", "weekends_holidays"),
    "transport_allowance": ("full", "partial", "none"),
    "conditions_unrecognised": ("experience", "employment_type", "working_hours", "education", "accommodation",
                                "work_schedule", "transport_allowance"),
}
CONDITION_LISTS = ("employment_tags", "education_levels", "schedule_tags", "conditions_unrecognised")


def quoted(codes: tuple[str, ...]) -> str:
    return ", ".join(f"'{code}'" for code in codes)


CONDITIONS_KNOWN = " AND ".join(
    f"{column} <@ ARRAY[{quoted(codes)}]::text[]" if column in CONDITION_LISTS else f"{column} IN ({quoted(codes)})"
    for column, codes in CONDITION_CODES.items()
)
CONDITION_COLUMNS = (
    "experience_months", "trainee", "contract", "employment_tags", "full_time", "weekly_hours", "education_levels",
    "accommodation", "schedule_tags", "transport_allowance",
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
            "(category IS NULL) = (category_source IS NULL) "
            "AND (coalesce(category_source, '') = 'feed') = (category_feed_id IS NOT NULL) "
            "AND coalesce(category_source, 'description') IN ('description', 'feed')",
            name="category_source_recorded",
        ),
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
        CheckConstraint(CONDITIONS_KNOWN, name="conditions_known"),
        CheckConstraint(
            "(experience_months IS NULL) = (trainee IS NULL) AND experience_months >= 0 "
            "AND (NOT trainee OR experience_months = 0)",
            name="experience_consistent",
        ),
        CheckConstraint("weekly_hours > 0", name="weekly_hours_positive"),
        CheckConstraint(
            f"page_fetched_at IS NOT NULL OR (num_nonnulls({', '.join(CONDITION_COLUMNS)}) = 0 "
            "AND conditions_unrecognised = '{}')",
            name="conditions_need_page",
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
    # 'description' when the job's own description names the category, 'feed'
    # when it was filled in from category_feed_id's confirmed mapping. A
    # description category always replaces a filled-in one.
    category_source: Mapped[str | None] = mapped_column(Text)
    category_feed_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("source_feeds.id", ondelete="RESTRICT"), index=True
    )
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
    # The page's conditions as JobConditionsNormalizer codes, stored with the
    # page; None is unknown. conditions_unrecognised names the page fields
    # whose value was not recognised.
    experience_months: Mapped[int | None] = mapped_column(Integer)
    trainee: Mapped[bool | None] = mapped_column(Boolean)
    contract: Mapped[str | None] = mapped_column(Text)
    employment_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    full_time: Mapped[bool | None] = mapped_column(Boolean)
    weekly_hours: Mapped[int | None] = mapped_column(Integer)
    education_levels: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    accommodation: Mapped[str | None] = mapped_column(Text)
    schedule_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    transport_allowance: Mapped[str | None] = mapped_column(Text)
    conditions_unrecognised: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]")
    )
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
