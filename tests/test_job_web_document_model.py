from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Job, JobWebDocument, WebDocument


class JobWebDocumentModelTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.job = Job(provider="hzz", canonical_url="https://example.com/job/1", content_hash="hash")
        self.document = WebDocument(
            canonical_url="https://example.com/detail", content_text="Uvjeti oglasa",
            content_hash="hash", retrieval_provider="tavily",
        )
        self.session.add_all([self.job, self.document])
        await self.session.flush()

    def link(self, **overrides: object) -> JobWebDocument:
        return JobWebDocument(**({
            "job_id": self.job.id, "document_id": self.document.id, "relation_kind": "job_detail"
        } | overrides))

    async def test_pair_is_unique_and_roles_are_validated(self) -> None:
        await self.assert_rejected(self.link(relation_kind="invented"))
        await self.assert_rejected(self.link(job_id=999999))
        await self.assert_rejected(self.link(document_id=999999))
        link = self.link()
        self.session.add(link)
        await self.session.flush()
        self.assertIsNotNone(link.linked_at.tzinfo)
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.execute(insert(JobWebDocument).values(
                    job_id=self.job.id, document_id=self.document.id, relation_kind="supporting_context"
                ))

    async def test_deleting_job_keeps_shared_document_and_other_jobs_link(self) -> None:
        other_job = Job(provider="hzz", canonical_url="https://example.com/job/2", content_hash="hash")
        self.session.add_all([
            self.link(), JobWebDocument(job=other_job, document_id=self.document.id, relation_kind="supporting_context")
        ])
        await self.session.flush()
        await self.session.delete(self.job)
        await self.session.flush()
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(JobWebDocument)), 1)
        self.assertIsNotNone(await self.session.get(WebDocument, self.document.id))

    async def test_referenced_document_cannot_be_deleted_even_when_links_are_loaded(self) -> None:
        self.session.add(self.link())
        await self.session.flush()
        await self.session.refresh(self.document, ["job_links"])
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.delete(self.document)
                await self.session.flush()
