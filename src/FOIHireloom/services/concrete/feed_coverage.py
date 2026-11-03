from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from FOIHireloom.dto.job_search import CountyFeedCheckDTO, CoverageDTO, DataStatus, RegionFreshnessDTO

# Counties named in a coverage warning before the rest are only counted.
WARNING_REGION_LIMIT = 5


class FeedCoverage:
    """How current the stored HZZ jobs of each county are, and the warning a result carries when they are not.

    A county's data is stale once its feeds last succeeded more than
    stale_after ago, and unavailable while it has no enabled feed or one has
    never succeeded.
    """

    def __init__(self, stale_after: timedelta = timedelta(hours=6)) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive.")
        self._stale_after = stale_after

    def status(self, successes: Sequence[datetime | None], now: datetime) -> DataStatus:
        if not successes or None in successes:
            return "unavailable"
        return "stale" if min(successes) < now - self._stale_after else "fresh"

    def freshness(self, checks: Sequence[CountyFeedCheckDTO], now: datetime) -> list[RegionFreshnessDTO]:
        """One entry per county, in the order of checks."""
        counties: dict[str, tuple[str, list[datetime | None]]] = {}
        for check in checks:
            _, successes = counties.setdefault(check.code, (check.name, []))
            if check.feed_id is not None:
                successes.append(check.last_success_at)
        return [
            RegionFreshnessDTO(
                code=code, name=name, data_status=self.status(successes, now),
                last_success_at=min((moment for moment in successes if moment is not None), default=None),
            )
            for code, (name, successes) in counties.items()
        ]

    def coverage(self, regions: Sequence[RegionFreshnessDTO]) -> CoverageDTO:
        affected = tuple(region for region in regions if region.data_status != "fresh")
        statuses = {region.data_status for region in affected}
        successes = [region.last_success_at for region in regions if region.last_success_at is not None]
        return CoverageDTO(
            data_status="unavailable" if "unavailable" in statuses or not regions else "stale" if affected else "fresh",
            data_as_of=min(successes, default=None),
            stale_after_hours=self._stale_after.total_seconds() / 3600,
            affected_regions=affected,
            warning=self._warning(affected, len(regions)),
        )

    def _warning(self, affected: Sequence[RegionFreshnessDTO], total: int) -> str | None:
        if total == 0:
            return "No counties are registered, so there is no job data to search."
        if not affected:
            return None
        named = ", ".join(self._describe(region) for region in affected[:WARNING_REGION_LIMIT])
        if len(affected) > WARNING_REGION_LIMIT:
            named += f" and {len(affected) - WARNING_REGION_LIMIT} more"
        scope = "the requested county" if total == 1 else f"{len(affected)} of {total} counties"
        hours = f"{self._stale_after.total_seconds() / 3600:g}"
        return (f"Job data for {scope} was not updated in the last {hours} hours or is unavailable: {named}. "
                "Results there may be outdated or incomplete; a job missing from them may still be advertised by HZZ.")

    @staticmethod
    def _describe(region: RegionFreshnessDTO) -> str:
        if region.last_success_at is None:
            return f"{region.name} (never loaded)"
        updated = f"last updated {region.last_success_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC"
        if region.data_status == "unavailable":
            updated += ", a feed never loaded"
        return f"{region.name} ({updated})"
