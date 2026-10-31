import math
from collections.abc import Callable
from datetime import datetime

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.hzz_feed import FeedResponseDTO
from FOIHireloom.dto.job import ParsedFeedDTO, ParsedJobDTO
from FOIHireloom.dto.job_sync import FeedCheckDTO, FeedSyncResultDTO, JobSyncResultDTO, SyncRunOutcomeDTO
from FOIHireloom.dto.source_feed import SourceFeedDTO
from FOIHireloom.exceptions import HzzFeedError, HzzFeedHttpError, NotFoundError, PersistenceError
from FOIHireloom.integrations.interfaces.hzz_feed import HzzFeedClientInterface
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface

from .hzz_feed_parser import HzzFeedParser

PROVIDER = "hzz"
ERROR_SUMMARY_LIMIT = 500


class JobSyncService(JobSyncServiceInterface):
    """Disappearing from a feed only marks the membership missing; jobs are
    never deleted or closed here. A response with fewer than min_retained_ratio
    of the last successful item count is rejected instead of applied.

    Occupation feeds only link jobs that county feeds have already imported:
    they neither create jobs nor change their content or last-seen time, and
    the jobs they list that are unknown are counted as unlinked. Their
    abandoned feeds still list long-closed jobs that no county feed has.
    """

    def __init__(
        self,
        client: HzzFeedClientInterface,
        parser: HzzFeedParser,
        uow_factory: Callable[[], UnitOfWork],
        min_retained_ratio: float = 0.5,
    ) -> None:
        if not math.isfinite(min_retained_ratio) or not 0 <= min_retained_ratio <= 1:
            raise ValueError("min_retained_ratio must be between 0 and 1.")
        self._client = client
        self._parser = parser
        self._uow_factory = uow_factory
        self._min_retained_ratio = min_retained_ratio

    async def sync_all(self) -> JobSyncResultDTO:
        async with self._uow_factory() as work:
            feeds = [SourceFeedDTO.model_validate(feed) for feed in await work.source_feeds.list_enabled()]
        results = tuple([await self._sync(feed) for feed in feeds])
        statuses = [result.status for result in results]
        return JobSyncResultDTO(
            feeds=results,
            succeeded=statuses.count("succeeded"),
            not_modified=statuses.count("not_modified"),
            failed=statuses.count("failed"),
            rejected=statuses.count("rejected"),
        )

    async def sync_feed(self, feed_id: int) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            feed = await work.source_feeds.get_by_id(feed_id)
            if feed is None:
                raise NotFoundError("source feed", str(feed_id))
            feed = SourceFeedDTO.model_validate(feed)
        return await self._sync(feed)

    async def _sync(self, feed: SourceFeedDTO) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            run_id = await work.sync_runs.start(feed.id)
            await work.commit()
        http_status = None
        try:
            # No transaction is open while the feed downloads.
            response = await self._client.fetch(feed.feed_url, feed.etag, feed.source_last_modified_at)
            if response.not_modified:
                return await self._confirm_unchanged(feed, run_id, response)
            http_status = 200
            return await self._import(feed, run_id, response, self._parser.parse(response.content))
        except (HzzFeedError, PersistenceError) as error:
            if isinstance(error, HzzFeedHttpError):
                http_status = error.status_code
            return await self._record_failure(feed, run_id, http_status, error)
        except Exception as error:
            await self._record_failure(feed, run_id, http_status, error)
            raise

    async def _confirm_unchanged(
        self, feed: SourceFeedDTO, run_id: int, response: FeedResponseDTO
    ) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            job_ids = await work.job_feed_memberships.touch_present(feed.id, now)
            if feed.scope == "county":
                await work.jobs.mark_seen(job_ids, now)
            await work.source_feeds.record_check(feed.id, FeedCheckDTO(
                succeeded=True, etag=response.etag, source_last_modified_at=response.last_modified,
            ), now)
            await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(status="not_modified", http_status=304), now)
            await work.commit()
        return FeedSyncResultDTO(
            feed_id=feed.id, label=feed.label, status="not_modified", http_status=304,
            items_seen=len(job_ids), items_unchanged=len(job_ids),
        )

    async def _import(
        self, feed: SourceFeedDTO, run_id: int, response: FeedResponseDTO, parsed: ParsedFeedDTO
    ) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            seen, invalid = len(parsed.jobs), parsed.invalid_items
            previous = await work.sync_runs.get_latest_items_seen(feed.id)
            if previous and seen < previous * self._min_retained_ratio:
                error = f"Feed returned {seen} valid items after {previous}; kept previous data."
                await work.source_feeds.record_check(feed.id, FeedCheckDTO(succeeded=False), now)
                await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(
                    status="rejected", http_status=200, items_seen=seen, items_invalid=invalid, error_summary=error,
                ), now)
                await work.commit()
                return FeedSyncResultDTO(
                    feed_id=feed.id, label=feed.label, status="rejected", http_status=200,
                    items_seen=seen, items_invalid=invalid, error=error,
                )

            if feed.scope == "county":
                job_ids, added, changed, unchanged = await self._upsert_jobs(work, parsed.jobs, now)
                unlinked = 0
            else:
                job_ids = await self._known_jobs(work, parsed.jobs)
                added = changed = 0
                unchanged = len(job_ids)
                unlinked = seen - unchanged
            memberships = {
                m.job_id: m.presence_status
                for m in await work.job_feed_memberships.list_snapshots_for_feed(feed.id)
            }
            present_ids = set(job_ids.values())
            missing = [
                job_id for job_id, status in memberships.items() if status == "present" and job_id not in present_ids
            ]
            returned = sum(memberships.get(job_id) == "missing" for job_id in present_ids)
            joined = [job_id for job_id in present_ids if job_id not in memberships]
            await work.job_feed_memberships.create_many(feed.id, joined, now)
            await work.job_feed_memberships.mark_present(
                feed.id, [job_id for job_id in present_ids if job_id in memberships], now
            )
            await work.job_feed_memberships.mark_missing(feed.id, missing, now)
            await work.source_feeds.record_check(feed.id, FeedCheckDTO(
                succeeded=True, etag=response.etag, source_last_modified_at=response.last_modified,
                content_changed=bool(added or changed or joined or missing or returned),
            ), now)
            await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(
                status="succeeded", http_status=200, items_seen=seen, items_added=added,
                items_updated=changed, items_invalid=invalid,
            ), now)
            await work.commit()
        return FeedSyncResultDTO(
            feed_id=feed.id, label=feed.label, status="succeeded", http_status=200, items_seen=seen,
            items_added=added, items_updated=changed, items_unchanged=unchanged, items_missing=len(missing),
            items_returned=returned, items_invalid=invalid, items_unlinked=unlinked,
        )

    @staticmethod
    async def _upsert_jobs(
        work: UnitOfWork, jobs: tuple[ParsedJobDTO, ...], now: datetime
    ) -> tuple[dict[str, int], int, int, int]:
        """Insert new jobs, rewrite changed content and confirm the rest by hash."""
        snapshots = await work.jobs.list_snapshots(PROVIDER, [job.source_job_id for job in jobs])
        existing = {snapshot.source_job_id: snapshot for snapshot in snapshots}
        new = [job for job in jobs if job.source_job_id not in existing]
        changed = {
            existing[job.source_job_id].id: job for job in jobs
            if job.source_job_id in existing and existing[job.source_job_id].content_hash != job.content_hash
        }
        unchanged = [
            existing[job.source_job_id].id for job in jobs
            if job.source_job_id in existing and existing[job.source_job_id].id not in changed
        ]
        job_ids = {source_job_id: snapshot.id for source_job_id, snapshot in existing.items()}
        job_ids |= await work.jobs.create_many(PROVIDER, new, now)
        await work.jobs.update_content(changed, now)
        await work.jobs.mark_seen(unchanged, now)
        return job_ids, len(new), len(changed), len(unchanged)

    @staticmethod
    async def _known_jobs(work: UnitOfWork, jobs: tuple[ParsedJobDTO, ...]) -> dict[str, int]:
        """Return the database IDs of the listed jobs that are already stored."""
        snapshots = await work.jobs.list_snapshots(PROVIDER, [job.source_job_id for job in jobs])
        return {snapshot.source_job_id: snapshot.id for snapshot in snapshots}

    async def _record_failure(
        self, feed: SourceFeedDTO, run_id: int, http_status: int | None, error: Exception
    ) -> FeedSyncResultDTO:
        """Record the failure in a new transaction; the import's writes are already rolled back."""
        summary = (str(error) or type(error).__name__)[:ERROR_SUMMARY_LIMIT]
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            await work.source_feeds.record_check(feed.id, FeedCheckDTO(succeeded=False), now)
            await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(
                status="failed", http_status=http_status, error_summary=summary,
            ), now)
            await work.commit()
        return FeedSyncResultDTO(
            feed_id=feed.id, label=feed.label, status="failed", http_status=http_status, error=summary,
        )
