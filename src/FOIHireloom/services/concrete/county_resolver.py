from collections.abc import Sequence

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.county import CountyDTO
from FOIHireloom.exceptions import InvalidIndicatorRequestError

from .croatian_counties import CroatianCountyCatalog


class CountyResolver:
    """CountyResolver turns the county labels a user gave into stored counties for county-level tools.

    Labels are codes or names as list_regions shows them; errors name the
    valid codes, so the caller can correct the request.
    """

    def __init__(self, catalog: CroatianCountyCatalog) -> None:
        self._catalog = catalog

    @staticmethod
    def check_count(counties: Sequence[str], least: int, most: int) -> None:
        if not least <= len(counties) <= most:
            raise InvalidIndicatorRequestError(f"Choose {least} to {most} counties, not {len(counties)}.")

    async def resolve(self, work: UnitOfWork, requested: Sequence[str]) -> list[CountyDTO]:
        """The stored counties by code or name, in the given order; raise for unknown or repeated ones."""
        stored = {county.code: county for county in await work.counties.list_all()}
        resolved: list[CountyDTO] = []
        unknown: list[str] = []
        for label in requested:
            definition = self._catalog.match(label)
            code = definition.code if definition is not None else label.strip().casefold()
            if code in stored:
                resolved.append(stored[code])
            else:
                unknown.append(label)
        if unknown:
            raise InvalidIndicatorRequestError(
                f"Unknown {'county' if len(unknown) == 1 else 'counties'}: {', '.join(unknown)}. Use county codes "
                f"or names from list_regions: {', '.join(sorted(stored))}.")
        codes = [county.code for county in resolved]
        if repeated := sorted({code for code in codes if codes.count(code) > 1}):
            raise InvalidIndicatorRequestError(
                f"Choose different counties; given more than once: {', '.join(repeated)}.")
        return resolved
