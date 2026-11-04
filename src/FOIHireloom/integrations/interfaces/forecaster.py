from abc import ABC, abstractmethod
from collections.abc import Sequence

from FOIHireloom.dto.forecast import QuantileForecastDTO


class TimeSeriesForecasterInterface(ABC):
    """Forecast equally spaced series with a pretrained model; it knows nothing about what the numbers mean."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model's ID, for telling users where a forecast comes from."""

    @abstractmethod
    async def forecast(self, histories: Sequence[Sequence[float]], horizon: int) -> list[QuantileForecastDTO]:
        """Return horizon future steps of each history, oldest value first, in the given order.

        NaN marks a missing past value. Quantiles follow QUANTILE_LEVELS.
        Raise ForecastUnavailableError when the model cannot be loaded or run.
        """
