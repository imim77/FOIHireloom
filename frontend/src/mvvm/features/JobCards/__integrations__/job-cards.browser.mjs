import assert from 'node:assert/strict'
import { test } from 'node:test'
import { open, deliver, request, reply, countCards } from '../../../../../test-support/mcp-host.mjs'
import { sample as jobSample } from '../utils/sample.ts'

test('hosts without capabilities show filters and omit tool and message controls', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data, true)
  try {
    await countCards(frame, data.jobs.length)
    assert.equal(await frame.locator('.filter').count(), data.active_filters.length)
    assert.equal(await frame.locator('.filter-remove, .compare-toggle').count(), 0)
    assert.equal(await frame.getByRole('button', { name: 'Pitaj o ovom oglasu' }).count(), 0)
    assert.equal(await frame.getByRole('button', { name: 'Prikaži još oglasa' }).count(), 0)
  } finally { await page.close() }
})

test('pagination deduplicates ads; removing a filter clears extra pages and comparison picks', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data)
  try {
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).click()
    const moreRequest = await request(page, 1)
    assert.equal(moreRequest.name, 'show_jobs')
    assert.deepEqual(moreRequest.arguments, { ...data.filters, cursor: data.next_cursor })
    assert.equal(await frame.locator('.filter-remove:disabled').count(), data.active_filters.length)
    const next = { ...data, jobs: [data.jobs[0], { ...data.jobs[0], id: 99 }], next_cursor: null }
    await reply(page, 0, next)
    await countCards(frame, data.jobs.length + 1)
    assert.equal(await frame.locator('[data-id="1"]').count(), 1)
    assert.equal(await frame.getByRole('button', { name: 'Prikaži još oglasa' }).count(), 0)
    await frame.getByRole('checkbox').first().check()
    await frame.getByRole('checkbox').nth(1).check()
    const filter = data.active_filters[0]
    await frame.getByRole('button', { name: `Ukloni filtar ${filter.label}` }).click()
    assert.deepEqual((await request(page, 2)).arguments,
      { ...data.filters, [filter.argument]: null, cursor: null })
    const filtered = { ...data, title: 'Bez filtra', jobs: [data.jobs[0]],
      active_filters: data.active_filters.slice(1), next_cursor: null }
    await reply(page, 1, filtered)
    await frame.getByText(filtered.title, { exact: true }).waitFor()
    await countCards(frame, 1)
    assert.equal(await frame.locator('.compare-bar').count(), 0)
    assert.equal(await frame.getByRole('checkbox').isChecked(), false)
    await frame.getByRole('button', { name: 'Prikaži oglase preko cijelog zaslona' }).waitFor({ state: 'detached' })
  } finally { await page.close() }
})

test('comparison keeps selection order, enforces three ads and sends a host message', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data)
  try {
    const picks = frame.getByRole('checkbox')
    for (const index of [2, 0, 1]) await picks.nth(index).check()
    assert.equal(await picks.nth(3).isDisabled(), true)
    // Picked cards are the view's only red: accent-500, #fb290e.
    assert.equal(await frame.locator('.job.compared').count(), 3)
    // After the checkbox's colour transition, which reduced motion does not skip.
    assert.equal(await picks.first().evaluate(async (box) => {
      await Promise.all(box.getAnimations().map((animation) => animation.finished))
      return getComputedStyle(box).backgroundColor
    }), 'rgb(251, 41, 14)')
    await frame.getByRole('button', { name: 'Usporedi odabrane (3)' }).click()
    await page.waitForFunction(() => window.messages.length === 1)
    const message = await page.evaluate(() => window.messages[0])
    assert.equal(message.role, 'user')
    assert.deepEqual([...message.content[0].text.matchAll(/id (\d+)/g)].map((match) => Number(match[1])), [3, 1, 2])
    await frame.locator('.compare-bar').waitFor({ state: 'detached' })
    assert.equal(await picks.nth(3).isDisabled(), false)
    await frame.getByRole('button', { name: 'Prikaži oglase preko cijelog zaslona' }).click()
    assert.equal(await frame.locator('.job-list.expanded').count(), 1)
  } finally { await page.close() }
})

test('replacement host results ignore pending job replies and reset request and selection state', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data)
  try {
    await frame.getByRole('checkbox').first().check()
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).click()
    await request(page, 1)
    const replacement = { ...data, title: 'Novi rezultat', jobs: data.jobs.slice(0, 2) }
    await deliver(page, frame, replacement)
    await countCards(frame, 2)
    assert.equal(await frame.locator('.compare-bar').count(), 0)
    assert.equal(await frame.getByRole('button', { name: 'Prikaži još oglasa' }).isEnabled(), true)
    await reply(page, 0, { ...data, jobs: [{ ...data.jobs[0], id: 999 }] })
    // A following request/reply round trip also flushes the earlier reply.
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).click()
    await request(page, 2)
    await reply(page, 1, { ...replacement, jobs: [], next_cursor: null })
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).waitFor({ state: 'detached' })
    assert.equal(await frame.locator('[data-id="999"]').count(), 0)
    assert.equal(await frame.locator('[data-slot="job"]').count(), 2)
    assert.equal(await frame.locator('.title').textContent(), replacement.title)
  } finally { await page.close() }
})

test('a failed job request retains cards and comparison picks and can be retried', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data)
  try {
    await frame.getByRole('checkbox').first().check()
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).click()
    await request(page, 1)
    await page.evaluate(() => window.reply(0, { content: [], isError: true }))
    await frame.getByText('Oglasi se nisu mogli učitati.').waitFor()
    await countCards(frame, data.jobs.length)
    assert.equal(await frame.getByRole('checkbox').first().isChecked(), true)
    assert.equal(await frame.getByRole('button', { name: 'Usporedi odabrane (1)' }).isDisabled(), true)
    await frame.getByRole('button', { name: 'Prikaži još oglasa' }).click()
    assert.deepEqual((await request(page, 2)).arguments, { ...data.filters, cursor: data.next_cursor })
    await reply(page, 1, { ...data, jobs: [{ ...data.jobs[0], id: 999 }], next_cursor: null })
    await countCards(frame, data.jobs.length + 1)
    assert.equal(await frame.getByText('Oglasi se nisu mogli učitati.').count(), 0)
    assert.equal(await frame.getByRole('checkbox').first().isChecked(), true)
  } finally { await page.close() }
})

test('a rejected comparison message preserves picks until a successful retry', async () => {
  const { page, frame } = await open('job-cards', jobSample())
  try {
    await page.evaluate(() => { window.failMessage = true })
    await frame.getByRole('checkbox').nth(0).check()
    await frame.getByRole('checkbox').nth(1).check()
    await frame.getByRole('button', { name: 'Usporedi odabrane (2)' }).click()
    await frame.getByText('Poruka nije poslana.').waitFor()
    assert.equal(await frame.getByRole('checkbox').nth(0).isChecked(), true)
    assert.equal(await frame.getByRole('checkbox').nth(1).isChecked(), true)
    await page.evaluate(() => { window.failMessage = false })
    await frame.getByRole('button', { name: 'Usporedi odabrane (2)' }).click()
    await page.waitForFunction(() => window.messages.length === 2)
    await frame.locator('.compare-bar').waitFor({ state: 'detached' })
    assert.equal(await frame.getByText('Poruka nije poslana.').count(), 0)
  } finally { await page.close() }
})

test('advertisement actions open the requested URL through the host', async () => {
  const data = jobSample()
  const { page, frame } = await open('job-cards', data)
  try {
    await frame.getByRole('button', { name: /Otvori oglas/ }).first().click()
    await page.waitForFunction(() => window.links.length === 1)
    assert.deepEqual(await page.evaluate(() => window.links), [data.jobs[0].canonical_url])
  } finally { await page.close() }
})
