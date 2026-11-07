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
    __tablename__ = "sinkronizacije"
    __table_args__ = (
        CheckConstraint(
            "stanje IN ('running', 'succeeded', 'not_modified', 'failed', 'rejected')",
            name="stanje_ispravno",
        ),
        CheckConstraint(
            "(stanje = 'running' AND vrijeme_zavrsetka IS NULL) OR "
            "(stanje <> 'running' AND vrijeme_zavrsetka IS NOT NULL AND vrijeme_zavrsetka >= vrijeme_pocetka)",
            name="zavrsetak_prema_stanju",
        ),
        CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599", name="http_status_ispravan"
        ),
        CheckConstraint(
            "stanje <> 'succeeded' OR (http_status IS NOT NULL AND http_status = 200)",
            name="uspjeh_trazi_http_200",
        ),
        CheckConstraint(
            "stanje <> 'not_modified' OR (http_status IS NOT NULL AND http_status = 304)",
            name="nepromijenjeno_trazi_http_304",
        ),
        CheckConstraint("broj_videnih_stavki IS NULL OR broj_videnih_stavki >= 0", name="broj_videnih_stavki_nenegativan"),
        CheckConstraint("broj_dodanih_stavki IS NULL OR broj_dodanih_stavki >= 0", name="broj_dodanih_stavki_nenegativan"),
        CheckConstraint("broj_azuriranih_stavki IS NULL OR broj_azuriranih_stavki >= 0", name="broj_azuriranih_stavki_nenegativan"),
        CheckConstraint("broj_neispravnih_stavki IS NULL OR broj_neispravnih_stavki >= 0", name="broj_neispravnih_stavki_nenegativan"),
        Index("ix_sinkronizacije_kanal_pocetak", "feed_id", text("vrijeme_pocetka DESC")),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    feed_id: Mapped[int] = mapped_column(
        "id_kanala", BigInteger, ForeignKey("izvorni_kanali.id", ondelete="RESTRICT"), key="feed_id",
    )
    started_at: Mapped[datetime] = mapped_column(
        "vrijeme_pocetka", DateTime(timezone=True), server_default=func.now(), key="started_at",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        "vrijeme_zavrsetka", DateTime(timezone=True), key="finished_at",
    )
    status: Mapped[str] = mapped_column(
        "stanje", Text, default="running", server_default="running", key="status",
    )
    http_status: Mapped[int | None] = mapped_column("http_status", SmallInteger, key="http_status")
    items_seen: Mapped[int | None] = mapped_column("broj_videnih_stavki", Integer, key="items_seen")
    items_added: Mapped[int | None] = mapped_column("broj_dodanih_stavki", Integer, key="items_added")
    items_updated: Mapped[int | None] = mapped_column("broj_azuriranih_stavki", Integer, key="items_updated")
    items_invalid: Mapped[int | None] = mapped_column("broj_neispravnih_stavki", Integer, key="items_invalid")
    error_summary: Mapped[str | None] = mapped_column("sazetak_greske", Text, key="error_summary")

    feed: Mapped["SourceFeed"] = relationship(back_populates="sync_runs", lazy="raise")
