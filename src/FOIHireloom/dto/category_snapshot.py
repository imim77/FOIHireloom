from datetime import datetime
from uuid import UUID

from .base import ModelConfigBaseModel

# A snapshot's job row: source job ID, description category, occupation feed
# IDs, stored category, its source and its feed ID. Categories are indices
# into CategorySnapshotDTO.categories.
CategorySnapshotRow = tuple[str | None, int | None, tuple[int, ...], int | None, str | None, int | None]
JOB_COLUMNS = (
    "source_job_id", "description_category", "occupation_feed_ids", "category", "category_source", "category_feed_id",
)


class CategoryInputDTO(ModelConfigBaseModel):
    """A listed job's category fill inputs and its stored result.

    description_category is set only when the category comes from the job's
    description; occupation_feed_ids are all occupation feeds that list or
    have listed it.
    """

    source_job_id: str | None
    description_category: str | None
    occupation_feed_ids: tuple[int, ...]
    category: str | None
    category_source: str | None
    category_feed_id: int | None


class CategorySnapshotFeedDTO(ModelConfigBaseModel):
    """A county or occupation feed's fetch times and, for occupation feeds, its category mapping."""

    id: int
    scope: str
    label: str
    feed_url: str
    ckan_resource_id: UUID
    last_success_at: datetime | None
    last_content_change_at: datetime | None
    source_last_modified_at: datetime | None
    mapped_category: str | None
    mapping_status: str | None
    mapping_matching_examples: int | None
    mapping_contradicting_examples: int | None
    mapping_verified_at: datetime | None


class CategoryCoverageDTO(ModelConfigBaseModel):
    """Listed jobs by where their category comes from; listed is the denominator.

    before counts jobs with a description category, after those with any
    category, filled those filled in from a feed and unknown the rest.
    conflicting counts jobs without a description category whose feeds'
    confirmed mappings disagree.
    """

    listed: int
    before: int
    after: int
    filled: int
    unknown: int
    conflicting: int


class CategorySnapshotDTO(ModelConfigBaseModel):
    """The category fill of every listed job at generated_at, with the feeds and mappings behind it."""

    generated_at: datetime
    denominator: str
    coverage: CategoryCoverageDTO
    feeds: tuple[CategorySnapshotFeedDTO, ...]
    categories: tuple[str, ...]
    job_columns: tuple[str, ...] = JOB_COLUMNS
    jobs: tuple[CategorySnapshotRow, ...]
