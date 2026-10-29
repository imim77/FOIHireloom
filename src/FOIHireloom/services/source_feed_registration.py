from collections.abc import Callable
from dataclasses import dataclass

from FOIHireloom.db.models import County, SourceFeed
from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.ckan import CkanResource
from FOIHireloom.exceptions import ConflictError
from FOIHireloom.integrations.concrete.ckan import CkanClient

from .croatian_counties import CountyDefinition, CroatianCountyCatalog


class SourceFeedRegistrationError(RuntimeError):
    """The metadata cannot be registered without ambiguity or conflicting data."""


@dataclass(frozen=True)
class PlannedSource:
    resource: CkanResource
    county: CountyDefinition
    label: str


@dataclass(frozen=True)
class RegistrationPlan:
    sources: tuple[PlannedSource, ...]
    resources_skipped: int


@dataclass(frozen=True)
class RegistrationResult:
    counties_added: int
    feeds_added: int
    feeds_updated: int
    feeds_unchanged: int
    resources_skipped: int


class SourceFeedRegistrationPlanner:
    def __init__(self) -> None:
        self.catalog = CroatianCountyCatalog()

    def build(self, resources: list[CkanResource]) -> RegistrationPlan:
        sources: list[PlannedSource] = []
        ids, urls = set(), set()
        skipped = 0
        for resource in resources:
            if resource.state != "active" or (resource.format or "").strip().casefold() not in {
                "xml", "rss", "application/rss+xml", "application/xml", "text/xml"
            }:
                skipped += 1
                continue
            label = next((text.strip() for text in (resource.description, resource.name) if text and text.strip()), "")
            if self.catalog.is_eu(label):
                skipped += 1
                continue
            county = self.catalog.match(label)
            if county is None:
                raise SourceFeedRegistrationError(f"Unrecognised county resource label: {label!r}.")
            url = str(resource.url)
            if resource.id in ids or url in urls:
                raise SourceFeedRegistrationError("Duplicate Croatian resource ID or feed URL in CKAN response.")
            ids.add(resource.id)
            urls.add(url)
            sources.append(PlannedSource(resource, county, label))
        if not sources:
            raise SourceFeedRegistrationError("CKAN returned no supported Croatian county resources.")
        return RegistrationPlan(tuple(sources), skipped)


class SourceFeedRegistrationService:
    """Fetch and validate first, then register all counties/feeds atomically.

    Existing enabled flags and sync history are preserved. Changed URLs clear
    their HTTP validators. Registration neither runs migrations nor imports jobs.
    """

    def __init__(self, client: CkanClient, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._client = client
        self._uow_factory = uow_factory
        self._planner = SourceFeedRegistrationPlanner()

    async def register_sources(self, dataset_id: str) -> RegistrationResult:
        plan = self._planner.build(await self._client.get_resources(dataset_id))
        try:
            async with self._uow_factory() as work:
                counties, counties_added = await self._ensure_counties(work)
                # Resolve both identifiers before mutating feeds, including URLs
                # reused by a CKAN resource whose UUID has been replaced.
                resolved: list[tuple[PlannedSource, SourceFeed | None]] = []
                targets: set[int] = set()
                for source in plan.sources:
                    by_id = await work.source_feeds.get_by_ckan_resource_id(source.resource.id)
                    by_url = await work.source_feeds.get_by_feed_url(str(source.resource.url))
                    if by_id is not None and by_url is not None and by_id.id != by_url.id:
                        raise SourceFeedRegistrationError("Resource ID and URL identify different existing feeds.")
                    existing = by_id or by_url
                    if existing is not None:
                        if existing.id in targets:
                            raise SourceFeedRegistrationError("Multiple resources identify the same existing feed.")
                        targets.add(existing.id)
                    resolved.append((source, existing))

                added = updated = unchanged = 0
                for source, existing in resolved:
                    resource = source.resource
                    county_id, url = counties[source.county.code], str(resource.url)
                    if existing is None:
                        await work.source_feeds.add(SourceFeed(
                            county_id=county_id, ckan_resource_id=resource.id,
                            label=source.label, feed_url=url, scope="county",
                        ))
                        added += 1
                    elif (existing.county_id, existing.ckan_resource_id, existing.label, existing.feed_url) != (
                        county_id, resource.id, source.label, url
                    ):
                        if existing.feed_url != url:
                            existing.etag = existing.source_last_modified_at = None
                        existing.county_id, existing.ckan_resource_id = county_id, resource.id
                        existing.label, existing.feed_url = source.label, url
                        updated += 1
                    else:
                        unchanged += 1
                await work.commit()
                return RegistrationResult(counties_added, added, updated, unchanged, plan.resources_skipped)
        except ConflictError as error:
            raise SourceFeedRegistrationError("County or feed data conflicts; registration was rolled back.") from error

    async def _ensure_counties(self, work: UnitOfWork) -> tuple[dict[str, int], int]:
        counties: dict[str, int] = {}
        added = 0
        for definition in self._planner.catalog.definitions:
            by_code = await work.counties.get_by_code(definition.code)
            by_name = await work.counties.get_by_name(definition.name)
            if by_code is not None and by_name is not None and by_code.id != by_name.id:
                raise SourceFeedRegistrationError("County code and name identify different existing counties.")
            county = by_code or by_name
            if county is None:
                county = County(code=definition.code, name=definition.name)
                await work.counties.add(county)
                added += 1
            elif self._planner.catalog.match(county.name) != definition:
                raise SourceFeedRegistrationError(f"County name conflicts with code {definition.code!r}.")
            counties[definition.code] = county.id
        return counties, added
