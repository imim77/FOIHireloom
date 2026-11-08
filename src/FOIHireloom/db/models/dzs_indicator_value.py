from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DzsIndicatorValue(Base):
    """A monthly DZS labour-market value for one county and sex.

    value is NULL exactly when the source cell held a marker or nothing:
    missing_reason then says which, so a missing value is never a zero.
    is_provisional follows the source's footnotes, not the cell. import_id is
    the import that last wrote the row.
    """

    __tablename__ = "vrijednosti_pokazatelja_dzs"
    __table_args__ = (
        UniqueConstraint("county_id", "indicator", "period", "sex", name="uq_vrijednosti_pokazatelja_dzs_prirodni_kljuc"),
        CheckConstraint(
            "pokazatelj IN ('active_population', 'employed', 'unemployed', 'unemployment_rate')",
            name="pokazatelj_ispravan",
        ),
        CheckConstraint("spol IN ('total', 'women', 'men')", name="spol_ispravan"),
        CheckConstraint("razdoblje = date_trunc('month', razdoblje)::date", name="razdoblje_pocinje_mjesecom"),
        CheckConstraint(
            "razlog_nedostupnosti IN ('no_occurrence', 'not_available', 'empty')", name="razlog_nedostupnosti_ispravan"
        ),
        CheckConstraint("(vrijednost IS NULL) = (razlog_nedostupnosti IS NOT NULL)", name="vrijednost_ili_razlog"),
        CheckConstraint(
            "vrijednost >= 0 AND CASE WHEN pokazatelj = 'unemployment_rate' THEN vrijednost <= 100 AND vrijednost = round(vrijednost, 1) "
            "ELSE vrijednost = trunc(vrijednost) END",
            name="vrijednost_u_jedinici",
        ),
        CheckConstraint(
            "izvor = 't1' OR (izvor = 'workbook_9_4_13' AND pokazatelj = 'active_population') "
            "OR (izvor = 'workbook_9_4_14' AND pokazatelj = 'unemployment_rate')",
            name="izvor_ima_pokazatelj",
        ),
    )

    id: Mapped[int] = mapped_column("id", BigInteger, Identity(), primary_key=True, key="id")
    county_id: Mapped[int] = mapped_column(
        "id_zupanije", SmallInteger, ForeignKey("zupanije.id", ondelete="RESTRICT"), key="county_id",
    )
    indicator: Mapped[str] = mapped_column("pokazatelj", Text, key="indicator")
    period: Mapped[date] = mapped_column("razdoblje", Date, key="period")
    sex: Mapped[str] = mapped_column("spol", Text, key="sex")
    value: Mapped[Decimal | None] = mapped_column("vrijednost", Numeric, key="value")
    missing_reason: Mapped[str | None] = mapped_column("razlog_nedostupnosti", Text, key="missing_reason")
    is_provisional: Mapped[bool] = mapped_column("privremeni_podatak", Boolean, key="is_provisional")
    source: Mapped[str] = mapped_column("izvor", Text, key="source")
    import_id: Mapped[int] = mapped_column(
        "id_uvoza", BigInteger, ForeignKey("uvozi_dzs.id", ondelete="RESTRICT"), index=True,
        key="import_id",
    )
