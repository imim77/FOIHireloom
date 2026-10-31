from typing import Literal

from .base import ModelConfigBaseModel

# permanent: "Na neodređeno"; fixed_term: "Na određeno"; other: "Drugi oblici
# rada" and HZZ's temporary seasonal work in agriculture.
type Contract = Literal["permanent", "fixed_term", "other"]
type Accommodation = Literal["none", "shared", "single", "family"]
type TransportAllowance = Literal["full", "partial", "none"]


class RawJobConditionsDTO(ModelConfigBaseModel):
    """The working conditions as an HZZ job detail page states them.

    Named as in ParsedJobPageDTO, so it validates from a parsed page or a
    job; lists are joined with "; ".
    """

    experience: str | None = None
    employment_type: str | None = None
    working_hours: str | None = None
    education: str | None = None
    accommodation: str | None = None
    work_schedule: str | None = None
    transport_allowance: str | None = None


class JobConditionsDTO(ModelConfigBaseModel):
    """Normalised working conditions; None means unknown, never "not required".

    A missing or empty value is unknown, and so is one that is not fully
    recognised, whose field is then named in unrecognised. Tags and
    education levels follow a fixed order; education_levels are the
    accepted levels from lowest to highest. full_time is True for "Puno
    radno vrijeme", which does not state weekly_hours.
    """

    experience_months: int | None = None
    trainee: bool | None = None
    contract: Contract | None = None
    employment_tags: tuple[str, ...] | None = None
    full_time: bool | None = None
    weekly_hours: int | None = None
    education_levels: tuple[str, ...] | None = None
    accommodation: Accommodation | None = None
    schedule_tags: tuple[str, ...] | None = None
    transport_allowance: TransportAllowance | None = None
    unrecognised: tuple[str, ...] = ()


class JobConditionsInputDTO(ModelConfigBaseModel):
    """A job's conditions as its fetched page states them, and the normalised ones stored for it."""

    job_id: int
    raw: RawJobConditionsDTO
    stored: JobConditionsDTO


class JobConditionsRunDTO(ModelConfigBaseModel):
    """One pass over the jobs with a fetched page.

    updated counts the jobs whose stored conditions changed; unrecognised
    counts the jobs per RawJobConditionsDTO field whose value was not
    recognised.
    """

    checked: int
    updated: int
    unrecognised: dict[str, int]
