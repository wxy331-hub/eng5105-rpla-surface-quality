// Render every extracted Mermaid block to PNG.
//
// Uses the Chromium puppeteer installs rather than the system Chrome, whose
// renderer terminates before it requests the page on this machine, and serves the
// build directory over local HTTP because a setContent page has an about:blank
// origin and cannot import the Mermaid ES module from file://.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const BUILD = path.join(HERE, 'build')
const PORT = 8741
const SCALE = 2
const MIME = {
  '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.map': 'application/json',
}

const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '')
  const file = path.join(HERE, rel)
  if (!file.startsWith(HERE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end('not found'); return
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' })
  fs.createReadStream(file).pipe(res)
})
await new Promise(resolve => server.listen(PORT, '127.0.0.1', resolve))

fs.writeFileSync(path.join(BUILD, 'shell.html'), `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;padding:0;background:#fff}
  #d{display:inline-block;padding:8px}
  #d svg{display:block}
  #d text,#d tspan{font-family:"Segoe UI","Microsoft YaHei",sans-serif !important}
</style><div id="d"></div>`)

const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none'],
})

const files = fs.readdirSync(BUILD).filter(f => f.endsWith('.mmd')).sort()
for (const file of files) {
  const name = file.replace(/\.mmd$/, '')
  const isFigure1 = name.startsWith('fig1_')
  let source = fs.readFileSync(path.join(BUILD, file), 'utf8')
  // left-to-right needs a width no page has
  if (isFigure1) source = source.replace(/^flowchart LR/m, 'flowchart TB')

  const page = await browser.newPage()
  await page.setViewport({ width: 1400, height: 1000, deviceScaleFactor: SCALE })
  await page.goto(`http://127.0.0.1:${PORT}/build/shell.html`, { waitUntil: 'load' })

  const size = await page.evaluate(async (src, narrow) => {
    const mermaid = (await import('/node_modules/mermaid/dist/mermaid.esm.mjs')).default
    mermaid.initialize({
      startOnLoad: false, theme: 'neutral', securityLevel: 'loose',
      flowchart: {
        htmlLabels: false, useMaxWidth: false,
        nodeSpacing: narrow ? 14 : 34, rankSpacing: narrow ? 70 : 44,
      },
      stateDiagram: { useMaxWidth: false },
      fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif', fontSize: 15,
    })
    const { svg } = await mermaid.render('g', src)
    document.getElementById('d').innerHTML = svg
    const node = document.querySelector('#d svg')
    const box = (node.getAttribute('viewBox') || '0 0 800 600').split(/\s+/).map(Number)
    node.removeAttribute('style')
    node.setAttribute('width', box[2])
    node.setAttribute('height', box[3])
    return { w: Math.ceil(box[2]) + 16, h: Math.ceil(box[3]) + 16 }
  }, source, isFigure1)

  await page.setViewport({ width: size.w, height: size.h, deviceScaleFactor: SCALE })
  const out = path.join(BUILD, `${name}.png`)
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: size.w, height: size.h } })
  await page.close()
  const kb = (fs.statSync(out).size / 1024).toFixed(0)
  console.log(`${name}: ${size.w}x${size.h} css -> ${size.w * SCALE}x${size.h * SCALE} px, ${kb} KB`)
}

await browser.close()
server.close()
