import assert from 'node:assert/strict'
import { test } from 'node:test'
import { growthRows, provisionalBands, seriesRuns, toGrowthData } from './chart-data.ts'
import { monthTicks, rateAxis } from './chart-geometry.ts'
import { sample } from './sample.ts'
import { formatPoints, formatRate } from '../../../utils/format.ts'

test('all source rates and metadata survive adaptation, without mutating the tool result', () => {
  const source = sample()
  const before = structuredClone(source)
  const data = toGrowthData(source.counties)
  assert.equal(data.points.length, source.months)
  assert.deepEqual(data.series.map((s) => s.id), source.counties.map((c) => c.code))
  for (const county of source.counties) {
    for (const point of county.series) {
      assert.deepEqual(data.points.find((p) => p.period === point.period).values[county.code], point)
    }
  }
  assert.deepEqual(source, before)
})

test('two counties retain monthly resolution and alignment when rows arrive in different orders', () => {
  const source = sample().counties.slice(0, 2)
  source[1].series.reverse()
  const removed = source[1].series.splice(4, 1)[0]
  const data = toGrowthData(source)
  assert.equal(data.series.length, 2)
  assert.equal(data.points.length, 24)
  assert.deepEqual(data.points.map((p) => p.period), source[0].series.map((p) => p.period))
  assert.equal(data.points.find((p) => p.period === removed.period).values[source[1].code].rate, null)
  for (const point of source[1].series) {
    assert.equal(data.points.find((p) => p.period === point.period).values[source[1].code].rate, point.rate)
  }
})

function dataWithRates(rates, provisional = []) {
  const county = sample().counties[0]
  county.series = county.series.slice(0, rates.length).map((point, index) => ({
    ...point, rate: rates[index], is_provisional: provisional.includes(index),
  }))
  return toGrowthData([county])
}

test('nulls break both the curve and its fill; actual zero and isolated known months remain', () => {
  const data = dataWithRates([0, 1, null, 2, null, 3, 4])
  const runs = seriesRuns(data.points, data.series[0].id)
  assert.deepEqual(runs.map((run) => run.indices), [[0, 1], [3], [5, 6]])
  assert.equal(data.points[0].values[data.series[0].id].rate, 0)
  const { rows, runs: drawn } = growthRows(data)
  assert.deepEqual(drawn[0].map((run) => rows.flatMap((row) => typeof row[run.key] === 'number' ? [row.index] : [])),
    [[0, 1], [5, 6]])
  assert.deepEqual(rows.map((row) => row.s0), [0, 1, null, 2, null, 3, 4])
})

test('dashed and solid runs meet at their shared month without overlapping', () => {
  const data = dataWithRates([1, 2, 3, 4, 5], [2])
  const { rows, runs } = growthRows(data)
  assert.deepEqual(runs[0].map((run) => [run.provisional, run.from, run.to]), [
    [false, data.points[0].period, data.points[1].period],
    [true, data.points[1].period, data.points[3].period],
    [false, data.points[3].period, data.points[4].period],
  ])
  assert.deepEqual(runs[0].map((run) => rows.filter((row) => typeof row[run.key] === 'number').length), [2, 3, 2])
})

test('provisional segments retain dashes on both sides of a provisional point', () => {
  const data = dataWithRates([1, 2, 3, 4, 5], [2])
  assert.deepEqual(seriesRuns(data.points, data.series[0].id), [
    { provisional: false, indices: [0, 1] },
    { provisional: true, indices: [1, 2, 3] },
    { provisional: false, indices: [3, 4] },
  ])
  assert.deepEqual(provisionalBands(data.points), [{ first: 2, last: 2 }])
})

test('provisional bands can be disjoint and use flags rather than a hardcoded year', () => {
  const data = dataWithRates([1, 2, 3, 4, 5, 6], [0, 1, 4])
  assert.deepEqual(provisionalBands(data.points), [{ first: 0, last: 1 }, { first: 4, last: 4 }])
})

test('no-data series never create zero-valued lines', () => {
  const data = dataWithRates([null, null, null])
  assert.deepEqual(seriesRuns(data.points, data.series[0].id), [])
  assert.deepEqual(toGrowthData([]), { series: [], points: [] })
})

test('six counties keep their ids, names and the original request order', () => {
  const county = sample().counties[0]
  const counties = Array.from({ length: 6 }, (_, index) => ({ ...county, code: `county-${index}`, short_name: `K${index}` }))
  const data = toGrowthData(counties)
  assert.deepEqual(data.series, counties.map((county) => ({ id: county.code, label: county.name, shortLabel: county.short_name })))
})

test('axis has a finite, nonzero range for empty, zero, constant and ordinary rates', () => {
  for (const values of [[], [0], [0, 0], [2.3, 2.3], [0, 100], [NaN, Infinity]]) {
    const axis = rateAxis(values)
    assert.equal(axis.low, 0)
    assert.ok(axis.high > axis.low)
    assert.ok(axis.ticks.every(Number.isFinite))
    for (const value of values.filter(Number.isFinite)) assert.ok(value >= axis.low && value <= axis.high)
  }
})

test('labels always include the last month on narrow and wide plots', () => {
  for (const count of [1, 12, 24]) {
    for (const width of [1, 200, 500, 900]) {
      assert.equal(monthTicks(count, width).at(-1), count - 1)
    }
  }
  assert.deepEqual(monthTicks(0, 200), [])
})

test('formatting preserves percent units and the existing year-on-year percentage points', () => {
  assert.equal(formatRate(2.3), '2,3\u00a0%')
  assert.equal(formatRate(0), '0,0\u00a0%')
  assert.equal(formatPoints(-0.6), '−0,6\u00a0p.\u00a0b.')
})
