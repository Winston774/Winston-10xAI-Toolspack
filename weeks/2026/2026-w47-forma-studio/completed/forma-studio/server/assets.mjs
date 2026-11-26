import path from 'node:path'
import { createReadStream } from 'node:fs'
import { mkdir, readFile, realpath, rename, stat, writeFile } from 'node:fs/promises'
import { pipeline } from 'node:stream/promises'
import { randomUUID } from 'node:crypto'
import { check, Problem } from './store.mjs'

const types = {
  '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8', '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml',
  '.webp':'image/webp', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.ico':'image/x-icon',
  '.mp3':'audio/mpeg', '.wav':'audio/wav', '.ogg':'audio/ogg', '.mp4':'video/mp4',
  '.woff2':'font/woff2', '.woff':'font/woff',
}
const imageTypes = { png:'image/png', jpg:'image/jpeg', webp:'image/webp' }
export const maxAsset = 20 * 1024 * 1024
const remotePaths = [
  ['ai-portrait-gallery.pages.dev', /^\/img\//],
  ['raw.githubusercontent.com', /^\/anhao\/ai-pose-gallery-zh\/(?:main|[a-f0-9]{40})\/(?:thumbs|img)\//],
  ['raw.githubusercontent.com', /^\/paipiange\/nvzhuang\/(?:main|[a-f0-9]{40})\/assets\/(?:thumbs|img)\//],
]

function permittedRemote(url) {
  const parsed = URL.parse(url)
  return parsed && parsed.protocol === 'https:' && !parsed.port && !parsed.username && !parsed.password &&
    remotePaths.some(([host, pattern]) => parsed.hostname === host && pattern.test(parsed.pathname))
}

export function imageFormat(bytes) {
  if (bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) return 'png'
  if (bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) return 'jpg'
  if (bytes.toString('ascii',0,4) === 'RIFF' && bytes.toString('ascii',8,12) === 'WEBP') return 'webp'
  return null
}

function inside(root, target) {
  const part = path.relative(root, target)
  return part && !path.isAbsolute(part) && part !== '..' && !part.startsWith('..' + path.sep)
}
async function contained(root, rel) {
  check(typeof rel === 'string' && !/[\\:\x00]/.test(rel), '檔案路徑無效。', 404)
  const target = path.resolve(root, rel)
  check(inside(root, target), '找不到檔案。', 404)
  try {
    const [actualRoot, actual] = await Promise.all([realpath(root), realpath(target)])
    check(inside(actualRoot, actual) && (await stat(actual)).isFile(), '找不到檔案。', 404)
    return actual
  } catch { throw new Problem(404, '找不到檔案。') }
}

export class Assets {
  constructor(store, root, publicDir, fetchImpl) {
    Object.assign(this, { store, root, publicDir, fetchImpl })
  }
  async pathFor(url) {
    check(typeof url === 'string' && url.startsWith('/') && !url.startsWith('//'), '請選擇本機素材。')
    if (url.startsWith('/media/')) {
      const rel = this.store.file(url)
      check(!!rel, '找不到這個作品檔案。', 404)
      return contained(this.root, rel)
    }
    let rel
    try { rel = decodeURIComponent(url.slice(1)) } catch { throw new Problem(400,'素材網址格式錯誤。') }
    return contained(this.publicDir, rel || 'index.html')
  }
  async publish(outputDir, filename) {
    const realDir = await realpath(outputDir)
    const actual = await realpath(filename)
    check(inside(realDir,actual) && (await stat(actual)).isFile(), '媒體服務沒有產生可用檔案。', 502)
    const rel = path.relative(await realpath(this.root), actual).split(path.sep).join('/')
    check(!rel.startsWith('../') && rel.startsWith('media/'), '媒體輸出路徑錯誤。', 502)
    return this.store.rememberFile('/media/' + rel.slice(6), rel)
  }
  async upload(dataUrl) {
    check(typeof dataUrl === 'string', '請選擇圖片。')
    const match = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/]+={0,2})$/.exec(dataUrl)
    check(match, '支援 PNG、JPEG 與 WebP 圖片。')
    const bytes = Buffer.from(match[2], 'base64')
    const ext = imageFormat(bytes)
    check(bytes.length <= maxAsset && imageTypes[ext] === match[1], '圖片格式不符或超過 20 MB。')
    const dir = path.join(this.root, 'media', 'uploads')
    await mkdir(dir,{recursive:true})
    const filename = path.join(dir, randomUUID() + '.' + ext)
    await writeFile(filename,bytes,{flag:'wx',mode:0o600})
    return this.publish(dir, filename)
  }
  async image(url, signal) {
    let bytes
    if (permittedRemote(url)) {
      const combined = AbortSignal.any([signal, AbortSignal.timeout(45000)])
      const response = await this.fetchImpl(url, { signal:combined, redirect:'error' })
      check(response.ok && response.body, '無法下載所選參考圖片，請重新選擇或上傳。', 502)
      const chunks = []
      let total = 0
      for await (const chunk of response.body) {
        total += chunk.length
        check(total <= maxAsset,'參考圖超過 20 MB。')
        chunks.push(chunk)
      }
      bytes = Buffer.concat(chunks)
    } else {
      const filename = await this.pathFor(url)
      check((await stat(filename)).size <= maxAsset, '參考圖超過 20 MB。')
      bytes = await readFile(filename)
    }
    const ext = imageFormat(bytes)
    check(!!ext, '參考圖片必須是 PNG、JPEG 或 WebP。')
    return {bytes, ext, mime:imageTypes[ext]}
  }
  async localImage(url, outputDir, signal, reuse = false) {
    if (reuse) {
      for (const ext of Object.keys(imageTypes)) {
        const file = path.join(outputDir,'source-photo.'+ext)
        try { if ((await stat(file)).size > 0) return file }
        catch (error) { if (error.code !== 'ENOENT') throw error }
      }
    }
    const {bytes, ext} = await this.image(url,signal)
    const file = path.join(outputDir, 'source-photo.' + ext)
    const temp = path.join(outputDir,'source-photo.pending')
    await writeFile(temp,bytes)
    await rename(temp,file)
    return file
  }
  async audio(url) {
    check(typeof url === 'string' && url.startsWith('/media/'), '請選擇已合成的語音。')
    const target = await this.pathFor(url)
    check(['.mp3','.wav','.ogg'].includes(path.extname(target).toLowerCase()), '所選檔案不是語音。')
    return target
  }
  async serve(url, req, res) {
    const file = await this.pathFor(url)
    const type = types[path.extname(file).toLowerCase()]
    check(type, '找不到檔案。', 404)
    const {size} = await stat(file)
    const headers = { 'Content-Type':type, 'Accept-Ranges':'bytes', 'Cache-Control':url.startsWith('/media/')?'private, max-age=604800':'no-cache' }
    let start = 0, end = size - 1, status = 200
    if (req.headers.range && size > 0) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range)
      if (match && (match[1] || match[2])) {
        if (!match[1]) start = Math.max(0, size - Number(match[2]))
        else {
          start = Number(match[1])
          if (match[2]) end = Math.min(end, Number(match[2]))
        }
      }
      if (!match || (!match[1] && !match[2]) || start > end || start >= size) {
        res.writeHead(416,{'Content-Range':'bytes */' + size}); res.end(); return
      }
      status = 206
      headers['Content-Range'] = `bytes ${start}-${end}/${size}`
    }
    res.writeHead(status, {...headers, 'Content-Length':end - start + 1})
    if (req.method === 'HEAD' || !size) return res.end()
    await pipeline(createReadStream(file, {start,end}), res)
  }
}
