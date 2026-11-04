import { formatAds, formatDecimal, formatInteger, formatMonth, formatRate, formatShare, plural }
  from '../../shared/format'
import type { ComparedCounty, CountyComparisonData, DzsValue, Indicator } from './types'

// What a cell shows: its value, or why there is none, with a quieter note under it.
interface CellView {
  text: string
  note?: string | null
  unavailable?: boolean
  provisional?: boolean
  // For the highest and lowest of a row; null when unavailable.
  value?: number | null
}

interface RowView {
  key: string
  name: string
  cell: (county: ComparedCounty, data: CountyComparisonData) => CellView
  // Mark the highest and the lowest value of the row.
  extremes?: boolean
}

interface Section {
  key: 'hzz' | 'dzs' | 'indicators'
  name: string
  hint: string
  rows: RowView[]
}

// A county none of whose HZZ feeds was ever loaded: its 0 ads are not known to be 0.
export const noHzz = (county: ComparedCounty) => county.hzz_last_success_at === null
const NO_HZZ: CellView = { text: 'nije poznato', note: 'HZZ oglasi za županiju nisu učitani', unavailable: true }

/** "u 9 od 10 oglasa (90,0 %)" */
function coverage(part: number, whole: number, percent: number | null): string {
  return `${formatInteger(part)} od ${formatAds(whole)}${percent === null ? '' : ` (${formatShare(percent)})`}`
}

function dzsCell(value: DzsValue, format: (value: number) => string): CellView {
  if (value.value === null) {
    return { text: 'podatak nije dostupan', note: value.unavailable_label, unavailable: true, value: null }
  }
  return { text: format(value.value), note: value.period ? formatMonth(value.period) : null,
    provisional: Boolean(value.is_provisional), value: value.value }
}

function indicatorCell(indicator: Indicator, note: string): CellView {
  if (indicator.value === null) {
    return { text: 'pokazatelj nije dostupan', note: indicator.unavailable_label, unavailable: true, value: null }
  }
  const month = indicator.dzs_period ? ` · ${formatMonth(indicator.dzs_period)}` : ''
  return { text: formatDecimal(indicator.value), note: note + month, provisional: Boolean(indicator.is_provisional),
    value: indicator.value }
}

export const SECTIONS: Section[] = [
  {
    key: 'hzz', name: 'Oglasi prema filtrima', hint: 'HZZ, oglasi koji odgovaraju filtrima',
    rows: [
      {
        key: 'jobs', name: 'Oglasi',
        cell: (county) => noHzz(county) ? NO_HZZ : { text: formatInteger(county.filtered_jobs.jobs) },
      },
      {
        key: 'workers', name: 'Traženi radnici',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const { jobs, workers_needed: workers, workers_needed_coverage: known } = county.filtered_jobs
          if (!jobs) return { text: '0', note: 'nema oglasa' }
          if (!known.part) return { text: 'nije poznato', note: 'nijedan oglas ne navodi broj radnika', unavailable: true }
          return { text: formatInteger(workers), note: `navodi ${coverage(known.part, known.whole, known.percent)}` }
        },
      },
      {
        key: 'permanent', name: 'Na neodređeno',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const { jobs, permanent_share: share } = county.filtered_jobs
          if (!jobs) return { text: '–', note: 'nema oglasa' }
          if (share.percent === null) return { text: 'nije poznato', note: 'nijedan oglas ne navodi ugovor', unavailable: true }
          return { text: formatShare(share.percent),
            note: `${formatInteger(share.part)} od ${formatInteger(share.whole)} s poznatim ugovorom` }
        },
      },
      {
        key: 'closing', name: 'Uskoro ističu',
        cell: (county, data) => noHzz(county) ? NO_HZZ : {
          text: formatInteger(county.filtered_jobs.closing_soon),
          note: `rok u sljedećih ${data.window_days} ${plural(data.window_days, 'dan', 'dana', 'dana')}`,
        },
      },
    ],
  },
  {
    key: 'dzs', name: 'Registrirana nezaposlenost', hint: 'DZS, za referentni mjesec',
    rows: [
      { key: 'unemployed', name: 'Registrirani nezaposleni', cell: (county) => dzsCell(county.unemployed, formatInteger) },
      { key: 'active', name: 'Aktivno stanovništvo', cell: (county) => dzsCell(county.active_population, formatInteger) },
      { key: 'rate', name: 'Stopa registrirane nezaposlenosti', cell: (county) => dzsCell(county.unemployment_rate, formatRate) },
    ],
  },
  {
    key: 'indicators', name: 'Pokazatelji za županiju u cjelini', hint: 'svi aktivni oglasi, bez filtara',
    rows: [
      {
        key: 'per-worker', name: 'Nezaposlenih na jednog traženog radnika', extremes: true,
        cell: (county) => {
          const { numerator, denominator } = county.unemployed_per_worker
          const known = county.all_active_jobs.workers_needed_coverage
          const note = numerator !== null && denominator !== null
            ? `${formatInteger(numerator)} nezaposlenih / ${formatInteger(denominator)} traženih radnika (broj navodi `
              + `${formatInteger(known.part)} od ${formatAds(known.whole)})`
            : ''
          return indicatorCell(county.unemployed_per_worker, note)
        },
      },
      {
        key: 'per-1000', name: 'Oglasa na 1.000 aktivnih stanovnika', extremes: true,
        cell: (county) => {
          const { numerator, denominator } = county.jobs_per_1000_active
          const note = numerator !== null && denominator !== null
            ? `${formatAds(numerator)} / ${formatInteger(denominator)} aktivnih` : ''
          return indicatorCell(county.jobs_per_1000_active, note)
        },
      },
    ],
  },
]

// Each section's place among the table's rows, its heading counted, for the rows' entrance delays.
export const FIRST_ROWS = SECTIONS.map((_, k) => SECTIONS.slice(0, k).reduce((sum, section) => sum + section.rows.length + 1, 0))

