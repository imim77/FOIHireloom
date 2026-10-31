from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import model_validator

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
    """A new Croatian county or occupation feed; other defaults are set by the DAO.

    County feeds name their county; occupation feeds have none.
    """

    scope: Literal["county", "occupation"] = "county"
    county_id: int | None
    ckan_resource_id: UUID
    label: str
    feed_url: str

    @model_validator(mode="after")
    def county_matches_scope(self) -> Self:
        if (self.scope == "county") != (self.county_id is not None):
            raise ValueError("County feeds need a county and occupation feeds must not have one.")
        return self


class SourceFeedUpdateDTO(SourceFeedCreateDTO):
    """Registration metadata for an existing feed.

    reset_http_validators clears the ETag and Last-Modified values, which
    belong to the previous URL. The scope must match the existing feed's.
    """

    reset_http_validators: bool = False


class PlannedSourceDTO(ModelConfigBaseModel):
    """A CKAN resource to register; occupation feeds have no county."""

    resource: CkanResource
    scope: Literal["county", "occupation"] = "county"
    county: CountyDefinitionDTO | None
    label: str


class RegistrationPlanDTO(ModelConfigBaseModel):
    sources: tuple[PlannedSourceDTO, ...]
    resources_skipped: int


class RegistrationPreviewDTO(ModelConfigBaseModel):
    """feeds counts both scopes; occupation_feeds is the occupation part."""

    counties: int
    feeds: int
    occupation_feeds: int
    resources_skipped: int


class RegistrationResultDTO(ModelConfigBaseModel):
    counties_added: int
    feeds_added: int
    feeds_updated: int
    feeds_unchanged: int
    resources_skipped: int
