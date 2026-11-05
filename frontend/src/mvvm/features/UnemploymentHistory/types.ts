import type { DzsProvenance, SourceLink, UnavailableReason } from '../../types'

export type Sex = 'total' | 'women' | 'men'

// UnemploymentPointDTO: one month's registered unemployment rate in percent; null when DZS has none.
export interface UnemploymentPoint {
  // The month's first day, YYYY-MM-01.
  period: string
  rate: number | null
  // null without a stored row.
  is_provisional: boolean | null
  unavailable_reason: UnavailableReason | null
  missing_reason: 'no_occurrence' | 'not_available' | 'empty' | null
}

// CountyUnemploymentHistoryViewDTO: one county's series, oldest month first, and its change over a year.
export interface CountyHistory {
  code: string
  name: string
  iso_code: string
  // "Varaždinska"
  short_name: string
  series: UnemploymentPoint[]
  latest: UnemploymentPoint | null
  same_month_previous_year: UnemploymentPoint | null
  // Percentage points; null when either rate is unknown.
  change_pp: number | null
  change_unavailable_reason: UnavailableReason | null
  // Why change_pp is null, in Croatian.
  change_unavailable_label: string | null
}

// UnemploymentHistoryViewDTO
export interface UnemploymentHistoryData {
  title: string
  description: string
  counties: CountyHistory[]
  sex: Sex
  months: number
  first_period: string | null
  last_period: string | null
  unavailable_reason: UnavailableReason | null
  // Why there is no series, in Croatian; null when there is one.
  unavailable_label: string | null
  dzs: DzsProvenance | null
  // English, for the LLM.
  sources: { name: string; url: string | null; description: string }[]
  notes: string[]
  source_links: SourceLink[]
  view_notes: string[]
}
