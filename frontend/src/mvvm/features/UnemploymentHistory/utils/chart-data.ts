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

export interface GrowthRow {
  index: number
  period: string
  [key: string]: number | string | null
}

export interface ChartRun {
  key: string
  provisional: boolean
  from: string
  to: string
}

export function growthRows({ series, points }: GrowthData): { rows: GrowthRow[]; runs: ChartRun[][] } {
  const rows: GrowthRow[] = points.map((point, index) => ({ index, period: point.period,
    ...Object.fromEntries(series.map((s, i) => [`s${i}`, point.values[s.id].rate])) }))
  const runs = series.map((s, i) => seriesRuns(points, s.id).filter((run) => run.indices.length > 1)
    .map((run, n) => {
      const key = `s${i}r${n}`
      for (const index of run.indices) rows[index][key] = points[index].values[s.id].rate
      return { key, provisional: run.provisional, from: points[run.indices[0]].period,
        to: points[run.indices.at(-1)!].period }
    }))
  return { rows, runs }
}
