import assert from 'node:assert/strict'
import { before, after, test } from 'node:test'
import { createServer } from 'node:http'
import { mkdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { sample } from '../utils/sample.ts'
import { INNER, layoutRing } from '../utils/ring-geometry.ts'

// A minimal MCP Apps host sends actual protocol messages into the built page; no app-state injection.
const host = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">
<script>
window.ready=false;
function post(message){document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',...message},'*');}
window.sendResult=data=>{post({method:'ui/notifications/tool-input',params:{arguments:{county:'varazdinska',query:'kuhar'}}});post({method:'ui/notifications/tool-result',params:{content:[],structuredContent:data}});};
window.setTheme=theme=>post({method:'ui/notifications/host-context-changed',params:{theme}});
addEventListener('message',event=>{
 const iframe=document.querySelector('iframe');if(event.source!==iframe.contentWindow)return;const m=event.data;
 if(m.method==='ui/initialize')post({id:m.id,result:{protocolVersion:m.params.protocolVersion,hostInfo:{name:'Chart tests',version:'1.0'},hostCapabilities:{},hostContext:{theme:'light',displayMode:'inline'}}});
 else if(m.method==='ui/notifications/initialized')window.ready=true;
 else if(m.method==='ui/notifications/size-changed'&&m.params.height)iframe.style.height=m.params.height+'px';
 else if(m.id!==undefined)post({id:m.id,result:{}});
});
</script><iframe src="/view" title="Usporedba smještaja" style="width:100%;height:1200px;border:0;display:block" onload="if(location.search.includes('hidden'))this.style.display='none'"></iframe></body></html>`

let server, browser, base
const errors = [], remote = []
before(async () => {
  const html = await readFile(new URL('../../../../../dist/accommodation-comparison.html', import.meta.url), 'utf8')
  server = createServer((req, res) => { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(req.url === '/view' ? html : host) })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  base = `http://127.0.0.1:${server.address().port}`
  browser = await chromium.launch({ headless: true })
})
after(async () => {
  await browser?.close()
  if (server) await new Promise((resolve) => server.close(resolve))
  assert.deepEqual(errors, [], 'No browser errors')
  assert.deepEqual(remote, [], 'No external assets')
})
async function open(width = 560, options = {}, query = '') {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, ...options })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('request', (request) => { if (!request.url().startsWith(base)) remote.push(request.url()) })
  await page.goto(base + query)
  await page.waitForFunction(() => window.ready)
  assert.equal(await page.evaluate(() => innerWidth), width)
  return { page, frame: page.frames().find((f) => f.url().endsWith('/view')) }
}
async function deliver(page, frame, data) {
  await page.evaluate((data) => window.sendResult(data), data)
  if (!data.total_jobs) { await frame.getByText('Nema oglasa za zadane filtre.').waitFor(); return }
  await frame.waitForFunction((data) => {
    const counts = [...document.querySelectorAll('.allocation-legend-count')].map((el) => Number(el.textContent.replace(/\D/g, '')))
    return counts.length === data.groups.length && counts.every((count, index) => count === data.groups[index].jobs) &&
      document.querySelector('.header .soft')?.textContent === data.description
  }, data)
}
async function settled(page) { await page.waitForTimeout(2500) }
async function checkLayout(frame) {
  assert.equal(await frame.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  assert.ok(await frame.locator('svg path').evaluateAll((paths) => paths.every((p) => !/NaN|Infinity/.test(p.getAttribute('d') ?? ''))))
}
async function pointOn(frame, index, values = [2, 7, 1]) {
  const box = await frame.getByRole('slider').boundingBox()
  const g = layoutRing(values)[index]
  const angle = (g.start + g.span / 2) * Math.PI / 180
  const radius = (INNER + g.outer) / 2
  return { x: box.x + (200 + radius * Math.sin(angle)) / 400 * box.width,
    y: box.y + (200 - radius * Math.cos(angle)) / 400 * box.height }
}
async function artifact(frame, name) {
  if (!process.env.CHART_ARTIFACT_DIR) return
  await mkdir(process.env.CHART_ARTIFACT_DIR, { recursive: true })
  await frame.locator('.card').screenshot({ path: join(process.env.CHART_ARTIFACT_DIR, name) })
}
function withCounts(counts) {
  const data = sample()
  data.total_jobs = counts.reduce((sum, value) => sum + value, 0)
  data.known_jobs = counts[0] + counts[1]
  data.groups = data.groups.map((group, index) => ({ ...group, jobs: counts[index],
    share: data.total_jobs ? counts[index] / data.total_jobs * 100 : 0 }))
  data.accommodation_types = []
  return data
}

test('real sample renders counts, percentages, source, filters and freshness with reference ring and glass pills', async () => {
  const { page, frame } = await open()
  try {
    await deliver(page, frame, sample())
    await settled(page)
    assert.deepEqual(await frame.locator('.allocation-legend-count').allTextContents(), ['2', '7', '1'])
    assert.deepEqual(await frame.locator('[data-slot="allocation-share"]').allTextContents(), ['20 %', '70 %', '10 %'])
    assert.equal(await frame.locator('.allocation-amount').textContent(), '10')
    assert.match(await frame.locator('.header .soft').textContent(), /kuhar.*Varaždinska/)
    assert.match(await frame.locator('.sources').textContent(), /HZZ/)
    assert.match(await frame.locator('.warning').textContent(), /stariji od 6 sati/)
    assert.equal(await frame.locator('[data-layer="shape"]').count(), 3)
    await checkLayout(frame)
    await artifact(frame, 'accommodation_comparison.png')

    const point = await pointOn(frame, 0)
    await page.mouse.move(point.x, point.y)
    assert.match(await frame.getByRole('slider').getAttribute('aria-valuetext'), /Nudi smještaj: 2 oglasa/)
    await page.mouse.click(point.x, point.y)
    await page.mouse.move(0, 0)
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Nudi smještaj')
    await frame.getByRole('slider').focus()
    await page.keyboard.press('End')
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Podatak nije poznat')
    await page.keyboard.press('Home')
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Nudi smještaj')
    await page.keyboard.press('Escape')
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Ukupno oglasa')
  } finally { await page.close() }
})

test('legend hiding morphs the ring, identifies its changed denominator and preserves original counts', async () => {
  const { page, frame } = await open()
  try {
    await deliver(page, frame, sample())
    await settled(page)
    const buttons = frame.locator('.allocation-legend-item')
    await buttons.nth(1).click()
    await frame.getByText('Prikazano 3 od 10 oglasa.', { exact: false }).waitFor()
    assert.equal(await buttons.nth(1).getAttribute('aria-pressed'), 'false')
    assert.match(await buttons.nth(1).getAttribute('aria-label'), /70,0.*svih oglasa/)
    assert.deepEqual(await frame.locator('.allocation-legend-count').allTextContents(), ['2', '7', '1'])
    await page.waitForTimeout(950)
    assert.equal(await frame.locator('[data-key="not_offered"] [data-layer="shape"]').getAttribute('d'), '')
    assert.equal(await frame.locator('[data-slot="allocation-share"]').first().getAttribute('data-share'), String(2 / 3 * 100))
    await buttons.first().click()
    await page.waitForTimeout(950)
    assert.equal(await buttons.nth(2).getAttribute('aria-disabled'), 'true')
    await buttons.nth(2).click({ force: true })
    assert.equal(await buttons.nth(2).getAttribute('aria-pressed'), 'true')
    assert.equal((await frame.locator('[data-key="unknown"] [data-layer="shape"]').getAttribute('d')).match(/ A /g).length, 4)
    await frame.getByRole('button', { name: 'Prikaži sve skupine' }).click()
    assert.deepEqual(await buttons.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-pressed'))), ['true', 'true', 'true'])
    await checkLayout(frame)
  } finally { await page.close() }
})

test('320px dark mobile supports touch selection, second-tap clearing and reduced motion', async () => {
  const { page, frame } = await open(320, { hasTouch: true, isMobile: true, reducedMotion: 'reduce' })
  try {
    await deliver(page, frame, sample())
    await page.evaluate(() => window.setTheme('dark'))
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    await frame.getByRole('slider').scrollIntoViewIfNeeded()
    const point = await pointOn(frame, 2)
    await page.touchscreen.tap(point.x, point.y)
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Podatak nije poznat')
    await page.touchscreen.tap(point.x, point.y)
    assert.equal(await frame.locator('.allocation-middle-label').textContent(), 'Ukupno oglasa')
    await checkLayout(frame)
    await artifact(frame, 'accommodation_comparison_mobile_dark.png')
  } finally { await page.close() }
})

test('all-unknown and single-known groups render complete rings; an empty result has an explanation', async () => {
  const { page, frame } = await open(400, { reducedMotion: 'reduce' })
  try {
    for (const counts of [[0, 0, 10], [10, 0, 0], [0, 10, 0]]) {
      await deliver(page, frame, withCounts(counts))
      const index = counts.findIndex((n) => n > 0)
      assert.equal(await frame.locator('.allocation-legend-item:disabled').count(), 2)
      const path = await frame.locator('[data-layer="shape"]').nth(index).getAttribute('d')
      // Select by key instead of paint order: the thin, empty bands are painted first.
      const key = ['offered', 'not_offered', 'unknown'][index]
      const correctPath = await frame.locator(`[data-key="${key}"] [data-layer="shape"]`).getAttribute('d')
      assert.equal((correctPath.match(/ A /g) ?? []).length, 4)
      assert.doesNotMatch(path, /NaN|Infinity/)
      await checkLayout(frame)
    }
    await deliver(page, frame, withCounts([0, 0, 0]))
    assert.equal(await frame.locator('.allocation-ring').count(), 0)
    assert.match(await frame.locator('.sources').textContent(), /HZZ/)
  } finally { await page.close() }
})

test('new tool results clear hidden selections and resize safely while animating', async () => {
  const { page, frame } = await open(900)
  try {
    await deliver(page, frame, sample())
    await frame.locator('.allocation-legend-item').nth(2).click()
    const next = sample()
    next.description = 'Istarska županija · novi odabrani skup'
    await deliver(page, frame, next)
    assert.deepEqual(await frame.locator('.allocation-legend-item').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-pressed'))), ['true', 'true', 'true'])
    await page.setViewportSize({ width: 320, height: 1000 })
    await settled(page)
    await checkLayout(frame)
  } finally { await page.close() }
})

test('hidden iframe animations finish by deadline and keep final percentages when revealed', async () => {
  const { page, frame } = await open(560, {}, '?hidden')
  try {
    await page.evaluate((data) => window.sendResult(data), sample())
    await page.waitForTimeout(3100)
    await page.evaluate(() => { document.querySelector('iframe').style.display = 'block' })
    await frame.locator('.allocation-ring').waitFor()
    assert.deepEqual(await frame.locator('[data-slot="allocation-share"]').allTextContents(), ['20 %', '70 %', '10 %'])
    assert.ok((await frame.locator('[data-layer="shape"]').evaluateAll((paths) => paths.map((p) => p.getAttribute('d')))).every(Boolean))
    await checkLayout(frame)
  } finally { await page.close() }
})
