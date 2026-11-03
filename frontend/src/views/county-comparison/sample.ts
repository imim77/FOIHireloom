import type { CountyComparisonData } from './types'

/**
 * Shown outside a host, e.g. on the dev server: show_county_comparison's result for Varaždinska, Međimurska and
 * Ličko-senjska with the query "kuhar" and full time, made by the server's own code from the local data of
 * 2. 11. 2026. and edited to show the unavailable cases: DZS has no count of Međimurska's unemployed for the month
 * (dzs_value_missing), and no active ad of Ličko-senjska states the number of workers (no_known_workers).
 * September 2026's active population and rate are provisional; the HZZ data is stale, so the coverage note shows.
 */
export function sample(): CountyComparisonData {
  return {
    "counties": [
      {
        "code": "varazdinska",
        "name": "Varaždinska županija",
        "iso_code": "HR-05",
        "hzz_data_status": "stale",
        "hzz_last_success_at": "2026-10-31T19:03:39.958173Z",
        "filtered_jobs": {
          "jobs": 9,
          "workers_needed": 13,
          "workers_needed_coverage": {
            "part": 9,
            "whole": 9,
            "percent": 100
          },
          "permanent_share": {
            "part": 4,
            "whole": 9,
            "percent": 44.4
          },
          "contract_coverage": {
            "part": 9,
            "whole": 9,
            "percent": 100
          },
          "closing_soon": 4
        },
        "all_active_jobs": {
          "jobs": 404,
          "workers_needed": 695,
          "workers_needed_coverage": {
            "part": 377,
            "whole": 404,
            "percent": 93.3
          },
          "permanent_share": {
            "part": 211,
            "whole": 377,
            "percent": 56
          },
          "contract_coverage": {
            "part": 377,
            "whole": 404,
            "percent": 93.3
          },
          "closing_soon": 126
        },
        "unemployed": {
          "indicator": "unemployed",
          "value": 1721,
          "period": "2026-09-01",
          "is_provisional": false,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "active_population": {
          "indicator": "active_population",
          "value": 73662,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployment_rate": {
          "indicator": "unemployment_rate",
          "value": 2.3,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployed_per_worker": {
          "value": 2.5,
          "numerator": 1721,
          "denominator": 695,
          "dzs_period": "2026-09-01",
          "is_provisional": false,
          "unavailable_reason": null,
          "unavailable_label": null
        },
        "jobs_per_1000_active": {
          "value": 5.5,
          "numerator": 404,
          "denominator": 73662,
          "dzs_period": "2026-09-01",
          "is_provisional": true,
          "unavailable_reason": null,
          "unavailable_label": null
        },
        "short_name": "Varaždinska"
      },
      {
        "code": "medimurska",
        "name": "Međimurska županija",
        "iso_code": "HR-20",
        "hzz_data_status": "stale",
        "hzz_last_success_at": "2026-10-31T19:03:38.520758Z",
        "filtered_jobs": {
          "jobs": 6,
          "workers_needed": 7,
          "workers_needed_coverage": {
            "part": 6,
            "whole": 6,
            "percent": 100
          },
          "permanent_share": {
            "part": 1,
            "whole": 6,
            "percent": 16.7
          },
          "contract_coverage": {
            "part": 6,
            "whole": 6,
            "percent": 100
          },
          "closing_soon": 2
        },
        "all_active_jobs": {
          "jobs": 231,
          "workers_needed": 415,
          "workers_needed_coverage": {
            "part": 217,
            "whole": 231,
            "percent": 93.9
          },
          "permanent_share": {
            "part": 138,
            "whole": 217,
            "percent": 63.6
          },
          "contract_coverage": {
            "part": 217,
            "whole": 231,
            "percent": 93.9
          },
          "closing_soon": 70
        },
        "unemployed": {
          "indicator": "unemployed",
          "value": null,
          "period": "2026-09-01",
          "is_provisional": null,
          "source": null,
          "unavailable_reason": "dzs_value_missing",
          "missing_reason": "not_available",
          "unavailable_label": "DZS nema podatak za rujan 2026."
        },
        "active_population": {
          "indicator": "active_population",
          "value": 45211,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployment_rate": {
          "indicator": "unemployment_rate",
          "value": 3.2,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployed_per_worker": {
          "value": null,
          "numerator": null,
          "denominator": 415,
          "dzs_period": "2026-09-01",
          "is_provisional": null,
          "unavailable_reason": "dzs_value_missing",
          "unavailable_label": "DZS nema podatak o nezaposlenima za rujan 2026."
        },
        "jobs_per_1000_active": {
          "value": 5.1,
          "numerator": 231,
          "denominator": 45211,
          "dzs_period": "2026-09-01",
          "is_provisional": true,
          "unavailable_reason": null,
          "unavailable_label": null
        },
        "short_name": "Međimurska"
      },
      {
        "code": "licko-senjska",
        "name": "Ličko-senjska županija",
        "iso_code": "HR-09",
        "hzz_data_status": "stale",
        "hzz_last_success_at": "2026-10-31T19:03:38.360718Z",
        "filtered_jobs": {
          "jobs": 1,
          "workers_needed": 0,
          "workers_needed_coverage": {
            "part": 0,
            "whole": 1,
            "percent": 0
          },
          "permanent_share": {
            "part": 0,
            "whole": 1,
            "percent": 0
          },
          "contract_coverage": {
            "part": 1,
            "whole": 1,
            "percent": 100
          },
          "closing_soon": 0
        },
        "all_active_jobs": {
          "jobs": 79,
          "workers_needed": 0,
          "workers_needed_coverage": {
            "part": 0,
            "whole": 79,
            "percent": 0
          },
          "permanent_share": {
            "part": 45,
            "whole": 64,
            "percent": 70.3
          },
          "contract_coverage": {
            "part": 64,
            "whole": 79,
            "percent": 81
          },
          "closing_soon": 46
        },
        "unemployed": {
          "indicator": "unemployed",
          "value": 673,
          "period": "2026-09-01",
          "is_provisional": false,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "active_population": {
          "indicator": "active_population",
          "value": 20040,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployment_rate": {
          "indicator": "unemployment_rate",
          "value": 3.4,
          "period": "2026-09-01",
          "is_provisional": true,
          "source": "t1",
          "unavailable_reason": null,
          "missing_reason": null,
          "unavailable_label": null
        },
        "unemployed_per_worker": {
          "value": null,
          "numerator": 673,
          "denominator": null,
          "dzs_period": "2026-09-01",
          "is_provisional": false,
          "unavailable_reason": "no_known_workers",
          "unavailable_label": "nijedan aktivni oglas ne navodi broj traženih radnika"
        },
        "jobs_per_1000_active": {
          "value": 3.9,
          "numerator": 79,
          "denominator": 20040,
          "dzs_period": "2026-09-01",
          "is_provisional": true,
          "unavailable_reason": null,
          "unavailable_label": null
        },
        "short_name": "Ličko-senjska"
      }
    ],
    "today": "2026-11-02",
    "window_days": 7,
    "filters": {
      "max_experience_months": null,
      "contract": null,
      "full_time": true,
      "education": null,
      "accommodation": null,
      "employment_tags": null,
      "place": null,
      "query": "kuhar",
      "category": null,
      "include_expired": false
    },
    "active_filters": [
      {
        "argument": "full_time",
        "label": "puno radno vrijeme"
      }
    ],
    "requested_period": null,
    "dzs_periods": [
      {
        "indicator": "unemployed",
        "period": "2026-09-01",
        "requested": false,
        "unavailable_reason": null
      },
      {
        "indicator": "active_population",
        "period": "2026-09-01",
        "requested": false,
        "unavailable_reason": null
      },
      {
        "indicator": "unemployment_rate",
        "period": "2026-09-01",
        "requested": false,
        "unavailable_reason": null
      }
    ],
    "hzz_coverage": {
      "data_status": "stale",
      "data_as_of": "2026-10-31T19:03:38.360718Z",
      "stale_after_hours": 6.0,
      "affected_regions": [
        {
          "code": "varazdinska",
          "name": "Varaždinska županija",
          "data_status": "stale",
          "last_success_at": "2026-10-31T19:03:39.958173Z"
        },
        {
          "code": "medimurska",
          "name": "Međimurska županija",
          "data_status": "stale",
          "last_success_at": "2026-10-31T19:03:38.520758Z"
        },
        {
          "code": "licko-senjska",
          "name": "Ličko-senjska županija",
          "data_status": "stale",
          "last_success_at": "2026-10-31T19:03:38.360718Z"
        }
      ],
      "warning": "Job data for 3 of 3 counties was not updated in the last 6 hours or is unavailable: Varaždinska županija (last updated 2026-10-31 19:03 UTC), Međimurska županija (last updated 2026-10-31 19:03 UTC), Ličko-senjska županija (last updated 2026-10-31 19:03 UTC). Results there may be outdated or incomplete; a job missing from them may still be advertised by HZZ."
    },
    "dzs": {
      "import_id": 2,
      "finished_at": "2026-11-02T14:21:34.058715Z",
      "files": [
        {
          "role": "t1",
          "location": "https://podaci.dzs.hr/media/ulbjlyex/rad-2026-2-6_3_tablice-hr.xlsx",
          "fetched_at": "2026-11-02T14:21:31.982594Z",
          "last_modified": "2026-10-21T13:36:44Z"
        },
        {
          "role": "workbook",
          "location": "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx",
          "fetched_at": "2026-11-02T14:21:33.863514Z",
          "last_modified": "2026-10-28T10:00:47Z"
        }
      ]
    },
    "sources": [
      {
        "name": "HZZ",
        "url": "https://burzarada.hzz.hr",
        "description": "Job advertisements of the Croatian Employment Service (HZZ), from its county RSS feeds and job pages, as stored at the last successful sync."
      },
      {
        "name": "DZS release table T1",
        "url": "https://podaci.dzs.hr/media/ulbjlyex/rad-2026-2-6_3_tablice-hr.xlsx",
        "description": "Exact registered unemployed, active population and unemployment rate by county for the release's months."
      },
      {
        "name": "DZS county workbook",
        "url": "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx",
        "description": "Monthly active population (sheet 9.4.13) and registered unemployment rate (sheet 9.4.14) by county since 2020."
      }
    ],
    "notes": [
      "These indicators describe HZZ job advertisements and registered unemployment as DZS publishes it, not the whole labour market, and say nothing about anyone's personal chance of finding a job.",
      "unemployed_per_worker and jobs_per_1000_active describe each county as a whole: they use all its active HZZ ads (all_active_jobs), never the job filters, which apply to filtered_jobs only. Do not divide the unemployed by the ads of one occupation.",
      "workers_needed counts only the ads whose HZZ page states it (workers_needed_coverage), so unemployed_per_worker is higher when fewer ads state it.",
      "HZZ counts are as of the last HZZ sync (hzz_coverage.data_as_of), DZS values are for a past reference month (dzs_periods); the two refer to different moments.",
      "DZS values for months of 2026 are provisional and may be revised (is_provisional)."
    ],
    "title": "Usporedba županija",
    "description": "Upit „kuhar” · aktivni oglasi na dan 02. 11. 2026.",
    "coverage_note": "Podaci su stariji od 6 sati za 3 županije (Varaždinska županija, Međimurska županija i Ličko-senjska županija), pa rezultat možda nije potpun.",
    "source_links": [
      {
        "label": "HZZ, burza rada (oglasi)",
        "url": "https://burzarada.hzz.hr"
      },
      {
        "label": "DZS, priopćenje o zaposlenosti (tablica T1)",
        "url": "https://podaci.dzs.hr/media/ulbjlyex/rad-2026-2-6_3_tablice-hr.xlsx"
      },
      {
        "label": "DZS, pregled po županijama (listovi 9.4.13 i 9.4.14)",
        "url": "https://podaci.dzs.hr/media/xpkfrkth/zaposlenost-i-place-pregled-po-zupanijama.xlsx"
      }
    ],
    "view_notes": [
      "Traženi radnici zbrajaju se samo iz oglasa koji navode njihov broj, pa je broj nezaposlenih na jednog traženog radnika veći kad manje oglasa navodi broj.",
      "HZZ oglasi su stanje u trenutku provjere, a DZS podaci za prošli referentni mjesec.",
      "DZS podaci za mjesece 2026. su privremeni i mogu se revidirati."
    ],
    "disclaimer": "Pokazatelji opisuju HZZ oglase i registriranu nezaposlenost, a ne cijelo tržište rada ni osobnu vjerojatnost zaposlenja."
  }
}
