import { useState } from 'react'
import { formatPeriod, formatValue } from '../utils/forecast-chart'
import type { CountyForecast, ForecastData } from '../types'

/** useForecast owns the selected and hovered periods and display values for one result. */
export function useForecast(data: ForecastData, county: CountyForecast) {
  const [selected, setSelected] = useState(Math.max(0, county.forecast.length - 1))
  const [hovered, setHovered] = useState<number | null>(null)
  // Hover previews a period; leaving the plot falls back to the selection.
  const active = hovered ?? selected
  const point = county.forecast[active]
  const last = county.last_observed
  const end = county.forecast.at(-1)
  const value = (n: number) => formatValue(n, data.unit)
  const period = (iso: string) => formatPeriod(iso, data.frequency)
  const interval = `${Math.round(data.interval * 100)}% interval`

  function selectPeriod(index: number) {
    setHovered(null) // a committed choice must show even while the pointer rests on another period
    setSelected(index)
  }

  return { data, county, selected, active, selectPeriod, hoverPeriod: setHovered, point,
    selectedPoint: county.forecast[selected], last, end, value, period, interval }
}
