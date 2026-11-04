from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .dto import ForecastPointDTO, ForecastSeriesDTO


class ForecastDataset:
    """In-memory dataset for time-series forecasting built from source rows."""

    def __init__(self, points: Iterable[ForecastPointDTO]) -> None:
        self.points = list(points)
        if not self.points:
            raise ValueError("Forecast dataset must contain at least one point.")

    def by_region_metric(self, region: str, metric: str) -> list[ForecastPointDTO]:
        series = [point for point in self.points if point.region == region and point.metric == metric]
        return sorted(series, key=lambda point: point.date)

    def series(self) -> list[ForecastSeriesDTO]:
        grouped: dict[tuple[str, str], list[ForecastPointDTO]] = defaultdict(list)
        for point in self.points:
            grouped[(point.region, point.metric)].append(point)
        return [
            ForecastSeriesDTO(region=region, metric=metric, points=sorted(points, key=lambda point: point.date))
            for (region, metric), points in sorted(grouped.items())
        ]


class ForecastDatasetBuilder:
    @staticmethod
    def from_rows(rows: Iterable[dict]) -> ForecastDataset:
        points: list[ForecastPointDTO] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Each row must be a dictionary with time-series fields.")
            points.append(ForecastPointDTO.model_validate(row))
        return ForecastDataset(points)
