from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import Field

from FOIHireloom.dto.dzs import DzsSex
from FOIHireloom.dto.forecast import (
    MAX_FORECAST_COUNTIES,
    CountyForecastDTO,
    CountyForecastRequestDTO,
    CountyForecastViewDTO,
    ForecastTarget,
)
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface

from .apps.labour_market_forecast import labour_market_forecast
from .apps.views import LABOUR_MARKET_FORECAST
from .tool_provider import DATA_ONLY, ServiceToolGroup

# Key of the forecast service in the server's lifespan context.
LABOUR_FORECAST_SERVICE = "labour_forecast_service"

ForecastCounties = Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(
    min_length=1, max_length=MAX_FORECAST_COUNTIES,
    description=f"1 to {MAX_FORECAST_COUNTIES} different counties, as codes or names from list_regions, e.g. "
                "['varazdinska', 'medimurska'].",
)]
Target = Annotated[ForecastTarget, Field(
    description="What to forecast: 'unemployment_rate' (DZS registered unemployment rate, %, monthly), "
                "'unemployed' (DZS registered unemployed persons, monthly), 'employed' (DZS employed persons, "
                "monthly) or 'job_ads' (new HZZ job advertisements per week, i.e. demand for workers).",
)]
Horizon = Annotated[int | None, Field(
    ge=1, le=26,
    description="How many periods ahead: months for DZS targets (1 to 24, default 12), weeks for job_ads "
                "(1 to 26, default 8). Leave out unless the user names a time span.",
)]
ForecastSex = Annotated[DzsSex, Field(description="DZS targets only: 'total', 'women' or 'men'.")]
ForecastCounty = Annotated[str, Field(
    min_length=1, max_length=100,
    description="One county code or name from list_regions, e.g. 'varazdinska' or 'Varaždinska županija'.",
)]


class ForecastTools(ServiceToolGroup[LabourMarketForecastServiceInterface]):
    """ForecastTools exposes county labour-market forecasts made by Amazon Chronos.

    The server's lifespan must provide LabourMarketForecastService under
    LABOUR_FORECAST_SERVICE.
    """

    _service_key = LABOUR_FORECAST_SERVICE
    _caller_errors = (InvalidIndicatorRequestError, ForecastUnavailableError)
    _unavailable_message = "Forecast data is temporarily unavailable; try again later."

    def register(self, server: FastMCP) -> None:
        self._add_tool(server, self.forecast_labour_market, app=DATA_ONLY)
        self._add_tool(server, self.show_labour_market_forecast, app=LABOUR_MARKET_FORECAST.app_config)

    async def forecast_labour_market(
        self,
        ctx: Context,
        counties: ForecastCounties,
        target: Target,
        horizon: Horizon = None,
        sex: ForecastSex = "total",
    ) -> CountyForecastDTO:
        """App-only Chronos data endpoint for 1 to 6 counties.

        For user-facing county forecasts use show_labour_market_forecast,
        which returns the same forecast with a chart and exact values.
        This endpoint remains available to apps consuming several counties.

        Per county, history holds recent observed values (oldest first)
        and forecast the predicted periods with median and an 80%
        interval (low, high); change_to_horizon compares the last
        forecast median with last_observed. Periods are first days of
        months, or Mondays for weekly job_ads. A county without a
        forecast has unavailable_reason: 'no_dzs_data', 'no_common_period',
        'no_hzz_data' or 'not_enough_history'; say the forecast is not
        available and why, never invent numbers.

        Always tell the user that this is a model estimate from past
        data, give the interval next to the median, name the sources and
        the model, and pass on the notes. job_ads counts advertisements,
        not workers.
        """
        request = CountyForecastRequestDTO(counties=tuple(counties), target=target, horizon=horizon, sex=sex)
        return await self._call(self._service(ctx).forecast(request))

    async def show_labour_market_forecast(
        self,
        ctx: Context,
        county: ForecastCounty,
        target: Target = "unemployment_rate",
        horizon: Horizon = None,
        sex: ForecastSex = "total",
    ) -> CountyForecastViewDTO:
        """Forecast and display unemployment, employment or new job ads for one Croatian county with Amazon Chronos.

        DEFAULT for questions about a county's future labour market or Chronos
        results. Call directly, even without a request for a chart or table.
        'Kolika će biti nezaposlenost u Varaždinskoj idućih 6 mjeseci?' means
        county='varazdinska', target='unemployment_rate', horizon=6.
        Use target='unemployed' or 'employed' for persons; 'job_ads' counts
        advertisements per week, not workers. Ask which county if unspecified.

        Returns recent history, every forecast median and its 80% interval,
        change at the horizon, model, sources and notes, and automatically
        presents a history/forecast chart and exact-value table. Forecasts
        start after the latest source period, which can lag behind today.
        DZS forecasts need 24 known months; HZZ forecasts need 8 full weeks.
        Preserve unavailable reasons, estimated/provisional flags and notes.
        Always report the interval with the median as a model estimate.
        For past unemployment values use show_unemployment_history.
        """
        request = CountyForecastRequestDTO(counties=(county,), target=target, horizon=horizon, sex=sex)
        return labour_market_forecast(await self._call(self._service(ctx).forecast(request)))
