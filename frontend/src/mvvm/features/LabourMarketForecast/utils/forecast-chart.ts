import { formatDay, formatInteger, formatMonth, formatMonthGenitive, formatPoints, formatRate } from '../../../utils/format.ts'
import type { CountyForecast, ForecastFrequency, ForecastUnit } from '../types.ts'

export const formatValue = (value: number, unit: ForecastUnit) =>
  unit === 'percent' ? formatRate(value) : formatInteger(value)

export const formatPeriod = (period: string, frequency: ForecastFrequency) =>
  frequency === 'month' ? formatMonth(period) : `tjedan od ${formatDay(period)}`

/** A period in the genitive, after "do": "ožujka 2027.", "tjedna od 02. 11. 2026.". */
export const formatPeriodGenitive = (period: string, frequency: ForecastFrequency) =>
  frequency === 'month' ? formatMonthGenitive(period) : `tjedna od ${formatDay(period)}`

export function formatChange(value: number, unit: ForecastUnit) {
  if (unit === 'percent') return formatPoints(value)
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatInteger(Math.abs(value))} ${unit === 'persons' ? 'osoba' : 'oglasa'}`
}

/** ForecastRow is one period on the chart's shared x axis: history first, then the forecast. */
export interface ForecastRow {
  index: number
  period: string
  value: number | null // observed history; null for a gap and for forecast periods
  median: number | null // the forecast median, anchored at the last known history value
  range: [number, number] | null // the interval band, anchored the same way
  [run: `run${number}`]: number | null // one key per unbroken history run, so gaps and dashes stay apart
}

/** HistoryRun is a stretch of known history drawn as one line, dashed when estimated or provisional. */
export interface HistoryRun {
  key: `run${number}`
  flagged: boolean
  from: string
  to: string
}

const flagged = (point: { is_estimated: boolean | null; is_provisional: boolean | null }) =>
  Boolean(point.is_estimated || point.is_provisional)

/**
 * forecastRows lays the county's history and forecast on one axis. History splits into runs at gaps and at changes
 * between published and flagged segments (a segment is flagged when either end is), each run under its own key, so
 * a dashed stretch is never drawn over a solid one and a gap is never bridged. The forecast starts from the last
 * history value when it is known, so median and band join the history line; straight segments keep medians and
 * bounds from overshooting the model's values.
 */
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

/** valueTicks returns round ticks from 0 to just over the largest history, median or interval value. */
export function valueTicks(county: CountyForecast, unit: ForecastUnit) {
  const known = county.history.flatMap((point) => point.value ?? [])
    .concat(county.forecast.flatMap((point) => [point.low, point.median, point.high]))
  const max = Math.max(1, ...known)
  const power = 10 ** Math.floor(Math.log10(max / 4))
  const step = Math.max(unit === 'percent' ? 0.1 : 1,
    ([1, 2, 2.5, 5, 10].find((factor) => factor * power >= max / 4) ?? 10) * power)
  const ceiling = Math.ceil(max / step) * step
  // Rounded, so 0.1 steps do not print as 0.30000000000000004.
  return Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => Math.round(index * step * 1e6) / 1e6)
}
