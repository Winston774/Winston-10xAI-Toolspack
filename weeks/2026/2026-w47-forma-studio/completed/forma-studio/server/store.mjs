import { DatabaseSync } from 'node:sqlite'
import { chmodSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { protect, takeSecrets, unprotect, withoutSecrets } from './credentials.mjs'

const DEFAULTS = {
  imageModel: 'gpt-image-2.6-sunburst', textModel: 'gpt-6.1-terra',
  fishModel: 's2-pro', breezeUrl: '', longcatEnabled: false,
  openaiKey: '', fishApiKey: '', breezeToken: '',
}

export class Problem extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export function check(condition, message, status = 400) {
  if (!condition) throw new Problem(status, message)
}

export function publicSettings({ openaiKey, fishApiKey, breezeToken, ...rest }) {
  return { ...rest, openaiKeySet: !!openaiKey, fishKeySet: !!fishApiKey, breezeTokenSet: !!breezeToken }
}

export class StudioStore {
  constructor(root) {
    mkdirSync(root, { recursive: true, mode: 0o700 })
    // A second port must not mark the first process's live provider jobs as interrupted.
    // SQLite releases this separate lock even when the owning process is terminated.
    this.runtimeLock = new DatabaseSync(path.join(root,'runtime.sqlite'))
    try { this.runtimeLock.exec('BEGIN EXCLUSIVE') } catch (error) {
      this.runtimeLock.close()
      if (error.errcode === 5 || error.errcode === 6) throw new Problem(409,'這個資料目錄已由另一個工作室使用。')
      throw error
    }
    this.db = new DatabaseSync(path.join(root, 'studio.sqlite'))
    if (process.platform !== 'win32') chmodSync(path.join(root,'studio.sqlite'),0o600)
    this.db.exec(`
      PRAGMA journal_mode = WAL;
      PRAGMA busy_timeout = 5000;
      PRAGMA secure_delete = ON;
      CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS characters (id TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS files (url TEXT PRIMARY KEY, relative_path TEXT NOT NULL);
    `)
  }

  settings() {
    if (this.currentSettings) return {...this.currentSettings}
    const row = this.db.prepare('SELECT value FROM settings WHERE id=1').get()
    const record=JSON.parse(row?.value || '{}')
    const {protectedSecrets,...fields}=record
    const next={...DEFAULTS,...fields}
    if(protectedSecrets) {
      check(process.platform==='win32','請使用儲存金鑰時的 Windows 帳戶開啟本機資料。',409)
      try { Object.assign(next,unprotect(protectedSecrets)) }
      catch { throw new Problem(409,'無法讀取 Windows 帳戶保護的金鑰。請使用原帳戶開啟工作室。') }
      this.protectedSecrets=protectedSecrets
    } else if(process.platform==='win32' && Object.values(takeSecrets(next)).some(Boolean)) {
      this.persistSettings(next)
      this.db.exec('PRAGMA wal_checkpoint(TRUNCATE)')
    }
    this.currentSettings=next
    return {...next}
  }
  persistSettings(next) {
    let record=next
    let ciphertext
    if(process.platform==='win32') {
      const secret=takeSecrets(next)
      record=withoutSecrets(next)
      if(Object.values(secret).some(Boolean)) {
        const same=this.currentSettings && JSON.stringify(secret)===JSON.stringify(takeSecrets(this.currentSettings))
        try { ciphertext=same && this.protectedSecrets ? this.protectedSecrets : protect(secret) }
        catch { throw new Problem(500,'Windows 無法保護金鑰，設定尚未寫入。') }
        record.protectedSecrets=ciphertext
      }
    }
    this.db.prepare('INSERT OR REPLACE INTO settings VALUES (1, ?)').run(JSON.stringify(record))
    this.protectedSecrets=ciphertext
    this.currentSettings={...next}
  }

  updateSettings(input) {
    const next = this.settings()
    if ('fishKey' in input) input = { ...input, fishApiKey: input.fishKey }
    for (const key of Object.keys(DEFAULTS)) {
      if (!(key in input)) continue
      const value = input[key]
      if (typeof DEFAULTS[key] === 'boolean') {
        check(typeof value === 'boolean', '啟用選項格式錯誤。')
        next[key] = value
        continue
      }
      check(typeof value === 'string' && value.length < 4096, '設定欄位格式錯誤。')
      const trimmed = value.trim()
      if (key.endsWith('Model')) check(/^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/.test(trimmed), '請輸入有效的模型 ID。')
      if (key === 'breezeUrl' && trimmed) {
        const url = URL.parse(trimmed)
        check(url && !url.username && !url.password && !url.search && !url.hash &&
          (url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))), '請填入 HTTPS 的 Breeze 服務網址，或本機 HTTP 網址。')
      }
      next[key] = trimmed
    }
    this.persistSettings(next)
    return publicSettings(next)
  }

  // Table names are supplied only by server routes.
  list(table) {
    return this.db.prepare(`SELECT value FROM ${table} ORDER BY rowid DESC`).all().map(row => JSON.parse(row.value))
  }
  get(table, id) {
    const row = this.db.prepare(`SELECT value FROM ${table} WHERE id=?`).get(id)
    if (!row) throw new Problem(404, table === 'jobs' ? '找不到這項任務。' : '找不到這個角色。')
    return JSON.parse(row.value)
  }
  put(table, record) {
    this.db.prepare(`INSERT INTO ${table} VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET value=excluded.value`).run(record.id, JSON.stringify(record))
    return record
  }
  removeCharacter(id) {
    this.get('characters', id)
    this.db.prepare('DELETE FROM characters WHERE id=?').run(id)
  }
  rememberFile(url, relativePath) {
    this.db.prepare('INSERT OR REPLACE INTO files VALUES (?, ?)').run(url, relativePath)
    return url
  }
  file(url) {
    return this.db.prepare('SELECT relative_path FROM files WHERE url=?').get(url)?.relative_path
  }
  recover() {
    for (const job of this.list('jobs')) {
      if (['queued','running'].includes(job.status)) this.put('jobs', {
        ...job, status: 'failed', completedAt: new Date().toISOString(), progress: '',
        error: '本機服務重新啟動，原任務已中斷。請確認供應商的執行紀錄後再重新送出。',
      })
    }
  }
  close() { this.db.close(); this.runtimeLock.close() }
}
