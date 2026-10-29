from datetime import datetime, timedelta, timezone

from model_test_case import ModelTestCase

from FOIHireloom.db.models import WebDocument


class WebDocumentModelTests(ModelTestCase):
    def document(self, **overrides: object) -> WebDocument:
        values = {
            "canonical_url": "https://example.com/jobs/1",
            "content_text": "Potpuni opis oglasa s hrvatskim znakovima: čćžšđ.",
            "content_hash": "first-hash",
            "retrieval_provider": "tavily",
        }
        return WebDocument(**(values | overrides))

    async def test_versions_of_same_url_have_separate_identities(self) -> None:
        first = self.document()
        second = self.document(content_hash="second-hash")
        self.session.add_all([first, second])
        await self.session.flush()
        self.assertNotEqual(first.id, second.id)
        self.assertIsNone(first.title)
        await self.assert_rejected(self.document())

    async def test_requires_nonblank_content_and_known_retrieval_provider(self) -> None:
        for field in ["canonical_url", "content_text", "content_hash"]:
            with self.subTest(field=field):
                await self.assert_rejected(self.document(**{field: " "}))
        await self.assert_rejected(self.document(retrieval_provider="unknown"))

    async def test_verification_cannot_precede_retrieval(self) -> None:
        now = datetime.now(timezone.utc)
        await self.assert_rejected(
            self.document(
                first_retrieved_at=now,
                last_verified_at=now - timedelta(seconds=1),
            )
        )
