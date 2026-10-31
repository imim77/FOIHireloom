// Build each src/views/<name>.html on its own into dist/<name>.html, which the MCP server serves.
// A single-file build takes one page at a time, so this runs Vite once per view.
// dist/sources.json then records a SHA-256 of every file the pages are built from; api/apps/views.py hashes the
// same files again, so the tests and the server can tell when the pages are older than their sources.
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { build } from 'vite'
import { OUT_DIR } from './vite.config.ts'

// What the pages are built from; dotfiles (.DS_Store …) are left out.
const SOURCES = ['src', 'package.json', 'package-lock.json', 'vite.config.ts', 'build-views.mjs', 'tsconfig.json',
  'tsconfig.app.json']

function files(path) {
  if (!statSync(path).isDirectory()) return [path]
  return readdirSync(path).filter((name) => !name.startsWith('.')).flatMap((name) => files(join(path, name)))
}

const views = readdirSync('src/views').filter((file) => file.endsWith('.html'))
for (const [i, view] of views.entries()) {
  await build({
    build: {
      // Clear the old pages on the first build only.
      emptyOutDir: i === 0,
      rolldownOptions: { input: `src/views/${view}` },
    },
  })
}

const hashes = Object.fromEntries(SOURCES.flatMap(files).map((file) => file.split('\\').join('/')).sort()
  .map((file) => [file, createHash('sha256').update(readFileSync(file)).digest('hex')]))
writeFileSync(join(OUT_DIR, 'sources.json'), `${JSON.stringify({ sources: SOURCES, files: hashes }, null, 2)}\n`)
