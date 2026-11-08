import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

from FOIHireloom.dto.forecast import QUANTILE_LEVELS, QuantileForecastDTO
from FOIHireloom.exceptions import ForecastUnavailableError
from FOIHireloom.integrations.interfaces.forecaster import TimeSeriesForecasterInterface

logger = logging.getLogger(__name__)

INSTALL_HINT = "install the forecast extra: pip install -e .[forecast]"


class ChronosForecaster(TimeSeriesForecasterInterface):
    """ChronosForecaster forecasts with an Amazon Chronos model, loaded on the first forecast.

    Loading takes seconds (and downloads the model once), so a server that
    never forecasts never pays for it, and requests wait on one shared load.
    chronos and torch are imported only then, which keeps them optional.
    Inference runs in a worker thread so the event loop keeps serving.
    Pass load to supply another pipeline, e.g. in tests; it must offer
    Chronos' predict_quantiles().
    """

    def __init__(self, model: str, device: str = "cpu", *, load: Callable[[], Any] | None = None) -> None:
        self._model = model
        self._device = device
        self._load = load or self._load_chronos
        self._pipeline: Any = None
        self._loading = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._model

    async def forecast(self, histories: Sequence[Sequence[float]], horizon: int) -> list[QuantileForecastDTO]:
        if not histories:
            return []
        pipeline = await self._loaded()
        try:
            return await asyncio.to_thread(self._predict, pipeline, histories, horizon)
        except Exception as error:
            logger.exception("Chronos forecast failed")
            raise ForecastUnavailableError("The forecasting model failed to produce a forecast.") from error

    async def _loaded(self) -> Any:
        async with self._loading:
            if self._pipeline is None:
                self._pipeline = await asyncio.to_thread(self._load)
        return self._pipeline

    def _load_chronos(self) -> Any:
        try:
            from chronos import BaseChronosPipeline
        except ImportError as error:
            raise ForecastUnavailableError(f"Forecasting needs Amazon Chronos; {INSTALL_HINT}.") from error
        try:
            return BaseChronosPipeline.from_pretrained(self._model, device_map=self._device)
        except Exception as error:
            logger.exception("Loading Chronos model %s failed", self._model)
            raise ForecastUnavailableError(f"The forecasting model {self._model} could not be loaded.") from error

    @staticmethod
    def _predict(pipeline: Any, histories: Sequence[Sequence[float]], horizon: int) -> list[QuantileForecastDTO]:
        import torch

        inputs = [torch.tensor(list(history), dtype=torch.float32) for history in histories]
        quantiles, _ = pipeline.predict_quantiles(
            inputs, prediction_length=horizon, quantile_levels=list(QUANTILE_LEVELS))
        forecasts = []
        for series in quantiles:
            steps = series.reshape(horizon, len(QUANTILE_LEVELS)).tolist()
            low, median, high = (tuple(step[index] for step in steps) for index in range(len(QUANTILE_LEVELS)))
            forecasts.append(QuantileForecastDTO(low=low, median=median, high=high))
        return forecasts
