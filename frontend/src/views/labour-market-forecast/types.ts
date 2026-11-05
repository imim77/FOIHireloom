import type { SourceLink } from '../../shared/types'

export type ForecastTarget = 'unemployment_rate' | 'unemployed' | 'employed' | 'job_ads'
export type ForecastUnit = 'percent' | 'persons' | 'ads'
export type ForecastFrequency = 'month' | 'week'
export type UnavailableReason = 'no_dzs_data' | 'no_common_period' | 'no_hzz_data' | 'not_enough_history'

export interface ObservedPoint {
  period: string
  value: number | null
  is_provisional: boolean | null
  is_estimated: boolean | null
}

export interface PredictedPoint {
  period: string
  median: number
  low: number
  high: number
}

export interface CountyForecast {
  code: string
  name: string
  iso_code: string
  history: ObservedPoint[]
  forecast: PredictedPoint[]
  last_observed: ObservedPoint | null
  change_to_horizon: number | null
  unavailable_reason: UnavailableReason | null
}

// CountyForecastViewDTO keeps the source forecast alongside Croatian display labels.
export interface ForecastData {
  target: ForecastTarget
  frequency: ForecastFrequency
  unit: ForecastUnit
  sex: 'total' | 'women' | 'men' | null
  horizon: number
  interval: number
  model: string
  last_observed_period: string | null
  counties: CountyForecast[]
  unavailable_reason: UnavailableReason | null
  sources: { name: string; url: string | null; description: string }[]
  notes: string[]
  title: string
  description: string
  unavailable_label: string | null
  source_links: SourceLink[]
  view_notes: string[]
}
