from uuid import UUID

from pydantic import AnyHttpUrl

from .base import ModelConfigBaseModel


class CkanResource(ModelConfigBaseModel):
    """One resource of a CKAN package_show response."""

    id: UUID
    url: AnyHttpUrl
    name: str | None = None
    description: str | None = None
    format: str | None = None
    state: str | None = "active"


class CkanPackage(ModelConfigBaseModel):
    resources: list[CkanResource]
