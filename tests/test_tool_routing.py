import unittest

from evals.tool_routing import score


class ToolRoutingScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [
            {"id": "jobs", "intent": "jobs", "tool": "show_jobs"},
            {"id": "geography", "intent": "geography", "tool": "show_jobs_by_county"},
        ]

    def test_missing_records_and_empty_call_lists_do_not_pass(self) -> None:
        report = score(self.cases, [{"case_id": "jobs", "tool_calls": []}])
        self.assertEqual((report["cases"], report["recorded"], report["workflow_selected"]), (2, 1, 0))
        self.assertFalse(report["results"][1]["recorded"])

    def test_raw_only_calls_do_not_pass_and_detours_are_counted_separately(self) -> None:
        report = score(self.cases, [
            {"case_id": "jobs", "tool_calls": [{"name": "search_jobs", "arguments": {}}]},
            {"case_id": "geography", "tool_calls": [
                {"name": "job_market_stats", "arguments": {}},
                {"name": "connector__show_jobs_by_county", "arguments": {}},
            ]},
        ])
        self.assertEqual((report["workflow_selected"], report["raw_calls"]), (1, 1))

    def test_lookups_before_the_workflow_are_allowed(self) -> None:
        report = score(self.cases[:1], [{"case_id": "jobs", "tool_calls": [
            {"name": "list_regions", "arguments": {}},
            {"name": "show_jobs", "arguments": {"county": "istarska"}},
        ]}])
        self.assertEqual(report["workflow_selected"], 1)
        self.assertEqual(report["results"][0]["tool_calls"], 2)

    def test_bad_records_are_rejected(self) -> None:
        for records in (
            [{"case_id": "unknown", "tool_calls": []}],
            [{"case_id": "jobs", "tool_calls": []}] * 2,
            [{"case_id": "jobs", "tool_calls": [{"name": "show_jobs", "arguments": "{}"}]}],
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                score(self.cases, records)

    def test_empty_or_duplicate_reference_cases_are_rejected(self) -> None:
        for cases in ([], self.cases[:1] * 2):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                score(cases, [])
