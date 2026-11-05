import { useMemo, useState } from 'react'
import { formatMonth, formatRate } from '../../shared/format'
import { toGrowthData } from './chart-data'
import type { CountyHistory } from './types'

/** useHistoryChart owns adapted rates and the inspected month across all series. */
export function useHistoryChart(counties: CountyHistory[]) {
  const { series, points } = useMemo(() => toGrowthData(counties), [counties])
  const [selected, setSelected] = useState(points.length - 1)
  const [hovered, setHovered] = useState<number | null>(null)
  const [emphasis, setEmphasis] = useState<string | null>(null)
  const active = hovered ?? selected
  const point = points[active]
  const select = (index: number) => setSelected(Math.min(points.length - 1, Math.max(0, index)))
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

  return { series, points, active, point, emphasis, valueText, selectMonth: select,
    hoverMonth: setHovered, emphasiseSeries: setEmphasis, navigate }
}
