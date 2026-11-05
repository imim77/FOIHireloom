import { useState } from 'react'
import { formatPeriod, formatValue } from './forecast-chart'
import type { CountyForecast, ForecastData } from './types'

/** useForecast owns the inspected period and display values for one result. */
export function useForecast(data: ForecastData, county: CountyForecast) {
  const [selected, setSelected] = useState(Math.max(0, county.forecast.length - 1))
  const point = county.forecast[selected]
  const last = county.last_observed
  const end = county.forecast.at(-1)
  const value = (n: number) => formatValue(n, data.unit)
  const period = (iso: string) => formatPeriod(iso, data.frequency)
  const interval = `${Math.round(data.interval * 100)}% interval`
  return { data, county, selected, selectPeriod: setSelected, point, last, end, value, period, interval }
}
