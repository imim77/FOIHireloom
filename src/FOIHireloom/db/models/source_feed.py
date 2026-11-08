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

SYNCED_SCOPES = ("county", "occupation")


class SourceFeed(Base):
    __tablename__ = "izvorni_kanali"
    __table_args__ = (
        CheckConstraint("length(btrim(oznaka)) > 0", name="oznaka_nije_prazna"),
        CheckConstraint("length(btrim(url_kanala)) > 0", name="url_kanala_nije_prazan"),
        CheckConstraint(
            "(opseg = 'county' AND id_zupanije IS NOT NULL) OR "
            "(opseg = 'occupation' AND id_zupanije IS NULL)",
            name="opseg_prema_zupaniji",
        ),
        CheckConstraint(
            "vrijeme_zadnjeg_uspjeha IS NULL OR "
            "(vrijeme_zadnje_provjere IS NOT NULL AND vrijeme_zadnjeg_uspjeha <= vrijeme_zadnje_provjere)",
            name="uspjeh_ne_nakon_provjere",
        ),
        CheckConstraint(
            "(stanje_pridruzivanja IS NULL AND pridruzena_kategorija IS NULL AND broj_podudarnih_primjera IS NULL "
            "AND broj_proturjecnih_primjera IS NULL AND vrijeme_provjere_pridruzivanja IS NULL) OR "
            "(opseg = 'occupation' AND stanje_pridruzivanja IS NOT NULL AND broj_podudarnih_primjera IS NOT NULL "
            "AND broj_proturjecnih_primjera IS NOT NULL AND vrijeme_provjere_pridruzivanja IS NOT NULL)",
            name="pridruzivanje_provjereno_za_zanimanje",
        ),
        CheckConstraint(
            "stanje_pridruzivanja IN ('confirmed', 'too_few_examples', 'contradicted') "
            "AND broj_podudarnih_primjera >= 0 "
            "AND broj_proturjecnih_primjera >= 0 "
            "AND (pridruzena_kategorija IS NULL) = (broj_podudarnih_primjera = 0) "
            "AND (stanje_pridruzivanja = 'contradicted') = (broj_proturjecnih_primjera > 0) "
            "AND (stanje_pridruzivanja <> 'confirmed' OR broj_podudarnih_primjera > 0)",
            name="primjeri_pridruzivanja_dosljedni",
        ),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    county_id: Mapped[int | None] = mapped_column(
        "id_zupanije", SmallInteger, ForeignKey("zupanije.id", ondelete="RESTRICT"), index=True,
        key="county_id",
    )
    ckan_resource_id: Mapped[UUID] = mapped_column(
        "id_ckan_resursa", Uuid, unique=True, key="ckan_resource_id",
    )
    label: Mapped[str] = mapped_column("oznaka", Text, key="label")
    feed_url: Mapped[str] = mapped_column("url_kanala", Text, unique=True, key="feed_url")
    scope: Mapped[str] = mapped_column("opseg", Text, key="scope")
    enabled: Mapped[bool] = mapped_column(
        "omogucen", Boolean, default=True, server_default=true(), key="enabled",
    )
    etag: Mapped[str | None] = mapped_column("http_oznaka_sadrzaja", Text, key="etag")
    source_last_modified_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_izmjene_izvora", DateTime(timezone=True), key="source_last_modified_at",
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_zadnje_provjere", DateTime(timezone=True), key="last_checked_at",
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_zadnjeg_uspjeha", DateTime(timezone=True), key="last_success_at",
    )
    last_content_change_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_zadnje_promjene_sadrzaja", DateTime(timezone=True), key="last_content_change_at",
    )
    mapped_category: Mapped[str | None] = mapped_column("pridruzena_kategorija", Text, key="mapped_category")
    mapping_status: Mapped[str | None] = mapped_column("stanje_pridruzivanja", Text, key="mapping_status")
    mapping_matching_examples: Mapped[int | None] = mapped_column(
        "broj_podudarnih_primjera", Integer, key="mapping_matching_examples",
    )
    mapping_contradicting_examples: Mapped[int | None] = mapped_column(
        "broj_proturjecnih_primjera", Integer, key="mapping_contradicting_examples",
    )
    mapping_verified_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_provjere_pridruzivanja", DateTime(timezone=True), key="mapping_verified_at",
    )

    county: Mapped["County | None"] = relationship(
        back_populates="source_feeds", lazy="raise"
    )
    sync_runs: Mapped[list["SyncRun"]] = relationship(
        back_populates="feed", passive_deletes="all", lazy="raise"
    )
    job_memberships: Mapped[list["JobFeedMembership"]] = relationship(
        back_populates="feed", passive_deletes="all", lazy="raise"
    )
