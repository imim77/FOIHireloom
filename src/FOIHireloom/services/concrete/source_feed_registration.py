from collections.abc import Callable, Sequence

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.ckan import CkanResource
from FOIHireloom.dto.source_feed import (
    PlannedSourceDTO,
    RegistrationPlanDTO,
    RegistrationPreviewDTO,
    RegistrationResultDTO,
    SourceFeedCreateDTO,
    SourceFeedDTO,
    SourceFeedUpdateDTO,
)
from FOIHireloom.exceptions import ConflictError, SourceFeedRegistrationError
from FOIHireloom.integrations.interfaces.ckan import CkanClientInterface
from FOIHireloom.services.interfaces.source_feed_registration import SourceFeedRegistrationServiceInterface

from .croatian_counties import CroatianCountyCatalog

FEED_FORMATS = {"xml", "rss", "application/rss+xml", "application/xml", "text/xml"}


class SourceFeedRegistrationPlanner:
    """Map CKAN resources to county and occupation feeds without touching the database.

    Occupation feeds keep their CKAN label, which does not name the HZZ
    category they hold; the category is read from their jobs instead.
    """

    def __init__(self, catalog: CroatianCountyCatalog) -> None:
        self.catalog = catalog

    def build(
        self, resources: Sequence[CkanResource], occupation_resources: Sequence[CkanResource]
    ) -> RegistrationPlanDTO:
        sources: list[PlannedSourceDTO] = []
        skipped = 0
        for resource in resources:
            label = self._feed_label(resource)
            if label is None or self.catalog.is_eu(label):
                skipped += 1
                continue
            county = self.catalog.match(label)
            if county is None:
                raise SourceFeedRegistrationError(f"Unrecognised county resource label: {label!r}.")
            sources.append(PlannedSourceDTO(resource=resource, county=county, label=label))
        if not sources:
            raise SourceFeedRegistrationError("CKAN returned no supported Croatian county resources.")
        occupations = 0
        for resource in occupation_resources:
            label = self._feed_label(resource)
            if label is None:
                skipped += 1
                continue
            sources.append(PlannedSourceDTO(resource=resource, scope="occupation", county=None, label=label))
            occupations += 1
        if not occupations:
            raise SourceFeedRegistrationError("CKAN returned no supported occupation resources.")
        ids = {source.resource.id for source in sources}
        urls = {str(source.resource.url) for source in sources}
        if len(ids) < len(sources) or len(urls) < len(sources):
            raise SourceFeedRegistrationError("Duplicate resource ID or feed URL in CKAN response.")
        return RegistrationPlanDTO(sources=tuple(sources), resources_skipped=skipped)

    @staticmethod
    def _feed_label(resource: CkanResource) -> str | None:
        """Return the label of an active feed resource, or None to skip it."""
        if resource.state != "active" or (resource.format or "").strip().casefold() not in FEED_FORMATS:
            return None
        return next((text.strip() for text in (resource.description, resource.name) if text and text.strip()), "")


class SourceFeedRegistrationService(SourceFeedRegistrationServiceInterface):
    """Changed URLs clear their HTTP validators. Registration neither runs
    migrations nor imports jobs. Without a uow_factory only previews work.
    """

    def __init__(
        self,
        client: CkanClientInterface,
        uow_factory: Callable[[], UnitOfWork] | None,
        planner: SourceFeedRegistrationPlanner,
    ) -> None:
        self._client = client
        self._uow_factory = uow_factory
        self._planner = planner

    async def preview_sources(self, dataset_id: str, occupation_dataset_id: str) -> RegistrationPreviewDTO:
        plan = await self._plan(dataset_id, occupation_dataset_id)
        return RegistrationPreviewDTO(
            counties=len(self._planner.catalog.definitions),
            feeds=len(plan.sources),
            occupation_feeds=sum(source.scope == "occupation" for source in plan.sources),
            resources_skipped=plan.resources_skipped,
        )

    async def register_sources(self, dataset_id: str, occupation_dataset_id: str) -> RegistrationResultDTO:
        if self._uow_factory is None:
            raise RuntimeError("Source registration requires a Unit of Work factory.")
        plan = await self._plan(dataset_id, occupation_dataset_id)
        try:
            async with self._uow_factory() as work:
                counties, counties_added = await self._ensure_counties(work)
                resolved = await self._resolve_existing(work, plan)
                added, updated, unchanged = await self._upsert_feeds(work, resolved, counties)
                await work.commit()
        except ConflictError as error:
            raise SourceFeedRegistrationError("County or feed data conflicts; registration was rolled back.") from error
        return RegistrationResultDTO(
            counties_added=counties_added, feeds_added=added, feeds_updated=updated,
            feeds_unchanged=unchanged, resources_skipped=plan.resources_skipped,
        )

    async def _plan(self, dataset_id: str, occupation_dataset_id: str) -> RegistrationPlanDTO:
        resources = await self._client.get_resources(dataset_id)
        return self._planner.build(resources, await self._client.get_resources(occupation_dataset_id))

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
                county = await work.counties.create(definition)
                added += 1
            elif self._planner.catalog.match(county.name) != definition:
                raise SourceFeedRegistrationError(f"County name conflicts with code {definition.code!r}.")
            counties[definition.code] = county.id
        return counties, added

    async def _resolve_existing(
        self, work: UnitOfWork, plan: RegistrationPlanDTO
    ) -> list[tuple[PlannedSourceDTO, SourceFeedDTO | None]]:
        """Resolve both identifiers before mutating feeds, including URLs
        reused by a CKAN resource whose UUID has been replaced."""
        resolved: list[tuple[PlannedSourceDTO, SourceFeedDTO | None]] = []
        targets: set[int] = set()
        for source in plan.sources:
            by_id = await work.source_feeds.get_by_ckan_resource_id(source.resource.id)
            by_url = await work.source_feeds.get_by_feed_url(str(source.resource.url))
            if by_id is not None and by_url is not None and by_id.id != by_url.id:
                raise SourceFeedRegistrationError("Resource ID and URL identify different existing feeds.")
            existing = by_id or by_url
            if existing is not None:
                if existing.scope != source.scope:
                    raise SourceFeedRegistrationError("A resource moved between county and occupation feeds.")
                if existing.id in targets:
                    raise SourceFeedRegistrationError("Multiple resources identify the same existing feed.")
                targets.add(existing.id)
                existing = SourceFeedDTO.model_validate(existing)
            resolved.append((source, existing))
        return resolved

    async def _upsert_feeds(
        self,
        work: UnitOfWork,
        resolved: list[tuple[PlannedSourceDTO, SourceFeedDTO | None]],
        counties: dict[str, int],
    ) -> tuple[int, int, int]:
        added = updated = unchanged = 0
        for source, existing in resolved:
            feed = SourceFeedCreateDTO(
                scope=source.scope, county_id=counties[source.county.code] if source.county else None,
                ckan_resource_id=source.resource.id, label=source.label, feed_url=str(source.resource.url),
            )
            if existing is None:
                await work.source_feeds.create(feed)
                added += 1
            elif (existing.county_id, existing.ckan_resource_id, existing.label, existing.feed_url) != (
                feed.county_id, feed.ckan_resource_id, feed.label, feed.feed_url
            ):
                await work.source_feeds.update(existing.id, SourceFeedUpdateDTO(
                    **feed.model_dump(), reset_http_validators=existing.feed_url != feed.feed_url,
                ))
                updated += 1
            else:
                unchanged += 1
        return added, updated, unchanged
