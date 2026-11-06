import assert from 'node:assert/strict'
import { test } from 'node:test'
import { forecastChart, formatChange, formatPeriod, formatPeriodGenitive, formatValue } from './forecast-chart.ts'
import { sample } from './sample.ts'

test('the chart includes interval extremes, preserves missing observations and stays within its bounds', () => {
  const county = sample().counties[0]
  county.history[3].value = null
  county.forecast[0] = { ...county.forecast[0], low: 0, high: 100 }
  for (const width of [80, 220, 700]) {
    const chart = forecastChart(county, width, 'percent')
    assert.equal(chart.history[3].y, null)
    assert.equal(chart.forecast[0].highY, chart.top)
    assert.equal(chart.forecast[0].lowY, chart.bottom)
    for (const p of [...chart.history, ...chart.forecast]) {
      assert.ok(p.x >= 0 && p.x <= width)
      if (p.y !== null) assert.ok(p.y >= chart.top && p.y <= chart.bottom)
    }
    assert.ok(!/NaN|Infinity/.test(chart.band + chart.median))
  }
})

test('zero and one-period forecasts have a usable scale, and missing history is not connected to a prediction', () => {
  const county = sample().counties[0]
  county.history = county.history.slice(-1).map((p) => ({ ...p, value: null }))
  county.forecast = [{ ...county.forecast[0], median: 0, low: 0, high: 0 }]
  const chart = forecastChart(county, 240, 'ads')
  assert.equal(chart.band, '')
  assert.equal(chart.median, `M${chart.forecast[0].x},${chart.forecast[0].y}`)
  assert.ok(chart.ticks.length >= 2)
  assert.ok(!/NaN|Infinity/.test(chart.median))
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
