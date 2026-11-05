import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Every MCP App view is a page under src/pages. The dev server serves them all, e.g.
// http://localhost:5173/jobs-by-county.html with sample data; build-views.mjs builds each one into a single
// HTML file in dist/ with its scripts, styles and the MCP Apps SDK inlined, which the MCP server serves as a ui:// page.
export const OUT_DIR = fileURLToPath(new URL('./dist', import.meta.url))

export default defineConfig({
  root: 'src/pages',
  resolve: {
    // HTML module URLs resolve from the page root during development.
    alias: { '/mvvm': fileURLToPath(new URL('./src/mvvm', import.meta.url)) },
  },
  plugins: [
    tailwindcss(),
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    viteSingleFile(),
  ],
  build: {
    outDir: OUT_DIR,
  },
})
