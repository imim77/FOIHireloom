import type { ActiveFilter, Coverage } from '../../types'

export type CountyMetric = 'jobs' | 'workers_needed'

export interface County {
  code?: string
  name: string
  short_name: string
  jobs: number
  workers_needed: number
  share: number
}

export interface JobsByCountyData {
  metric: CountyMetric
  title: string
  description: string
  total_jobs: number
  total_workers_needed: number
  top: number
  counties: County[]
  coverage: Coverage | null
  active_filters: ActiveFilter[]
  coverage_note: string | null
  unknown_note: string | null
}
