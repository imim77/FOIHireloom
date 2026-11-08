
export interface Coverage {
  data_status?: string
  warning: string | null
}

export interface ActiveFilter {
  argument: string
  label: string
}

export type UnavailableReason = 'no_dzs_data' | 'no_common_period' | 'dzs_value_missing' | 'no_hzz_data'
  | 'no_known_workers' | 'zero_denominator'

export interface SourceLink {
  label: string
  url: string | null
}

export interface DzsProvenance {
  import_id: number
  finished_at: string
  files: { role: 't1' | 'workbook'; location: string; fetched_at: string; last_modified: string | null }[]
}
