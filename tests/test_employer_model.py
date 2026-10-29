from datetime import datetime, timedelta, timezone

from model_test_case import ModelTestCase

from FOIHireloom.db.models import Employer


class EmployerModelTests(ModelTestCase):
    async def test_same_name_does_not_merge_employers(self) -> None:
        first = Employer(name="Primjer d.o.o.")
        second = Employer(name="Primjer d.o.o.")
        self.session.add_all([first, second])
        await self.session.flush()
        self.assertNotEqual(first.id, second.id)
        self.assertIsNone(first.website_url)
        self.assertIsNotNone(first.created_at.tzinfo)

    async def test_updates_refresh_updated_at(self) -> None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        employer = Employer(name="Prvi naziv", created_at=yesterday, updated_at=yesterday)
        self.session.add(employer)
        await self.session.commit()
        employer.name = "Novi naziv"
        await self.session.commit()
        await self.session.refresh(employer)
        self.assertEqual(employer.created_at, yesterday)
        self.assertGreater(employer.updated_at, yesterday)

    async def test_rejects_blank_name_and_reversed_timestamps(self) -> None:
        await self.assert_rejected(Employer(name=" "))
        now = datetime.now(timezone.utc)
        await self.assert_rejected(
            Employer(name="Poslodavac", created_at=now, updated_at=now - timedelta(days=1))
        )
