// Build each src/views/<name>.html on its own into ../src/FOIHireloom/api/apps/views/<name>.html.
// A single-file build takes one page at a time, so this runs Vite once per view.
import { readdirSync } from 'node:fs'
import { build } from 'vite'

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
