"""Score recorded client calls without making model requests or accessing job data."""

import argparse
import json
from pathlib import Path

CASES = Path(__file__).with_name("tool-routing-cases.json")
RAW_TOOLS = {"search_jobs", "compare_jobs", "compare_counties", "unemployment_history", "forecast_labour_market"}


def score(cases: list[dict], records: list[dict]) -> dict:
    """Score workflow selection; argument semantics and rendered results need review."""
    expected = {case["id"]: case for case in cases}
    if not expected or len(expected) != len(cases):
        raise ValueError("Cases must have unique IDs and must not be empty.")
    observed = {}
    for record in records:
        case_id = record["case_id"]
        if case_id not in expected or case_id in observed:
            raise ValueError(f"Unknown or repeated case ID: {case_id}")
        calls = record["tool_calls"]
        if not isinstance(calls, list) or any(
            not isinstance(call, dict) or not isinstance(call.get("name"), str)
            or not isinstance(call.get("arguments"), dict) for call in calls
        ):
            raise ValueError(f"{case_id}: tool_calls must contain names and argument objects.")
        observed[case_id] = calls

    results = []
    for case_id, case in expected.items():
        calls = observed.get(case_id, [])
        # Connector prefixes vary; preserve the actual registered tool name.
        names = [call["name"].rsplit("__", 1)[-1] for call in calls]
        results.append({
            "case_id": case_id,
            "intent": case["intent"],
            "recorded": case_id in observed,
            "workflow_selected": case["tool"] in names,
            "raw_calls": sum(name in RAW_TOOLS for name in names),
            "tool_calls": len(calls),
        })
    return {
        "cases": len(cases),
        "recorded": len(observed),
        "workflow_selected": sum(result["workflow_selected"] for result in results),
        "raw_calls": sum(result["raw_calls"] for result in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSON array of recorded client calls")
    args = parser.parse_args()
    try:
        report = score(json.loads(CASES.read_text()), json.loads(args.records.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["recorded"] != report["cases"] or report["workflow_selected"] != report["cases"])


if __name__ == "__main__":
    raise SystemExit(main())
