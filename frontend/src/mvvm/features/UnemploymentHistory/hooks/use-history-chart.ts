import { useMemo, useState } from 'react'
import { formatMonth, formatRate } from '../../../utils/format'
import { toGrowthData } from '../utils/chart-data'
import type { CountyHistory } from '../types'

const clamp = (index: number, count: number) => Math.min(Math.max(index, 0), count - 1)

/** useHistoryChart owns adapted rates, the inspected month across all series and the focused county. */
export function useHistoryChart(counties: CountyHistory[]) {
  const { series, points } = useMemo(() => toGrowthData(counties), [counties])
  const [selected, setSelected] = useState(points.length - 1)
  const [hovered, setHovered] = useState<number | null>(null)
  const active = hovered ?? selected
  const point = points[active]
  const select = (index: number) => setSelected(clamp(index, points.length))
  function navigate(key: string) {
    const next = ({ ArrowRight: active + 1, ArrowUp: active + 1, ArrowLeft: active - 1, ArrowDown: active - 1,
      Home: 0, End: points.length - 1 } as Record<string, number>)[key]
    if (next === undefined) return false
    setHovered(null)
    select(next)
    return true
  }
  const valueText = point ? `${formatMonth(point.period)}: ${series.map((s) => {
    const value = point.values[s.id]
    return `${s.label}: ${value.rate === null ? 'nema podatka' : formatRate(value.rate)}${value.is_provisional ? ', privremeno' : ''}`
  }).join('; ')}` : ''

  // The county lit orange and read out above the chart: the first one until the legend picks another.
  const n = series.length
  const [selectedIndex, setSelectedSeries] = useState(0)
  const [hoveredSeries, setHoveredSeries] = useState<number | null>(null)
  const selectedSeries = clamp(selectedIndex, n)
  const activeSeries = hoveredSeries !== null && hoveredSeries < n ? hoveredSeries : selectedSeries
  const selectSeries = (index: number) => setSelectedSeries(clamp(index, n))
  function navigateSeries(key: string): number | null {
    const next = ({ ArrowRight: selectedSeries + 1, ArrowDown: selectedSeries + 1, ArrowLeft: selectedSeries - 1,
      ArrowUp: selectedSeries - 1, Home: 0, End: n - 1 } as Record<string, number>)[key]
    if (next === undefined || !n) return null
    const index = clamp(next, n)
    setHoveredSeries(null)
    selectSeries(index)
    return index
  }

  return { series, points, active, point, valueText, selectMonth: select, hoverMonth: setHovered, navigate,
    selectedSeries, activeSeries, selectSeries, hoverSeries: setHoveredSeries, navigateSeries }
}
