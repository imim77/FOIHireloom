import assert from 'node:assert/strict'
import { test } from 'node:test'
import { open } from '../../../../../test-support/mcp-host.mjs'
import { sample as comparisonSample } from '../utils/sample.ts'

test('advertisement actions open the requested URL through the host', async () => {
  const data = comparisonSample()
  const { page, frame } = await open('job-comparison', data)
  try {
    await frame.getByRole('button', { name: /Otvori oglas/ }).first().click()
    await page.waitForFunction(() => window.links.length === 1)
    assert.deepEqual(await page.evaluate(() => window.links), [data.jobs[0].canonical_url])
  } finally { await page.close() }
})
