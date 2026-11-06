import type { Contract, EducationLevel, JobConditions } from '../../utils/jobs'

export type Aspect = 'experience' | 'education' | 'contract' | 'working_time' | 'accommodation' | 'deadline'
export type Verdict = 'match' | 'no_match' | 'unknown'
export type UnknownReason = 'page_not_read' | 'page_unavailable' | 'page_failed' | 'not_stated' | 'unreadable'
  | 'contract_not_stated'

// ComparedJobDTO: a compared job as its card names it.
export interface ComparedJob {
  id: number
  display_title: string
  employer_name: string | null
  county_name: string | null
  display_location: string
  canonical_url: string
  details_status: 'pending' | 'fetched' | 'unavailable' | 'failed'
  category: string | null
  // 'feed' when the category was filled in from an HZZ occupation feed, not stated in the job's description.
  category_source: 'description' | 'feed' | null
  // ISO dates (YYYY-MM-DD)
  published_on: string | null
  deadline_on: string | null
  deadline_passed: boolean | null
  // null until the job's page has been read.
  conditions: JobConditions | null
}

// ComparisonCellViewDTO: one job's value for one aspect.
export interface ComparisonCell {
  job_id: number
  // English, for the LLM; null when unknown.
  value: string | null
  evidence: string | null
  // null when the user set no condition for the aspect.
  verdict: Verdict | null
  reason: string | null
  unknown_reason: UnknownReason | null
  // Croatian: the page's own words, the worded deadline or why the value is unknown.
  text: string
  // Why the value is unknown when text is the page's own words.
  note: string | null
  verdict_label: string | null
}

// ComparisonRowViewDTO: one aspect across the jobs, a cell per job in the jobs' order.
export interface ComparisonRow {
  aspect: Aspect
  differs: boolean
  condition: boolean | number | string | null
  name: string
  // The user's condition in Croatian, null without one.
  condition_label: string | null
  cells: ComparisonCell[]
}

export interface ComparisonConditions {
  max_experience_months: number | null
  contract: Contract | null
  full_time: boolean | null
  education: EducationLevel | null
  accommodation: boolean | null
}

// JobComparisonViewDTO
export interface JobComparisonData {
  title: string
  description: string
  today: string
  jobs: ComparedJob[]
  rows: ComparisonRow[]
  conditions: ComparisonConditions | null
  disclaimer: string
  unknown_note: string | null
}
