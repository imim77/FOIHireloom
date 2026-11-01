import type { ActiveFilter, Coverage } from '../../shared/types'

export type CountyMetric = 'jobs' | 'workers_needed'

// CountyShareDTO
export interface County {
  code?: string
  name: string
  short_name: string
  jobs: number
  workers_needed: number
  share: number
}

// JobsByCountyDTO
export interface JobsByCountyData {
  metric: CountyMetric
  title: string
  description: string
  total_jobs: number
  total_workers_needed: number
  top: number
  counties: County[]
  coverage: Coverage | null
  // Every set filter but the query; the description names them too.
  active_filters: ActiveFilter[]
  // Croatian for coverage.warning and for the jobs left out only because a value is unknown.
  coverage_note: string | null
  unknown_note: string | null
}
