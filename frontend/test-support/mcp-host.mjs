import assert from 'node:assert/strict'
import { after, before } from 'node:test'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { chromium } from 'playwright'

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

export const views = ['job-cards', 'job-comparison', 'county-comparison', 'jobs-by-county',
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

export async function pageFor(path, width = 760) {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('request', (request) => { if (!request.url().startsWith(base)) remote.push(request.url()) })
  await page.goto(base + path)
  return page
}
export async function open(view, data, readonly = false) {
  const page = await pageFor(`/?view=${view}${readonly ? '&readonly' : ''}`)
  await page.waitForFunction(() => window.ready)
  const frame = page.frames().find((frame) => frame.url().includes('/view/'))
  await deliver(page, frame, data)
  return { page, frame }
}
export async function deliver(page, frame, data) {
  await page.evaluate((data) => window.sendResult(data), data)
  await frame.waitForFunction((title) => document.querySelector('.title')?.textContent === title, data.title)
}
export async function request(page, count) {
  await page.waitForFunction((count) => window.requests.length === count, count)
  return page.evaluate((index) => window.requests[index].params, count - 1)
}
export async function reply(page, index, data) {
  await page.evaluate(({ index, data }) => window.reply(index, { content: [], structuredContent: data }), { index, data })
}
export async function countCards(frame, count) {
  await frame.waitForFunction((count) => document.querySelectorAll('[data-slot="job"]').length === count, count)
}
