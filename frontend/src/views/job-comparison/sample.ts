import type { JobComparisonData } from './types'

/**
 * Shown outside a host, e.g. on the dev server: show_job_comparison's result for three jobs on 1. 11. 2026., made by
 * the server's own comparison code. The first job's page is read and states no accommodation; the second's category
 * comes from an HZZ occupation feed, its deadline has passed, it states a type of employment but no contract and an
 * accommodation that is not recognised; the third's page has not been read, so all its values are unknown.
 */
export function sample(): JobComparisonData {
  return {
    "today": "2026-11-01",
    "jobs": [
      {
        "id": 101,
        "display_title": "KUHAR/KUHARICA",
        "employer_name": "HOTEL ADRIATIC d.o.o.",
        "county_name": "Istarska županija",
        "display_location": "ROVINJ-ROVIGNO, ISTARSKA ŽUPANIJA",
        "canonical_url": "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=101",
        "details_status": "fetched",
        "category": "UGOSTITELJI, RADNICI U TURIZMU",
        "category_source": "description",
        "published_on": "2026-10-29",
        "deadline_on": "2026-11-29",
        "deadline_passed": false,
        "conditions": {
          "experience_months": 12,
          "trainee": false,
          "contract": "permanent",
          "employment_tags": [
            "new_position"
          ],
          "full_time": true,
          "weekly_hours": null,
          "education_levels": [
            "secondary_3",
            "secondary_4"
          ],
          "accommodation": null,
          "schedule_tags": null,
          "transport_allowance": null,
          "unrecognised": []
        }
      },
      {
        "id": 102,
        "display_title": "POMOĆNI KUHAR/POMOĆNA KUHARICA",
        "employer_name": "RESTORAN MASLINA j.d.o.o.",
        "county_name": "Istarska županija",
        "display_location": "PULA-POLA, ISTARSKA ŽUPANIJA",
        "canonical_url": "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=102",
        "details_status": "fetched",
        "category": "UGOSTITELJI, RADNICI U TURIZMU",
        "category_source": "feed",
        "published_on": "2026-10-15",
        "deadline_on": "2026-10-31",
        "deadline_passed": true,
        "conditions": {
          "experience_months": 0,
          "trainee": false,
          "contract": null,
          "employment_tags": [
            "new_position"
          ],
          "full_time": false,
          "weekly_hours": 20,
          "education_levels": [
            "secondary_3"
          ],
          "accommodation": null,
          "schedule_tags": null,
          "transport_allowance": null,
          "unrecognised": [
            "accommodation"
          ]
        }
      },
      {
        "id": 103,
        "display_title": "KONOBAR/KONOBARICA",
        "employer_name": null,
        "county_name": "Primorsko-goranska županija",
        "display_location": "OPATIJA, Primorsko-goranska županija",
        "canonical_url": "https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=103",
        "details_status": "pending",
        "category": null,
        "category_source": null,
        "published_on": "2026-10-30",
        "deadline_on": "2026-11-03",
        "deadline_passed": false,
        "conditions": null
      }
    ],
    "rows": [
      {
        "aspect": "experience",
        "differs": true,
        "condition": 0,
        "cells": [
          {
            "job_id": 101,
            "value": "12 months",
            "evidence": "1 godinu",
            "verdict": "no_match",
            "reason": "the job asks for 12 months of experience; you have none",
            "unknown_reason": null,
            "text": "1 godinu",
            "note": null,
            "verdict_label": "ne odgovara"
          },
          {
            "job_id": 102,
            "value": "no experience required",
            "evidence": "Nije važno",
            "verdict": "match",
            "reason": "the job asks for no experience",
            "unknown_reason": null,
            "text": "Nije važno",
            "note": null,
            "verdict_label": "odgovara"
          },
          {
            "job_id": 103,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job's HZZ page has not been read yet",
            "unknown_reason": "page_not_read",
            "text": "stranica oglasa još nije pročitana",
            "note": null,
            "verdict_label": "nije poznato"
          }
        ],
        "name": "Iskustvo",
        "condition_label": "bez iskustva"
      },
      {
        "aspect": "education",
        "differs": true,
        "condition": "secondary_3",
        "cells": [
          {
            "job_id": 101,
            "value": "secondary school (3 years) or secondary school (4 years)",
            "evidence": "Srednja škola 3 godine; Srednja škola 4 godine",
            "verdict": "match",
            "reason": "the job page lists secondary school (3 years) among the accepted levels",
            "unknown_reason": null,
            "text": "Srednja škola 3 godine; Srednja škola 4 godine",
            "note": null,
            "verdict_label": "odgovara"
          },
          {
            "job_id": 102,
            "value": "secondary school (3 years)",
            "evidence": "Srednja škola 3 godine",
            "verdict": "match",
            "reason": "the job page lists secondary school (3 years) among the accepted levels",
            "unknown_reason": null,
            "text": "Srednja škola 3 godine",
            "note": null,
            "verdict_label": "odgovara"
          },
          {
            "job_id": 103,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job's HZZ page has not been read yet",
            "unknown_reason": "page_not_read",
            "text": "stranica oglasa još nije pročitana",
            "note": null,
            "verdict_label": "nije poznato"
          }
        ],
        "name": "Obrazovanje",
        "condition_label": "srednja škola (3 god.)"
      },
      {
        "aspect": "contract",
        "differs": true,
        "condition": "permanent",
        "cells": [
          {
            "job_id": 101,
            "value": "permanent",
            "evidence": "Na neodređeno; Novootvoreni poslovi",
            "verdict": "match",
            "reason": "the job's contract is permanent, as you want",
            "unknown_reason": null,
            "text": "Na neodređeno; Novootvoreni poslovi",
            "note": null,
            "verdict_label": "odgovara"
          },
          {
            "job_id": 102,
            "value": null,
            "evidence": "Novootvoreni poslovi",
            "verdict": "unknown",
            "reason": "the job page states the type of employment but not the contract",
            "unknown_reason": "contract_not_stated",
            "text": "Novootvoreni poslovi",
            "note": "oglas navodi vrstu zaposlenja, ali ne i ugovor",
            "verdict_label": "nije poznato"
          },
          {
            "job_id": 103,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job's HZZ page has not been read yet",
            "unknown_reason": "page_not_read",
            "text": "stranica oglasa još nije pročitana",
            "note": null,
            "verdict_label": "nije poznato"
          }
        ],
        "name": "Ugovor",
        "condition_label": "na neodređeno"
      },
      {
        "aspect": "working_time",
        "differs": true,
        "condition": true,
        "cells": [
          {
            "job_id": 101,
            "value": "full time",
            "evidence": "Puno radno vrijeme",
            "verdict": "match",
            "reason": "the job is full time, as you want",
            "unknown_reason": null,
            "text": "Puno radno vrijeme",
            "note": null,
            "verdict_label": "odgovara"
          },
          {
            "job_id": 102,
            "value": "part time, 20 h a week",
            "evidence": "20 sati tjedno",
            "verdict": "no_match",
            "reason": "the job is part time (20 h a week); you want full time",
            "unknown_reason": null,
            "text": "20 sati tjedno",
            "note": null,
            "verdict_label": "ne odgovara"
          },
          {
            "job_id": 103,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job's HZZ page has not been read yet",
            "unknown_reason": "page_not_read",
            "text": "stranica oglasa još nije pročitana",
            "note": null,
            "verdict_label": "nije poznato"
          }
        ],
        "name": "Radno vrijeme",
        "condition_label": "puno radno vrijeme"
      },
      {
        "aspect": "accommodation",
        "differs": false,
        "condition": true,
        "cells": [
          {
            "job_id": 101,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job page does not state the accommodation",
            "unknown_reason": "not_stated",
            "text": "oglas ne navodi",
            "note": null,
            "verdict_label": "nije poznato"
          },
          {
            "job_id": 102,
            "value": null,
            "evidence": "Smještaj po dogovoru",
            "verdict": "unknown",
            "reason": "the job page states the accommodation in a way that could not be read",
            "unknown_reason": "unreadable",
            "text": "Smještaj po dogovoru",
            "note": "nije prepoznato",
            "verdict_label": "nije poznato"
          },
          {
            "job_id": 103,
            "value": null,
            "evidence": null,
            "verdict": "unknown",
            "reason": "the job's HZZ page has not been read yet",
            "unknown_reason": "page_not_read",
            "text": "stranica oglasa još nije pročitana",
            "note": null,
            "verdict_label": "nije poznato"
          }
        ],
        "name": "Smještaj",
        "condition_label": "uz smještaj"
      },
      {
        "aspect": "deadline",
        "differs": true,
        "condition": null,
        "cells": [
          {
            "job_id": 101,
            "value": "open until 2026-11-29 (28 days left)",
            "evidence": "2026-11-29, from the job page",
            "verdict": null,
            "reason": null,
            "unknown_reason": null,
            "text": "do 29. 11. 2026. (još 28 dana)",
            "note": null,
            "verdict_label": null
          },
          {
            "job_id": 102,
            "value": "expired on 2026-10-31",
            "evidence": "2026-10-31, from the job page",
            "verdict": null,
            "reason": null,
            "unknown_reason": null,
            "text": "istekao 31. 10. 2026.",
            "note": null,
            "verdict_label": null
          },
          {
            "job_id": 103,
            "value": "open until 2026-11-03 (2 days left)",
            "evidence": "2026-11-03, from the HZZ feed",
            "verdict": null,
            "reason": null,
            "unknown_reason": null,
            "text": "do 03. 11. 2026. (još 2 dana)",
            "note": null,
            "verdict_label": null
          }
        ],
        "name": "Rok prijave",
        "condition_label": null
      }
    ],
    "conditions": {
      "max_experience_months": 0,
      "contract": "permanent",
      "full_time": true,
      "education": "secondary_3",
      "accommodation": true
    },
    "title": "Usporedba oglasa",
    "description": "Vaši uvjeti: bez iskustva · na neodređeno · puno radno vrijeme · obrazovanje: srednja škola (3 god.) · uz smještaj",
    "disclaimer": "Usporedba pokazuje samo što oglasi navode, ne i hoće li vas poslodavac odabrati.",
    "unknown_note": "Za 8 uvjeta podatak u oglasima nije poznat; to ne znači da su ispunjeni."
  }
}
