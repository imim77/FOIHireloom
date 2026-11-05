import type { CountyHistory, UnemploymentPoint } from '../types'

export interface GrowthSeries {
  id: string
  label: string
  shortLabel: string
}

export interface GrowthPoint {
  period: string
  values: Record<string, UnemploymentPoint>
}

export interface GrowthData {
  series: GrowthSeries[]
  points: GrowthPoint[]
}

/** Adapt the existing MCP result without changing rates, provenance or the county order.
 * Join by month, not array position: a missing row must never shift another month's value.
 */
export function toGrowthData(counties: CountyHistory[]): GrowthData {
  const periods = [...new Set(counties.flatMap((county) => county.series.map((point) => point.period)))].sort()
  const lookup = counties.map((county) => new Map(county.series.map((point) => [point.period, point])))
  return {
    series: counties.map((county) => ({ id: county.code, label: county.name, shortLabel: county.short_name })),
    points: periods.map((period) => ({
      period,
      values: Object.fromEntries(counties.map((county, index) => [county.code, lookup[index].get(period) ?? {
        period, rate: null, is_provisional: null, unavailable_reason: 'dzs_value_missing', missing_reason: null,
      }])),
    })),
  }
}

export interface GrowthRun {
  provisional: boolean
  indices: number[]
}

/** Split at missing values and at changes of segment status, retaining isolated known points. */
export function seriesRuns(points: GrowthPoint[], id: string): GrowthRun[] {
  const runs: GrowthRun[] = []
  points.forEach((point, index) => {
    const value = point.values[id]
    if (value.rate === null) return
    const next = points[index + 1]?.values[id]
    const before = points[index - 1]?.values[id]
    if ((!before || before.rate === null) && (!next || next.rate === null)) {
      runs.push({ provisional: Boolean(value.is_provisional), indices: [index] })
    }
    if (!next || next.rate === null) return
    const provisional = Boolean(value.is_provisional || next.is_provisional)
    const last = runs[runs.length - 1]
    if (last?.provisional === provisional && last.indices.at(-1) === index) last.indices.push(index + 1)
    else runs.push({ provisional, indices: [index, index + 1] })
  })
  return runs
}

/** Mark only months flagged provisional, including disjoint ranges. */
export function provisionalBands(points: GrowthPoint[]) {
  const bands: { first: number; last: number }[] = []
  points.forEach((point, index) => {
    if (!Object.values(point.values).some((value) => value.is_provisional)) return
    const last = bands.at(-1)
    if (last?.last === index - 1) last.last = index
    else bands.push({ first: index, last: index })
  })
  return bands
}
