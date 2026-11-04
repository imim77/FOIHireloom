from abc import ABC, abstractmethod

from FOIHireloom.dto.forecast import CountyForecastDTO, CountyForecastRequestDTO


class LabourMarketForecastServiceInterface(ABC):
    """Forecast county labour-market series from stored DZS values and HZZ job ads; nothing here contacts either."""

    @abstractmethod
    async def forecast(self, request: CountyForecastRequestDTO) -> CountyForecastDTO:
        """Forecast request.target for 1 to 6 distinct counties, as CountyForecastDTO describes.

        Without stored data, or with too short a series, a county gets no
        forecast and a reason. Raise InvalidIndicatorRequestError for too
        many, repeated or unknown counties or a horizon out of range, and
        ForecastUnavailableError when the model cannot run.
        """
