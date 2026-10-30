from .base import ModelConfigBaseModel


class JobPageTargetDTO(ModelConfigBaseModel):
    """A job whose detail page is due, with the feed content hash it is fetched for."""

    id: int
    canonical_url: str
    content_hash: str


class JobPageFetchResultDTO(ModelConfigBaseModel):
    """One run over due detail pages.

    remaining counts the pages still due afterwards, including ones that
    failed in this run but may be retried later. stopped_early is True when
    the run gave up after repeated failed downloads.
    """

    attempted: int
    fetched: int
    unavailable: int
    failed: int
    remaining: int
    stopped_early: bool
