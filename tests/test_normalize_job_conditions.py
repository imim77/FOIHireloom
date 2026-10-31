import asyncio
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from sqlalchemy import func, select, update

from model_test_case import ModelTestCase

from FOIHireloom.commands.normalize_job_conditions import main
from FOIHireloom.db.models import Job
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dto.job_conditions import JobConditionsRunDTO
from FOIHireloom.exceptions import PersistenceError
from FOIHireloom.services import JobConditionsNormalizer, JobConditionsService

NONE_UNRECOGNISED = dict.fromkeys(
    ("experience", "employment_type", "working_hours", "education", "accommodation", "work_schedule",
     "transport_allowance"), 0,
)


class FixedService:
    def __init__(self, result: JobConditionsRunDTO | None = None, error: Exception | None = None) -> None:
        self.result, self.error = result, error

    async def normalize_all(self) -> JobConditionsRunDTO:
        if self.error is not None:
            raise self.error
        return self.result


def run_main(service: FixedService) -> tuple[int, str, str]:
    class FakeDependencyService:
        def __init__(self, settings) -> None:
            pass

        @contextlib.asynccontextmanager
        async def job_conditions_service(self):
            yield service

    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch("FOIHireloom.commands.normalize_job_conditions.DependencyService", FakeDependencyService), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main([])
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class JobConditionsServiceTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # Fetched before conditions were normalised, so only the raw page values are stored.
        now = func.now()
        fetched = {"page_status": "fetched", "page_checked_at": now, "page_fetched_at": now, "page_source_hash": "h"}
        jobs = {
            "kitchen": Job(**fetched, page_employment_type="Na određeno; sezonski", page_accommodation="Nema smještaja",
                           page_working_hours="20 sati tjedno", page_experience="Traži se pripravnik"),
            "office": Job(**fetched, page_education="Fakultet, akademija, magisterij, doktorat",
                          page_experience="Puno iskustva"),
            "pending": Job(),
        }
        for key, job in jobs.items():
            job.provider, job.source_job_id, job.canonical_url, job.content_hash = (
                "hzz", key, f"https://example.com/{key}", "h"
            )
        self.session.add_all(jobs.values())
        await self.session.commit()
        self.service = JobConditionsService(SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine)),
                                            JobConditionsNormalizer())

    async def stored(self) -> dict[str, tuple]:
        statement = select(Job.source_job_id, Job.contract, Job.employment_tags, Job.weekly_hours, Job.trainee,
                           Job.accommodation, Job.education_levels, Job.conditions_unrecognised)
        return {row[0]: tuple(row[1:]) for row in await self.session.execute(statement)}

    async def test_normalises_fetched_pages_once_and_again_after_a_raw_value_changes(self) -> None:
        result = await self.service.normalize_all()
        self.assertEqual(result, JobConditionsRunDTO(
            checked=2, updated=2, unrecognised=NONE_UNRECOGNISED | {"experience": 1},
        ))
        self.assertEqual(await self.stored(), {
            "kitchen": ("fixed_term", ["seasonal"], 20, True, "none", None, []),
            "office": (None, None, None, None, None, ["university"], ["experience"]),
            "pending": (None, None, None, None, None, None, []),
        })

        self.assertEqual((await self.service.normalize_all()).updated, 0)

        await self.session.execute(update(Job).where(Job.source_job_id == "kitchen")
                                   .values(page_accommodation="Obiteljski stan"))
        await self.session.commit()
        result = await self.service.normalize_all()
        self.assertEqual((result.checked, result.updated), (2, 1))
        self.assertEqual((await self.stored())["kitchen"], ("fixed_term", ["seasonal"], 20, True, "family", None, []))

    async def test_command_prints_the_summary(self) -> None:
        result = await self.service.normalize_all()
        # The command starts its own event loop.
        code, out, _ = await asyncio.to_thread(run_main, FixedService(result))
        self.assertEqual((code, json.loads(out)), (0, result.model_dump()))


class NormalizeJobConditionsCommandErrorTests(unittest.TestCase):
    def test_database_error_exits_1(self) -> None:
        code, out, err = run_main(FixedService(error=PersistenceError("db down")))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("DATABASE_URL", err)
