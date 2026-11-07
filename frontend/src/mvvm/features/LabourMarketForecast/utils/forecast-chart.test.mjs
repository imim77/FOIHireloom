import assert from 'node:assert/strict'
import { test } from 'node:test'
import { forecastRows, formatChange, formatPeriod, formatPeriodGenitive, formatValue, valueTicks } from './forecast-chart.ts'
import { sample } from './sample.ts'

test('rows keep every value, leave gaps open and split history into solid and dashed runs', () => {
  const county = sample().counties[0]
  county.history[3].value = null
  county.history = county.history.map((p, i) => ({ ...p, is_provisional: i >= 15 }))
  county.forecast[0] = { ...county.forecast[0], low: 0, high: 100 }
  const { rows, runs } = forecastRows(county)
  assert.equal(rows.length, county.history.length + county.forecast.length)
  assert.deepEqual(rows.slice(0, county.history.length).map((row) => row.value), county.history.map((p) => p.value))
  // The gap at 3 ends one run and starts the next; the first provisional month starts a dashed run.
  assert.deepEqual(runs.map((run) => [run.flagged, run.from, run.to]), [
    [false, county.history[0].period, county.history[2].period],
    [false, county.history[4].period, county.history[14].period],
    [true, county.history[14].period, county.history.at(-1).period],
  ])
  for (const run of runs) {
    const months = rows.flatMap((row, index) => typeof row[run.key] === 'number' ? [index] : [])
    for (let i = 1; i < months.length; i++) assert.equal(months[i] - months[i - 1], 1, 'a run never bridges a gap')
  }
  // The forecast joins the last known history value; its rows carry the model's medians and intervals unchanged.
  const anchor = rows[county.history.length - 1]
  assert.deepEqual([anchor.median, anchor.range], [county.history.at(-1).value, [county.history.at(-1).value, county.history.at(-1).value]])
  assert.deepEqual(rows.slice(county.history.length).map((row) => [row.median, ...row.range]),
    county.forecast.map((p) => [p.median, p.low, p.high]))
  assert.equal(valueTicks(county, 'percent').at(-1) >= 100, true)
})

test('zero and one-period forecasts have a usable scale, and missing history is not connected to a prediction', () => {
  const county = sample().counties[0]
  county.history = county.history.slice(-1).map((p) => ({ ...p, value: null }))
  county.forecast = [{ ...county.forecast[0], median: 0, low: 0, high: 0 }]
  const { rows, runs } = forecastRows(county)
  assert.deepEqual(runs, [])
  assert.deepEqual([rows[0].median, rows[0].range], [null, null])
  assert.ok(valueTicks(county, 'ads').length >= 2)
  assert.ok(valueTicks(county, 'ads').every(Number.isFinite))
})

test('units and time labels distinguish rates, people and weekly advertisements', () => {
  assert.match(formatValue(2.5, 'percent'), /2,5.*%/)
  assert.equal(formatValue(1250, 'persons'), '1.250')
  assert.equal(formatValue(0, 'ads'), '0')
  assert.match(formatChange(-0.4, 'percent'), /−0,4.*p\..*b\./)
  assert.equal(formatChange(15, 'persons'), '+15 osoba')
  assert.equal(formatPeriod('2026-09-01', 'month'), 'rujan 2026.')
  assert.equal(formatPeriod('2026-11-02', 'week'), 'tjedan od 02. 11. 2026.')
})

test('periods after "do" take the genitive', () => {
  assert.equal(formatPeriodGenitive('2027-03-01', 'month'), 'ožujka 2027.')
  assert.equal(formatPeriodGenitive('2026-11-01', 'month'), 'studenoga 2026.')
  assert.equal(formatPeriodGenitive('2026-11-02', 'week'), 'tjedna od 02. 11. 2026.')
})
