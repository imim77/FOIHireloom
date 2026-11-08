import type { DzsProvenance, SourceLink, UnavailableReason } from '../../types'

export type Sex = 'total' | 'women' | 'men'

export interface UnemploymentPoint {
  period: string
  rate: number | null
  is_provisional: boolean | null
  unavailable_reason: UnavailableReason | null
  missing_reason: 'no_occurrence' | 'not_available' | 'empty' | null
}

export interface CountyHistory {
  code: string
  name: string
  iso_code: string
  short_name: string
  series: UnemploymentPoint[]
  latest: UnemploymentPoint | null
  same_month_previous_year: UnemploymentPoint | null
  change_pp: number | null
  change_unavailable_reason: UnavailableReason | null
  change_unavailable_label: string | null
}

export interface UnemploymentHistoryData {
  title: string
  description: string
  counties: CountyHistory[]
  sex: Sex
  months: number
  first_period: string | null
  last_period: string | null
  unavailable_reason: UnavailableReason | null
  unavailable_label: string | null
  dzs: DzsProvenance | null
  sources: { name: string; url: string | null; description: string }[]
  notes: string[]
  source_links: SourceLink[]
  view_notes: string[]
}
