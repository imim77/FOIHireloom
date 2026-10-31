import type { Coverage } from '../../shared/types'

// JobCardDTO: a search result with the job page values; null when HZZ did not state them.
export interface JobCard {
  id: number
  display_title: string
  display_location: string
  employer_name: string | null
  category: string | null
  county_name: string | null
  work_place: string | null
  // ISO dates (YYYY-MM-DD)
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
}

// The show_jobs arguments, so the view can ask for the next page.
export interface JobCardsFilters {
  query: string | null
  county: string | null
  category: string | null
  include_expired: boolean
  limit: number
}

// JobCardsDTO
export interface JobCardsData {
  title: string
  description: string
  today: string
  jobs: JobCard[]
  next_cursor: string | null
  filters: JobCardsFilters
  coverage: Coverage | null
}
