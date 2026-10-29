from .base import ModelConfigBaseModel


class CountyDefinitionDTO(ModelConfigBaseModel):
    """A county's stable application code and official name."""

    code: str
    name: str


class CountyDTO(CountyDefinitionDTO):
    id: int
