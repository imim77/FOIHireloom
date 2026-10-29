from datetime import datetime
from uuid import UUID

from .base import ModelConfigBaseModel
from .ckan import CkanResource
from .county import CountyDefinitionDTO


class SourceFeedDTO(ModelConfigBaseModel):
    id: int
    county_id: int | None
    ckan_resource_id: UUID
    label: str
    feed_url: str
    scope: str
    enabled: bool
    etag: str | None = None
    source_last_modified_at: datetime | None = None


class SourceFeedCreateDTO(ModelConfigBaseModel):
    """A new Croatian county feed; scope and defaults are set by the DAO."""

    county_id: int
    ckan_resource_id: UUID
    label: str
    feed_url: str


class SourceFeedUpdateDTO(SourceFeedCreateDTO):
    """Registration metadata for an existing feed.

    reset_http_validators clears the ETag and Last-Modified values, which
    belong to the previous URL.
    """

    reset_http_validators: bool = False


class PlannedSourceDTO(ModelConfigBaseModel):
    resource: CkanResource
    county: CountyDefinitionDTO
    label: str


class RegistrationPlanDTO(ModelConfigBaseModel):
    sources: tuple[PlannedSourceDTO, ...]
    resources_skipped: int


class RegistrationPreviewDTO(ModelConfigBaseModel):
    counties: int
    feeds: int
    resources_skipped: int


class RegistrationResultDTO(ModelConfigBaseModel):
    counties_added: int
    feeds_added: int
    feeds_updated: int
    feeds_unchanged: int
    resources_skipped: int
