import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Dev: `npm run dev` serves the UI on :5173 and proxies /api to FastAPI on :8000.
// Prod: `npm run build` writes the bundle into app/backend/static, which FastAPI
//       serves from the same origin as the API (no CORS, no separate deployment).

const here = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.resolve(here, '../backend/static')

// Content-hashed assets + a fresh BUILD_ID.txt on every build: the API reports the
// stamp at /api/health and the UI prints it in the footer, so "am I looking at the
// new build?" is answerable at a glance (this was a real support question).
const buildId = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14)

function buildStamp() {
  return {
    name: 'agrismart-build-stamp',
    closeBundle() {
      fs.mkdirSync(outDir, { recursive: true })
      fs.writeFileSync(path.join(outDir, 'BUILD_ID.txt'), `${buildId}\n`)
      console.log(`\n  AgriSmart build id: ${buildId}  ->  app/backend/static/BUILD_ID.txt`)
    },
  }
}

export default defineConfig({
  plugins: [react(), buildStamp()],
  define: { __BUILD_ID__: JSON.stringify(buildId) },
  base: '/',
  build: {
    outDir,
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
