from datetime import date
from typing import Literal

from pydantic import Field

from .base import ModelConfigBaseModel
from .job_market import MarketCountDTO
from .job_search import ActiveFilterDTO, CoverageDTO

type AccommodationGroup = Literal["offered", "not_offered", "unknown"]


class AccommodationGroupDTO(ModelConfigBaseModel):
    key: AccommodationGroup
    label: str
    jobs: int = Field(ge=0)
    share: float = Field(ge=0, le=100)


class AccommodationComparisonDTO(ModelConfigBaseModel):
    """Three disjoint groups of matching job ads; counts sum to total_jobs.

    offered is shared + single + family; not_offered is explicitly none;
    unknown is total_jobs minus all known accommodation types. Unknowns
    for other requested conditions are separate from this partition.
    """

    title: str
    description: str
    today: date
    total_jobs: int = Field(ge=0)
    known_jobs: int = Field(ge=0)
    groups: tuple[AccommodationGroupDTO, ...]
    accommodation_types: tuple[MarketCountDTO, ...]
    coverage: CoverageDTO
    active_filters: tuple[ActiveFilterDTO, ...]
    coverage_note: str | None
    unknown_conditions: dict[str, int]
    unknown_total: int
    unknown_note: str | None
    view_notes: tuple[str, ...]
