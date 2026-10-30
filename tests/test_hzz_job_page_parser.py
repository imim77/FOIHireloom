import unittest
from datetime import date
from pathlib import Path

from FOIHireloom.exceptions import HzzJobPageParseError, HzzJobPageUnavailableError
from FOIHireloom.services import HzzJobPageParser

FIXTURES = Path(__file__).parent / "fixtures"


def page(name: str) -> bytes:
    return (FIXTURES / f"hzz_job_page_{name}.html").read_bytes()


class HzzJobPageParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HzzJobPageParser()

    def test_reads_structured_fields_by_element_id(self) -> None:
        job = self.parser.parse(page("school"))
        self.assertEqual(job.title, "STRUKOVNI/A UČITELJ/ICA U KUHARSTVU")
        self.assertEqual(job.work_place, "VELIKA GORICA, ZAGREBAČKA ŽUPANIJA")
        # "Natječaj vrijedi do: 6.11.2026." is the application deadline.
        self.assertEqual((job.valid_from, job.valid_until), (date(2026, 10, 29), date(2026, 11, 6)))
        self.assertEqual((job.workers_needed, job.working_hours, job.work_schedule), (1, "Puno radno vrijeme", "2 smjene"))
        self.assertEqual((job.accommodation, job.transport_allowance), ("Nema smještaja", "U cijelosti"))
        self.assertEqual((job.education, job.experience), ("Srednja škola 4 godine", "Nije važno"))
        self.assertEqual(job.employer_name, "SREDNJA STRUKOVNA ŠKOLA VELIKA GORICA")

    def test_list_fields_are_joined_and_optional_fields_may_be_missing(self) -> None:
        school, restaurant = self.parser.parse(page("school")), self.parser.parse(page("restaurant"))
        self.assertEqual(school.employment_type,
                         "Na neodređeno; upražnjeni poslovi; mogućnost zaposlenja osobe sa invaliditetom")
        self.assertEqual(restaurant.education, "Završena osnovna škola; Srednja škola 3 godine; Srednja škola 4 godine")
        self.assertIsNone(restaurant.work_schedule)
        self.assertEqual(restaurant.employer_name, "RIBARSKA KOLIBA d. o. o. za turizam i ugostiteljstvo")

    def test_description_is_full_plain_text_without_contact_section(self) -> None:
        text = self.parser.parse(page("school")).description_text
        self.assertTrue(text.startswith("Srednja strukovna škola Velika Gorica, Ulica kralja"))
        self.assertIn("\nživotopis,\n", text)
        self.assertTrue(text.endswith("Rok za podnošenje prijava je 8 dana od dana objave natječaja."))
        self.assertNotRegex(text, r"[<>]|&\w+;|\xa0|  ")
        self.assertNotIn("pisana zamolba", text)
        self.assertNotIn("posao@example.com", self.parser.parse(page("restaurant")).description_text)

    def test_error_page_is_unavailable(self) -> None:
        with self.assertRaises(HzzJobPageUnavailableError):
            self.parser.parse(page("error"))

    def test_unexpected_pages_are_rejected(self) -> None:
        school = page("school").decode()
        for content in (b"", b"<html>maintenance</html>", "čšž".encode("cp1250"),
                        school.replace("lblMjestoRada\"", "x\"").replace("lblVrijediDo\"", "y\"").encode()):
            with self.subTest(content=content[:30]), self.assertRaises(HzzJobPageParseError):
                self.parser.parse(content)

    def test_missing_or_invalid_values_become_none(self) -> None:
        school = page("school").decode()
        job = self.parser.parse(school.replace(">6.11.2026.<", ">31.02.2026.<").replace(">1</span>", "></span>")
                                .replace('id="ctl00_MainContent_lblNazivPoslodavca"', 'id="other"').encode())
        self.assertEqual((job.valid_until, job.workers_needed, job.employer_name), (None, None, None))
        self.assertEqual(job.work_place, "VELIKA GORICA, ZAGREBAČKA ŽUPANIJA")
