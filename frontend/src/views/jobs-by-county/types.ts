import type { Coverage } from '../../shared/types'

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
}
