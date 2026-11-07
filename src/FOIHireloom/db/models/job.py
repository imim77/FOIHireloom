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

from FOIHireloom.domain.search_text import SEARCH_FOLD_FROM, SEARCH_FOLD_TO
from FOIHireloom.domain.skill_catalog import SKILL_FOLD_FROM, SKILL_FOLD_TO, SKILL_PATTERNS, URL_PATTERN

from .base import Base

# Title words get weight A, so a query restricted to it (kuhar:*A) tells
# whether the title matched; everything else keeps the default weight D. The
# job page's values replace the feed's truncated title and description once
# read, and add the employer, place of work and education.
SEARCH_TITLE_WEIGHT = "A"
SEARCH_DOCUMENT = (
    "setweight(to_tsvector('simple'::regconfig, translate("
    f"coalesce(naslov_stranice, naslov, ''), '{SEARCH_FOLD_FROM}', '{SEARCH_FOLD_TO}')), '{SEARCH_TITLE_WEIGHT}') || "
    "to_tsvector('simple'::regconfig, translate("
    "coalesce(tekst_opisa_stranice, tekst_opisa, '') || ' ' || coalesce(naziv_poslodavca_stranice, '') || ' ' || "
    "coalesce(mjesto_rada_stranice, '') || ' ' || coalesce(obrazovanje_stranice, ''), "
    f"'{SEARCH_FOLD_FROM}', '{SEARCH_FOLD_TO}'))"
)
# URLs must be removed before punctuation-sensitive skills are matched.
_SKILL_TEXT = (
    "regexp_replace(lower(translate("
    "coalesce(naslov_stranice, naslov, '') || ' ' || coalesce(tekst_opisa_stranice, tekst_opisa, ''), "
    f"'{SKILL_FOLD_FROM}', '{SKILL_FOLD_TO}')), '{URL_PATTERN}', ' ', 'g')"
)
SKILLS_DOCUMENT = "array_remove(ARRAY[" + ", ".join(
    f"CASE WHEN {_SKILL_TEXT} ~ '{pattern}' THEN '{code}' END"
    for code, pattern in SKILL_PATTERNS.items()
) + "], NULL)"

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


CONDITION_SQL_NAMES = {'contract': 'ugovor',
 'employment_tags': 'oznake_zaposlenja',
 'education_levels': 'razine_obrazovanja',
 'accommodation': 'smjestaj',
 'schedule_tags': 'oznake_rasporeda',
 'transport_allowance': 'naknada_prijevoza',
 'conditions_unrecognised': 'neprepoznati_uvjeti'}

CONDITIONS_KNOWN = " AND ".join(
    f"{CONDITION_SQL_NAMES[column]} <@ ARRAY[{quoted(codes)}]::text[]" if column in CONDITION_LISTS
    else f"{CONDITION_SQL_NAMES[column]} IN ({quoted(codes)})"
    for column, codes in CONDITION_CODES.items()
)
CONDITION_COLUMNS = (
    "mjeseci_iskustva", "pripravnik", "ugovor", "oznake_zaposlenja", "puno_radno_vrijeme", "tjedni_sati", "razine_obrazovanja",
    "smjestaj", "oznake_rasporeda", "naknada_prijevoza",
)

if TYPE_CHECKING:
    from .job_feed_membership import JobFeedMembership


class Job(Base):
    __tablename__ = "oglasi"
    __table_args__ = (
        UniqueConstraint("source_job_id"),
        UniqueConstraint("canonical_url"),
        CheckConstraint("length(btrim(izvorni_url)) > 0", name="izvorni_url_nije_prazan"),
        CheckConstraint("length(btrim(sazetak_sadrzaja)) > 0", name="sazetak_sadrzaja_nije_prazan"),
        CheckConstraint("vrijeme_prvog_opazanja <= vrijeme_zadnjeg_opazanja", name="vremena_opazanja_redom"),
        CheckConstraint(
            "(kategorija IS NULL) = (izvor_kategorije IS NULL) "
            "AND (coalesce(izvor_kategorije, '') = 'feed') = (id_kanala_kategorije IS NOT NULL) "
            "AND coalesce(izvor_kategorije, 'description') IN ('description', 'feed')",
            name="izvor_kategorije_zabiljezen",
        ),
        CheckConstraint(
            "vrijeme_promjene_sadrzaja BETWEEN vrijeme_prvog_opazanja AND vrijeme_zadnjeg_opazanja",
            name="promjena_unutar_opazanja",
        ),
        Index("ix_oglasi_vektor_pretrage", "search_vector", postgresql_using="gin"),
        Index("ix_oglasi_vjestine", "skills", postgresql_using="gin"),
        # Filters use these expressions (job_predicates.py); expression indexes
        # let the planner narrow matches before loading job content.
        Index("ix_oglasi_velika_kategorija", text("upper(kategorija)")),
        Index("ix_oglasi_rok_prijave", text("coalesce(rok_prijave_stranice, rok_prijave)")),
        CheckConstraint(
            "stanje_stranice IN ('pending', 'fetched', 'unavailable', 'failed')", name="stanje_stranice_poznato"
        ),
        CheckConstraint("(stanje_stranice = 'pending') = (vrijeme_provjere_stranice IS NULL)", name="provjera_stranice_zabiljezena"),
        CheckConstraint(
            "stanje_stranice <> 'fetched' OR (vrijeme_dohvata_stranice IS NOT NULL AND sazetak_izvora_stranice IS NOT NULL)",
            name="dohvat_stranice_zabiljezen",
        ),
        CheckConstraint(CONDITIONS_KNOWN, name="uvjeti_poznati"),
        CheckConstraint(
            "(mjeseci_iskustva IS NULL) = (pripravnik IS NULL) AND mjeseci_iskustva >= 0 "
            "AND (NOT pripravnik OR mjeseci_iskustva = 0)",
            name="iskustvo_dosljedno",
        ),
        CheckConstraint("tjedni_sati > 0", name="tjedni_sati_pozitivni"),
        CheckConstraint(
            f"vrijeme_dohvata_stranice IS NOT NULL OR (num_nonnulls({', '.join(CONDITION_COLUMNS)}) = 0 "
            "AND neprepoznati_uvjeti = '{}')",
            name="uvjeti_traze_stranicu",
        ),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    source_job_id: Mapped[str | None] = mapped_column("id_izvornog_oglasa", Text, key="source_job_id")
    canonical_url: Mapped[str] = mapped_column("izvorni_url", Text, key="canonical_url")
    title: Mapped[str | None] = mapped_column("naslov", Text, key="title")
    description_text: Mapped[str | None] = mapped_column("tekst_opisa", Text, key="description_text")
    published_on: Mapped[date | None] = mapped_column("datum_objave", Date, index=True, key="published_on")
    deadline_on: Mapped[date | None] = mapped_column("rok_prijave", Date, key="deadline_on")
    category: Mapped[str | None] = mapped_column("kategorija", Text, key="category")
    # 'description' when the job's own description names the category, 'feed'
    # when it was filled in from category_feed_id's confirmed mapping. A
    # description category always replaces a filled-in one.
    category_source: Mapped[str | None] = mapped_column("izvor_kategorije", Text, key="category_source")
    category_feed_id: Mapped[int | None] = mapped_column(
        "id_kanala_kategorije", BigInteger, ForeignKey("izvorni_kanali.id", ondelete="RESTRICT"),
        index=True, key="category_feed_id",
    )
    location_text: Mapped[str | None] = mapped_column("tekst_lokacije", Text, key="location_text")
    municipality: Mapped[str | None] = mapped_column("opcina", Text, key="municipality")
    quality_flags: Mapped[list[str]] = mapped_column(
        "oznake_kvalitete", MutableList.as_mutable(ARRAY(Text)), default=list,
        server_default=text("'{}'::text[]"), key="quality_flags",
    )
    content_hash: Mapped[str] = mapped_column("sazetak_sadrzaja", Text, key="content_hash")
    search_vector: Mapped[str | None] = mapped_column(
        "vektor_pretrage", TSVECTOR, Computed(SEARCH_DOCUMENT, persisted=True), deferred=True,
        key="search_vector",
    )
    skills: Mapped[list[str]] = mapped_column(
        "vjestine", ARRAY(Text), Computed(SKILLS_DOCUMENT, persisted=True), key="skills",
    )
    # Fields from the job's HZZ detail page, kept apart from the feed's values.
    # A later failed check keeps the last fetched values; page_source_hash is
    # the feed content hash they were fetched for.
    page_status: Mapped[str] = mapped_column(
        "stanje_stranice", Text, default="pending", server_default="pending", key="page_status",
    )
    page_checked_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_provjere_stranice", DateTime(timezone=True), key="page_checked_at",
    )
    page_fetched_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_dohvata_stranice", DateTime(timezone=True), key="page_fetched_at",
    )
    page_source_hash: Mapped[str | None] = mapped_column(
        "sazetak_izvora_stranice", Text, key="page_source_hash",
    )
    page_error: Mapped[str | None] = mapped_column("greska_stranice", Text, key="page_error")
    page_title: Mapped[str | None] = mapped_column("naslov_stranice", Text, key="page_title")
    page_work_place: Mapped[str | None] = mapped_column("mjesto_rada_stranice", Text, key="page_work_place")
    page_workers_needed: Mapped[int | None] = mapped_column(
        "broj_trazenih_radnika_stranice", Integer, key="page_workers_needed",
    )
    page_employment_type: Mapped[str | None] = mapped_column(
        "vrsta_zaposlenja_stranice", Text, key="page_employment_type",
    )
    page_working_hours: Mapped[str | None] = mapped_column(
        "radno_vrijeme_stranice", Text, key="page_working_hours",
    )
    page_work_schedule: Mapped[str | None] = mapped_column(
        "raspored_rada_stranice", Text, key="page_work_schedule",
    )
    page_accommodation: Mapped[str | None] = mapped_column(
        "smjestaj_stranice", Text, key="page_accommodation",
    )
    page_transport_allowance: Mapped[str | None] = mapped_column(
        "naknada_prijevoza_stranice", Text, key="page_transport_allowance",
    )
    page_valid_from: Mapped[date | None] = mapped_column(
        "datum_pocetka_stranice", Date, key="page_valid_from",
    )
    page_valid_until: Mapped[date | None] = mapped_column(
        "rok_prijave_stranice", Date, key="page_valid_until",
    )
    page_education: Mapped[str | None] = mapped_column("obrazovanje_stranice", Text, key="page_education")
    page_experience: Mapped[str | None] = mapped_column("iskustvo_stranice", Text, key="page_experience")
    page_description_text: Mapped[str | None] = mapped_column(
        "tekst_opisa_stranice", Text, key="page_description_text",
    )
    page_employer_name: Mapped[str | None] = mapped_column(
        "naziv_poslodavca_stranice", Text, key="page_employer_name",
    )
    # The page's conditions as JobConditionsNormalizer codes, stored with the
    # page; None is unknown. conditions_unrecognised names the page fields
    # whose value was not recognised.
    experience_months: Mapped[int | None] = mapped_column(
        "mjeseci_iskustva", Integer, key="experience_months",
    )
    trainee: Mapped[bool | None] = mapped_column("pripravnik", Boolean, key="trainee")
    contract: Mapped[str | None] = mapped_column("ugovor", Text, key="contract")
    employment_tags: Mapped[list[str] | None] = mapped_column(
        "oznake_zaposlenja", ARRAY(Text), key="employment_tags",
    )
    full_time: Mapped[bool | None] = mapped_column("puno_radno_vrijeme", Boolean, key="full_time")
    weekly_hours: Mapped[int | None] = mapped_column("tjedni_sati", Integer, key="weekly_hours")
    education_levels: Mapped[list[str] | None] = mapped_column(
        "razine_obrazovanja", ARRAY(Text), key="education_levels",
    )
    accommodation: Mapped[str | None] = mapped_column("smjestaj", Text, key="accommodation")
    schedule_tags: Mapped[list[str] | None] = mapped_column(
        "oznake_rasporeda", ARRAY(Text), key="schedule_tags",
    )
    transport_allowance: Mapped[str | None] = mapped_column(
        "naknada_prijevoza", Text, key="transport_allowance",
    )
    conditions_unrecognised: Mapped[list[str]] = mapped_column(
        "neprepoznati_uvjeti", ARRAY(Text), default=list, server_default=text("'{}'::text[]"),
        key="conditions_unrecognised",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        "vrijeme_prvog_opazanja", DateTime(timezone=True), server_default=func.now(),
        key="first_seen_at",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        "vrijeme_zadnjeg_opazanja", DateTime(timezone=True), server_default=func.now(),
        key="last_seen_at",
    )
    content_changed_at: Mapped[datetime] = mapped_column(
        "vrijeme_promjene_sadrzaja", DateTime(timezone=True), server_default=func.now(),
        key="content_changed_at",
    )

    feed_memberships: Mapped[list["JobFeedMembership"]] = relationship(
        back_populates="job",
        cascade="save-update, merge, delete, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
