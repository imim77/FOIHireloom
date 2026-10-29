from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Employer, EmployerWebDocument, WebDocument


class EmployerWebDocumentModelTests(ModelTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.employer = Employer(name="Poslodavac")
        self.document = WebDocument(
            canonical_url="https://example.com/about", content_text="O poslodavcu",
            content_hash="hash", retrieval_provider="direct",
        )
        self.session.add_all([self.employer, self.document])
        await self.session.flush()

    def link(self, **overrides: object) -> EmployerWebDocument:
        return EmployerWebDocument(**({
            "employer_id": self.employer.id, "document_id": self.document.id,
            "relation_kind": "official_site",
        } | overrides))

    async def test_composite_identity_foreign_keys_and_allowed_roles(self) -> None:
        await self.assert_rejected(self.link(relation_kind="invented"))
        await self.assert_rejected(self.link(employer_id=999999))
        await self.assert_rejected(self.link(document_id=999999))
        link = self.link()
        self.session.add(link)
        await self.session.flush()
        self.assertIsNotNone(link.linked_at.tzinfo)
        with self.assertRaises(IntegrityError):
            async with self.session.begin_nested():
                await self.session.execute(insert(EmployerWebDocument).values(
                    employer_id=self.employer.id, document_id=self.document.id,
                    relation_kind="company_context",
                ))

    async def test_linked_employer_and_document_cannot_be_deleted(self) -> None:
        self.session.add(self.link())
        await self.session.flush()
        await self.session.refresh(self.employer, ["web_document_links"])
        await self.session.refresh(self.document, ["employer_links"])
        for instance in [self.employer, self.document]:
            with self.assertRaises(IntegrityError):
                async with self.session.begin_nested():
                    await self.session.delete(instance)
                    await self.session.flush()

    async def test_document_can_describe_multiple_employers(self) -> None:
        other = Employer(name="Drugi poslodavac")
        self.session.add(other)
        await self.session.flush()
        self.session.add_all([
            self.link(), self.link(employer_id=other.id, relation_kind="company_context")
        ])
        await self.session.flush()
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(WebDocument)), 1)
        self.assertEqual(await self.session.scalar(select(func.count()).select_from(EmployerWebDocument)), 2)

    async def test_explicit_unlink_keeps_document(self) -> None:
        link = self.link(relation_kind="careers")
        self.session.add(link)
        await self.session.flush()
        await self.session.delete(link)
        await self.session.flush()
        await self.session.delete(self.employer)
        await self.session.flush()
        self.assertIsNotNone(await self.session.get(WebDocument, self.document.id))
