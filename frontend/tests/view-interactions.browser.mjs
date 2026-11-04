import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { sample as jobSample } from '../src/views/job-cards/sample.ts'
import { sample as countySample } from '../src/views/county-comparison/sample.ts'

// The host holds tool replies so tests can deliver a replacement result first.
const host = `<!doctype html><html><body style="margin:0"><script>
window.ready=false;window.requests=[];window.messages=[];
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
 else if(m.method==='ui/message'){window.messages.push(m.params);post({id:m.id,result:{}});}
 else if(m.id!==undefined)post({id:m.id,result:{}});
});
</script><iframe title="MCP view" style="display:block;width:100%;height:1600px;border:0"></iframe>
<script>document.querySelector('iframe').src='/view/'+options.get('view');</script></body></html>`

const views = ['job-cards', 'job-comparison', 'county-comparison', 'jobs-by-county',
  'unemployment-history', 'accommodation-comparison']
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

test('all six standalone previews render at mobile width', async () => {
  for (const view of views) {
    const page = await pageFor(`/view/${view}`, 320)
    try {
      await page.locator('.card .title').waitFor()
      assert.ok(await page.locator('.card .body').textContent(), view)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, view)
    } finally { await page.close() }
  }
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
