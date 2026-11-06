import assert from 'node:assert/strict'
import { test } from 'node:test'
import { open, deliver } from '../../../../../test-support/mcp-host.mjs'

test('county ranking preserves its metric, keyboard selection and expansion across new results', async () => {
  const data = {
    title: 'Traženi radnici', description: 'Usporedba županija', metric: 'workers_needed', top: 2,
    total_jobs: 6, total_workers_needed: 60, coverage: { warning: null }, active_filters: [],
    coverage_note: null, unknown_note: null,
    counties: [
      { name: 'Prva', short_name: 'Prva', jobs: 3, workers_needed: 30, share: 50 },
      { name: 'Druga', short_name: 'Druga', jobs: 2, workers_needed: 20, share: 33.3 },
      { name: 'Treća', short_name: 'Treća', jobs: 1, workers_needed: 10, share: 16.7 },
    ],
  }
  const { page, frame } = await open('jobs-by-county', data)
  try {
    const columns = frame.locator('[data-slot="column"]')
    assert.equal(await columns.count(), 2)
    assert.deepEqual(await frame.locator('[data-slot="value-text"]').allTextContents(), ['30', '20'])
    await columns.first().focus()
    await columns.first().press('End')
    assert.equal(await columns.nth(1).getAttribute('aria-pressed'), 'true')
    assert.equal(await columns.nth(1).evaluate((el) => el === document.activeElement), true)
    await frame.getByRole('button', { name: 'Prikaži svih 3 županija' }).click()
    assert.equal(await columns.count(), 3)
    await columns.nth(1).focus()
    await columns.nth(1).press('End')
    assert.equal(await columns.nth(2).getAttribute('aria-pressed'), 'true')
    await deliver(page, frame, { ...data, title: 'Nova potražnja' })
    assert.equal(await columns.count(), 3, 'expansion survives a replacement host result')
    assert.equal(await columns.first().getAttribute('aria-pressed'), 'true', 'selection starts a fresh session')
    await frame.getByRole('button', { name: 'Prikaži manje županija' }).click()
    assert.equal(await columns.count(), 2)
  } finally { await page.close() }
})
