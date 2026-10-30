from datetime import date

from .base import ModelConfigBaseModel


class ParsedJobPageDTO(ModelConfigBaseModel):
    """The structured fields of an HZZ job detail page; None when the page omits one.

    Fields HZZ shows as lists, such as several employment types, are joined
    with "; ". The employer's contact details are deliberately not kept.
    """

    title: str | None
    work_place: str | None
    workers_needed: int | None
    employment_type: str | None
    working_hours: str | None
    work_schedule: str | None
    accommodation: str | None
    transport_allowance: str | None
    valid_from: date | None
    valid_until: date | None
    education: str | None
    experience: str | None
    description_text: str | None
    employer_name: str | None
