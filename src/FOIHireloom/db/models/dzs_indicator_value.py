from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DzsIndicatorValue(Base):
    """A monthly DZS labour-market value for one county and sex.

    value is NULL exactly when the source cell held a marker or nothing:
    missing_reason then says which, so a missing value is never a zero.
    is_provisional follows the source's footnotes, not the cell. import_id is
    the import that last wrote the row; revised_at is set when a later import
    changed its value.
    """

    __tablename__ = "dzs_indicator_values"
    __table_args__ = (
        UniqueConstraint("county_id", "indicator", "period", "sex"),
        CheckConstraint(
            "indicator IN ('active_population', 'employed', 'unemployed', 'unemployment_rate')",
            name="indicator_valid",
        ),
        CheckConstraint("sex IN ('total', 'women', 'men')", name="sex_valid"),
        CheckConstraint("period = date_trunc('month', period)::date", name="period_is_month_start"),
        CheckConstraint(
            "missing_reason IN ('no_occurrence', 'not_available', 'empty')", name="missing_reason_valid"
        ),
        CheckConstraint("(value IS NULL) = (missing_reason IS NOT NULL)", name="value_or_missing_reason"),
        CheckConstraint(
            "value >= 0 AND CASE WHEN indicator = 'unemployment_rate' THEN value <= 100 AND value = round(value, 1) "
            "ELSE value = trunc(value) END",
            name="value_in_unit",
        ),
        CheckConstraint(
            "source = 't1' OR (source = 'workbook_9_4_13' AND indicator = 'active_population') "
            "OR (source = 'workbook_9_4_14' AND indicator = 'unemployment_rate')",
            name="source_has_indicator",
        ),
        CheckConstraint("created_at <= updated_at", name="timestamps_ordered"),
        CheckConstraint("revised_at IS NULL OR revised_at BETWEEN created_at AND updated_at", name="revised_in_lifetime"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    county_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("counties.id", ondelete="RESTRICT"))
    indicator: Mapped[str] = mapped_column(Text)
    # First day of the reference month.
    period: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(Text)
    # Persons as whole numbers; the rate in percent with one decimal.
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    missing_reason: Mapped[str | None] = mapped_column(Text)
    is_provisional: Mapped[bool] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(Text)
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dzs_imports.id", ondelete="RESTRICT"), index=True)
    revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
