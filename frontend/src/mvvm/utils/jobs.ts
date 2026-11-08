export type Contract = 'permanent' | 'fixed_term' | 'other'
export type EducationLevel = 'primary_lower' | 'primary' | 'secondary_3' | 'secondary_4' | 'college' | 'university'
export type EmploymentTag = 'new_position' | 'vacancy' | 'replacement' | 'increased_workload' | 'seasonal'
  | 'reappointment' | 'trainee' | 'retirees' | 'disability'

export interface JobConditions {
  experience_months: number | null
  trainee: boolean | null
  contract: Contract | null
  employment_tags: EmploymentTag[] | null
  full_time: boolean | null
  weekly_hours: number | null
  education_levels: EducationLevel[] | null
  accommodation: 'none' | 'shared' | 'single' | 'family' | null
  schedule_tags: string[] | null
  transport_allowance: 'full' | 'partial' | 'none' | null
  unrecognised: string[]
}

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
