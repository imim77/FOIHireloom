from abc import ABC, abstractmethod

from FOIHireloom.dto.forecast_accuracy import ForecastAccuracyReportDTO, ForecastAccuracyRequestDTO


class ForecastAccuracyServiceInterface(ABC):
    """ForecastAccuracyServiceInterface evaluates county unemployment forecasts against held-out months."""

    @abstractmethod
    async def evaluate(self, request: ForecastAccuracyRequestDTO) -> ForecastAccuracyReportDTO:
        """Return rolling-origin scores, seasonal baselines and per-month evidence using a stored DZS snapshot."""
