import { readFile, writeFile, copyFile } from 'node:fs/promises'
const names =
  'accessibility aperture arrow-left arrow-right arrow-up-right audio-lines bookmark camera check chevron-right contact-round download image images layers-3 mic monitor panels-top-left plus refresh-cw scan-face search settings-2 shirt sparkles upload user-round video x'.split(
    ' ',
  )
const symbols = []
for (const name of names) {
  const source = await readFile(
    new URL(
      '../node_modules/lucide-static/icons/' +
        (name === 'layers-3' ? 'layers' : name) +
        '.svg',
      import.meta.url,
    ),
    'utf8',
  )
  const body = source.match(/<svg[^>]*>([\s\S]*?)<\/svg>/)?.[1]
  if (!body) throw new Error('無法讀取圖示 ' + name)
  symbols.push(
    '<symbol id="' + name + '" viewBox="0 0 24 24">' + body + '</symbol>',
  )
}
await writeFile(
  new URL('../public/ui/icons.svg', import.meta.url),
  '<svg xmlns="http://www.w3.org/2000/svg">' + symbols.join('') + '</svg>',
)
await copyFile(
  new URL('../node_modules/lucide-static/LICENSE', import.meta.url),
  new URL('../public/ui/lucide-license.txt', import.meta.url),
)
