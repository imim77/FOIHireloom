import assert from 'node:assert/strict'
import { test } from 'node:test'
import { open, deliver, request, reply } from '../../../../../test-support/mcp-host.mjs'
import { sample as countySample } from '../utils/sample.ts'

test('county filter calls preserve counties and period, recover from errors and ignore stale replies', async () => {
  const data = countySample()
  data.requested_period = '2026-09-01'
  data.filters.include_expired = true
  data.active_filters = [{ argument: 'include_expired', label: 'istekli oglasi' }]
  const { page, frame } = await open('county-comparison', data)
  try {
    const remove = frame.getByRole('button', { name: 'Ukloni filtar istekli oglasi' })
    await remove.click()
    const first = await request(page, 1)
    assert.equal(first.name, 'show_county_comparison')
    assert.deepEqual(first.arguments, { ...data.filters, include_expired: false,
      counties: data.counties.map((county) => county.code), period: '2026-09' })
    await page.evaluate(() => window.reply(0, { content: [], isError: true }))
    await frame.getByText('Usporedba se nije mogla učitati.').waitFor()
    assert.equal(await remove.isEnabled(), true)
    await remove.click()
    await request(page, 2)
    const filtered = { ...data, title: 'Bez isteklih oglasa', active_filters: [] }
    await reply(page, 1, filtered)
    await frame.getByText(filtered.title, { exact: true }).waitFor()
    assert.equal(await frame.locator('.filters').count(), 0)
    assert.equal(await frame.getByText('Usporedba se nije mogla učitati.').count(), 0)
    await deliver(page, frame, data)
    await remove.click()
    await request(page, 3)
    await deliver(page, frame, { ...data, title: 'Nova usporedba' })
    await reply(page, 2, filtered)
    await page.evaluate(() => window.setTheme('dark'))
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    assert.equal(await frame.locator('.title').textContent(), 'Nova usporedba')
    assert.equal(await remove.isEnabled(), true)
  } finally { await page.close() }
})
