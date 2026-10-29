from datetime import date

from .base import ModelConfigBaseModel


class ParsedJobDTO(ModelConfigBaseModel):
    """A job advertisement as published in one feed item.

    Optional fields are None when the source omits them or truncates them
    beyond recognition; quality_flags says which values may be incomplete.
    """

    source_job_id: str
    source_guid: str
    canonical_url: str
    title: str | None
    subject: str | None
    description_raw: str
    description_text: str | None
    published_on: date
    deadline_on: date | None
    category: str | None
    location_text: str | None
    quality_flags: tuple[str, ...]
    content_hash: str


class ParsedFeedDTO(ModelConfigBaseModel):
    jobs: tuple[ParsedJobDTO, ...]
    invalid_items: int
