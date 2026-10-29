from model_test_case import ModelTestCase

from FOIHireloom.db.models import County


class CountyModelTests(ModelTestCase):
    async def test_generated_identity_and_croatian_text(self) -> None:
        county = County(code="hr-city-zagreb", name="Grad Zagreb")
        self.session.add(county)
        await self.session.commit()
        await self.session.refresh(county)
        self.assertIsInstance(county.id, int)
        self.assertEqual(county.name, "Grad Zagreb")

    async def test_code_and_name_are_independently_unique(self) -> None:
        self.session.add(County(code="zagreb", name="Grad Zagreb"))
        await self.session.flush()
        await self.assert_rejected(County(code="zagreb", name="Drugi naziv"))
        await self.assert_rejected(County(code="druga-sifra", name="Grad Zagreb"))

    async def test_required_fields_reject_null_and_blank_values(self) -> None:
        await self.assert_rejected(County(code=None, name="Županija"))
        await self.assert_rejected(County(code="sifra", name=None))
        await self.assert_rejected(County(code=" ", name="Županija"))
        await self.assert_rejected(County(code="sifra", name=" "))
