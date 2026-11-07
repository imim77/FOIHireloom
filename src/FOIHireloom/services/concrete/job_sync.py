import math
from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from FOIHireloom.db.uow.base import UnitOfWork, UnitOfWorkFactory
from FOIHireloom.dto.hzz_feed import FeedResponseDTO
from FOIHireloom.dto.job import ParsedFeedDTO, ParsedJobDTO
from FOIHireloom.dto.job_sync import (
    FeedCheckDTO,
    FeedSyncResultDTO,
    FilledCategoryDTO,
    JobSyncResultDTO,
    SyncRunOutcomeDTO,
)
from FOIHireloom.dto.source_feed import FeedCategoryMappingDTO, SourceFeedDTO
from FOIHireloom.exceptions import HzzFeedError, HzzFeedHttpError, NotFoundError, PersistenceError
from FOIHireloom.integrations.interfaces.hzz_feed import HzzFeedClientInterface
from FOIHireloom.services.interfaces.job_sync import JobSyncServiceInterface

from .feed_category import FeedCategoryVerifier, resolve_category
from .hzz_feed_parser import HzzFeedParser

ERROR_SUMMARY_LIMIT = 500


@dataclass(frozen=True)
class LinkedJobs:
    """LinkedJobs holds the stored jobs a feed response lists and how linking them changed the jobs."""

    job_ids: dict[str, int]  # Database ID by HZZ source job ID.
    added: int = 0
    changed: int = 0
    unchanged: int = 0
    unlinked: int = 0  # Listed jobs no county feed has imported.
    mapping: FeedCategoryMappingDTO | None = None


@dataclass(frozen=True)
class CategoryRefresh:
    """CategoryRefresh counts the filled-in categories one recheck set, cleared and found contradicted."""

    filled: int = 0
    cleared: int = 0
    conflicting: int = 0


@dataclass(frozen=True)
class MembershipChanges:
    """MembershipChanges counts how a feed's listed jobs differ from the jobs it listed before."""

    joined: int
    missing: int
    returned: int  # Jobs listed again after being missing.


class FeedScopeSync(ABC):
    """FeedScopeSync applies the part of a feed sync that depends on the feed's scope.

    A new scope is a new subclass registered in JobSyncService; the shared
    steps (download, rejection, memberships, run records) stay unchanged.
    """

    def validators(self, feed: SourceFeedDTO) -> tuple[str | None, datetime | None]:
        """Return the HTTP validators to send, as (ETag, Last-Modified)."""
        return feed.etag, feed.source_last_modified_at

    @abstractmethod
    async def link_jobs(
        self, work: UnitOfWork, feed: SourceFeedDTO, jobs: tuple[ParsedJobDTO, ...], now: datetime,
    ) -> LinkedJobs:
        """Store or find the listed jobs within the caller's transaction."""

    @abstractmethod
    async def confirm_listed(self, work: UnitOfWork, feed: SourceFeedDTO, job_ids: Collection[int],
                             now: datetime) -> CategoryRefresh:
        """Confirm the jobs an unchanged response still lists."""

    async def refresh_categories(self, work: UnitOfWork, feed: SourceFeedDTO) -> CategoryRefresh:
        """Recheck the filled-in categories that depend on this feed, after its memberships are updated."""
        return CategoryRefresh()


class CountyFeedSync(FeedScopeSync):
    """CountyFeedSync imports the jobs a county feed lists and keeps their content current."""

    async def link_jobs(
        self, work: UnitOfWork, feed: SourceFeedDTO, jobs: tuple[ParsedJobDTO, ...], now: datetime,
    ) -> LinkedJobs:
        return await self.upsert_jobs(work, jobs, now)

    async def confirm_listed(self, work: UnitOfWork, feed: SourceFeedDTO, job_ids: Collection[int],
                             now: datetime) -> CategoryRefresh:
        await work.jobs.mark_seen(job_ids, now)
        return CategoryRefresh()

    @staticmethod
    async def upsert_jobs(work: UnitOfWork, jobs: tuple[ParsedJobDTO, ...], now: datetime) -> LinkedJobs:
        """Insert new jobs, rewrite changed content and confirm the rest by hash."""
        snapshots = await work.jobs.list_snapshots([job.source_job_id for job in jobs])
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
        job_ids |= await work.jobs.create_many(new, now)
        await work.jobs.update_content(changed, now)
        await work.jobs.mark_seen(unchanged, now)
        return LinkedJobs(job_ids=job_ids, added=len(new), changed=len(changed), unchanged=len(unchanged))


class OccupationFeedSync(FeedScopeSync):
    """OccupationFeedSync links the stored jobs an occupation feed lists and fills in their categories.

    Its jobs are never created or changed here; each full download verifies
    the feed's category mapping on the explicit categories of the jobs it
    lists.
    """

    def __init__(self, verifier: FeedCategoryVerifier) -> None:
        self._verifier = verifier

    def validators(self, feed: SourceFeedDTO) -> tuple[str | None, datetime | None]:
        # An unchanged response carries no jobs to verify a mapping on.
        if feed.mapping_verified_at is None:
            return None, None
        return super().validators(feed)

    async def link_jobs(
        self, work: UnitOfWork, feed: SourceFeedDTO, jobs: tuple[ParsedJobDTO, ...], now: datetime,
    ) -> LinkedJobs:
        snapshots = await work.jobs.list_snapshots([job.source_job_id for job in jobs])
        job_ids = {snapshot.source_job_id: snapshot.id for snapshot in snapshots}
        mapping = self._verifier.verify(jobs)
        await work.source_feeds.record_category_mapping(feed.id, mapping, now)
        return LinkedJobs(job_ids=job_ids, unchanged=len(job_ids), unlinked=len(jobs) - len(job_ids),
                          mapping=mapping)

    async def confirm_listed(self, work: UnitOfWork, feed: SourceFeedDTO, job_ids: Collection[int],
                             now: datetime) -> CategoryRefresh:
        return await self.refresh_categories(work, feed)

    async def refresh_categories(self, work: UnitOfWork, feed: SourceFeedDTO) -> CategoryRefresh:
        changes: dict[int, FilledCategoryDTO | None] = {}
        conflicting = 0
        for evidence in await work.jobs.list_category_evidence(feed.id):
            target, conflict = resolve_category(evidence.mappings)
            conflicting += conflict
            current = evidence.category and FilledCategoryDTO(
                category=evidence.category, feed_id=evidence.category_feed_id,
            )
            if target != current:
                changes[evidence.job_id] = target
        await work.jobs.set_feed_categories(changes)
        filled = sum(target is not None for target in changes.values())
        return CategoryRefresh(filled=filled, cleared=len(changes) - filled, conflicting=conflicting)


class JobSyncService(JobSyncServiceInterface):
    """Disappearing from a feed only marks the membership missing; jobs are
    never deleted or closed here. A response with fewer than min_retained_ratio
    of the last successful item count is rejected instead of applied.

    Occupation feeds only link jobs that county feeds have already imported:
    they neither create jobs nor change their content or last-seen time, and
    the jobs they list that are unknown are counted as unlinked. Their
    abandoned feeds still list long-closed jobs that no county feed has.

    Each download of an occupation feed also verifies its category mapping on
    the explicit categories of all the jobs it lists. A feed never verified is
    downloaded in full, since an unchanged response carries no jobs to check.

    Then, and also after an unchanged response, every job the feed lists or
    has listed without a description category is rechecked: it gets the category its feeds' confirmed mappings
    agree on, and none when they disagree or no confirmed mapping is left.
    Leaving a feed keeps a filled-in category; a category in the job's
    description always replaces it.
    """

    def __init__(
        self,
        client: HzzFeedClientInterface,
        parser: HzzFeedParser,
        uow_factory: UnitOfWorkFactory,
        min_retained_ratio: float = 0.5,
        category_verifier: FeedCategoryVerifier | None = None,
    ) -> None:
        if not math.isfinite(min_retained_ratio) or not 0 <= min_retained_ratio <= 1:
            raise ValueError("min_retained_ratio must be between 0 and 1.")
        self._client = client
        self._parser = parser
        self._uow_factory = uow_factory
        self._min_retained_ratio = min_retained_ratio
        self._scopes: dict[str, FeedScopeSync] = {
            "county": CountyFeedSync(),
            "occupation": OccupationFeedSync(category_verifier or FeedCategoryVerifier()),
        }

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
            scope = self._scopes[feed.scope]
            # No transaction is open while the feed downloads.
            response = await self._client.fetch(feed.feed_url, *scope.validators(feed))
            if response.not_modified:
                return await self._confirm_unchanged(scope, feed, run_id, response)
            http_status = 200
            return await self._import(scope, feed, run_id, response, self._parser.parse(response.content))
        except (HzzFeedError, PersistenceError) as error:
            if isinstance(error, HzzFeedHttpError):
                http_status = error.status_code
            return await self._record_failure(feed, run_id, http_status, error)
        except Exception as error:
            await self._record_failure(feed, run_id, http_status, error)
            raise

    async def _confirm_unchanged(
        self, scope: FeedScopeSync, feed: SourceFeedDTO, run_id: int, response: FeedResponseDTO
    ) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            job_ids = await work.job_feed_memberships.touch_present(feed.id, now)
            categories = await scope.confirm_listed(work, feed, job_ids, now)
            await work.source_feeds.record_check(feed.id, FeedCheckDTO(
                succeeded=True, etag=response.etag, source_last_modified_at=response.last_modified,
            ), now)
            await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(status="not_modified", http_status=304), now)
            await work.commit()
        return FeedSyncResultDTO(
            feed_id=feed.id, label=feed.label, status="not_modified", http_status=304,
            items_seen=len(job_ids), items_unchanged=len(job_ids),
            categories_filled=categories.filled, categories_cleared=categories.cleared,
            categories_conflicting=categories.conflicting,
        )

    async def _import(
        self, scope: FeedScopeSync, feed: SourceFeedDTO, run_id: int, response: FeedResponseDTO,
        parsed: ParsedFeedDTO,
    ) -> FeedSyncResultDTO:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            previous = await work.sync_runs.get_latest_items_seen(feed.id)
            if previous and len(parsed.jobs) < previous * self._min_retained_ratio:
                return await self._reject_shrunken(work, feed, run_id, parsed, previous, now)
            linked = await scope.link_jobs(work, feed, parsed.jobs, now)
            memberships = await self._update_memberships(work, feed.id, set(linked.job_ids.values()), now)
            categories = await scope.refresh_categories(work, feed)
            await work.source_feeds.record_check(feed.id, FeedCheckDTO(
                succeeded=True, etag=response.etag, source_last_modified_at=response.last_modified,
                content_changed=bool(linked.added or linked.changed or memberships.joined or memberships.missing
                                     or memberships.returned),
            ), now)
            await work.sync_runs.finish(run_id, SyncRunOutcomeDTO(
                status="succeeded", http_status=200, items_seen=len(parsed.jobs), items_added=linked.added,
                items_updated=linked.changed, items_invalid=parsed.invalid_items,
            ), now)
            await work.commit()
        return FeedSyncResultDTO(
            feed_id=feed.id, label=feed.label, status="succeeded", http_status=200, items_seen=len(parsed.jobs),
            items_added=linked.added, items_updated=linked.changed, items_unchanged=linked.unchanged,
            items_missing=memberships.missing, items_returned=memberships.returned,
            items_invalid=parsed.invalid_items, items_unlinked=linked.unlinked, category_mapping=linked.mapping,
            categories_filled=categories.filled, categories_cleared=categories.cleared,
            categories_conflicting=categories.conflicting,
        )

    @staticmethod
    async def _reject_shrunken(
        work: UnitOfWork, feed: SourceFeedDTO, run_id: int, parsed: ParsedFeedDTO, previous: int, now: datetime,
    ) -> FeedSyncResultDTO:
        """Record a response that lost too many items as rejected, keeping the stored jobs as they are."""
        seen, invalid = len(parsed.jobs), parsed.invalid_items
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

    @staticmethod
    async def _update_memberships(
        work: UnitOfWork, feed_id: int, present_ids: set[int], now: datetime,
    ) -> MembershipChanges:
        """Mark the listed jobs present and the jobs no longer listed missing."""
        memberships = {
            m.job_id: m.presence_status
            for m in await work.job_feed_memberships.list_snapshots_for_feed(feed_id)
        }
        missing = [
            job_id for job_id, status in memberships.items() if status == "present" and job_id not in present_ids
        ]
        returned = sum(memberships.get(job_id) == "missing" for job_id in present_ids)
        joined = [job_id for job_id in present_ids if job_id not in memberships]
        await work.job_feed_memberships.create_many(feed_id, joined, now)
        await work.job_feed_memberships.mark_present(
            feed_id, [job_id for job_id in present_ids if job_id in memberships], now
        )
        await work.job_feed_memberships.mark_missing(feed_id, missing, now)
        return MembershipChanges(joined=len(joined), missing=len(missing), returned=returned)

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
