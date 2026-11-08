import { formatDecimal, formatInteger, formatRate, formatShare, plural }
  from '../../../utils/format'
import type { ComparedCounty, CountyComparisonData, DzsValue, Indicator } from '../types'

interface CellView {
  text: string
  reason?: string | null
  unavailable?: boolean
  provisional?: boolean
  value?: number | null
}

interface RowView {
  key: string
  name: (data: CountyComparisonData) => string
  cell: (county: ComparedCounty) => CellView
  extremes?: boolean
}

interface Section {
  key: 'hzz' | 'dzs' | 'indicators'
  name: string
  rows: RowView[]
}

export const noHzz = (county: ComparedCounty) => county.hzz_last_success_at === null
const UNKNOWN = '–'
const NO_HZZ: CellView = { text: UNKNOWN, reason: 'HZZ oglasi za županiju nisu učitani', unavailable: true }

function dzsCell(value: DzsValue, format: (value: number) => string): CellView {
  if (value.value === null) return { text: UNKNOWN, reason: value.unavailable_label, unavailable: true, value: null }
  return { text: format(value.value), provisional: Boolean(value.is_provisional), value: value.value }
}

function indicatorCell(indicator: Indicator): CellView {
  if (indicator.value === null) return { text: UNKNOWN, reason: indicator.unavailable_label, unavailable: true, value: null }
  return { text: formatDecimal(indicator.value), provisional: Boolean(indicator.is_provisional), value: indicator.value }
}

export const SECTIONS: Section[] = [
  {
    key: 'hzz', name: 'Oglasi',
    rows: [
      { key: 'jobs', name: () => 'Oglasi',
        cell: (county) => noHzz(county) ? NO_HZZ : { text: formatInteger(county.filtered_jobs.jobs) } },
      {
        key: 'workers', name: () => 'Traženi radnici',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const { jobs, workers_needed: workers, workers_needed_coverage: known } = county.filtered_jobs
          if (jobs && !known.part) return { text: UNKNOWN, reason: 'nijedan oglas ne navodi broj radnika', unavailable: true }
          return { text: formatInteger(workers) }
        },
      },
      {
        key: 'permanent', name: () => 'Na neodređeno',
        cell: (county) => {
          if (noHzz(county)) return NO_HZZ
          const share = county.filtered_jobs.permanent_share
          if (share.percent === null) return { text: UNKNOWN, reason: 'nijedan oglas ne navodi ugovor', unavailable: true }
          return { text: formatShare(share.percent) }
        },
      },
      {
        key: 'closing', name: (data) => `Ističu u ${data.window_days} ${plural(data.window_days, 'dan', 'dana', 'dana')}`,
        cell: (county) => noHzz(county) ? NO_HZZ : { text: formatInteger(county.filtered_jobs.closing_soon) },
      },
    ],
  },
  {
    key: 'dzs', name: 'Nezaposlenost',
    rows: [
      { key: 'unemployed', name: () => 'Nezaposleni', cell: (county) => dzsCell(county.unemployed, formatInteger) },
      { key: 'active', name: () => 'Aktivno stanovništvo', cell: (county) => dzsCell(county.active_population, formatInteger) },
      { key: 'rate', name: () => 'Stopa', cell: (county) => dzsCell(county.unemployment_rate, formatRate) },
    ],
  },
  {
    key: 'indicators', name: 'Pokazatelji',
    rows: [
      { key: 'per-worker', name: () => 'Nezaposlenih po traženom radniku', extremes: true,
        cell: (county) => indicatorCell(county.unemployed_per_worker) },
      { key: 'per-1000', name: () => 'Oglasa na 1.000 aktivnih', extremes: true,
        cell: (county) => indicatorCell(county.jobs_per_1000_active) },
    ],
  },
]

export const FIRST_ROWS = SECTIONS.map((_, k) => SECTIONS.slice(0, k).reduce((sum, section) => sum + section.rows.length + 1, 0))
