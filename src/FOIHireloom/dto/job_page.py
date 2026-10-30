from .base import ModelConfigBaseModel


class JobPageTargetDTO(ModelConfigBaseModel):
    """A job whose detail page is due, with the feed content hash it is fetched for."""

    id: int
    canonical_url: str
    content_hash: str
