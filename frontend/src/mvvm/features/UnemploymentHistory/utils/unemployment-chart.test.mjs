import assert from 'node:assert/strict'
import { test } from 'node:test'
import { provisionalBands, seriesRuns, toGrowthData } from './chart-data.ts'
import { areaPath, curvePath, curveSegments, monthTicks, rateAxis } from './chart-geometry.ts'
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
  for (const run of runs) {
    const coords = run.indices.map((index) => ({ x: index * 10, y: data.points[index].values[data.series[0].id].rate }))
    assert.equal(areaPath(coords, 100).includes('NaN'), false)
    if (run.indices.length === 1) assert.equal(areaPath(coords, 100), '')
    for (let i = 1; i < run.indices.length; i++) assert.equal(run.indices[i] - run.indices[i - 1], 1)
  }
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

test('smoothing cannot overshoot endpoints, including abrupt peaks, zeros and flat segments', () => {
  for (const values of [[0, 10, 0, 8, 0], [2, 2, 2, 2], [1, 1.1, 9, 9.1], [9, 7, 3, 0], [0]]) {
    const points = values.map((y, index) => ({ x: index * 20, y }))
    for (const { from, c1, c2, to } of curveSegments(points)) {
      for (let i = 0; i <= 100; i++) {
        const t = i / 100
        const u = 1 - t
        const y = u ** 3 * from.y + 3 * u ** 2 * t * c1.y + 3 * u * t ** 2 * c2.y + t ** 3 * to.y
        assert.ok(y >= Math.min(from.y, to.y) - 1e-10 && y <= Math.max(from.y, to.y) + 1e-10)
      }
    }
    assert.doesNotMatch(curvePath(points), /NaN|Infinity/)
  }
  assert.equal(curvePath([]), '')
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
