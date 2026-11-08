import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { build } from 'vite'
import { OUT_DIR } from './vite.config.ts'

const SOURCES = ['src', 'package.json', 'package-lock.json', 'vite.config.ts', 'build-views.mjs', 'tsconfig.json',
  'tsconfig.app.json']

function files(path) {
  if (!statSync(path).isDirectory()) return [path]
  return readdirSync(path).filter((name) => !name.startsWith('.')).flatMap((name) => files(join(path, name)))
}

const views = readdirSync('src/pages').filter((file) => file.endsWith('.html'))
for (const [i, view] of views.entries()) {
  await build({
    build: {
      emptyOutDir: i === 0,
      rolldownOptions: { input: `src/pages/${view}` },
    },
  })
}

const hashes = Object.fromEntries(SOURCES.flatMap(files).map((file) => file.split('\\').join('/')).sort()
  .map((file) => [file, createHash('sha256').update(readFileSync(file)).digest('hex')]))
writeFileSync(join(OUT_DIR, 'sources.json'), `${JSON.stringify({ sources: SOURCES, files: hashes }, null, 2)}\n`)
