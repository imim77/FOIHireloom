import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createServer } from 'vite'
import { chromium } from 'playwright'

test('Vite serves every preview URL and its MVVM modules', async () => {
  const server = await createServer({
    logLevel: 'error',
    server: { host: '127.0.0.1', port: 0 },
  })
  let browser
  const errors = []
  try {
    await server.listen()
    const base = `http://127.0.0.1:${server.httpServer.address().port}`
    browser = await chromium.launch({ headless: true })
    for (const view of ['job-cards', 'job-comparison', 'county-comparison', 'jobs-by-county',
      'unemployment-history', 'accommodation-comparison', 'labour-market-forecast']) {
      const page = await browser.newPage({ reducedMotion: 'reduce' })
      try {
        page.on('pageerror', (error) => errors.push(`${view}: ${error.message}`))
        const response = await page.goto(`${base}/${view}.html`)
        assert.equal(response.status(), 200, view)
        await page.locator('.card .title').waitFor()
        assert.ok(await page.locator('.card .body').textContent(), view)
      } finally { await page.close() }
    }
    assert.deepEqual(errors, [])
  } finally {
    await browser?.close()
    await server.close()
  }
})
