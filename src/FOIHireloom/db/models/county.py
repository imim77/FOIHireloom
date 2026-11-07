from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Identity, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .source_feed import SourceFeed


class County(Base):
    __tablename__ = "zupanije"
    __table_args__ = (
        CheckConstraint("length(btrim(sifra)) > 0", name="sifra_nije_prazna"),
        CheckConstraint("length(btrim(naziv)) > 0", name="naziv_nije_prazan"),
        CheckConstraint("iso_sifra ~ '^HR-(0[1-9]|1[0-9]|2[01])$'", name="iso_sifra_ispravna"),
    )

    id: Mapped[int] = mapped_column("id", SmallInteger, Identity(), primary_key=True, key="id")
    code: Mapped[str] = mapped_column("sifra", Text, unique=True, key="code")
    # ISO 3166-2:HR, HR-01 … HR-21; links DZS tables to the county.
    iso_code: Mapped[str] = mapped_column("iso_sifra", Text, unique=True, key="iso_code")
    name: Mapped[str] = mapped_column("naziv", Text, unique=True, key="name")

    source_feeds: Mapped[list["SourceFeed"]] = relationship(
        back_populates="county", passive_deletes="all", lazy="raise"
    )
