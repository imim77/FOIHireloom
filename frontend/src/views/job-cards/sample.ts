import type { JobCard, JobCardsData } from './types'

const job = (id: number, fields: Partial<JobCard>): JobCard => ({
  id, display_title: '', display_location: '', employer_name: null, category: null, county_name: null,
  work_place: null, published_on: null, deadline_on: null, deadline_passed: null,
  canonical_url: `https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=${id}`, workers_needed: null,
  employment_type: null, working_hours: null, education: null, experience: null, accommodation: null, ...fields,
})

/** Shown outside a host, e.g. on the dev server; dates count from 31. 10. 2026. */
export function sample(): JobCardsData {
  return {
    title: 'Oglasi za „kuhar”',
    description: 'Pregled s probnim podacima',
    today: '2026-10-31',
    filters: { query: 'kuhar', county: null, category: null, include_expired: false, limit: 4 },
    next_cursor: 'sample',
    coverage: { warning: null },
    jobs: [
      job(1, {
        display_title: 'KUHAR/KUHARICA', employer_name: 'HOTEL ADRIATIC d.o.o.',
        category: 'UGOSTITELJI, RADNICI U TURIZMU', county_name: 'Istarska županija',
        work_place: 'ROVINJ-ROVIGNO, ISTARSKA ŽUPANIJA', published_on: '2026-10-29', deadline_on: '2026-11-12',
        deadline_passed: false, workers_needed: 3, employment_type: 'Na određeno; sezonski poslovi',
        working_hours: 'Puno radno vrijeme', education: 'Srednja škola 3 godine; Srednja škola 4 godine',
        experience: '1 godinu', accommodation: 'Zajednički smještaj',
      }),
      job(2, {
        display_title: 'POMOĆNI KUHAR/POMOĆNA KUHARICA', employer_name: 'OSNOVNA ŠKOLA JAKOVLJE',
        county_name: 'Zagrebačka županija', work_place: 'JAKOVLJE, ZAGREBAČKA ŽUPANIJA', published_on: '2026-10-31',
        deadline_on: '2026-11-03', deadline_passed: false, workers_needed: 1,
        employment_type: 'Na neodređeno; upražnjeni poslovi', working_hours: '20 sati tjedno',
        education: 'Završena osnovna škola; Srednja škola 3 godine', experience: 'Nije važno',
        accommodation: 'Nema smještaja',
      }),
      job(3, {
        display_title: 'KUHAR/KUHARICA U RESTORANU', employer_name: 'LOTTA, obrt za ugostiteljstvo, vl. Ana Horvat',
        category: 'UGOSTITELJI, RADNICI U TURIZMU', county_name: 'Grad Zagreb', work_place: 'ZAGREB',
        published_on: '2026-10-20', deadline_on: '2026-11-19', deadline_passed: false, workers_needed: 2,
        employment_type: 'Na neodređeno; novootvoreni poslovi', working_hours: 'Puno radno vrijeme',
        education: 'Srednja škola 3 godine', experience: '2 godine',
      }),
      job(4, {
        display_title: 'Oglas HZZ 4521', county_name: 'Ličko-senjska županija',
        display_location: 'Ličko-senjska županija (mjesto rada nije navedeno)', published_on: '2026-10-27',
      }),
    ],
  }
}
