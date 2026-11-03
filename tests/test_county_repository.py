from model_test_case import ModelTestCase

from FOIHireloom.db.models import County
from FOIHireloom.db.session import SessionManager
from FOIHireloom.db.uow import SqlAlchemyUnitOfWorkFactory
from FOIHireloom.dao.concrete.sqla_county import SqlAlchemyCountyRepository
from FOIHireloom.dto.county import CountyDefinitionDTO, CountyDTO
from FOIHireloom.exceptions import ConflictError


class CountyRepositoryTests(ModelTestCase):
    async def test_code_and_name_lookups_share_explicit_unit_of_work_commit(self) -> None:
        factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))
        async with factory() as work:
            county = County(code="grad-zagreb", iso_code="HR-21", name="Grad Zagreb")
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
            await work.counties.add(County(code="grad-zagreb", iso_code="HR-21", name="Grad Zagreb"))
            await work.commit()
        for duplicate in [
            County(code="grad-zagreb", iso_code="HR-01", name="Other"),
            County(code="other", iso_code="HR-01", name="Grad Zagreb"),
        ]:
            with self.subTest(code=duplicate.code), self.assertRaises(ConflictError):
                async with factory() as work:
                    await work.counties.add(County(code="pending", iso_code="HR-02", name="Pending"))
                    await work.counties.add(duplicate)
            async with factory() as work:
                self.assertIsNone(await work.counties.get_by_code("pending"))
                self.assertIsNotNone(await work.counties.get_by_name("Grad Zagreb"))
        self.assertEqual(self.engine.pool.checkedout(), 0)

    async def test_create_returns_county_dto_with_generated_id(self) -> None:
        factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))
        async with factory() as work:
            created = await work.counties.create(
                CountyDefinitionDTO(code="istarska", iso_code="HR-18", name="Istarska županija")
            )
            self.assertIsInstance(created, CountyDTO)
            self.assertEqual(created.iso_code, "HR-18")
            self.assertEqual((await work.counties.get_by_code("istarska")).id, created.id)
            await work.commit()

    async def test_list_all_returns_counties_by_iso_code(self) -> None:
        factory = SqlAlchemyUnitOfWorkFactory(SessionManager(self.engine))
        async with factory() as work:
            self.assertEqual(await work.counties.list_all(), [])
            for definition in (
                CountyDefinitionDTO(code="grad-zagreb", iso_code="HR-21", name="Grad Zagreb"),
                CountyDefinitionDTO(code="zagrebacka", iso_code="HR-01", name="Zagrebačka županija"),
            ):
                await work.counties.create(definition)
            counties = await work.counties.list_all()
        self.assertEqual([(county.iso_code, county.code) for county in counties],
                         [("HR-01", "zagrebacka"), ("HR-21", "grad-zagreb")])
        self.assertTrue(all(isinstance(county, CountyDTO) for county in counties))
