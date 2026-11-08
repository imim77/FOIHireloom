import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

export const OUT_DIR = fileURLToPath(new URL('./dist', import.meta.url))

export default defineConfig({
  root: 'src/pages',
  resolve: {
    alias: {
      '/mvvm': fileURLToPath(new URL('./src/mvvm', import.meta.url)),
      '@': fileURLToPath(new URL('./src/mvvm', import.meta.url)),
    },
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
