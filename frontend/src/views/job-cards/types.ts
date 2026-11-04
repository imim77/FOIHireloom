import type { ActiveFilter, Coverage } from '../../shared/types'
import type { JobConditions, JobFilters } from '../../shared/jobs'

// JobCardDTO: a search result with the job page values; null when HZZ did not state them.
export interface JobCard {
  id: number
  display_title: string
  display_location: string
  employer_name: string | null
  category: string | null
  // 'feed' when the category was filled in from an HZZ occupation feed, not stated in the job's description.
  category_source: 'description' | 'feed' | null
  county_name: string | null
  work_place: string | null
  // ISO dates (YYYY-MM-DD)
  published_on: string | null
  deadline_on: string | null
  deadline_passed: boolean | null
  canonical_url: string
  workers_needed: number | null
  // The page's text, as HZZ wrote it.
  employment_type: string | null
  working_hours: string | null
  education: string | null
  experience: string | null
  accommodation: string | null
  // The same page's conditions normalised; null until the page has been read.
  conditions: JobConditions | null
}

// The show_jobs arguments that found the cards, so the view can ask for the next page or drop a filter.
export interface JobCardsFilters extends JobFilters {
  county: string | null
  limit: number
  cursor: string | null
}

// JobCardsDTO
export interface JobCardsData {
  title: string
  description: string
  today: string
  jobs: JobCard[]
  next_cursor: string | null
  filters: JobCardsFilters
  // Every set filter but the query, which is in the title.
  active_filters: ActiveFilter[]
  coverage: Coverage | null
  // Croatian for coverage.warning and for the jobs left out only because a value is unknown.
  coverage_note: string | null
  unknown_note: string | null
}
