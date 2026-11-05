// Shapes of the server's DTOs, as the tools return them in structuredContent.

export interface Coverage {
  data_status?: string
  warning: string | null
}

// ActiveFilterDTO: a set filter in Croatian; argument is the tool argument that sets it.
export interface ActiveFilter {
  argument: string
  label: string
}

// UnavailableReason of the county indicators: why a DZS value, an indicator or a change is not given.
export type UnavailableReason = 'no_dzs_data' | 'no_common_period' | 'dzs_value_missing' | 'no_hzz_data'
  | 'no_known_workers' | 'zero_denominator'

// SourceLinkDTO: a source in Croatian; url is null for a local file.
export interface SourceLink {
  label: string
  url: string | null
}

// DzsImportProvenanceDTO: the latest succeeded DZS import.
export interface DzsProvenance {
  import_id: number
  // ISO date-time (UTC)
  finished_at: string
  files: { role: 't1' | 'workbook'; location: string; fetched_at: string; last_modified: string | null }[]
}
