import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'node:http'
import { mkdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { sample } from '../utils/sample.ts'

const host = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">
<script>
  window.ready = false;
  window.theme = 'light';
  window.hidden = new URLSearchParams(location.search).has('hidden');
  function post(message) { document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',...message}, '*'); }
  window.sendResult = (data) => {
    post({method:'ui/notifications/tool-input',params:{arguments:{counties:data.counties.map(c=>c.code),months:data.months,sex:data.sex}}});
    post({method:'ui/notifications/tool-result',params:{content:[],structuredContent:data}});
  };
  window.setTheme = (theme) => { window.theme=theme; post({method:'ui/notifications/host-context-changed',params:{theme}}); };
  addEventListener('message', event => {
    const frame = document.querySelector('iframe');
    if (event.source !== frame.contentWindow) return;
    const message = event.data;
    if (message.method === 'ui/initialize') post({id:message.id,result:{
      protocolVersion:message.params.protocolVersion,hostInfo:{name:'FOIHireloom browser tests',version:'1.0.0'},
      hostCapabilities:{},hostContext:{theme:window.theme,displayMode:'inline',availableDisplayModes:['inline']}
    }});
    else if (message.method === 'ui/notifications/initialized') window.ready=true;
    else if (message.method === 'ui/notifications/size-changed' && message.params.height) frame.style.height=message.params.height+'px';
    else if (message.id !== undefined) post({id:message.id,result:{}});
  });
</script>
<iframe title="Povijest nezaposlenosti" src="/view" style="display:block;width:100%;height:1200px;border:0" onload="if(window.hidden)this.style.display='none'"></iframe>
</body></html>`

let server, browser, base
const errors = []
const remoteRequests = []
before(async () => {
  const html = await readFile(new URL('../../../../../dist/unemployment-history.html', import.meta.url), 'utf8')
  server = createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8')
    res.end(req.url === '/view' ? html : host)
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  base = `http://127.0.0.1:${server.address().port}`
  browser = await chromium.launch({ headless: true })
})
after(async () => {
  await browser?.close()
  if (server) await new Promise((resolve) => server.close(resolve))
  assert.deepEqual(errors, [], 'No JavaScript errors in the app or host')
  assert.deepEqual(remoteRequests, [], 'The bundled view must not fetch remote assets')
})

async function open(width = 900, options = {}, query = '') {
  const page = await browser.newPage({ viewport: { width, height: 1200 }, ...options })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => { if (!request.url().startsWith(base)) remoteRequests.push(request.url()) })
  await page.goto(base + query)
  await page.waitForFunction(() => window.ready)
  assert.equal(await page.evaluate(() => innerWidth), width, 'Test the actual CSS viewport, including mobile emulation')
  return { page, frame: page.frames().find((frame) => frame.url().endsWith('/view')) }
}
async function deliver(page, frame, data) {
  await page.evaluate((data) => window.sendResult(data), data)
  await frame.locator('[data-slot="unemployment-growth-chart"]').first().waitFor()
}
async function settled(frame) {
  await frame.locator('[data-slot="growth-line"]').first().waitFor({ state: 'attached' })
  await frame.page().waitForTimeout(1600)
}
async function layout(frame) {
  return frame.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth,
    finite: [...document.querySelectorAll('svg path')].every((path) => !/NaN|Infinity/.test(path.getAttribute('d') ?? '')),
    labelsOverlap: [...document.querySelectorAll('.growth-x-label')].some((el, index, labels) =>
      index > 0 && el.getBoundingClientRect().left < labels[index - 1].getBoundingClientRect().right + 2),
  }))
}
async function looks(frame) {
  return frame.evaluate(() => ({
    lit: [...new Set([...document.querySelectorAll('[data-slot="growth-focus-line"][data-lit="true"]')].map((p) => p.dataset.series))],
    litColor: [...new Set([...document.querySelectorAll('[data-slot="growth-focus-line"]')].map((p) => getComputedStyle(p).stroke))],
    greyColor: [...new Set([...document.querySelectorAll('[data-slot="growth-line"]')].map((p) => getComputedStyle(p).stroke))],
    greyOpacity: [...new Set([...document.querySelectorAll('[data-slot="growth-line"]')].map((p) =>
      getComputedStyle(p.closest('.growth-series')).opacity))],
    pressed: [...document.querySelectorAll('[data-slot="legend-county"]')].map((b) => b.getAttribute('aria-pressed')),
    tabbable: [...document.querySelectorAll('[data-slot="legend-county"]')].map((b) => b.tabIndex),
    tiles: [...document.querySelectorAll('[data-slot="tile"]')].map((t) => t.dataset.lit),
    readout: document.querySelector('.growth-readout-name')?.textContent,
  }))
}
const ACCENT = 'rgb(251, 41, 14)'
async function painted(frame) {
  await frame.waitForFunction(() => [...document.querySelectorAll('[data-slot="growth-focus-line"]')].every((p) =>
    getComputedStyle(p.closest('.growth-focus')).opacity === (p.dataset.lit === 'true' ? '1' : '0')))
}
const monthX = (box, index, months = 24) => box.x + 60 + (box.width - 68) * index / (months - 1)

async function screenshot(page, name) {
  if (!process.env.CHART_ARTIFACT_DIR) return
  await mkdir(process.env.CHART_ARTIFACT_DIR, { recursive: true })
  const frame = page.frames().find((frame) => frame.url().endsWith('/view'))
  await frame.locator('.card').screenshot({ path: join(process.env.CHART_ARTIFACT_DIR, name) })
}

test('production iframe preserves every monthly rate, gaps, provisional segments and annual comparisons', async () => {
  const { page, frame } = await open()
  try {
    const data = sample()
    await deliver(page, frame, data)
    await settled(frame)
    for (const county of data.counties) {
      const nodes = await frame.locator(`[data-slot="growth-node"][data-series="${county.code}"]`).evaluateAll((nodes) =>
        nodes.map((node) => ({ period: node.dataset.period, rate: Number(node.dataset.rate) })))
      assert.deepEqual(nodes, county.series.filter((p) => p.rate !== null).map(({ period, rate }) => ({ period, rate })))
    }
    const provisional = frame.locator('[data-slot="growth-line"][data-provisional="true"]')
    assert.ok(await provisional.count() > 0)
    assert.ok((await provisional.evaluateAll((paths) => paths.map((p) => p.getAttribute('stroke-dasharray'))))
      .every((dash) => /^5(px)?,? 4(px)?/.test(dash)))
    assert.equal(await frame.locator('.tile').count(), 3)
    assert.match(await frame.locator('.tiles').textContent(), /−0,6/)
    assert.match(await frame.locator('.sources').textContent(), /DZS/)
    assert.match(await frame.locator('.notes').textContent(), /nije sezonska prilagodba/)
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
    await screenshot(page, 'unemployment_chart_wide.png')

    const slider = frame.getByRole('slider')
    const box = await slider.boundingBox()
    await page.mouse.move(monthX(box, 11), box.y + 120)
    await frame.waitForFunction(() => document.querySelector('[role="slider"]').dataset.period === '2025-09-01')
    assert.match(await frame.locator('[data-slot="legend-county"]').nth(2).getAttribute('aria-label'),
      /Ličko-senjska županija, rujan 2025\.: nema podatka/)
    assert.match(await slider.getAttribute('aria-valuetext'), /Ličko-senjska županija: nema podatka/)
    await page.mouse.click(monthX(box, 7), box.y + 120)
    await page.mouse.move(0, 0)
    assert.equal(await slider.getAttribute('data-period'), '2025-05-01')
    await slider.focus()
    await page.keyboard.press('Home')
    assert.equal(await slider.getAttribute('data-period'), '2024-10-01')
    await page.keyboard.press('ArrowRight')
    assert.equal(await slider.getAttribute('data-period'), '2024-11-01')
    await page.keyboard.press('End')
    assert.equal(await slider.getAttribute('data-period'), '2026-09-01')
    assert.match(await frame.locator('.tiles').textContent(), /rujan 2026/)
  } finally { await page.close() }
})

test('the legend lights one county: hover previews, click and keys select, readout and tiles follow', async () => {
  const { page, frame } = await open()
  try {
    const data = sample()
    const [first, second, third] = data.counties.map((county) => county.code)
    await deliver(page, frame, data)
    await settled(frame)
    await painted(frame)
    assert.deepEqual(await looks(frame), {
      lit: [first], litColor: [ACCENT], greyColor: ['rgb(205, 205, 205)'], greyOpacity: ['0.5'],
      pressed: ['true', 'false', 'false'], tabbable: [0, -1, -1], tiles: ['true', 'false', 'false'],
      readout: 'Varaždinska županija · rujan 2026.privremeno',
    })
    assert.equal(await frame.locator('.growth-value').textContent(), '2,3\u00a0%')
    assert.equal(await frame.locator('.growth-focus').first().evaluate((g) => getComputedStyle(g).transitionDuration), '0.3s')
    const chips = frame.locator('[data-slot="legend-county"]')
    assert.equal(await chips.first().evaluate((chip) => getComputedStyle(chip).backgroundColor), 'rgb(25, 25, 25)')

    await chips.nth(1).hover()
    await frame.waitForFunction(() => document.querySelector('.growth-readout-name').textContent.startsWith('Istarska'))
    await frame.waitForFunction(() => document.querySelector('.growth-value').textContent === '1,1\u00a0%')
    let state = await looks(frame)
    assert.deepEqual([state.lit, state.pressed, state.tiles], [[second], ['true', 'false', 'false'], ['false', 'true', 'false']])
    await page.mouse.move(0, 0)
    await frame.waitForFunction(() => document.querySelector('.growth-readout-name').textContent.startsWith('Varaždinska'))
    assert.deepEqual((await looks(frame)).lit, [first])

    await chips.nth(2).click()
    await page.mouse.move(0, 0)
    state = await looks(frame)
    assert.deepEqual([state.lit, state.pressed, state.tabbable], [[third], ['false', 'false', 'true'], [-1, -1, 0]])
    await frame.waitForFunction(() => document.querySelector('.growth-value').textContent === '3,4\u00a0%')
    await painted(frame)

    await page.keyboard.press('ArrowLeft')
    state = await looks(frame)
    assert.deepEqual([state.lit, state.pressed, state.tabbable], [[second], ['false', 'true', 'false'], [-1, 0, -1]])
    assert.equal(await frame.evaluate(() => document.activeElement.getAttribute('aria-pressed')), 'true')
    await frame.waitForFunction(() => getComputedStyle(document.activeElement.querySelector('.focus-ring')).opacity === '1')
    await page.keyboard.press('Home')
    assert.deepEqual((await looks(frame)).lit, [first])
    await page.keyboard.press('ArrowLeft')
    assert.deepEqual((await looks(frame)).pressed, ['true', 'false', 'false'], 'Selection stops at the first county')
    await page.keyboard.press('End')
    state = await looks(frame)
    assert.deepEqual([state.lit, state.tiles], [[third], ['false', 'false', 'true']])
    assert.match(await frame.evaluate(() => document.activeElement.getAttribute('aria-label')), /^Ličko-senjska županija, rujan 2026\.: 3,4/)

    await frame.getByRole('slider').focus()
    await page.keyboard.press('Home')
    await frame.waitForFunction(() => document.querySelector('.growth-readout-name').textContent === 'Ličko-senjska županija · listopad 2024.')
    await frame.waitForFunction(() => document.querySelector('.growth-value').textContent === '5,0\u00a0%')
    assert.deepEqual((await looks(frame)).lit, [third])
    await screenshot(page, 'unemployment_chart_selected.png')
  } finally { await page.close() }
})

test('two-county dark mobile view supports real touch dragging and reduced motion', async () => {
  const { page, frame } = await open(320, { hasTouch: true, isMobile: true, reducedMotion: 'reduce' })
  try {
    await page.evaluate(() => window.setTheme('dark'))
    const data = sample()
    data.counties = data.counties.slice(0, 2)
    await deliver(page, frame, data)
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    assert.equal(await frame.locator('[data-slot="legend-county"]').count(), 2)
    await painted(frame)
    const state = await looks(frame)
    assert.deepEqual([state.lit, state.litColor, state.greyColor], [[data.counties[0].code], [ACCENT], ['rgb(110, 110, 110)']])
    assert.equal(await frame.locator('[data-slot="legend-county"]').first().evaluate((chip) => getComputedStyle(chip).backgroundColor),
      'rgb(244, 244, 244)')
    assert.equal(await frame.locator('.growth-focus').first().evaluate((g) => getComputedStyle(g).transitionDuration), '0s')
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
    const slider = frame.getByRole('slider')
    await slider.scrollIntoViewIfNeeded()
    const box = await slider.boundingBox()
    const cdp = await page.context().newCDPSession(page)
    const y = box.y + 120
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: monthX(box, 0), y }] })
    assert.equal(await slider.getAttribute('data-period'), '2024-10-01')
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: monthX(box, 23), y }] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    assert.equal(await slider.getAttribute('data-period'), '2026-09-01')
    assert.match(await frame.locator('.growth-value').textContent(), /2,3/)
    await page.evaluate(() => scrollTo(0, 0))
    await screenshot(page, 'unemployment_chart_mobile_dark.png')
  } finally { await page.close() }
})

test('new MCP results reset selection and render six series, one lit, at 560 px without stale animations', async () => {
  const { page, frame } = await open(560)
  try {
    const data = sample()
    await deliver(page, frame, data)
    await frame.getByRole('slider').focus()
    await page.keyboard.press('Home')
    await frame.locator('[data-slot="legend-county"]').nth(2).click()
    const six = structuredClone(data)
    six.counties = [...data.counties, ...data.counties.map((county) => ({ ...county, code: county.code + '-test' }))]
    await deliver(page, frame, six)
    await settled(frame)
    assert.equal(await frame.locator('[data-slot="legend-county"]').count(), 6)
    await painted(frame)
    const state = await looks(frame)
    assert.deepEqual([state.lit, state.litColor, state.greyColor, state.pressed.indexOf('true')],
      [[six.counties[0].code], [ACCENT], ['rgb(205, 205, 205)'], 0])
    assert.equal(await frame.getByRole('slider').getAttribute('data-period'), data.last_period)
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
    const reordered = { ...data, counties: [...data.counties].reverse() }
    await deliver(page, frame, reordered)
    await page.setViewportSize({ width: 320, height: 1200 })
    await settled(frame)
    assert.match(await frame.locator('[data-slot="legend-county"]').first().textContent(), /Ličko-senjska/)
    assert.match(await frame.locator('.growth-readout-name').textContent(), /^Ličko-senjska/)
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
  } finally { await page.close() }
})

test('zero is a known rate, all-null data has no chart and empty data keeps its explanation', async () => {
  const { page, frame } = await open(900, { reducedMotion: 'reduce' })
  try {
    const data = sample()
    data.counties = data.counties.slice(0, 1)
    data.counties[0].series = data.counties[0].series.map((point) => ({ ...point, rate: 0 }))
    await deliver(page, frame, data)
    assert.match(await frame.locator('.growth-value').textContent(), /0,0/)
    assert.equal(await frame.locator('[data-slot="growth-node"]').count(), 24)
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
    data.counties[0].series = data.counties[0].series.map((point) => ({ ...point, rate: null }))
    await deliver(page, frame, data)
    await frame.getByText('Za odabrano razdoblje nema poznatih stopa nezaposlenosti.').waitFor()
    assert.equal(await frame.getByRole('slider').count(), 0)
    assert.equal(await frame.locator('[data-slot="growth-line"]').count(), 0)
    data.counties[0].series = []
    data.unavailable_label = 'DZS podaci nisu uvezeni.'
    await page.evaluate((data) => window.sendResult(data), data)
    await frame.getByText('DZS podaci nisu uvezeni.').waitFor()
    assert.equal(await frame.locator('.growth-chart').count(), 0)
    assert.match(await frame.locator('.sources').textContent(), /DZS/)
  } finally { await page.close() }
})

test('an initially hidden MCP iframe completes its entrance and renders correctly when shown', async () => {
  const { page, frame } = await open(900, {}, '?hidden')
  try {
    await page.evaluate((data) => window.sendResult(data), sample())
    await page.waitForTimeout(2900)
    await page.evaluate(() => { document.querySelector('iframe').style.display = 'block' })
    await frame.locator('.growth-value').first().waitFor()
    await settled(frame)
    assert.match(await frame.locator('.growth-value').first().textContent(), /2,3/)
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
  } finally { await page.close() }
})

test('the captured live MCP response renders its original county rates', { skip: !process.env.CHART_LIVE_DATA_FILE }, async () => {
  const data = JSON.parse(await readFile(process.env.CHART_LIVE_DATA_FILE, 'utf8'))
  const { page, frame } = await open()
  try {
    await deliver(page, frame, data)
    await settled(frame)
    assert.equal(await frame.locator('[data-slot="legend-county"]').count(), data.counties.length)
    for (const county of data.counties) {
      const nodes = await frame.locator(`[data-slot="growth-node"][data-series="${county.code}"]`).evaluateAll((nodes) =>
        nodes.map((node) => ({ period: node.dataset.period, rate: Number(node.dataset.rate) })))
      assert.deepEqual(nodes, county.series.filter((p) => p.rate !== null).map(({ period, rate }) => ({ period, rate })))
    }
    assert.deepEqual(await layout(frame), { overflow: false, finite: true, labelsOverlap: false })
    await screenshot(page, 'unemployment_chart_two_counties.png')
  } finally { await page.close() }
})
