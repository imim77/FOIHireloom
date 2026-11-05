# Tool routing evaluation

The cases reproduce ordinary Croatian and English requests without asking for
cards or charts. They cover job search, geographic demand, accommodation,
county comparison, unemployment history, selected ads, details and statistics.
`arguments` are reference values for human review, not an exact string oracle:
equivalent occupation stems, county names and omitted schema defaults are valid.

Run the cases separately in Claude and ChatGPT after restarting the MCP server
and refreshing each connector's cached catalog. Record client/model version,
date, server revision and whether the host respects `ui.visibility`. Compare the
same cases and settings before and after a description change. Use fresh chats
and include the supplied `context` where present; repeat runs to check variance.
Give the client only `context` and `prompt`, never the expected tool or arguments.

Save actual observed calls as a JSON array, with one record per case:

```json
[
  {
    "case_id": "jobs_waiter_town",
    "tool_calls": [
      {"name": "show_jobs", "arguments": {"query": "konobar", "place": "Pula"}}
    ]
  }
]
```

Keep every call, including lookups and retries. An empty `tool_calls` list records
a response without tools. Missing records count as failures; repeated or unknown
IDs are rejected. Run from the repository root:

```sh
.venv/bin/python evals/tool_routing.py /absolute/path/claude-calls.json
.venv/bin/python evals/tool_routing.py /absolute/path/chatgpt-calls.json
```

The report separates coverage, workflow selection, raw-data detours and call
count. It accepts preliminary lookups and different call orders. A correct
workflow anywhere in the trace passes routing, even if its execution fails;
this is **not** a score of end-to-end task completion. Raw detours are diagnostic
and do not fail the routing gate. Exit status is nonzero for missing cases or
incorrect workflow selection.

Review arguments and actual results separately: stated filters must survive,
unstated filters must not be invented, selected IDs retain their order, totals
must use the full matching set, and unknown accommodation must remain separate
from no accommodation. Confirm that the appropriate app renders in each host and
freshness warnings remain visible. Record these outcomes alongside routing.

Backend tests check published tool metadata, reference argument schemas and the
scorer. They do not run Claude or ChatGPT and cannot demonstrate model accuracy.
These 29 cases are an initial regression set; extend it with production failures,
ambiguous requests and longer conversations before treating scores as reliable.

The skill cases check that the user's technologies go into `skills`, with the
stated town preserved. Review the follow-up response separately: sparse direct
matches should prompt an offer of related jobs using an occupation or IT category
without `skills`. Related results must not be presented as explicit skill matches,
and the user's location and other conditions should survive. The routing score
alone does not establish this fallback behavior.
