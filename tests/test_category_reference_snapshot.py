import unittest
from pathlib import Path

from FOIHireloom.dto.category_snapshot import JOB_COLUMNS, CategorySnapshotDTO
from FOIHireloom.services.concrete.feed_category import resolve_category

FIXTURE = Path(__file__).parent / "fixtures" / "category_reference_snapshot.json"


class CategoryReferenceSnapshotTests(unittest.TestCase):
    """Recheck the saved category fill from its own inputs, without the database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = CategorySnapshotDTO.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
        cls.confirmed = {
            feed.id: feed.mapped_category for feed in cls.snapshot.feeds
            if feed.scope == "occupation" and feed.mapping_status == "confirmed"
        }

    def name(self, index: int | None) -> str | None:
        return None if index is None else self.snapshot.categories[index]

    def recompute(self) -> tuple[dict[str, tuple[str | None, str | None, int | None]], int]:
        """Every job's category, source and feed ID by the sync's rule, from the snapshot's inputs only,
        and the number of jobs left unknown by disagreeing mappings."""
        results, conflicting = {}, 0
        for source_job_id, description, feed_ids, *_ in self.snapshot.jobs:
            if description is not None:
                results[source_job_id] = (self.name(description), "description", None)
                continue
            filled, conflict = resolve_category([(feed_id, self.confirmed[feed_id])
                                                 for feed_id in feed_ids if feed_id in self.confirmed])
            results[source_job_id] = (filled.category, "feed", filled.feed_id) if filled else (None, None, None)
            conflicting += conflict
        return results, conflicting

    def test_rule_reproduces_every_stored_category(self) -> None:
        self.assertEqual(self.snapshot.job_columns, JOB_COLUMNS)
        stored = {row[0]: (self.name(row[3]), row[4], row[5]) for row in self.snapshot.jobs}
        self.assertEqual(len(stored), len(self.snapshot.jobs))
        recomputed, _ = self.recompute()
        mismatches = {job: (stored[job], result) for job, result in recomputed.items() if stored[job] != result}
        self.assertEqual(mismatches, {})

    def test_coverage_before_and_after_the_fill_matches_the_saved_numbers(self) -> None:
        results, conflicting = self.recompute()
        listed = len(results)
        before = sum(source == "description" for _, source, _ in results.values())
        after = sum(category is not None for category, _, _ in results.values())
        self.assertEqual(self.snapshot.coverage.model_dump(), {
            "listed": listed, "before": before, "after": after, "filled": after - before, "unknown": listed - after,
            "conflicting": conflicting,
        })
        self.assertGreaterEqual(after / listed, 0.80)

    def test_jobs_are_filled_only_from_their_own_confirmed_feeds(self) -> None:
        for source_job_id, _, feed_ids, category, source, feed_id in self.snapshot.jobs:
            if source == "feed":
                with self.subTest(source_job_id=source_job_id):
                    self.assertIn(feed_id, feed_ids)
                    self.assertEqual(self.confirmed.get(feed_id), self.name(category))
