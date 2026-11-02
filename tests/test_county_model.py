from model_test_case import ModelTestCase

from FOIHireloom.db.models import County


class CountyModelTests(ModelTestCase):
    async def test_generated_identity_and_croatian_text(self) -> None:
        county = County(code="hr-city-zagreb", iso_code="HR-21", name="Grad Zagreb")
        self.session.add(county)
        await self.session.commit()
        await self.session.refresh(county)
        self.assertIsInstance(county.id, int)
        self.assertEqual(county.name, "Grad Zagreb")

    async def test_code_iso_code_and_name_are_independently_unique(self) -> None:
        self.session.add(County(code="zagreb", iso_code="HR-21", name="Grad Zagreb"))
        await self.session.flush()
        await self.assert_rejected(County(code="zagreb", iso_code="HR-01", name="Drugi naziv"))
        await self.assert_rejected(County(code="druga-sifra", iso_code="HR-01", name="Grad Zagreb"))
        await self.assert_rejected(County(code="druga-sifra", iso_code="HR-21", name="Drugi naziv"))

    async def test_required_fields_reject_null_and_blank_values(self) -> None:
        await self.assert_rejected(County(code=None, iso_code="HR-01", name="Županija"))
        await self.assert_rejected(County(code="sifra", iso_code="HR-01", name=None))
        await self.assert_rejected(County(code="sifra", iso_code=None, name="Županija"))
        await self.assert_rejected(County(code=" ", iso_code="HR-01", name="Županija"))
        await self.assert_rejected(County(code="sifra", iso_code="HR-01", name=" "))

    async def test_iso_code_must_be_a_croatian_county_code(self) -> None:
        for iso_code in ("HR-00", "HR-22", "HR-1", "hr-01", "SI-01", " HR-01", ""):
            with self.subTest(iso_code=iso_code):
                await self.assert_rejected(County(code="sifra", iso_code=iso_code, name="Županija"))
