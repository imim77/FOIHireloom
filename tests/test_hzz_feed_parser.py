import unittest
from datetime import date
from pathlib import Path

from FOIHireloom.exceptions import HzzFeedParseError
from FOIHireloom.services import HzzFeedParser

FIXTURE = Path(__file__).parent / "fixtures/hzz_feed_sample.xml"


def feed(*items: str, encoding: str = "utf-8") -> bytes:
    body = "".join(f"<item>{item}</item>" for item in items)
    return f'<?xml version="1.0" encoding="{encoding}"?><rss version="2.0"><channel>{body}</channel></rss>'.encode(encoding)


def item(web_sifra: str = "167800201", pub: str = "27.10.2026", title: str = "KUHAR", description: str = "Opis posla: KUHAR") -> str:
    link = f"http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra={web_sifra}"
    return (f"<title>{title}</title><subject>{title}</subject><pubDate>{pub}</pubDate>"
            f"<description>{description}</description><link>{link}</link><guid>{link}</guid>")


class HzzFeedParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HzzFeedParser()
        self.jobs = {job.source_job_id: job for job in self.parser.parse(FIXTURE.read_bytes()).jobs}

    def test_real_sample_decodes_iso_8859_2_and_identifies_ads_by_web_sifra(self) -> None:
        result = self.parser.parse(FIXTURE.read_bytes())
        self.assertEqual((len(result.jobs), result.invalid_items), (7, 0))
        job = self.jobs["167800201"]
        self.assertEqual(job.title, "KUHAR/KUHARICA - II")
        self.assertEqual(job.canonical_url, "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=167800201")
        self.assertEqual(job.published_on, date(2026, 10, 27))
        self.assertIn("ZAŠTITE", self.jobs["167777512"].title)

    def test_suffix_fields_keep_commas_inside_category(self) -> None:
        job = self.jobs["167800201"]
        self.assertEqual(job.category, "UGOSTITELJI, RADNICI U TURIZMU")
        self.assertEqual(job.deadline_on, date(2026, 11, 2))
        self.assertEqual(job.location_text, "BJELOVAR")
        self.assertEqual(job.municipality, "BJELOVAR")
        self.assertEqual(job.description_text, "KUHAR/KUHARICA - II")
        self.assertEqual(job.quality_flags, ())

    def test_empty_title_is_none_and_flagged_without_inventing_one(self) -> None:
        job = self.jobs["167488856"]
        self.assertIsNone(job.title)
        self.assertEqual(job.quality_flags, ("title_missing",))
        self.assertTrue(job.description_text.startswith("Priprema i obrada namirnica"))
        self.assertEqual(job.deadline_on, date(2026, 10, 30))

    def test_truncated_html_description_is_cleaned_and_flagged(self) -> None:
        for web_sifra in ("167777856", "167777798", "167711851"):
            with self.subTest(web_sifra=web_sifra):
                job = self.jobs[web_sifra]
                self.assertIn("description_truncated", job.quality_flags)
                self.assertIn("deadline_unknown", job.quality_flags)
                self.assertIsNone(job.category)
                self.assertNotRegex(job.description_text, r"[<>]|&\w+;| ")
        self.assertTrue(self.jobs["167777856"].description_text.startswith("PODRUČNI URED ČAZMA\nMJESTO RADA:"))

    def test_150_character_title_is_flagged_as_possibly_truncated(self) -> None:
        job = self.jobs["167711851"]
        self.assertEqual(len(job.title), 150)
        self.assertIn("title_truncated", job.quality_flags)

    def test_cut_suffix_drops_unreliable_last_value(self) -> None:
        cut = "Opis posla: X, Kategorija: TRGOVCI, Rok za prijavu: 30.10.2026, Mjesto rada: SPLI"
        job = self.parser.parse(feed(item(description=cut))).jobs[0]
        self.assertEqual((job.category, job.deadline_on, job.location_text), ("TRGOVCI", date(2026, 10, 30), None))
        self.assertIsNone(job.municipality)
        self.assertIn("description_truncated", job.quality_flags)
        cut_deadline = "Opis posla: X, Kategorija: TRGOVCI, Rok za prijavu: 30.10.20"
        self.assertIsNone(self.parser.parse(feed(item(description=cut_deadline))).jobs[0].deadline_on)

    def test_content_hash_tracks_title_date_and_description(self) -> None:
        base = self.parser.parse(feed(item())).jobs[0].content_hash
        self.assertEqual(base, self.parser.parse(feed(item())).jobs[0].content_hash)
        for changed in (item(title="KONOBAR"), item(pub="28.10.2026"), item(description="Opis posla: KUHAR II")):
            with self.subTest(changed=changed):
                self.assertNotEqual(self.parser.parse(feed(changed)).jobs[0].content_hash, base)

    def test_items_without_web_sifra_or_date_are_counted_not_guessed(self) -> None:
        bad_link = item().replace("WebSifra=167800201", "Id=1")
        result = self.parser.parse(feed(item("1"), bad_link, item("2", pub="2026-10-27"), item("3", pub="31.02.2026")))
        self.assertEqual([job.source_job_id for job in result.jobs], ["1"])
        self.assertEqual(result.invalid_items, 3)

    def test_empty_channel_is_an_empty_result(self) -> None:
        result = self.parser.parse(feed())
        self.assertEqual((result.jobs, result.invalid_items), ((), 0))

    def test_duplicate_web_sifra_is_rejected(self) -> None:
        with self.assertRaisesRegex(HzzFeedParseError, "Duplicate"):
            self.parser.parse(feed(item("1"), item("1", title="OTHER")))

    def test_malformed_unsafe_or_non_rss_documents_are_rejected(self) -> None:
        documents = [
            b"",
            b"<html>proxy error</html>",
            b"<rss version='2.0'><item/></rss>",
            FIXTURE.read_bytes()[:-40],
            b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel><title>&x;</title></channel></rss>',
            b'<?xml version="1.0"?><!DOCTYPE rss SYSTEM "http://example.com/rss.dtd"><rss><channel/></rss>',
        ]
        for document in documents:
            with self.subTest(document=document[:40]), self.assertRaises(HzzFeedParseError):
                self.parser.parse(document)
