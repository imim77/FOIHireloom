from collections.abc import Callable

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.category_snapshot import (
    CategoryCoverageDTO,
    CategoryInputDTO,
    CategorySnapshotDTO,
    CategorySnapshotFeedDTO,
    CategorySnapshotRow,
)
from FOIHireloom.services.interfaces.category_snapshot import CategorySnapshotServiceInterface

from .feed_category import resolve_category

DENOMINATOR = (
    "Jobs present in at least one county feed at generated_at, each counted once; "
    "occupation feeds only add categories to them."
)


class CategorySnapshotService(CategorySnapshotServiceInterface):
    """Save what the category fill used and stored, so it can be rechecked without the database.

    Coverage counts the stored results; conflicting is recomputed from the
    feeds' confirmed mappings with the rule the sync applies.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def take(self) -> CategorySnapshotDTO:
        async with self._uow_factory() as work:
            generated_at = await work.transaction_time()
            feeds = tuple(CategorySnapshotFeedDTO.model_validate(feed) for feed in await work.source_feeds.list_synced())
            jobs = await work.jobs.list_category_inputs()
        confirmed = {feed.id: feed.mapped_category for feed in feeds if feed.mapping_status == "confirmed"}
        conflicting = sum(
            job.description_category is None and resolve_category(
                [(feed_id, confirmed[feed_id]) for feed_id in job.occupation_feed_ids if feed_id in confirmed]
            )[1]
            for job in jobs
        )
        known = sum(job.category is not None for job in jobs)
        coverage = CategoryCoverageDTO(
            listed=len(jobs), before=sum(job.description_category is not None for job in jobs), after=known,
            filled=sum(job.category_source == "feed" for job in jobs), unknown=len(jobs) - known,
            conflicting=conflicting,
        )
        categories = sorted({name for job in jobs for name in (job.description_category, job.category) if name})
        index = {name: position for position, name in enumerate(categories)}
        return CategorySnapshotDTO(
            generated_at=generated_at, denominator=DENOMINATOR, coverage=coverage, feeds=feeds,
            categories=tuple(categories), jobs=tuple(self._row(job, index) for job in jobs),
        )

    @staticmethod
    def _row(job: CategoryInputDTO, index: dict[str, int]) -> CategorySnapshotRow:
        """The job as a row of JOB_COLUMNS, with categories replaced by their index."""
        return (
            job.source_job_id, index.get(job.description_category), job.occupation_feed_ids,
            index.get(job.category), job.category_source, job.category_feed_id,
        )
