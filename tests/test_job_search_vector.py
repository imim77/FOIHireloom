from sqlalchemy import func, select, text

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Job
from FOIHireloom.db.models.job import SEARCH_FOLD_FROM, SEARCH_FOLD_TO


class JobSearchVectorTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.session.add_all([
            Job(provider="hzz", source_job_id="1", canonical_url="https://example.com/1", content_hash="1",
                title="ČISTAČICA/ČISTAČ", description_text="Čišćenje apartmana u Đakovu."),
            Job(provider="hzz", source_job_id="2", canonical_url="https://example.com/2", content_hash="2",
                title="KUHAR/KUHARICA", description_text=None),
            Job(provider="hzz", source_job_id="3", canonical_url="https://example.com/3", content_hash="3",
                title=None, description_text=None),
        ])
        await self.session.commit()

    async def search(self, query: str) -> list[str]:
        folded = func.translate(query, SEARCH_FOLD_FROM, SEARCH_FOLD_TO)
        statement = (
            select(Job.source_job_id)
            .where(Job.search_vector.bool_op("@@")(func.plainto_tsquery("simple", folded)))
            .order_by(Job.source_job_id)
        )
        return list(await self.session.scalars(statement))

    async def test_queries_match_with_or_without_croatian_diacritics(self) -> None:
        for query in ("čistačica", "cistacica", "CISTACICA", "đakovu", "dakovu", "kuharica"):
            with self.subTest(query=query):
                self.assertEqual(len(await self.search(query)), 1)
        self.assertEqual(await self.search("konobar"), [])

    async def test_vector_combines_title_and_description_and_tolerates_nulls(self) -> None:
        self.assertEqual(await self.search("apartmana cistac"), ["1"])
        vectors = await self.session.execute(select(Job.source_job_id, Job.search_vector).order_by(Job.source_job_id))
        self.assertEqual({key: str(vector) for key, vector in vectors.all()}["3"], "")

    async def test_search_vector_is_deferred_and_backed_by_a_gin_index(self) -> None:
        job = await self.session.scalar(select(Job).where(Job.source_job_id == "2"))
        self.assertNotIn("search_vector", job.__dict__)
        plan = "\n".join(await self.session.scalars(text(
            "EXPLAIN SELECT id FROM jobs WHERE search_vector @@ plainto_tsquery('simple', 'kuhar')"
        )))
        indexes = await self.session.scalar(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() AND indexname = 'ix_jobs_search_vector'"
        ))
        self.assertIn("USING gin (search_vector)", indexes)
        self.assertIn("jobs", plan)
