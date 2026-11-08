import type { ActiveFilter, Coverage } from '../../types'

export interface AccommodationGroup {
  key: 'offered' | 'not_offered' | 'unknown'
  label: string
  jobs: number
  share: number
}

export interface AccommodationComparisonData {
  title: string
  description: string
  today: string
  total_jobs: number
  known_jobs: number
  groups: AccommodationGroup[]
  accommodation_types: { name: string; jobs: number; workers_needed: number }[]
  coverage: Coverage & {
    data_as_of: string | null
    stale_after_hours: number
    affected_regions: { code: string; name: string; data_status: string; last_success_at: string | null }[]
  }
  active_filters: ActiveFilter[]
  coverage_note: string | null
  unknown_conditions: Record<string, number>
  unknown_total: number
  unknown_note: string | null
  view_notes: string[]
}
