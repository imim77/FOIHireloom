from pydantic import BaseModel, ConfigDict


class ModelConfigBaseModel(BaseModel):
    """Immutable DTO that can also be read from ORM entities."""

    model_config = ConfigDict(extra="ignore", from_attributes=True, frozen=True)
