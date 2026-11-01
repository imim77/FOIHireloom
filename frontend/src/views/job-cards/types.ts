import type { Coverage } from '../../shared/types'

export type Contract = 'permanent' | 'fixed_term' | 'other'
export type EducationLevel = 'primary_lower' | 'primary' | 'secondary_3' | 'secondary_4' | 'college' | 'university'
export type EmploymentTag = 'new_position' | 'vacancy' | 'replacement' | 'increased_workload' | 'seasonal'
  | 'reappointment' | 'trainee' | 'retirees' | 'disability'

// JobConditionsDTO: the job page's conditions as codes; null is unknown, never "not required".
export interface JobConditions {
  experience_months: number | null
  // true for "Traži se pripravnik", whose experience_months is 0.
  trainee: boolean | null
  contract: Contract | null
  employment_tags: EmploymentTag[] | null
  // true for "Puno radno vrijeme", which states no weekly_hours.
  full_time: boolean | null
  weekly_hours: number | null
  education_levels: EducationLevel[] | null
  accommodation: 'none' | 'shared' | 'single' | 'family' | null
  schedule_tags: string[] | null
  transport_allowance: 'full' | 'partial' | 'none' | null
  // The page fields whose text was not recognised.
  unrecognised: string[]
}

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

// The show_jobs arguments that found the cards, so the view can ask for the next page.
export interface JobCardsFilters {
  query: string | null
  county: string | null
  category: string | null
  max_experience_months: number | null
  contract: Contract | null
  full_time: boolean | null
  education: EducationLevel | null
  accommodation: boolean | null
  employment_tags: EmploymentTag[] | null
  place: string | null
  include_expired: boolean
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
  coverage: Coverage | null
}
