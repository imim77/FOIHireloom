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

// JobCountFiltersDTO: shared search conditions, without pagination or a county.
export interface JobFilters {
  query: string | null
  category: string | null
  max_experience_months: number | null
  contract: Contract | null
  full_time: boolean | null
  education: EducationLevel | null
  accommodation: boolean | null
  employment_tags: EmploymentTag[] | null
  place: string | null
  include_expired: boolean
}
