from sqlalchemy.exc import IntegrityError

from model_test_case import ModelTestCase

from FOIHireloom.db.models import County
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dao.concrete.sqla_county import SqlAlchemyCountyRepository


class CountyRepositoryTests(ModelTestCase):
    async def test_code_and_name_lookups_share_explicit_unit_of_work_commit(self) -> None:
        factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))
        async with factory() as work:
            county = County(code="grad-zagreb", name="Grad Zagreb")
            await work.counties.add(county)
            self.assertIsInstance(county.id, int)
            self.assertIs(await work.counties.get_by_code("grad-zagreb"), county)
            async with SessionManager(self.engine).session() as reader:
                self.assertIsNone(await SqlAlchemyCountyRepository(reader).get_by_name("Grad Zagreb"))
            await work.commit()
        async with factory() as work:
            self.assertEqual((await work.counties.get_by_name("Grad Zagreb")).id, county.id)
            self.assertEqual((await work.counties.get_by_code("grad-zagreb")).id, county.id)
            self.assertIsNone(await work.counties.get_by_code("missing"))
            self.assertIsNone(await work.counties.get_by_name("missing"))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_conflicting_code_or_name_rolls_back_new_counties(self) -> None:
        factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))
        async with factory() as work:
            await work.counties.add(County(code="grad-zagreb", name="Grad Zagreb"))
            await work.commit()
        for duplicate in [
            County(code="grad-zagreb", name="Other"),
            County(code="other", name="Grad Zagreb"),
        ]:
            with self.subTest(code=duplicate.code), self.assertRaises(IntegrityError):
                async with factory() as work:
                    await work.counties.add(County(code="pending", name="Pending"))
                    await work.counties.add(duplicate)
            async with factory() as work:
                self.assertIsNone(await work.counties.get_by_code("pending"))
                self.assertIsNotNone(await work.counties.get_by_name("Grad Zagreb"))
        self.assertEqual(self.engine.pool.checkedout(), 0)
