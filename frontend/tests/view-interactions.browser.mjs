import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { sample as jobSample } from '../src/mvvm/features/JobCards/utils/sample.ts'
import { sample as countySample } from '../src/mvvm/features/CountyComparison/utils/sample.ts'
import { sample as forecastSample } from '../src/mvvm/features/LabourMarketForecast/utils/sample.ts'
import { sample as comparisonSample } from '../src/mvvm/features/JobComparison/utils/sample.ts'
import { sample as historySample } from '../src/mvvm/features/UnemploymentHistory/utils/sample.ts'
import { sample as accommodationSample } from '../src/mvvm/features/AccommodationComparison/utils/sample.ts'

// The host holds tool replies so tests can deliver a replacement result first.
const host = `<!doctype html><html><body style="margin:0"><script>
window.ready=false;window.requests=[];window.messages=[];window.links=[];window.failMessage=false;
const options=new URLSearchParams(location.search);
function post(message){document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',...message},'*');}
window.sendResult=data=>{
 post({method:'ui/notifications/tool-input',params:{arguments:{}}});
 post({method:'ui/notifications/tool-result',params:{content:[],structuredContent:data}});
};
window.reply=(index,result)=>post({id:window.requests[index].id,result});
window.setTheme=theme=>post({method:'ui/notifications/host-context-changed',params:{theme}});
addEventListener('message',event=>{
 if(event.source!==document.querySelector('iframe').contentWindow)return;
 const m=event.data;
 if(m.method==='ui/initialize')post({id:m.id,result:{protocolVersion:m.params.protocolVersion,
  hostInfo:{name:'Interaction tests',version:'1.0'},
  hostCapabilities:options.has('readonly')?{}:{serverTools:{},message:{text:{}}},
  hostContext:{theme:'light',displayMode:'inline',availableDisplayModes:['inline']}}});
 else if(m.method==='ui/notifications/initialized')window.ready=true;
 else if(m.method==='tools/call')window.requests.push(m);
 else if(m.method==='ui/message'){window.messages.push(m.params);post({id:m.id,result:{isError:window.failMessage}});}
 else if(m.method==='ui/open-link'){window.links.push(m.params.url);post({id:m.id,result:{}});}
 else if(m.id!==undefined)post({id:m.id,result:{}});
});
</script><iframe title="MCP view" style="display:block;width:100%;height:1600px;border:0"></iframe>
<script>document.querySelector('iframe').src='/view/'+options.get('view');</script></body></html>`

const views = ['job-cards', 'job-comparison', 'county-comparison', 'jobs-by-county',
  'unemployment-history', 'accommodation-comparison', 'labour-market-forecast']
let browser, server, base
const errors = [], remote = []
before(async () => {
  const pages = new Map(await Promise.all(views.map(async (name) =>
    [name, await readFile(new URL(`../dist/${name}.html`, import.meta.url), 'utf8')])))
  server = createServer((req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8')
    res.end(req.url.startsWith('/view/') ? pages.get(req.url.slice(6)) : host)
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  base = `http://127.0.0.1:${server.address().port}`
  browser = await chromium.launch({ headless: true })
})
after(async () => {
  await browser?.close()
  if (server?.listening) await new Promise((resolve) => server.close(resolve))
  assert.deepEqual(errors, [], 'Views produce no browser errors')
  assert.deepEqual(remote, [], 'Views require no external assets')
})

async function pageFor(path, width = 760) {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('request', (request) => { if (!request.url().startsWith(base)) remote.push(request.url()) })
  await page.goto(base + path)
  return page
}
async function open(view, data, readonly = false) {
  const page = await pageFor(`/?view=${view}${readonly ? '&readonly' : ''}`)
  await page.waitForFunction(() => window.ready)
  const frame = page.frames().find((frame) => frame.url().includes('/view/'))
  await deliver(page, frame, data)
  return { page, frame }
}
async function deliver(page, frame, data) {
  await page.evaluate((data) => window.sendResult(data), data)
  await frame.waitForFunction((title) => document.querySelector('.title')?.textContent === title, data.title)
}
async function request(page, count) {
  await page.waitForFunction((count) => window.requests.length === count, count)
  return page.evaluate((index) => window.requests[index].params, count - 1)
}
async function reply(page, index, data) {
  await page.evaluate(({ index, data }) => window.reply(index, { content: [], structuredContent: data }), { index, data })
}
async function countCards(frame, count) {
  await frame.waitForFunction((count) => document.querySelectorAll('[data-slot="job"]').length === count, count)
}

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
        'rgb(250, 250, 250)', view)
      await page.evaluate(() => { document.documentElement.dataset.theme = 'light' })
      assert.equal(await page.locator('.card').evaluate((card) => getComputedStyle(card).color),
        'rgb(24, 24, 27)', view)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, view)
    } finally { await page.close() }
  }
})

test('Chronos displays exact medians and intervals, preserves gaps and supports keyboard selection', async () => {
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
    await frame.getByText('Povijesni podaci (24)', { exact: true }).click()
    assert.ok(await frame.getByRole('region', { name: 'Povijesne vrijednosti' }).getByText('procijenjeno', { exact: true }).count())
    await page.evaluate(() => window.setTheme('dark'))
    await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    assert.notEqual(await frame.locator('.forecast-predicted').evaluate((el) => getComputedStyle(el).stroke), 'none')
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


test('source and advertisement callbacks open the requested URLs through the host', async () => {
  for (const [view, data] of [
    ['county-comparison', countySample()], ['unemployment-history', historySample()],
    ['accommodation-comparison', accommodationSample()], ['labour-market-forecast', forecastSample()],
  ]) {
    const { page, frame } = await open(view, data)
    try {
      const source = frame.locator('.sources button').first()
      const url = await source.getAttribute('title')
      await source.click()
      await page.waitForFunction(() => window.links.length === 1)
      assert.deepEqual(await page.evaluate(() => window.links), [url], view)
    } finally { await page.close() }
  }
  for (const [view, data] of [['job-cards', jobSample()], ['job-comparison', comparisonSample()]]) {
    const { page, frame } = await open(view, data)
    try {
      await frame.getByRole('button', { name: /Otvori oglas/ }).first().click()
      await page.waitForFunction(() => window.links.length === 1)
      assert.deepEqual(await page.evaluate(() => window.links), [data.jobs[0].canonical_url], view)
    } finally { await page.close() }
  }
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
