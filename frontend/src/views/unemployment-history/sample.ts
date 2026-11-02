import type { UnemploymentHistoryData } from './types'

/**
 * Shown outside a host, e.g. on the dev server: show_unemployment_history's result for Varaždinska, Istarska and
 * Ličko-senjska over 24 months, made by the server's own code from the local data of 2. 11. 2026. and edited to
 * leave a gap in Ličko-senjska's series: August and September 2025 are missing, so its change over the year is
 * unavailable. The months of 2026 are provisional.
 */
export function sample(): UnemploymentHistoryData {
  return {
    "counties": [
      {
        "code": "varazdinska",
        "name": "Varaždinska županija",
        "iso_code": "HR-05",
        "series": [
          {
            "period": "2024-10-01",
            "rate": 3,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-11-01",
            "rate": 2.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-12-01",
            "rate": 2.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-01-01",
            "rate": 3.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-02-01",
            "rate": 3.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-03-01",
            "rate": 3,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-04-01",
            "rate": 2.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-05-01",
            "rate": 2.7,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-06-01",
            "rate": 2.7,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-07-01",
            "rate": 2.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-08-01",
            "rate": 2.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-09-01",
            "rate": 2.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-10-01",
            "rate": 2.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-11-01",
            "rate": 2.6,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-12-01",
            "rate": 2.6,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-01-01",
            "rate": 2.8,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-02-01",
            "rate": 2.7,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-03-01",
            "rate": 2.5,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-04-01",
            "rate": 2.3,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-05-01",
            "rate": 2.2,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-06-01",
            "rate": 2.2,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-07-01",
            "rate": 2.3,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-08-01",
            "rate": 2.4,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-09-01",
            "rate": 2.3,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          }
        ],
        "latest": {
          "period": "2026-09-01",
          "rate": 2.3,
          "is_provisional": true,
          "unavailable_reason": null,
          "missing_reason": null
        },
        "same_month_previous_year": {
          "period": "2025-09-01",
          "rate": 2.9,
          "is_provisional": false,
          "unavailable_reason": null,
          "missing_reason": null
        },
        "change_pp": -0.6,
        "change_unavailable_reason": null,
        "short_name": "Varaždinska",
        "change_unavailable_label": null
      },
      {
        "code": "istarska",
        "name": "Istarska županija",
        "iso_code": "HR-18",
        "series": [
          {
            "period": "2024-10-01",
            "rate": 2.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-11-01",
            "rate": 2.6,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-12-01",
            "rate": 2.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-01-01",
            "rate": 3.3,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-02-01",
            "rate": 3.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-03-01",
            "rate": 2.7,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-04-01",
            "rate": 1.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-05-01",
            "rate": 1.3,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-06-01",
            "rate": 1.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-07-01",
            "rate": 1.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-08-01",
            "rate": 1.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-09-01",
            "rate": 1.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-10-01",
            "rate": 1.7,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-11-01",
            "rate": 2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-12-01",
            "rate": 2.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-01-01",
            "rate": 2.6,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-02-01",
            "rate": 2.5,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-03-01",
            "rate": 1.9,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-04-01",
            "rate": 1.4,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-05-01",
            "rate": 1.1,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-06-01",
            "rate": 1,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-07-01",
            "rate": 1.1,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-08-01",
            "rate": 1.1,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-09-01",
            "rate": 1.1,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          }
        ],
        "latest": {
          "period": "2026-09-01",
          "rate": 1.1,
          "is_provisional": true,
          "unavailable_reason": null,
          "missing_reason": null
        },
        "same_month_previous_year": {
          "period": "2025-09-01",
          "rate": 1.2,
          "is_provisional": false,
          "unavailable_reason": null,
          "missing_reason": null
        },
        "change_pp": -0.1,
        "change_unavailable_reason": null,
        "short_name": "Istarska",
        "change_unavailable_label": null
      },
      {
        "code": "licko-senjska",
        "name": "Ličko-senjska županija",
        "iso_code": "HR-09",
        "series": [
          {
            "period": "2024-10-01",
            "rate": 5,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-11-01",
            "rate": 5.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2024-12-01",
            "rate": 6.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-01-01",
            "rate": 6.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-02-01",
            "rate": 6.6,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-03-01",
            "rate": 6.1,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-04-01",
            "rate": 5.2,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-05-01",
            "rate": 4.4,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-06-01",
            "rate": 3.9,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-07-01",
            "rate": 3.7,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-08-01",
            "rate": null,
            "is_provisional": null,
            "unavailable_reason": "dzs_value_missing",
            "missing_reason": null
          },
          {
            "period": "2025-09-01",
            "rate": null,
            "is_provisional": null,
            "unavailable_reason": "dzs_value_missing",
            "missing_reason": null
          },
          {
            "period": "2025-10-01",
            "rate": 4.6,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-11-01",
            "rate": 5.3,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2025-12-01",
            "rate": 5.8,
            "is_provisional": false,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-01-01",
            "rate": 6.4,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-02-01",
            "rate": 5.8,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-03-01",
            "rate": 4.8,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-04-01",
            "rate": 4,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-05-01",
            "rate": 3.5,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-06-01",
            "rate": 3.2,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-07-01",
            "rate": 3.3,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-08-01",
            "rate": 3.2,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          },
          {
            "period": "2026-09-01",
            "rate": 3.4,
            "is_provisional": true,
            "unavailable_reason": null,
            "missing_reason": null
          }
        ],
        "latest": {
          "period": "2026-09-01",
          "rate": 3.4,
          "is_provisional": true,
          "unavailable_reason": null,
          "missing_reason": null
        },
        "same_month_previous_year": {
          "period": "2025-09-01",
          "rate": null,
          "is_provisional": null,
          "unavailable_reason": "dzs_value_missing",
          "missing_reason": null
        },
        "change_pp": null,
        "change_unavailable_reason": "dzs_value_missing",
        "short_name": "Ličko-senjska",
        "change_unavailable_label": "DZS nema stopu za rujan 2025."
      }
    ],
    "sex": "total",
    "months": 24,
    "first_period": "2024-10-01",
    "last_period": "2026-09-01",
    "unavailable_reason": null,
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
      "The rate is the registered unemployment rate: registered unemployed as a percentage of the active population, as DZS publishes it.",
      "Comparing with the same month a year earlier reduces the effect of seasonality, which is strong in coastal counties, but it is not a seasonal adjustment of the data.",
      "DZS values for months of 2026 are provisional and may be revised (is_provisional)."
    ],
    "title": "Stopa registrirane nezaposlenosti",
    "description": "Po mjesecima, listopad 2024. – rujan 2026.",
    "unavailable_label": null,
    "source_links": [
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
      "Stopa je udio registriranih nezaposlenih u aktivnom stanovništvu, kako je objavljuje DZS.",
      "Usporedba s istim mjesecom prethodne godine smanjuje utjecaj sezone, koji je jak u priobalnim županijama, ali nije sezonska prilagodba podataka.",
      "DZS podaci za mjesece 2026. su privremeni i mogu se revidirati."
    ]
  }
}
