import unittest
from datetime import date

from FOIHireloom.dto.job import ParsedJobDTO
from FOIHireloom.dto.job_sync import FilledCategoryDTO
from FOIHireloom.services import FeedCategoryVerifier
from FOIHireloom.services.concrete.feed_category import resolve_category

IT = "INFORMATIČKI, RAČUNALNI I STRUČNJACI ZA INTERNET"
LAW = "EKONOMISTI, PRAVNICI, ADMINISTRATIVCI"


def jobs(*categories: str | None) -> tuple[ParsedJobDTO, ...]:
    return tuple(
        ParsedJobDTO(
            source_job_id=str(number), canonical_url=f"https://example.com/{number}", title=None,
            description_raw="", description_text=None, published_on=date(2026, 10, 31), deadline_on=None,
            category=category, location_text=None, municipality=None, quality_flags=(), content_hash=str(number),
        )
        for number, category in enumerate(categories)
    )


class FeedCategoryVerifierTests(unittest.TestCase):
    def verify(self, *categories: str | None, min_examples: int = 3) -> tuple:
        mapping = FeedCategoryVerifier(min_examples).verify(jobs(*categories))
        return mapping.category, mapping.status, mapping.matching_examples, mapping.contradicting_examples

    def test_agreeing_examples_confirm_and_jobs_without_category_are_no_evidence(self) -> None:
        self.assertEqual(self.verify(IT, None, IT, None, IT), (IT, "confirmed", 3, 0))

    def test_too_few_examples_are_not_confirmed(self) -> None:
        self.assertEqual(self.verify(IT, IT, None), (IT, "too_few_examples", 2, 0))
        self.assertEqual(self.verify(IT, min_examples=1), (IT, "confirmed", 1, 0))
        self.assertEqual(self.verify(None, None), (None, "too_few_examples", 0, 0))
        self.assertEqual(self.verify(), (None, "too_few_examples", 0, 0))

    def test_any_other_category_contradicts_the_mapping(self) -> None:
        self.assertEqual(self.verify(IT, IT, IT, IT, LAW), (IT, "contradicted", 4, 1))
        self.assertEqual(self.verify(IT, LAW, min_examples=1), (LAW, "contradicted", 1, 1))

    def test_min_examples_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            FeedCategoryVerifier(0)


class ResolveCategoryTests(unittest.TestCase):
    def test_agreeing_mappings_fill_in_their_category_from_the_smallest_feed_id(self) -> None:
        self.assertEqual(resolve_category([(7, IT)]), (FilledCategoryDTO(category=IT, feed_id=7), False))
        self.assertEqual(resolve_category([(9, IT), (4, IT), (6, IT)]), (FilledCategoryDTO(category=IT, feed_id=4), False))

    def test_disagreeing_mappings_leave_the_category_unknown_and_conflicting(self) -> None:
        self.assertEqual(resolve_category([(4, IT), (5, LAW), (6, IT)]), (None, True))

    def test_no_mapping_leaves_the_category_unknown_without_a_conflict(self) -> None:
        self.assertEqual(resolve_category([]), (None, False))
