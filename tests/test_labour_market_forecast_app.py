import unittest
from contextlib import asynccontextmanager
from datetime import date

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from FOIHireloom.api.app_views import AppViews
from FOIHireloom.api.apps.labour_market_forecast import labour_market_forecast
from FOIHireloom.api.apps.views import LABOUR_MARKET_FORECAST
from FOIHireloom.api.forecast_tools import LABOUR_FORECAST_SERVICE, ForecastTools
from FOIHireloom.dto.county_indicators import SourceDTO
from FOIHireloom.dto.forecast import (
    CountyForecastDTO,
    CountyForecastRequestDTO,
    CountyForecastSeriesDTO,
    ObservedPointDTO,
    PredictedPointDTO,
)
from FOIHireloom.exceptions import ForecastUnavailableError, InvalidIndicatorRequestError, PersistenceError

from test_labour_forecast import FakeForecastService


def forecast(target="unemployment_rate", reason=None, sex="total") -> CountyForecastDTO:
    last = ObservedPointDTO(period=date(2026, 9, 1), value=2.5, is_provisional=True,
                            is_estimated=target in ("employed", "unemployed"))
    return CountyForecastDTO(
        target=target, frequency="week" if target == "job_ads" else "month",
        unit="ads" if target == "job_ads" else "percent" if target == "unemployment_rate" else "persons",
        sex=None if target == "job_ads" else sex, horizon=1, model="amazon/chronos-2",
        last_observed_period=last.period, unavailable_reason=None,
        counties=(CountyForecastSeriesDTO(
            code="varazdinska", name="Varaždinska županija", iso_code="HR-05", history=(last,), last_observed=last,
            forecast=() if reason else (PredictedPointDTO(period=date(2026, 10, 1), median=2.6, low=2.1, high=3.2),),
            change_to_horizon=None if reason else 0.1, unavailable_reason=reason,
        ),),
        sources=(SourceDTO(name="DZS county workbook", url="https://podaci.dzs.hr/workbook.xlsx", description="Source"),
                 SourceDTO(name="Amazon Chronos (amazon/chronos-2)", url="https://huggingface.co/amazon/chronos-2",
                           description="Model")), notes=("Original model notes",),
    )


class LabourMarketForecastAppTests(unittest.TestCase):
    def test_keeps_every_forecast_field_and_source_without_rounding(self) -> None:
        original = forecast()
        view = labour_market_forecast(original)
        self.assertEqual(view.model_dump(include=set(CountyForecastDTO.model_fields)), original.model_dump())
        self.assertEqual(view.title, "Prognoza stope nezaposlenosti")
        self.assertEqual(view.description, "Varaždinska županija · po mjesecima")
        self.assertIsNone(view.unavailable_label)
        self.assertIn("80% interval", " ".join(view.view_notes))
        self.assertIn("rujan 2026.", " ".join(view.view_notes))
        self.assertIn("privremeni", " ".join(view.view_notes))
        self.assertEqual(view.source_links[0].url, original.sources[0].url)

    def test_all_targets_keep_units_sex_and_estimated_history_visible(self) -> None:
        for target, title in (("unemployed", "Prognoza broja nezaposlenih"),
                              ("employed", "Prognoza broja zaposlenih"),
                              ("job_ads", "Prognoza broja oglasa")):
            with self.subTest(target=target):
                view = labour_market_forecast(forecast(target, sex="women"))
                self.assertEqual(view.title, title)
                if target == "job_ads":
                    self.assertEqual(view.description, "Varaždinska županija · po tjednima")
                    self.assertIn("više radnika", " ".join(view.view_notes))
                    self.assertNotIn("privremeni", " ".join(view.view_notes))
                else:
                    self.assertIn("žene", view.description)
                    self.assertIn("procijenjeni", " ".join(view.view_notes))

    def test_missing_series_explains_why_without_inventing_a_forecast(self) -> None:
        for target in ("unemployment_rate", "job_ads"):
            for reason in ("no_dzs_data", "no_common_period", "no_hzz_data", "not_enough_history"):
                with self.subTest(target=target, reason=reason):
                    view = labour_market_forecast(forecast(target, reason))
                    self.assertTrue(view.unavailable_label)
                    self.assertEqual(view.counties[0].forecast, ())
                    self.assertIsNone(view.counties[0].change_to_horizon)
                    if reason == "not_enough_history":
                        self.assertIn("8 punih tjedana" if target == "job_ads" else "24 mjeseca",
                                      view.unavailable_label)


class ShowLabourMarketForecastTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.service = FakeForecastService()
        self.result = forecast()

        async def predict(request):
            self.service.requests.append(request)
            if self.service.error is not None:
                raise self.service.error
            return self.result

        self.service.forecast = predict

        @asynccontextmanager
        async def lifespan(server):
            yield {LABOUR_FORECAST_SERVICE: self.service}

        self.server = FastMCP("test", lifespan=lifespan, mask_error_details=True)
        ForecastTools().register(self.server)
        AppViews().register(self.server)

    async def test_registers_the_page_and_calls_chronos_once_for_one_county(self) -> None:
        async with Client(self.server) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            tool = tools["show_labour_market_forecast"]
            self.assertEqual(tool.inputSchema["required"], ["county"])
            self.assertEqual(tools["forecast_labour_market"].meta["ui"]["visibility"], ["app"])
            self.assertEqual(tool.meta["ui"]["resourceUri"], LABOUR_MARKET_FORECAST.uri)
            result = await client.call_tool("show_labour_market_forecast", {"county": "varazdinska"})
            self.assertEqual((await client.read_resource(LABOUR_MARKET_FORECAST.uri))[0].text,
                             LABOUR_MARKET_FORECAST.page())
        self.assertEqual(self.service.requests, [CountyForecastRequestDTO(
            counties=("varazdinska",), target="unemployment_rate")])
        self.assertEqual(result.structured_content["counties"], self.result.model_dump(mode="json")["counties"])

    async def test_all_arguments_reach_the_service_and_bad_arguments_never_do(self) -> None:
        async with Client(self.server) as client:
            await client.call_tool("show_labour_market_forecast", {
                "county": "Varaždinska županija", "target": "employed", "horizon": 6, "sex": "women"})
            self.assertEqual(self.service.requests, [CountyForecastRequestDTO(
                counties=("Varaždinska županija",), target="employed", horizon=6, sex="women")])
            for arguments in ({}, {"county": ""}, {"county": ["varazdinska", "istarska"]},
                              {"county": "varazdinska", "target": "workers"},
                              {"county": "varazdinska", "horizon": 27}):
                with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                    await client.call_tool("show_labour_market_forecast", arguments)
        self.assertEqual(len(self.service.requests), 1)

    async def test_errors_are_actionable_and_database_details_are_masked(self) -> None:
        errors = ((ForecastUnavailableError("Install the forecast extra."), "forecast extra"),
                  (InvalidIndicatorRequestError("Unknown county: x."), "Unknown county"),
                  (PersistenceError("secret database address"), "temporarily unavailable"))
        async with Client(self.server) as client:
            for error, message in errors:
                self.service.error = error
                with self.subTest(error=error), self.assertRaisesRegex(ToolError, message) as raised:
                    await client.call_tool("show_labour_market_forecast", {"county": "x"})
                self.assertNotIn("secret database", str(raised.exception))
