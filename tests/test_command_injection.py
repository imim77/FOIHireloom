import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from FOIHireloom.commands.fetch_job_pages import JobPageCommand
from FOIHireloom.commands.import_dzs import DzsImportCommand
from FOIHireloom.commands.sync_jobs import JobSyncCommand
from FOIHireloom.config.settings import Settings
from FOIHireloom.dto.dzs import DzsImportResultDTO
from FOIHireloom.dto.job_page import JobPageFetchResultDTO
from FOIHireloom.dto.job_sync import JobSyncResultDTO
from FOIHireloom.exceptions import PersistenceError


class CommandInjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_command_uses_injected_service_and_closes_it_after_failure(self) -> None:
        events = []
        result = JobSyncResultDTO(feeds=(), succeeded=0, failed=0, rejected=0, not_modified=0)
        service = SimpleNamespace(sync_all=AsyncMock(return_value=result),
                                  sync_feed=AsyncMock(side_effect=PersistenceError("unavailable")))

        @asynccontextmanager
        async def opener():
            events.append("opened")
            try:
                yield service
            finally:
                events.append("closed")

        command = JobSyncCommand(opener)
        with patch("FOIHireloom.commands.sync_jobs.DependencyService", side_effect=AssertionError("Use injection")):
            self.assertEqual((await command.run())["feeds"], ())
            with self.assertRaises(PersistenceError):
                await command.run(feed_id=7)
        service.sync_feed.assert_awaited_once_with(7)
        self.assertEqual(events, ["opened", "closed", "opened", "closed"])

    async def test_page_command_passes_default_and_explicit_limits_to_the_injected_service(self) -> None:
        result = JobPageFetchResultDTO(attempted=0, fetched=0, unavailable=0, failed=0, remaining=0, stopped_early=False)
        service = SimpleNamespace(fetch_due=AsyncMock(return_value=result))

        @asynccontextmanager
        async def opener():
            yield service

        command = JobPageCommand(opener, batch_size=12)
        await command.run()
        await command.run(limit=3)
        self.assertEqual([call.args[0] for call in service.fetch_due.call_args_list], [12, 3])

    async def test_dzs_command_selects_validation_without_opening_persistence(self) -> None:
        database_modes = []
        service = SimpleNamespace(validate_release=AsyncMock(return_value=DzsImportResultDTO(status="validated")),
                                  import_release=AsyncMock(return_value=DzsImportResultDTO(status="succeeded")))

        @asynccontextmanager
        async def opener(*, with_database=True):
            database_modes.append(with_database)
            yield service

        settings = Settings(_env_file=None, DATABASE_URL="unused-invalid-url")
        command = DzsImportCommand(settings, opener)
        await command.run(dry_run=True)
        await command.run()
        self.assertEqual(database_modes, [False, True])
        self.assertEqual(service.validate_release.call_args.args[0].location, settings.DZS_T1_URL)
        service.import_release.assert_awaited_once()
