from .base import ModelConfigBaseModel


class CountyDefinitionDTO(ModelConfigBaseModel):
    """A county's stable application code, ISO 3166-2:HR code and official name."""

    code: str
    iso_code: str
    name: str


class CountyDTO(CountyDefinitionDTO):
    id: int
