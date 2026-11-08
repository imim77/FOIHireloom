import type { JobFilters } from '../../utils/jobs'
import type { ActiveFilter, DzsProvenance, SourceLink, UnavailableReason } from '../../types'

export type DzsIndicator = 'unemployed' | 'active_population' | 'unemployment_rate' | 'employed'
export type DataStatus = 'fresh' | 'stale' | 'unavailable'

export interface Share {
  part: number
  whole: number
  percent: number | null
}

export interface JobCounts {
  jobs: number
  workers_needed: number
  workers_needed_coverage: Share
  permanent_share: Share
  contract_coverage: Share
  closing_soon: number
}

export interface DzsValue {
  indicator: DzsIndicator
  value: number | null
  period: string | null
  is_provisional: boolean | null
  source: 't1' | 'workbook_9_4_13' | 'workbook_9_4_14' | null
  unavailable_reason: UnavailableReason | null
  missing_reason: 'no_occurrence' | 'not_available' | 'empty' | null
  unavailable_label: string | null
}

export interface Indicator {
  value: number | null
  numerator: number | null
  denominator: number | null
  dzs_period: string | null
  is_provisional: boolean | null
  unavailable_reason: UnavailableReason | null
  unavailable_label: string | null
}

export interface ComparedCounty {
  code: string
  name: string
  short_name: string
  iso_code: string
  hzz_data_status: DataStatus
  hzz_last_success_at: string | null
  filtered_jobs: JobCounts
  all_active_jobs: JobCounts
  unemployed: DzsValue
  active_population: DzsValue
  unemployment_rate: DzsValue
  unemployed_per_worker: Indicator
  jobs_per_1000_active: Indicator
}

export type CountyFilters = JobFilters

export interface ReferencePeriod {
  indicator: DzsIndicator
  period: string | null
  requested: boolean
  unavailable_reason: UnavailableReason | null
}

export interface CountyComparisonData {
  title: string
  description: string
  counties: ComparedCounty[]
  today: string
  window_days: number
  filters: CountyFilters
  active_filters: ActiveFilter[]
  requested_period: string | null
  dzs_periods: ReferencePeriod[]
  hzz_coverage: {
    data_status: DataStatus
    data_as_of: string | null
    stale_after_hours: number
    affected_regions: { code: string; name: string; data_status: DataStatus; last_success_at: string | null }[]
    warning: string | null
  }
  dzs: DzsProvenance | null
  sources: { name: string; url: string | null; description: string }[]
  notes: string[]
  coverage_note: string | null
  source_links: SourceLink[]
  view_notes: string[]
  disclaimer: string
}
