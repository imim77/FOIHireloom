import { useState } from 'react'
import { formatPeriod, formatValue } from '../utils/forecast-chart'
import type { CountyForecast, ForecastData } from '../types'

export function useForecast(data: ForecastData, county: CountyForecast) {
  const [selected, setSelected] = useState(Math.max(0, county.forecast.length - 1))
  const [hovered, setHovered] = useState<number | null>(null)
  const active = hovered ?? selected
  const point = county.forecast[active]
  const last = county.last_observed
  const value = (n: number) => formatValue(n, data.unit)
  const period = (iso: string) => formatPeriod(iso, data.frequency)
  const interval = `${Math.round(data.interval * 100)}% interval`

  function selectPeriod(index: number) {
    setHovered(null)
    setSelected(index)
  }

  return { data, county, selected, active, selectPeriod, hoverPeriod: setHovered, point,
    selectedPoint: county.forecast[selected], last, value, period, interval }
}
