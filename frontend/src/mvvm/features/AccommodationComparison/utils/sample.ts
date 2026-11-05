import type { AccommodationComparisonData } from '../types'

// Preview outside a host: the server's real local data for Varaždinska and query kuhar, 2 November 2026.
export function sample(): AccommodationComparisonData {
  return {
  "title": "Smještaj u oglasima za posao",
  "description": "Upit „kuhar” · Varaždinska županija · aktivni oglasi na dan 02. 11. 2026.",
  "today": "2026-11-02",
  "total_jobs": 10,
  "known_jobs": 9,
  "groups": [
    {
      "key": "offered",
      "label": "Nudi smještaj",
      "jobs": 2,
      "share": 20.0
    },
    {
      "key": "not_offered",
      "label": "Bez smještaja",
      "jobs": 7,
      "share": 70.0
    },
    {
      "key": "unknown",
      "label": "Podatak nije poznat",
      "jobs": 1,
      "share": 10.0
    }
  ],
  "accommodation_types": [
    {
      "name": "none",
      "jobs": 7,
      "workers_needed": 11
    },
    {
      "name": "shared",
      "jobs": 1,
      "workers_needed": 1
    },
    {
      "name": "single",
      "jobs": 1,
      "workers_needed": 1
    }
  ],
  "coverage": {
    "data_status": "stale",
    "data_as_of": "2026-10-31T19:03:39.958173Z",
    "stale_after_hours": 6.0,
    "affected_regions": [
      {
        "code": "varazdinska",
        "name": "Varaždinska županija",
        "data_status": "stale",
        "last_success_at": "2026-10-31T19:03:39.958173Z"
      }
    ],
    "warning": "Job data for the requested county was not updated in the last 6 hours or is unavailable: Varaždinska županija (last updated 2026-10-31 19:03 UTC). Results there may be outdated or incomplete; a job missing from them may still be advertised by HZZ."
  },
  "active_filters": [
    {
      "argument": "county",
      "label": "Varaždinska županija"
    }
  ],
  "coverage_note": "Varaždinska županija: podaci su stariji od 6 sati, pa rezultat možda nije potpun.",
  "unknown_conditions": {},
  "unknown_total": 0,
  "unknown_note": null,
  "view_notes": [
    "Broje se oglasi, a ne traženi radnici. Jedan oglas može tražiti više radnika.",
    "Nepoznat podatak ne znači da smještaj nije ponuđen. Kad su prikazane sve skupine, udjeli se odnose na sve odabrane oglase.",
    "Upit pretražuje naslov i sadržaj oglasa; nije stroga klasifikacija zanimanja."
  ]
}
}
