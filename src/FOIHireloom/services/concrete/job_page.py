import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.job_conditions import RawJobConditionsDTO
from FOIHireloom.dto.job_page import JobPageFetchResultDTO
from FOIHireloom.exceptions import HzzJobPageError, HzzJobPageUnavailableError
from FOIHireloom.integrations.interfaces.hzz_job_page import HzzJobPageClientInterface
from FOIHireloom.services.interfaces.job_page import JobPageServiceInterface

from .hzz_job_page_parser import HzzJobPageParser
from .job_conditions import JobConditionsNormalizer

ERROR_SUMMARY_LIMIT = 500


class JobPageService(JobPageServiceInterface):
    """Fetch HZZ job pages politely: a pause between requests and a stop when HZZ keeps failing.

    An error page only marks the check 'unavailable'; it is not evidence that
    the job closed, and the fields fetched earlier stay. Unavailable and
    failed pages are retried after retry_after. A fetched page's conditions
    are normalised and stored with it.
    """

    def __init__(
        self,
        client: HzzJobPageClientInterface,
        parser: HzzJobPageParser,
        normalizer: JobConditionsNormalizer,
        uow_factory: Callable[[], UnitOfWork],
        delay_seconds: float = 1.0,
        retry_after: timedelta = timedelta(hours=24),
        max_consecutive_failures: int = 5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if delay_seconds < 0 or retry_after <= timedelta(0) or max_consecutive_failures < 1:
            raise ValueError("Delay must not be negative; retry time and failure limit must be positive.")
        self._client = client
        self._parser = parser
        self._normalizer = normalizer
        self._uow_factory = uow_factory
        self._delay_seconds = delay_seconds
        self._retry_after = retry_after
        self._max_consecutive_failures = max_consecutive_failures
        self._sleep = sleep

    async def fetch_due(self, limit: int) -> JobPageFetchResultDTO:
        if limit < 1:
            raise ValueError("limit must be at least 1.")
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            targets = await work.jobs.list_page_candidates(now - self._retry_after, limit)
        counts = {"fetched": 0, "unavailable": 0, "failed": 0}
        consecutive_failures, stopped_early = 0, False
        for index, target in enumerate(targets):
            if index:
                await self._sleep(self._delay_seconds)
            page, status, error = None, "fetched", None
            try:
                page = self._parser.parse(await self._client.fetch(target.canonical_url))
            except HzzJobPageUnavailableError as problem:
                status, error = "unavailable", problem
            except (HzzJobPageError, ValueError) as problem:
                status, error = "failed", problem
            async with self._uow_factory() as work:
                checked_at = await work.transaction_time()
                if page is not None:
                    conditions = self._normalizer.normalize(RawJobConditionsDTO.model_validate(page))
                    await work.jobs.record_page(target.id, page, conditions, target.content_hash, checked_at)
                else:
                    summary = (str(error) or type(error).__name__)[:ERROR_SUMMARY_LIMIT]
                    await work.jobs.record_page_problem(target.id, status, summary, checked_at)
                await work.commit()
            counts[status] += 1
            consecutive_failures = consecutive_failures + 1 if status == "failed" else 0
            if consecutive_failures >= self._max_consecutive_failures:
                stopped_early = True
                break
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            remaining = await work.jobs.count_page_candidates(now - self._retry_after)
        return JobPageFetchResultDTO(
            attempted=sum(counts.values()), remaining=remaining, stopped_early=stopped_early, **counts,
        )
