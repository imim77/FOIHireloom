from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    Text,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .county import County
    from .job_feed_membership import JobFeedMembership
    from .sync_run import SyncRun

# County feeds place a job in a county; occupation feeds only add an HZZ
# occupation group to jobs already known from county feeds. Legacy EU rows
# are kept but never synced.
SYNCED_SCOPES = ("county", "occupation")


class SourceFeed(Base):
    __tablename__ = "source_feeds"
    __table_args__ = (
        CheckConstraint("length(btrim(label)) > 0", name="label_not_blank"),
        CheckConstraint("length(btrim(feed_url)) > 0", name="url_not_blank"),
        CheckConstraint(
            "(scope = 'county' AND county_id IS NOT NULL) OR "
            "(scope IN ('occupation', 'eu') AND county_id IS NULL)",
            name="scope_matches_county",
        ),
        CheckConstraint(
            "last_success_at IS NULL OR "
            "(last_checked_at IS NOT NULL AND last_success_at <= last_checked_at)",
            name="success_not_after_check",
        ),
        CheckConstraint(
            "(mapping_status IS NULL AND mapped_category IS NULL AND mapping_matching_examples IS NULL "
            "AND mapping_contradicting_examples IS NULL AND mapping_verified_at IS NULL) OR "
            "(scope = 'occupation' AND mapping_status IS NOT NULL AND mapping_matching_examples IS NOT NULL "
            "AND mapping_contradicting_examples IS NOT NULL AND mapping_verified_at IS NOT NULL)",
            name="mapping_verified_for_occupation",
        ),
        CheckConstraint(
            "mapping_status IN ('confirmed', 'too_few_examples', 'contradicted') "
            "AND mapping_matching_examples >= 0 "
            "AND mapping_contradicting_examples >= 0 "
            "AND (mapped_category IS NULL) = (mapping_matching_examples = 0) "
            "AND (mapping_status = 'contradicted') = (mapping_contradicting_examples > 0) "
            "AND (mapping_status <> 'confirmed' OR mapping_matching_examples > 0)",
            name="mapping_evidence_consistent",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    county_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("counties.id", ondelete="RESTRICT"), index=True
    )
    ckan_resource_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    label: Mapped[str] = mapped_column(Text)
    feed_url: Mapped[str] = mapped_column(Text, unique=True)
    scope: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    etag: Mapped[str | None] = mapped_column(Text)
    source_last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_content_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # An occupation feed's category, checked against the explicit categories of
    # its own jobs because CKAN labels name the wrong group. Only a confirmed
    # mapping may fill in categories that job descriptions leave out.
    mapped_category: Mapped[str | None] = mapped_column(Text)
    mapping_status: Mapped[str | None] = mapped_column(Text)
    mapping_matching_examples: Mapped[int | None] = mapped_column(Integer)
    mapping_contradicting_examples: Mapped[int | None] = mapped_column(Integer)
    mapping_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    county: Mapped["County | None"] = relationship(
        back_populates="source_feeds", lazy="raise"
    )
    sync_runs: Mapped[list["SyncRun"]] = relationship(
        back_populates="feed", passive_deletes="all", lazy="raise"
    )
    job_memberships: Mapped[list["JobFeedMembership"]] = relationship(
        back_populates="feed", passive_deletes="all", lazy="raise"
    )
