from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from FOIHireloom.dto.base import ModelConfigBaseModel


class ForecastPointDTO(ModelConfigBaseModel):
    """One measured value in a time series used for forecasting."""

    date: date
    region: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float = Field(allow_inf_nan=False)
    source: str = "unknown"
    unit: str | None = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, value: object) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise TypeError("date must be a ISO date string or a date instance.")

    @field_validator("region", "metric", "source", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("forecast text field must be a string.")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("forecast text field must not be blank.")
        return cleaned


class ForecastSeriesDTO(ModelConfigBaseModel):
    """A sorted, region-specific series of observations."""

    region: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    points: list[ForecastPointDTO]

    @property
    def ordered_points(self) -> list[ForecastPointDTO]:
        return sorted(self.points, key=lambda point: point.date)
