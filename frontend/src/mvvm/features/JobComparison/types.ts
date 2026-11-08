import type { Contract, EducationLevel, JobConditions } from '../../utils/jobs'

export type Aspect = 'experience' | 'education' | 'contract' | 'working_time' | 'accommodation' | 'deadline'
export type Verdict = 'match' | 'no_match' | 'unknown'
export type UnknownReason = 'page_not_read' | 'page_unavailable' | 'page_failed' | 'not_stated' | 'unreadable'
  | 'contract_not_stated'

export interface ComparedJob {
  id: number
  display_title: string
  employer_name: string | null
  county_name: string | null
  display_location: string
  canonical_url: string
  details_status: 'pending' | 'fetched' | 'unavailable' | 'failed'
  category: string | null
  category_source: 'description' | 'feed' | null
  published_on: string | null
  deadline_on: string | null
  deadline_passed: boolean | null
  conditions: JobConditions | null
}

export interface ComparisonCell {
  job_id: number
  value: string | null
  evidence: string | null
  verdict: Verdict | null
  reason: string | null
  unknown_reason: UnknownReason | null
  text: string
  note: string | null
  verdict_label: string | null
}

export interface ComparisonRow {
  aspect: Aspect
  differs: boolean
  condition: boolean | number | string | null
  name: string
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
