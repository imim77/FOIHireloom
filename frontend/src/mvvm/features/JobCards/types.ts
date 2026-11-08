import type { ActiveFilter, Coverage } from '../../types'
import type { JobConditions, JobFilters } from '../../utils/jobs'

export interface JobCard {
  id: number
  display_title: string
  display_location: string
  employer_name: string | null
  category: string | null
  category_source: 'description' | 'feed' | null
  county_name: string | null
  work_place: string | null
  published_on: string | null
  deadline_on: string | null
  deadline_passed: boolean | null
  canonical_url: string
  workers_needed: number | null
  employment_type: string | null
  working_hours: string | null
  education: string | null
  experience: string | null
  accommodation: string | null
  conditions: JobConditions | null
}

export interface JobCardsFilters extends JobFilters {
  county: string | null
  limit: number
  cursor: string | null
}

export interface JobCardsData {
  title: string
  description: string
  today: string
  jobs: JobCard[]
  next_cursor: string | null
  filters: JobCardsFilters
  active_filters: ActiveFilter[]
  coverage: Coverage | null
  coverage_note: string | null
  unknown_note: string | null
}
