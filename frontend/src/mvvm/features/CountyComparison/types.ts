import type { JobFilters } from '../../utils/jobs'
import type { ActiveFilter, DzsProvenance, SourceLink, UnavailableReason } from '../../types'

export type DzsIndicator = 'unemployed' | 'active_population' | 'unemployment_rate' | 'employed'
export type DataStatus = 'fresh' | 'stale' | 'unavailable'

// ShareDTO: part of whole in percent; percent is null when whole is 0.
export interface Share {
  part: number
  whole: number
  percent: number | null
}

// CountyJobCountsDTO
export interface JobCounts {
  jobs: number
  // Only the ads that state the number; workers_needed_coverage says how many do.
  workers_needed: number
  workers_needed_coverage: Share
  // Permanent contracts out of the ads whose contract is known.
  permanent_share: Share
  contract_coverage: Share
  // Deadline within window_days days.
  closing_soon: number
}

// DzsCountyValueViewDTO: persons, or a percentage for the rate, for its reference month.
export interface DzsValue {
  indicator: DzsIndicator
  value: number | null
  // The month's first day, YYYY-MM-01; null when no month could be chosen.
  period: string | null
  is_provisional: boolean | null
  source: 't1' | 'workbook_9_4_13' | 'workbook_9_4_14' | null
  unavailable_reason: UnavailableReason | null
  missing_reason: 'no_occurrence' | 'not_available' | 'empty' | null
  // Why value is null, in Croatian.
  unavailable_label: string | null
}

// CountyIndicatorViewDTO: a county-wide ratio with the numbers it was computed from.
export interface Indicator {
  value: number | null
  numerator: number | null
  denominator: number | null
  dzs_period: string | null
  is_provisional: boolean | null
  unavailable_reason: UnavailableReason | null
  unavailable_label: string | null
}

// ComparedCountyViewDTO
export interface ComparedCounty {
  code: string
  name: string
  short_name: string
  iso_code: string
  hzz_data_status: DataStatus
  // ISO date-time (UTC); null when the county's feeds were never loaded.
  hzz_last_success_at: string | null
  filtered_jobs: JobCounts
  all_active_jobs: JobCounts
  unemployed: DzsValue
  active_population: DzsValue
  unemployment_rate: DzsValue
  unemployed_per_worker: Indicator
  jobs_per_1000_active: Indicator
}

// JobCountFiltersDTO: the arguments compare_counties takes besides the counties and the period.
export type CountyFilters = JobFilters

export interface ReferencePeriod {
  indicator: DzsIndicator
  period: string | null
  requested: boolean
  unavailable_reason: UnavailableReason | null
}

// CountyComparisonViewDTO
export interface CountyComparisonData {
  title: string
  description: string
  counties: ComparedCounty[]
  // ISO date (YYYY-MM-DD), the day in Croatia.
  today: string
  window_days: number
  filters: CountyFilters
  active_filters: ActiveFilter[]
  requested_period: string | null
  dzs_periods: ReferencePeriod[]
  hzz_coverage: {
    data_status: DataStatus
    // The oldest last successful HZZ sync of the compared counties.
    data_as_of: string | null
    stale_after_hours: number
    affected_regions: { code: string; name: string; data_status: DataStatus; last_success_at: string | null }[]
    warning: string | null
  }
  dzs: DzsProvenance | null
  // English, for the LLM.
  sources: { name: string; url: string | null; description: string }[]
  notes: string[]
  coverage_note: string | null
  source_links: SourceLink[]
  view_notes: string[]
  disclaimer: string
}
