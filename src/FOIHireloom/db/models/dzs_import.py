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

    __tablename__ = "uvozi_dzs"
    __table_args__ = (
        CheckConstraint("stanje IN ('running', 'succeeded', 'failed', 'rejected')", name="stanje_ispravno"),
        CheckConstraint(
            "(stanje = 'running' AND vrijeme_zavrsetka IS NULL) OR "
            "(stanje <> 'running' AND vrijeme_zavrsetka IS NOT NULL AND vrijeme_zavrsetka >= vrijeme_pocetka)",
            name="zavrsetak_prema_stanju",
        ),
        CheckConstraint(
            "stanje <> 'succeeded' OR num_nonnulls(broj_dodanih_vrijednosti, broj_azuriranih_vrijednosti, broj_nepromijenjenih_vrijednosti) = 3",
            name="uspjeh_ima_brojace",
        ),
        CheckConstraint(
            "stanje NOT IN ('failed', 'rejected') OR sazetak_greske IS NOT NULL", name="neuspjeh_ima_gresku"
        ),
        CheckConstraint(
            "broj_dodanih_vrijednosti >= 0 AND broj_azuriranih_vrijednosti >= 0 AND broj_nepromijenjenih_vrijednosti >= 0", name="brojaci_nenegativni"
        ),
        Index("ix_uvozi_dzs_pocetak", text("vrijeme_pocetka DESC")),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    started_at: Mapped[datetime] = mapped_column(
        "vrijeme_pocetka", DateTime(timezone=True), server_default=func.now(), key="started_at",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_zavrsetka", DateTime(timezone=True), key="finished_at",
    )
    status: Mapped[str] = mapped_column(
        "stanje", Text, default="running", server_default="running", key="status",
    )
    values_inserted: Mapped[int | None] = mapped_column(
        "broj_dodanih_vrijednosti", Integer, key="values_inserted",
    )
    values_updated: Mapped[int | None] = mapped_column(
        "broj_azuriranih_vrijednosti", Integer, key="values_updated",
    )
    values_unchanged: Mapped[int | None] = mapped_column(
        "broj_nepromijenjenih_vrijednosti", Integer, key="values_unchanged",
    )
    error_summary: Mapped[str | None] = mapped_column("sazetak_greske", Text, key="error_summary")

    files: Mapped[list["DzsImportFile"]] = relationship(
        back_populates="dzs_import", order_by="DzsImportFile.role", passive_deletes=True, lazy="raise"
    )


class DzsImportFile(Base):
    """Provenance of one source file of an import: the T1 release table or the county workbook."""

    __tablename__ = "datoteke_uvoza_dzs"
    __table_args__ = (
        UniqueConstraint("import_id", "role"),
        CheckConstraint("uloga IN ('t1', 'workbook')", name="uloga_ispravna"),
        CheckConstraint("length(btrim(lokacija)) > 0", name="lokacija_nije_prazna"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_ispravan"),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    import_id: Mapped[int] = mapped_column(
        "id_uvoza", BigInteger, ForeignKey("uvozi_dzs.id", ondelete="CASCADE"), key="import_id",
    )
    role: Mapped[str] = mapped_column("uloga", Text, key="role")
    location: Mapped[str] = mapped_column("lokacija", Text, key="location")
    sheets: Mapped[list[str]] = mapped_column("listovi", ARRAY(Text), key="sheets")
    sha256: Mapped[str] = mapped_column("sha256", Text, key="sha256")
    source_last_modified_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_izmjene_izvora", DateTime(timezone=True), key="source_last_modified_at",
    )
    fetched_at: Mapped[datetime] = mapped_column("vrijeme_dohvata", DateTime(timezone=True), key="fetched_at")

    dzs_import: Mapped[DzsImport] = relationship(back_populates="files", lazy="raise")
