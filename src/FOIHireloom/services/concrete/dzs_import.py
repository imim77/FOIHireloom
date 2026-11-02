import hashlib
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from FOIHireloom.db.uow.base import UnitOfWork
from FOIHireloom.dto.dzs import (
    DzsFileDTO,
    DzsImportOutcomeDTO,
    DzsImportResultDTO,
    DzsReleaseDTO,
    DzsSourceDTO,
    DzsValueChangeDTO,
    DzsValueDTO,
)
from FOIHireloom.exceptions import DzsError, DzsValidationError, PersistenceError
from FOIHireloom.integrations.interfaces.dzs import DzsClientInterface
from FOIHireloom.services.interfaces.dzs_import import DzsImportServiceInterface

from .croatian_counties import CroatianCountyCatalog
from .dzs_release_parser import SHEETS, DzsReleaseParser

ERROR_LIMIT = 20
ERROR_SUMMARY_LIMIT = 2000


class DzsImportService(DzsImportServiceInterface):
    """Files are obtained, parsed and validated before any transaction opens;
    all values are then written in one transaction. A value is unchanged when
    its value, missing reason, provisional flag and source are all equal;
    otherwise the row is updated and points to this import, and revised_at
    is set when the value or missing reason changed.

    Without a uow_factory only validate_release works.
    """

    def __init__(
        self,
        client: DzsClientInterface,
        parser: DzsReleaseParser,
        uow_factory: Callable[[], UnitOfWork] | None,
        catalog: CroatianCountyCatalog,
    ) -> None:
        self._client = client
        self._parser = parser
        self._uow_factory = uow_factory
        self._catalog = catalog

    async def validate_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        files: list[DzsFileDTO] = []
        try:
            release = self._parser.parse(*await self._obtain(t1, workbook, files))
        except DzsValidationError as error:
            return DzsImportResultDTO(status="rejected", dry_run=True, files=tuple(files),
                                      errors=self._errors(error.problems))
        except DzsError as error:
            return DzsImportResultDTO(status="failed", dry_run=True, files=tuple(files), errors=(self._summary(error),))
        return DzsImportResultDTO(status="validated", dry_run=True, files=tuple(files), series=release.series)

    async def import_release(self, t1: DzsSourceDTO, workbook: DzsSourceDTO) -> DzsImportResultDTO:
        if self._uow_factory is None:
            raise RuntimeError("DZS import requires a Unit of Work factory.")
        async with self._uow_factory() as work:
            import_id = await work.dzs_imports.start()
            await work.commit()
        files: list[DzsFileDTO] = []
        try:
            # No transaction is open while the files download and are checked.
            release = self._parser.parse(*await self._obtain(t1, workbook, files))
            return await self._apply(import_id, release, files)
        except DzsValidationError as error:
            return await self._record_failure(import_id, "rejected", files, self._errors(error.problems))
        except (DzsError, PersistenceError) as error:
            return await self._record_failure(import_id, "failed", files, (self._summary(error),))
        except Exception as error:
            await self._record_failure(import_id, "failed", files, (self._summary(error),))
            raise

    async def _obtain(self, t1: DzsSourceDTO, workbook: DzsSourceDTO, files: list[DzsFileDTO]) -> tuple[bytes, bytes]:
        """Return both files' bytes, appending each file's provenance as soon as it is obtained."""
        contents = []
        for role, source in (("t1", t1), ("workbook", workbook)):
            if source.local:
                response = await self._client.read(Path(source.location))
            else:
                response = await self._client.fetch(source.location)
            files.append(DzsFileDTO(
                role=role, location=source.location, sheets=SHEETS[role],
                sha256=hashlib.sha256(response.content).hexdigest(), size_bytes=len(response.content),
                etag=response.etag, last_modified=response.last_modified, fetched_at=datetime.now(timezone.utc),
            ))
            contents.append(response.content)
        return contents[0], contents[1]

    async def _apply(self, import_id: int, release: DzsReleaseDTO, files: list[DzsFileDTO]) -> DzsImportResultDTO:
        async with self._uow_factory() as work:
            now = await work.transaction_time()
            stored_counties = {county.iso_code for county in await work.counties.list_all()}
            missing = [county.iso_code for county in self._catalog.definitions if county.iso_code not in stored_counties]
            if missing:
                raise DzsError(f"Counties {', '.join(sorted(missing))} are not stored; run foihireloom-register-sources first.")
            existing = {snapshot.key: snapshot for snapshot in await work.dzs_indicator_values.list_snapshots()}
            new: list[DzsValueDTO] = []
            changes: list[DzsValueChangeDTO] = []
            for value in release.values:
                stored = existing.get(value.key)
                if stored is None:
                    new.append(value)
                elif self._content(stored) != self._content(value):
                    revised = (stored.value, stored.missing_reason) != (value.value, value.missing_reason)
                    changes.append(DzsValueChangeDTO(id=stored.id, value=value, revised=revised))
            unchanged = len(release.values) - len(new) - len(changes)
            await work.dzs_indicator_values.create_many(new, import_id, now)
            await work.dzs_indicator_values.update_many(changes, import_id, now)
            await work.dzs_imports.finish(import_id, DzsImportOutcomeDTO(
                status="succeeded", values_inserted=len(new), values_updated=len(changes), values_unchanged=unchanged,
                files=tuple(files),
            ), now)
            await work.commit()
        return DzsImportResultDTO(
            import_id=import_id, status="succeeded", files=tuple(files), series=release.series,
            values_inserted=len(new), values_updated=len(changes), values_unchanged=unchanged,
        )

    async def _record_failure(
        self, import_id: int, status: Literal["failed", "rejected"], files: list[DzsFileDTO], errors: tuple[str, ...]
    ) -> DzsImportResultDTO:
        """Record the outcome in a new transaction; the import's writes are already rolled back."""
        async with self._uow_factory() as work:
            await work.dzs_imports.finish(import_id, DzsImportOutcomeDTO(
                status=status, error_summary="\n".join(errors)[:ERROR_SUMMARY_LIMIT], files=tuple(files),
            ), await work.transaction_time())
            await work.commit()
        return DzsImportResultDTO(import_id=import_id, status=status, files=tuple(files), errors=errors)

    @staticmethod
    def _content(value: DzsValueDTO) -> tuple:
        return value.value, value.missing_reason, value.is_provisional, value.source

    @staticmethod
    def _errors(problems: Sequence[str]) -> tuple[str, ...]:
        if len(problems) <= ERROR_LIMIT:
            return tuple(problems)
        return (*problems[:ERROR_LIMIT], f"… and {len(problems) - ERROR_LIMIT} more problems.")

    @staticmethod
    def _summary(error: Exception) -> str:
        return str(error) or type(error).__name__
