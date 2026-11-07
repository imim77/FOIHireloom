from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from .base import ModelConfigBaseModel

DzsIndicator = Literal["active_population", "employed", "unemployed", "unemployment_rate"]
DzsSex = Literal["total", "women", "men"]
DzsValueSource = Literal["t1", "workbook_9_4_13", "workbook_9_4_14"]
# "-" means no occurrence, "…" that DZS does not have the figure; neither is a zero.
DzsMissingReason = Literal["no_occurrence", "not_available", "empty"]
DzsFileRole = Literal["t1", "workbook"]
DzsImportStatus = Literal["succeeded", "failed", "rejected", "validated"]


class DzsValueDTO(ModelConfigBaseModel):
    """One DZS cell for a county, or for Croatia as a whole when county_iso is None.

    value is None exactly when missing_reason is set. Persons are whole
    numbers; the unemployment rate is a percentage with one decimal.
    """

    county_iso: str | None
    indicator: DzsIndicator
    period: date
    sex: DzsSex
    value: Decimal | None
    missing_reason: DzsMissingReason | None = None
    is_provisional: bool
    source: DzsValueSource

    @property
    def key(self) -> tuple[str | None, str, date, str]:
        return self.county_iso, self.indicator, self.period, self.sex


class DzsValueSnapshotDTO(DzsValueDTO):
    """A stored value with its row ID."""

    id: int
    county_iso: str


class DzsValueChangeDTO(ModelConfigBaseModel):
    """DzsValueChangeDTO carries the replacement content of a stored row."""

    id: int
    value: DzsValueDTO


class DzsSeriesDTO(ModelConfigBaseModel):
    """What a release supplies for one source table, after T1 took precedence for shared keys."""

    source: DzsValueSource
    values: int
    provisional: int
    missing: int
    first_period: date
    last_period: date


class DzsReleaseDTO(ModelConfigBaseModel):
    """The validated county values of a T1 table and county workbook, one per key."""

    values: tuple[DzsValueDTO, ...]
    series: tuple[DzsSeriesDTO, ...]


class DzsSourceDTO(ModelConfigBaseModel):
    """Where to obtain a file: a URL, or a local path when local is True."""

    location: str
    local: bool = False


class DzsFileResponseDTO(ModelConfigBaseModel):
    """The bytes of one downloaded or local DZS file with its source modification time, if known."""

    content: bytes
    last_modified: datetime | None = None


class DzsFileDTO(ModelConfigBaseModel):
    """Provenance of one source file: location is the URL or the local path as given."""

    role: DzsFileRole
    location: str
    sheets: tuple[str, ...]
    sha256: str
    size_bytes: int
    last_modified: datetime | None = None
    fetched_at: datetime


class DzsImportOutcomeDTO(ModelConfigBaseModel):
    status: Literal["succeeded", "failed", "rejected"]
    values_inserted: int | None = None
    values_updated: int | None = None
    values_unchanged: int | None = None
    error_summary: str | None = None
    files: tuple[DzsFileDTO, ...] = ()


class DzsImportResultDTO(ModelConfigBaseModel):
    """Summary of one import. A dry run never touches the database: import_id
    and the write counts are then None and status is "validated" on success.

    errors lists validation problems (at most ERROR_LIMIT, then a count of the
    rest) or the single error of a failed run.
    """

    import_id: int | None = None
    status: DzsImportStatus
    dry_run: bool = False
    files: tuple[DzsFileDTO, ...] = ()
    series: tuple[DzsSeriesDTO, ...] = ()
    values_inserted: int | None = None
    values_updated: int | None = None
    values_unchanged: int | None = None
    errors: tuple[str, ...] = ()


class DzsStoredValueDTO(ModelConfigBaseModel):
    """A stored county value as the indicators read it; value is None exactly when missing_reason is set."""

    county_id: int
    indicator: DzsIndicator
    period: date
    sex: DzsSex
    value: Decimal | None
    missing_reason: DzsMissingReason | None
    is_provisional: bool
    source: DzsValueSource


class DzsImportFileRefDTO(ModelConfigBaseModel):
    """Where an import's file came from: location is the URL, or a local path as given to the command."""

    role: DzsFileRole
    location: str
    fetched_at: datetime
    last_modified: datetime | None = None


class DzsImportProvenanceDTO(ModelConfigBaseModel):
    """The latest succeeded DZS import: when it finished and the files it read."""

    import_id: int
    finished_at: datetime
    files: tuple[DzsImportFileRefDTO, ...]
