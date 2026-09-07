// Render PDF pages to PNG so a preview can be looked at without a PDF viewer.
// usage: node pdfshot.mjs <pdf> <outPrefix> <page> [page...]
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const [, , pdfArg, prefix, ...pageArgs] = process.argv
if (!pdfArg || !prefix || !pageArgs.length) {
  console.error('usage: node pdfshot.mjs <pdf> <outPrefix> <page> [page...]')
  process.exit(1)
}
const pages = pageArgs.map(Number)
const PORT = 8742
const MIME = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript',
               '.pdf': 'application/pdf', '.map': 'application/json' }

const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '')
  const file = path.join(HERE, rel)
  if (!file.startsWith(HERE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end(); return
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' })
  fs.createReadStream(file).pipe(res)
})
await new Promise(resolve => server.listen(PORT, '127.0.0.1', resolve))

const shell = path.join(HERE, 'build', 'pdfshell.html')
fs.writeFileSync(shell, '<!doctype html><meta charset="utf-8">'
  + '<style>html,body{margin:0}canvas{display:block}</style><canvas id="c"></canvas>')

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] })
const page = await browser.newPage()
await page.goto(`http://127.0.0.1:${PORT}/build/pdfshell.html`, { waitUntil: 'load' })

const pdfUrl = '/' + path.relative(HERE, path.resolve(pdfArg)).replace(/\\/g, '/')
for (const number of pages) {
  const size = await page.evaluate(async (url, pageNo) => {
    const pdfjs = await import('/node_modules/pdfjs-dist/build/pdf.mjs')
    pdfjs.GlobalWorkerOptions.workerSrc = '/node_modules/pdfjs-dist/build/pdf.worker.mjs'
    const doc = await pdfjs.getDocument({ url }).promise
    const sheet = await doc.getPage(pageNo)
    const viewport = sheet.getViewport({ scale: 1.6 })
    const canvas = document.getElementById('c')
    canvas.width = Math.ceil(viewport.width)
    canvas.height = Math.ceil(viewport.height)
    const context = canvas.getContext('2d')
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    await sheet.render({ canvasContext: context, viewport }).promise
    return { w: canvas.width, h: canvas.height }
  }, pdfUrl, number)

  await page.setViewport({ width: size.w, height: size.h, deviceScaleFactor: 1 })
  const out = path.resolve(`${prefix}_p${number}.png`)
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: size.w, height: size.h } })
  console.log(`page ${number}: ${size.w}x${size.h} -> ${path.basename(out)}`)
}

await browser.close()
server.close()
