import { formatDay, formatInteger, formatMonth, formatMonthGenitive, formatPoints, formatRate } from '../../../utils/format.ts'
import type { CountyForecast, ForecastFrequency, ForecastUnit } from '../types.ts'

export const formatValue = (value: number, unit: ForecastUnit) =>
  unit === 'percent' ? formatRate(value) : formatInteger(value)

export const formatPeriod = (period: string, frequency: ForecastFrequency) =>
  frequency === 'month' ? formatMonth(period) : `tjedan od ${formatDay(period)}`

export const formatPeriodGenitive = (period: string, frequency: ForecastFrequency) =>
  frequency === 'month' ? formatMonthGenitive(period) : `tjedna od ${formatDay(period)}`

export function formatChange(value: number, unit: ForecastUnit) {
  if (unit === 'percent') return formatPoints(value)
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatInteger(Math.abs(value))} ${unit === 'persons' ? 'osoba' : 'oglasa'}`
}

export interface ForecastRow {
  index: number
  period: string
  value: number | null
  median: number | null
  range: [number, number] | null
  [run: `run${number}`]: number | null
}

export interface HistoryRun {
  key: `run${number}`
  flagged: boolean
  from: string
  to: string
}

const flagged = (point: { is_estimated: boolean | null; is_provisional: boolean | null }) =>
  Boolean(point.is_estimated || point.is_provisional)

export function forecastRows(county: CountyForecast): { rows: ForecastRow[]; runs: HistoryRun[] } {
  const { history, forecast } = county
  const rows: ForecastRow[] = [
    ...history.map((p, index) => ({ index, period: p.period, value: p.value, median: null, range: null })),
    ...forecast.map((p, index) => ({ index: history.length + index, period: p.period, value: null, median: p.median,
      range: [p.low, p.high] as [number, number] })),
  ]
  const runs: HistoryRun[] = []
  history.forEach((p, index) => {
    const next = history[index + 1]
    if (p.value === null || next?.value == null) return
    const dashed = flagged(p) || flagged(next)
    let run = runs.at(-1)
    if (run && run.flagged === dashed && run.to === p.period) run.to = next.period
    else runs.push(run = { key: `run${runs.length}`, flagged: dashed, from: p.period, to: next.period })
    rows[index][run.key] = p.value
    rows[index + 1][run.key] = next.value
  })
  const anchor = history.at(-1)
  if (anchor?.value != null && forecast.length) {
    rows[history.length - 1].median = anchor.value
    rows[history.length - 1].range = [anchor.value, anchor.value]
  }
  return { rows, runs }
}

export function valueTicks(county: CountyForecast, unit: ForecastUnit) {
  const known = county.history.flatMap((point) => point.value ?? [])
    .concat(county.forecast.flatMap((point) => [point.low, point.median, point.high]))
  const max = Math.max(1, ...known)
  const power = 10 ** Math.floor(Math.log10(max / 4))
  const step = Math.max(unit === 'percent' ? 0.1 : 1,
    ([1, 2, 2.5, 5, 10].find((factor) => factor * power >= max / 4) ?? 10) * power)
  const ceiling = Math.ceil(max / step) * step
  return Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => Math.round(index * step * 1e6) / 1e6)
}
