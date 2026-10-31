import type { JobsByCountyData } from './types'

const COUNTIES: [string, string, number, number][] = [
  ['Grad Zagreb', 'Grad Zagreb', 1325, 3093], ['Splitsko-dalmatinska županija', 'Splitsko-dalmatinska', 656, 1315],
  ['Zagrebačka županija', 'Zagrebačka', 607, 1266], ['Osječko-baranjska županija', 'Osječko-baranjska', 531, 992],
  ['Istarska županija', 'Istarska', 507, 1185], ['Primorsko-goranska županija', 'Primorsko-goranska', 498, 1040],
  ['Varaždinska županija', 'Varaždinska', 402, 801], ['Zadarska županija', 'Zadarska', 344, 690],
  ['Međimurska županija', 'Međimurska', 329, 610], ['Krapinsko-zagorska županija', 'Krapinsko-zagorska', 297, 540],
  ['Vukovarsko-srijemska županija', 'Vukovarsko-srijemska', 263, 480], ['Karlovačka županija', 'Karlovačka', 251, 470],
  ['Šibensko-kninska županija', 'Šibensko-kninska', 226, 420], ['Sisačko-moslavačka županija', 'Sisačko-moslavačka', 222, 400],
  ['Dubrovačko-neretvanska županija', 'Dubrovačko-neretvanska', 212, 390], ['Brodsko-posavska županija', 'Brodsko-posavska', 205, 380],
  ['Koprivničko-križevačka županija', 'Koprivničko-križevačka', 202, 370], ['Bjelovarsko-bilogorska županija', 'Bjelovarsko-bilogorska', 180, 330],
  ['Virovitičko-podravska županija', 'Virovitičko-podravska', 100, 190], ['Požeško-slavonska županija', 'Požeško-slavonska', 97, 180],
  ['Ličko-senjska županija', 'Ličko-senjska', 91, 170],
]

/** Shown outside a host, e.g. on the dev server; "?metric=workers_needed" ranks by workers sought. */
export function sample(): JobsByCountyData {
  const counties = COUNTIES.map(([name, short_name, jobs, workers_needed]) => ({
    name, short_name, jobs, workers_needed, share: Math.round((1000 * jobs) / 7676) / 10,
  }))
  const data: JobsByCountyData = {
    metric: 'jobs', title: 'Broj oglasa po županijama', description: 'Pregled s probnim podacima',
    total_jobs: 7676, total_workers_needed: 15922, top: 7, counties, coverage: { warning: null },
  }
  if (new URLSearchParams(location.search).get('metric') === 'workers_needed') {
    data.metric = 'workers_needed'
    data.title = 'Broj traženih radnika po županijama'
    counties.sort((a, b) => b.workers_needed - a.workers_needed)
  }
  return data
}
