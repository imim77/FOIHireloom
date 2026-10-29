from datetime import datetime

from .base import ModelConfigBaseModel


class JobSnapshotDTO(ModelConfigBaseModel):
    id: int
    source_job_id: str
    content_hash: str


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
    error: str | None = None


class JobSyncResultDTO(ModelConfigBaseModel):
    feeds: tuple[FeedSyncResultDTO, ...]
    succeeded: int
    not_modified: int
    failed: int
    rejected: int
