import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import path from 'node:path'
import { existsSync, readdirSync } from 'node:fs'
import { chromium } from 'playwright-core'
import { createStudio } from '../server/index.mjs'

// Run against a new local database. Screenshots and transient credentials stay outside the project history.
function chromiumPath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH
  if (existsSync(chromium.executablePath())) return chromium.executablePath()
  const root = path.join(homedir(), 'AppData', 'Local', 'ms-playwright')
  if (existsSync(root)) {
    for (const dir of readdirSync(root)
      .filter((n) => n.startsWith('chromium_headless_shell-'))
      .sort()
      .reverse()) {
      const exe = path.join(
        root,
        dir,
        'chrome-headless-shell-win64',
        'chrome-headless-shell.exe',
      )
      if (existsSync(exe)) return exe
    }
  }
  return undefined
}

const dataDir = await mkdtemp(path.join(tmpdir(), 'forma-ui-'))
const studio = createStudio({ dataDir })
await new Promise((resolve) => studio.server.listen(0, '127.0.0.1', resolve))
const url = 'http://127.0.0.1:' + studio.server.address().port
let browser
try {
  browser = await chromium.launch({
    executablePath: chromiumPath(),
    headless: true,
  })
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
  })
  const faults = []
  page.on('pageerror', (e) => faults.push(e.message))
  const act = (name) => page.locator('[data-act="' + name + '"]')
  await page.goto(url)
  await page.getByRole('heading', { name: '角色工作室', exact: true }).waitFor()
  await page
    .locator('.card-photo img')
    .first()
    .evaluate((img) => img.decode())
  assert.equal(await page.locator('.char-card').count(), 5)
  await mkdir('test-results', { recursive: true })
  await page.screenshot({ path: 'test-results/workspace.png' })
  await page.getByRole('button', { name: '收藏 Mio', exact: true }).click()
  await page.getByRole('button', { name: '已收藏', exact: true }).click()
  assert.equal(await page.locator('.char-card').count(), 1)
  await page.getByRole('button', { name: '全部角色', exact: true }).click()
  await page.getByRole('searchbox', { name: '搜尋角色' }).fill('Ren')
  assert.equal(await page.locator('.char-card').count(), 1)
  await page.getByRole('button', { name: '使用範本', exact: true }).click()
  await page.locator('[data-field=name]').fill('測試角色')
  await page.locator('[data-field=personality]').fill('平靜、親切')
  await page.locator('[data-act=choose][data-type=outfit]').click()
  await page.locator('dialog [data-act=lib-item]').first().click()
  await page.locator('[data-act=choose][data-type=pose]').click()
  await page.locator('dialog [data-act=lib-item]').first().click()
  await act('add-ref').click()
  await page.locator('#ref-label').selectOption('側面')
  await page.locator('#ref-file').setInputFiles('public/art/sora.webp')
  await act('upload-ref').click()
  await page.locator('dialog').waitFor({ state: 'hidden' })
  await act('save').click()
  await page.waitForURL(/#edit\/[\w-]{36}\/profile/)
  await page.reload()
  await page.locator('[data-field=name]').waitFor()
  assert.equal(await page.locator('[data-field=name]').inputValue(), '測試角色')
  const character = (await (await fetch(url + '/api/characters')).json())
    .characters[0]
  assert.equal(character.personality, '平靜、親切')
  assert.ok(character.outfit?.reference && character.pose?.reference)
  assert.equal(character.references.at(-1).label, '側面')
  await act('duplicate').click()
  await page.locator('#copy-name').fill('另一套造型')
  await act('save-copy').click()
  await page.getByRole('heading', { name: '另一套造型', exact: true }).waitFor()
  const variants = (await (await fetch(url + '/api/characters')).json())
    .characters
  assert.equal(variants.length, 2)
  assert.notEqual(variants[0].id, character.id)
  assert.deepEqual(variants[0].references, character.references)
  await page.locator('[data-act=clear-asset][data-type=pose]').click()
  await page.locator('[data-id=shoot][data-act=tab]').click()
  await act('prod-scene').click()
  await page.locator('dialog [data-act=lib-item]').nth(2).click()
  await act('save').click()
  await page.waitForFunction(
    () => !document.querySelector('[data-act=save]')?.disabled,
  )
  const variant = (
    await (await fetch(url + '/api/characters/' + variants[0].id)).json()
  ).character
  assert.equal(variant.pose, null)
  assert.equal(variant.scene, '雨夜街巷')
  assert.equal(
    (await (await fetch(url + '/api/characters/' + character.id)).json())
      .character.pose.id,
    character.pose.id,
  )
  await page.getByRole('heading', { name: '拍攝設定' }).waitFor()
  await page.screenshot({ path: 'test-results/shoot.png' })
  const otherPage = await fetch(url + '/api/characters/' + variant.id, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updatedAt: variant.updatedAt, name: '另一頁的角色版本' }),
  })
  assert.ok(otherPage.ok)
  await page.locator('[data-field=material]').fill('緞面')
  await act('save').click()
  await act('reload-role').click()
  await page.getByRole('heading', { name: '另一頁的角色版本', exact: true }).waitFor()
  await page.locator('[data-act=nav][data-page=settings]').first().click()
  await page.locator('#setting-openaiKey').fill('local-fixture-unused')
  await page
    .locator('[data-settings-group=openai] [data-act=settings-save]')
    .click()
  await page.getByText('已儲存金鑰', { exact: true }).waitFor()
  assert.equal(await page.locator('#setting-openaiKey').inputValue(), '')
  assert.equal(
    (await (await fetch(url + '/api/settings')).json()).settings.openaiKeySet,
    true,
  )
  page.once('dialog', (dialog) => dialog.accept())
  await page.locator('[data-act=settings-remove][data-key=openaiKey]').click()
  await page.getByText('尚未設定', { exact: true }).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator('[data-act=nav][data-page=home]').last().click()
  await page.locator('#home-search').fill('')
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  )
  await page.screenshot({ path: 'test-results/mobile.png' })
  assert.deepEqual(faults, [])
  console.log(
    '桌面與手機瀏覽器測試通過，包含角色、收藏、上傳、服裝、姿勢、場景、金鑰與重新載入。',
  )
} finally {
  await browser?.close()
  await studio.close()
  await rm(dataDir, { recursive: true, force: true })
}
