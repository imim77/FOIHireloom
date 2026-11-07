import assert from 'node:assert/strict'
import { test } from 'node:test'
import { views, pageFor, open, deliver } from '../test-support/mcp-host.mjs'
import { sample as countySample } from '../src/mvvm/features/CountyComparison/utils/sample.ts'
import { sample as forecastSample } from '../src/mvvm/features/LabourMarketForecast/utils/sample.ts'
import { sample as historySample } from '../src/mvvm/features/UnemploymentHistory/utils/sample.ts'
import { sample as accommodationSample } from '../src/mvvm/features/AccommodationComparison/utils/sample.ts'
import { sample as jobSample } from '../src/mvvm/features/JobCards/utils/sample.ts'

test('loading placeholders give way to accessible shadcn controls at mobile width', async () => {
  const page = await pageFor('/?view=job-cards', 320)
  try {
    await page.waitForFunction(() => window.ready)
    const frame = page.frames().find((frame) => frame.url().includes('/view/'))
    await frame.locator('.card[aria-busy="true"]').waitFor()
    assert.equal(await frame.locator('[data-slot="skeleton"]').count(), 2)
    await deliver(page, frame, jobSample())
    await frame.locator('.card[aria-busy="false"]').waitFor()
    assert.equal(await frame.locator('[data-slot="skeleton"]').count(), 0)
    const checkbox = frame.getByRole('checkbox').first()
    await checkbox.focus()
    await checkbox.press('Space')
    assert.equal(await checkbox.isChecked(), true)
    assert.equal(await frame.getByRole('button', { name: 'Usporedi odabrane (1)' }).isDisabled(), true)
    assert.equal(await frame.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  } finally { await page.close() }
})

test('all standalone previews render with shared styling and both themes at mobile width', async () => {
  for (const view of views) {
    const page = await pageFor(`/view/${view}`, 320)
    try {
      await page.locator('.card .title').waitFor()
      assert.ok(await page.locator('.card .body').textContent(), view)
      const layout = await page.locator('.card').evaluate((card) => ({
        card: getComputedStyle(card).display,
        header: getComputedStyle(card.querySelector('.header')).display,
        body: getComputedStyle(card.querySelector('.body')).display,
        font: getComputedStyle(card.querySelector('.title')).fontSize,
      }))
      assert.deepEqual(layout, { card: 'flex', header: 'flex', body: 'flex', font: '16px' }, view)
      if (view === 'job-comparison') {
        assert.deepEqual(await page.locator('.verdict.no_match').first().evaluate((badge) => ({
          background: getComputedStyle(badge).backgroundColor, color: getComputedStyle(badge).color,
        })), { background: 'rgb(255, 244, 229)', color: 'rgb(154, 77, 0)' })
        assert.equal(await page.locator('.cell.expired .cell-text').first()
          .evaluate((text) => getComputedStyle(text).fontWeight), '500')
      }
      await page.evaluate(() => { document.documentElement.dataset.theme = 'dark' })
      assert.equal(await page.locator('.card').evaluate((card) => getComputedStyle(card).color),
        'rgb(244, 244, 244)', view)
      await page.evaluate(() => { document.documentElement.dataset.theme = 'light' })
      assert.equal(await page.locator('.card').evaluate((card) => getComputedStyle(card).color),
        'rgb(25, 25, 25)', view)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, view)
    } finally { await page.close() }
  }
})

test('source callbacks open the requested URLs through the host', async () => {
  for (const [view, data] of [
    ['county-comparison', countySample()], ['unemployment-history', historySample()],
    ['accommodation-comparison', accommodationSample()], ['labour-market-forecast', forecastSample()],
  ]) {
    const { page, frame } = await open(view, data)
    try {
      // The forecast keeps its sources behind its details control.
      if (view === 'labour-market-forecast') await frame.getByRole('button', { name: 'Detalji, izvori i napomene' }).click()
      const source = frame.locator('.sources button').first()
      const url = await source.getAttribute('title')
      await source.click()
      await page.waitForFunction(() => window.links.length === 1)
      assert.deepEqual(await page.evaluate(() => window.links), [url], view)
    } finally { await page.close() }
  }
})
