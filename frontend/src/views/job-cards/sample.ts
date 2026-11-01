import type { JobCard, JobCardsData, JobConditions } from './types'

const job = (id: number, fields: Partial<JobCard>): JobCard => ({
  id, display_title: '', display_location: '', employer_name: null, category: null, category_source: null,
  county_name: null, work_place: null, published_on: null, deadline_on: null, deadline_passed: null,
  canonical_url: `https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra=${id}`, workers_needed: null,
  employment_type: null, working_hours: null, education: null, experience: null, accommodation: null,
  conditions: null, ...fields,
})

const conditions = (fields: Partial<JobConditions>): JobConditions => ({
  experience_months: null, trainee: null, contract: null, employment_tags: null, full_time: null, weekly_hours: null,
  education_levels: null, accommodation: null, schedule_tags: null, transport_allowance: null, unrecognised: [],
  ...fields,
})

/** Shown outside a host, e.g. on the dev server; dates count from 31. 10. 2026. */
export function sample(): JobCardsData {
  return {
    title: 'Oglasi za „kuhar”',
    description: 'Pregled s probnim podacima',
    today: '2026-10-31',
    filters: {
      query: 'kuhar', county: null, category: null, max_experience_months: null, contract: null, full_time: null,
      education: null, accommodation: null, employment_tags: null, place: null, include_expired: false, limit: 5,
      cursor: null,
    },
    next_cursor: 'sample',
    coverage: { warning: null },
    jobs: [
      job(1, {
        display_title: 'KUHAR/KUHARICA', employer_name: 'HOTEL ADRIATIC d.o.o.',
        category: 'UGOSTITELJI, RADNICI U TURIZMU', category_source: 'description', county_name: 'Istarska županija',
        work_place: 'ROVINJ-ROVIGNO, ISTARSKA ŽUPANIJA', published_on: '2026-10-29', deadline_on: '2026-11-12',
        deadline_passed: false, workers_needed: 3, employment_type: 'Na određeno; sezonski poslovi',
        working_hours: 'Puno radno vrijeme', education: 'Srednja škola 3 godine; Srednja škola 4 godine',
        experience: '1 godinu', accommodation: 'Zajednički smještaj',
        conditions: conditions({
          experience_months: 12, trainee: false, contract: 'fixed_term', employment_tags: ['seasonal'], full_time: true,
          education_levels: ['secondary_3', 'secondary_4'], accommodation: 'shared',
        }),
      }),
      job(2, {
        display_title: 'POMOĆNI KUHAR/POMOĆNA KUHARICA', employer_name: 'OSNOVNA ŠKOLA JAKOVLJE',
        county_name: 'Zagrebačka županija', work_place: 'JAKOVLJE, ZAGREBAČKA ŽUPANIJA', published_on: '2026-10-31',
        deadline_on: '2026-11-03', deadline_passed: false, workers_needed: 1,
        employment_type: 'Na neodređeno; upražnjeni poslovi', working_hours: '20 sati tjedno',
        education: 'Završena osnovna škola; Srednja škola 3 godine', experience: 'Nije važno',
        accommodation: 'Nema smještaja',
        conditions: conditions({
          experience_months: 0, trainee: false, contract: 'permanent', employment_tags: ['vacancy'], full_time: false,
          weekly_hours: 20, education_levels: ['primary', 'secondary_3'], accommodation: 'none',
        }),
      }),
      job(3, {
        display_title: 'KUHAR/KUHARICA U RESTORANU', employer_name: 'LOTTA, obrt za ugostiteljstvo, vl. Ana Horvat',
        // Filled in from the occupation feed, and with experience the normaliser did not recognise.
        category: 'UGOSTITELJI, RADNICI U TURIZMU', category_source: 'feed', county_name: 'Grad Zagreb',
        work_place: 'ZAGREB', published_on: '2026-10-20', deadline_on: '2026-11-19', deadline_passed: false,
        workers_needed: 2, employment_type: 'Na neodređeno; novootvoreni poslovi', working_hours: 'Puno radno vrijeme',
        education: 'Srednja škola 3 godine', experience: '2 godine u struci',
        conditions: conditions({
          contract: 'permanent', employment_tags: ['new_position'], full_time: true, education_levels: ['secondary_3'],
          unrecognised: ['experience', 'accommodation'],
        }),
      }),
      job(5, {
        display_title: 'POMOĆNI KUHAR/POMOĆNA KUHARICA - PRIPRAVNIK', employer_name: 'DJEČJI VRTIĆ MASLAČAK',
        category: 'UGOSTITELJI, RADNICI U TURIZMU', category_source: 'description',
        county_name: 'Osječko-baranjska županija', work_place: 'OSIJEK, OSJEČKO-BARANJSKA ŽUPANIJA', published_on: '2026-10-30', deadline_on: '2026-11-07',
        deadline_passed: false, workers_needed: 1, employment_type: 'Na određeno; pripravnik',
        working_hours: '30 sati tjedno', education: 'Srednja škola 3 godine', experience: 'Traži se pripravnik',
        accommodation: 'Obiteljski stan',
        conditions: conditions({
          experience_months: 0, trainee: true, contract: 'fixed_term', employment_tags: ['trainee'], full_time: false,
          weekly_hours: 30, education_levels: ['secondary_3'], accommodation: 'family',
        }),
      }),
      job(4, {
        display_title: 'Oglas HZZ 4521', county_name: 'Ličko-senjska županija',
        display_location: 'Ličko-senjska županija (mjesto rada nije navedeno)', published_on: '2026-10-27',
      }),
    ],
  }
}
