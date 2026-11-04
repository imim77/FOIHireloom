from collections.abc import Awaitable
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from FOIHireloom.dto.dzs import DzsSex
from FOIHireloom.dto.forecast import MAX_FORECAST_COUNTIES, CountyForecastDTO, CountyForecastRequestDTO, ForecastTarget
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError, PersistenceError
from FOIHireloom.services.interfaces.labour_forecast import LabourMarketForecastServiceInterface

from .tool_provider import READ_ONLY, ToolGroup

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


class ForecastTools(ToolGroup):
    """ForecastTools exposes county labour-market forecasts made by Amazon Chronos.

    The tool only translates arguments and errors; LabourMarketForecastService
    holds the rules. The server's lifespan must provide the service under
    LABOUR_FORECAST_SERVICE.
    """

    def register(self, server: FastMCP) -> None:
        @server.tool(annotations=READ_ONLY)
        async def forecast_labour_market(
            ctx: Context,
            counties: ForecastCounties,
            target: Target,
            horizon: Horizon = None,
            sex: ForecastSex = "total",
        ) -> CountyForecastDTO:
            """Forecast a county labour-market series into the future with the Amazon Chronos model.

            Use it whenever the user asks about the future: how unemployment
            will develop ('Kolika će biti nezaposlenost u Varaždinskoj
            županiji idućih 6 mjeseci?' means counties=['varazdinska'],
            target='unemployment_rate', horizon=6), how many jobs or workers
            will be needed ('Koliko će poslova trebati u Splitu?' means
            target='job_ads' for splitsko-dalmatinska) or how employment will
            change (target='employed'). For past values use
            show_unemployment_history instead.

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
            return await self._call(service(ctx).forecast(request))

    @staticmethod
    async def _call[T](operation: Awaitable[T]) -> T:
        """Turn errors the caller can act on into tool errors; database and model details stay in the server log."""
        try:
            return await operation
        except (InvalidIndicatorRequestError, ForecastUnavailableError) as error:
            raise ToolError(error.details) from error
        except PersistenceError as error:
            raise ToolError("Forecast data is temporarily unavailable; try again later.") from error


def service(ctx: Context) -> LabourMarketForecastServiceInterface:
    return ctx.lifespan_context[LABOUR_FORECAST_SERVICE]
