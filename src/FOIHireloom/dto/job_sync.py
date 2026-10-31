from datetime import datetime

from .base import ModelConfigBaseModel
from .source_feed import FeedCategoryMappingDTO


class JobSnapshotDTO(ModelConfigBaseModel):
    id: int
    source_job_id: str
    content_hash: str


class CategoryEvidenceDTO(ModelConfigBaseModel):
    """A job without a description category and the confirmed mappings of
    the occupation feeds that list or have listed it, as (feed ID, category).

    category and category_feed_id are its current filled-in value, if any.
    """

    job_id: int
    category: str | None
    category_feed_id: int | None
    mappings: tuple[tuple[int, str], ...]


class FilledCategoryDTO(ModelConfigBaseModel):
    category: str
    feed_id: int


class MembershipSnapshotDTO(ModelConfigBaseModel):
    job_id: int
    presence_status: str


class FeedCheckDTO(ModelConfigBaseModel):
    """Outcome of one check of a feed, applied to its sync metadata.

    Validators and content-change time are only stored for a successful check,
    so a failed or rejected download is retried in full next time.
    """

    succeeded: bool
    etag: str | None = None
    source_last_modified_at: datetime | None = None
    content_changed: bool = False


class SyncRunOutcomeDTO(ModelConfigBaseModel):
    status: str
    http_status: int | None = None
    items_seen: int | None = None
    items_added: int | None = None
    items_updated: int | None = None
    items_invalid: int | None = None
    error_summary: str | None = None


class FeedSyncResultDTO(ModelConfigBaseModel):
    """items_unlinked counts an occupation feed's jobs that no county feed has imported.

    category_mapping is the occupation feed's mapping verified by this download.
    categories_filled counts its jobs whose category was filled in or changed
    from feed mappings, categories_cleared those whose filled-in category no
    mapping supports any more, and categories_conflicting those left without
    a category because confirmed mappings of their feeds disagree.
    """

    feed_id: int
    label: str
    status: str
    http_status: int | None = None
    items_seen: int = 0
    items_added: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    items_missing: int = 0
    items_returned: int = 0
    items_invalid: int = 0
    items_unlinked: int = 0
    category_mapping: FeedCategoryMappingDTO | None = None
    categories_filled: int = 0
    categories_cleared: int = 0
    categories_conflicting: int = 0
    error: str | None = None


class JobSyncResultDTO(ModelConfigBaseModel):
    feeds: tuple[FeedSyncResultDTO, ...]
    succeeded: int
    not_modified: int
    failed: int
    rejected: int
