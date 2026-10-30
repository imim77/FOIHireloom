import unittest

from FOIHireloom.services.concrete.croatian_stem import stem


class CroatianStemTests(unittest.TestCase):
    def test_case_and_feminine_endings_are_removed(self) -> None:
        cases = {
            "njemacki": "njemack", "engleskog": "englesk", "medicinske": "medicinsk", "sestre": "sestr",
            "vozaci": "vozac", "zagrebu": "zagreb", "varazdinu": "varazdin", "racunalima": "racunal",
            "kuharica": "kuhar", "uciteljice": "ucitelj", "prodavacicama": "prodavac", "smjestajem": "smjestaj",
        }
        for word, expected in cases.items():
            with self.subTest(word=word):
                self.assertEqual(stem(word), expected)

    def test_short_stems_and_words_with_digits_are_kept(self) -> None:
        # "zadr" would match "zadrzava".
        for word in ("zadru", "placa", "puli", "kuhar", "skola", "b2", "c"):
            with self.subTest(word=word):
                self.assertEqual(stem(word), word)

    def test_ka_is_not_an_ending(self) -> None:
        # "osije" and "vozac" (driver, from "vozacka" licence) would change the meaning.
        for word, expected in {"osijeku": "osijek", "vozacka": "vozack", "frizerka": "frizerk"}.items():
            with self.subTest(word=word):
                self.assertEqual(stem(word), expected)
