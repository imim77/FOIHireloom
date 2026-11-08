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
    assert.equal(await frame.locator('[data-slot="forecast-row"], .sources, .notes').count(), 0)
    await frame.getByRole('button', { name: 'Detalji, izvori i napomene' }).click()
    assert.equal(await frame.locator('[data-slot="forecast-row"]').count(), county.forecast.length)
    assert.equal(await frame.locator('.sources').count(), 1)
    assert.equal(await frame.locator('.forecast-band .recharts-area-area').count(), 1)
    assert.equal(await frame.locator('[data-slot="history-node"]').count(), county.history.length - 1)
    const runs = await frame.locator('[data-slot="history-run"]').evaluateAll((paths) =>
      paths.map((p) => ({ from: p.dataset.from, to: p.dataset.to, flagged: p.dataset.flagged === 'true' })))
    const gap = county.history[3].period
    assert.ok(runs.length > 1 && runs.every((run) => !(run.from <= gap && gap <= run.to)))
    assert.ok(runs.some((run) => run.flagged && run.from === county.history[4].period))
    const slider = frame.getByRole('slider', { name: 'Mjesec prognoze' })
    await slider.focus()
    await slider.press('Home')
    await frame.waitForFunction(() => document.querySelector('[data-slot="forecast-cursor"]').dataset.period === '2026-10-01')
    assert.match(await frame.locator('[data-slot="forecast-median"]').textContent(), /2,6.*%/)
    assert.match(await frame.locator('[data-slot="forecast-interval"]').textContent(), /2,3.*2,9.*80%/)
    assert.match(await frame.locator('[data-slot="forecast-summary"]').textContent(),
      /\+0,1\s?p\.\s?b\. u odnosu na rujan 2026\. \(privremeno\)/)
    await slider.press('ArrowRight')
    await frame.waitForFunction(() => document.querySelector('[data-slot="forecast-cursor"]').dataset.period === '2026-11-01')
    const cursor = (period) => frame.waitForFunction((period) =>
      document.querySelector('[data-slot="forecast-cursor"]').dataset.period === period, period)
    const plot = await frame.locator('.forecast-plot').boundingBox()
    await page.mouse.move(plot.x + plot.width - 8, plot.y + plot.height / 2)
    await cursor('2027-03-01')
    assert.match(await frame.locator('[data-slot="forecast-median"]').textContent(), /2,7.*%/)
    assert.match(await frame.locator('[data-slot="forecast-period"]').textContent(), /ožujak 2027/)
    assert.match(await slider.getAttribute('aria-valuetext'), /studeni 2026/)
    await page.mouse.move(plot.x + plot.width / 2, plot.y - 200)
    await cursor('2026-11-01')
    await page.mouse.click(plot.x + plot.width - 8, plot.y + plot.height / 2)
    await page.mouse.move(plot.x + plot.width / 2, plot.y - 200)
    await cursor('2027-03-01')
    assert.match(await slider.getAttribute('aria-valuetext'), /ožujak 2027/)
    assert.ok(await frame.getByRole('region', { name: 'Povijesne vrijednosti' }).getByText('procijenjeno', { exact: true }).count())
    const strokes = () => frame.evaluate(() => ({
      history: getComputedStyle(document.querySelector('.forecast-observed .recharts-curve')).stroke,
      forecast: getComputedStyle(document.querySelector('.forecast-predicted .recharts-curve')).stroke,
      dashed: document.querySelector('.forecast-predicted .recharts-curve').getAttribute('stroke-dasharray') !== null,
    }))
    assert.deepEqual(await strokes(), { history: 'rgb(110, 110, 110)', forecast: 'rgb(251, 41, 14)', dashed: true })
    await page.evaluate(() => window.setTheme('dark'))
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    assert.deepEqual(await strokes(), { history: 'rgb(154, 154, 154)', forecast: 'rgb(251, 41, 14)', dashed: true })
    assert.match(await frame.evaluate(() => getComputedStyle(document.querySelector('.forecast-band .recharts-area-area')).fill),
      /0\.984314 0\.160784 0\.054902 \/ 0\.4\)$/)
    const replacement = { ...data, title: 'Prognoza nije dostupna', unavailable_label: 'Potrebna su 24 mjeseca podataka.',
      counties: [{ ...county, forecast: [], change_to_horizon: null, unavailable_reason: 'not_enough_history' }] }
    await deliver(page, frame, replacement)
    await frame.getByText(replacement.unavailable_label, { exact: true }).waitFor()
    assert.equal(await frame.getByRole('slider').count(), 0)
    assert.equal(await frame.locator('[data-slot="forecast-row"], .forecast-band').count(), 0)
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
