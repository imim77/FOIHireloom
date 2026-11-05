import { formatDay, formatInteger, formatMonth, formatPoints, formatRate } from '../../shared/format.ts'
import type { CountyForecast, ForecastFrequency, ForecastUnit } from './types.ts'

export const formatValue = (value: number, unit: ForecastUnit) =>
  unit === 'percent' ? formatRate(value) : formatInteger(value)

export const formatPeriod = (period: string, frequency: ForecastFrequency) =>
  frequency === 'month' ? formatMonth(period) : `tjedan od ${formatDay(period)}`

export function formatChange(value: number, unit: ForecastUnit) {
  if (unit === 'percent') return formatPoints(value)
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${formatInteger(Math.abs(value))} ${unit === 'persons' ? 'osoba' : 'oglasa'}`
}

/** Forecast geometry uses straight segments so neither medians nor interval bounds overshoot model values. */
export function forecastChart(county: CountyForecast, width: number, unit: ForecastUnit) {
  const height = 240
  const top = 12
  const bottom = height - 12
  const edge = 6
  const total = county.history.length + county.forecast.length
  const known = county.history.flatMap((point) => point.value ?? [])
    .concat(county.forecast.flatMap((point) => [point.low, point.median, point.high]))
  const max = Math.max(1, ...known)
  const power = 10 ** Math.floor(Math.log10(max / 4))
  const step = Math.max(unit === 'percent' ? 0.1 : 1,
    ([1, 2, 2.5, 5, 10].find((factor) => factor * power >= max / 4) ?? 10) * power)
  const ceiling = Math.ceil(max / step) * step
  const ticks = Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => index * step)
  const x = (index: number) => total > 1 ? edge + index / (total - 1) * (width - 2 * edge) : width / 2
  const y = (value: number) => bottom - value / ceiling * (bottom - top)
  const history = county.history.map((point, index) => ({ ...point, x: x(index), y: point.value === null ? null : y(point.value) }))
  const forecast = county.forecast.map((point, index) => ({ ...point, x: x(county.history.length + index),
    y: y(point.median), lowY: y(point.low), highY: y(point.high) }))
  const last = history.at(-1)
  const anchor = last?.value != null ? [{ x: last.x, y: last.y!, lowY: last.y!, highY: last.y! }] : []
  const predicted = [...anchor, ...forecast]
  const path = (points: { x: number; y: number }[]) => points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')
  const band = predicted.length > 1 ? `${path(predicted.map((p) => ({ x: p.x, y: p.highY })))} ${
    [...predicted].reverse().map((p) => `L${p.x},${p.lowY}`).join(' ')} Z` : ''
  return { height, top, bottom, ticks, y, history, forecast, median: path(predicted), band,
    boundary: last?.x ?? 0 }
}
