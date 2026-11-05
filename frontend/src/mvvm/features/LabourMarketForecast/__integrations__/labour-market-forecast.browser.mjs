import assert from 'node:assert/strict'
import { test } from 'node:test'
import { open, deliver } from '../../../../../test-support/mcp-host.mjs'
import { sample as forecastSample } from '../utils/sample.ts'

test('Chronos displays exact medians and intervals, preserves gaps and supports keyboard and pointer selection', async () => {
  const data = forecastSample()
  const county = data.counties[0]
  county.history[3].value = null
  county.history[4].is_estimated = true
  const { page, frame } = await open('labour-market-forecast', data)
  try {
    assert.equal(await frame.locator('[data-slot="forecast-row"]').count(), county.forecast.length)
    assert.equal(await frame.locator('[data-slot="forecast-band"]').count(), 1)
    assert.equal(await frame.locator('[data-slot="history-node"]').count(), county.history.length - 1)
    assert.equal(await frame.locator(`[data-slot="history-segment"][data-from="${county.history[2].period}"]`).count(), 0)
    assert.equal(await frame.locator(`[data-slot="history-segment"][data-from="${county.history[3].period}"]`).count(), 0)
    const slider = frame.getByRole('slider', { name: 'Mjesec prognoze' })
    await slider.focus()
    await slider.press('Home')
    await frame.waitForFunction(() => document.querySelector('[data-slot="forecast-cursor"]').dataset.period === '2026-10-01')
    assert.match(await frame.locator('[data-slot="forecast-median"]').textContent(), /2,6.*%/)
    assert.match(await frame.locator('[data-slot="forecast-interval"]').textContent(), /2,3.*2,9.*80%/)
    await slider.press('ArrowRight')
    await frame.waitForFunction(() => document.querySelector('[data-slot="forecast-cursor"]').dataset.period === '2026-11-01')
    // Hover previews the last period, leaving falls back to the selection, a click selects.
    const cursor = (period) => frame.waitForFunction((period) =>
      document.querySelector('[data-slot="forecast-cursor"]').dataset.period === period, period)
    const plot = await frame.locator('.forecast-plot').boundingBox()
    await page.mouse.move(plot.x + plot.width - 2, plot.y + plot.height / 2)
    await cursor('2027-03-01')
    assert.match(await frame.locator('[data-slot="forecast-median"]').textContent(), /2,7.*%/)
    assert.match(await frame.locator('[data-slot="forecast-period"]').textContent(), /ožujak 2027/)
    assert.match(await slider.getAttribute('aria-valuetext'), /studeni 2026/)
    await page.mouse.move(plot.x + plot.width / 2, plot.y - 200)
    await cursor('2026-11-01')
    await page.mouse.click(plot.x + plot.width - 2, plot.y + plot.height / 2)
    await page.mouse.move(plot.x + plot.width / 2, plot.y - 200)
    await cursor('2027-03-01')
    assert.match(await slider.getAttribute('aria-valuetext'), /ožujak 2027/)
    await frame.getByText('Povijesni podaci (24)', { exact: true }).click()
    assert.ok(await frame.getByRole('region', { name: 'Povijesne vrijednosti' }).getByText('procijenjeno', { exact: true }).count())
    // Grey history, dashed orange projection, in both themes.
    const strokes = () => frame.evaluate(() => ({
      history: getComputedStyle(document.querySelector('.forecast-observed')).stroke,
      forecast: getComputedStyle(document.querySelector('.forecast-predicted')).stroke,
      dashed: document.querySelector('.forecast-predicted').getAttribute('stroke-dasharray') !== null,
    }))
    assert.deepEqual(await strokes(), { history: 'rgb(113, 113, 122)', forecast: 'rgb(242, 100, 25)', dashed: true })
    await page.evaluate(() => window.setTheme('dark'))
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    assert.deepEqual(await strokes(), { history: 'rgb(161, 161, 170)', forecast: 'rgb(242, 100, 25)', dashed: true })
    const replacement = { ...data, title: 'Prognoza nije dostupna', unavailable_label: 'Potrebna su 24 mjeseca podataka.',
      counties: [{ ...county, forecast: [], change_to_horizon: null, unavailable_reason: 'not_enough_history' }] }
    await deliver(page, frame, replacement)
    await frame.getByText(replacement.unavailable_label, { exact: true }).waitFor()
    assert.equal(await frame.getByRole('slider').count(), 0)
    assert.equal(await frame.locator('[data-slot="forecast-row"], [data-slot="forecast-band"]').count(), 0)
    assert.ok(await frame.locator('[data-slot="history-node"]').count())
  } finally { await page.close() }
})

test('weekly Chronos counts render without percentages and empty histories show a reason', async () => {
  const data = forecastSample()
  data.title = 'Prognoza broja oglasa'
  data.target = 'job_ads'
  data.unit = 'ads'
  data.frequency = 'week'
  data.sex = null
  data.counties[0].forecast = [{ period: '2026-11-02', median: 120, low: 80, high: 170 }]
  const { page, frame } = await open('labour-market-forecast', data)
  try {
    assert.equal(await frame.locator('[data-slot="forecast-median"]').textContent(), '120')
    assert.match(await frame.locator('[data-slot="forecast-period"]').textContent(), /tjedan od 02\. 11\. 2026/)
    const empty = { ...data, title: 'Nema HZZ podataka', unavailable_label: 'HZZ oglasi nisu učitani.',
      counties: [{ ...data.counties[0], history: [], forecast: [], last_observed: null, change_to_horizon: null }] }
    await deliver(page, frame, empty)
    await frame.getByText(empty.unavailable_label, { exact: true }).waitFor()
    assert.equal(await frame.locator('[data-slot="forecast-chart"]').count(), 0)
    assert.equal(await frame.locator('table').count(), 0)
  } finally { await page.close() }
})
