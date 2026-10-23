import { access, mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'

const FILE = 'outbox.json'

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export class PersistentOutbox {
  constructor({ directory, ingestUrl, ingestKey, retryBaseMs = 1000, retryMaxMs = 900000, httpTimeoutMs = 30000, fetchImpl = fetch, logger = console }) {
    this.directory = directory
    this.ingestUrl = ingestUrl
    this.ingestKey = ingestKey
    this.retryBaseMs = retryBaseMs
    this.retryMaxMs = retryMaxMs
    this.httpTimeoutMs = httpTimeoutMs
    this.fetchImpl = fetchImpl
    this.logger = logger
    this.items = new Map()
    this.writeChain = Promise.resolve()
    this.processing = false
  }

  async init() {
    await mkdir(this.directory, { recursive: true, mode: 0o700 })
    let changed = false
    try {
      const parsed = JSON.parse(await readFile(join(this.directory, FILE), 'utf8'))
      for (const item of Object.values(parsed.items || {})) {
        if (item.state === 'sending') item.state = 'pending'
        if (item.state === 'staging') {
          try {
            await access(item.filePath)
            item.state = 'pending'
          } catch {
            item.state = 'download_failed'
            item.lastError = 'adapter restarted while staging media'
          }
          changed = true
        }
        this.items.set(item.key, item)
      }
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
    if (changed) await this.persist()
    return this
  }

  async persist() {
    const payload = JSON.stringify({ version: 1, items: Object.fromEntries(this.items) })
    const temporary = join(this.directory, `.${FILE}.${randomUUID()}.tmp`)
    this.writeChain = this.writeChain.then(async () => {
      await writeFile(temporary, payload, { mode: 0o600 })
      await rename(temporary, join(this.directory, FILE))
    })
    return this.writeChain
  }

  async stage({ key, fields, filePath }) {
    const existing = this.items.get(key)
    if (existing && !['download_failed', 'staging'].includes(existing.state)) return { item: existing, duplicate: true }
    if (existing) {
      existing.fields = fields
      existing.filePath = filePath
      existing.state = 'staging'
      existing.lastError = ''
      existing.nextAttemptAt = 0
      await this.persist()
      return { item: existing, duplicate: false, recovered: true }
    }
    const item = {
      key,
      id: randomUUID(),
      fields,
      filePath,
      state: 'staging',
      attempts: 0,
      nextAttemptAt: 0,
      lastError: '',
      createdAt: new Date().toISOString(),
    }
    this.items.set(key, item)
    await this.persist()
    return { item, duplicate: false }
  }

  async activate(key, fields) {
    const item = this.items.get(key)
    if (!item) throw new Error('cannot activate an unknown outbox item')
    item.fields = fields
    item.state = 'pending'
    item.lastError = ''
    await this.persist()
    return item
  }

  async addDownloadFailure({ key, fields, error }) {
    const existing = this.items.get(key)
    if (existing) return { item: existing, duplicate: true }
    const item = {
      key, id: randomUUID(), fields, filePath: '', state: 'download_failed', attempts: 0,
      nextAttemptAt: 0, lastError: String(error?.message || 'download failed').slice(0, 300),
      createdAt: new Date().toISOString(),
    }
    this.items.set(key, item)
    await this.persist()
    return { item, duplicate: false }
  }

  async markDownloadFailure(key, error) {
    const item = this.items.get(key)
    if (!item) return
    item.state = 'download_failed'
    item.filePath = ''
    item.lastError = String(error?.message || 'media staging failed').slice(0, 300)
    await this.persist()
  }

  async send(item) {
    const body = new FormData()
    for (const [name, value] of Object.entries(item.fields)) body.append(name, String(value ?? ''))
    const bytes = await readFile(item.filePath)
    body.append('file', new Blob([bytes], { type: item.fields.mime_type }), 'original')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.httpTimeoutMs)
    try {
      const response = await this.fetchImpl(this.ingestUrl, {
        method: 'POST',
        headers: { 'X-WhatsApp-Ingest-Key': this.ingestKey },
        body,
        signal: controller.signal,
      })
      if (![200, 201].includes(response.status)) throw new Error(`Django ingest returned HTTP ${response.status}`)
    } finally {
      clearTimeout(timeout)
    }
  }

  async processDue(now = Date.now()) {
    if (this.processing) return
    this.processing = true
    try {
      for (const item of this.items.values()) {
        if (!['pending', 'failed'].includes(item.state) || item.nextAttemptAt > now) continue
        if (!item.filePath) continue
        item.state = 'sending'
        item.attempts += 1
        await this.persist()
        try {
          await this.send(item)
          item.state = 'delivered'
          item.lastError = ''
          await this.persist()
          // Keep the metadata for idempotency; delete only after Django confirms receipt.
          await rm(item.filePath, { force: true })
        } catch (error) {
          item.state = 'failed'
          item.lastError = String(error?.message || 'delivery failed').slice(0, 300)
          const delay = Math.min(this.retryMaxMs, this.retryBaseMs * (2 ** Math.min(item.attempts - 1, 10)))
          item.nextAttemptAt = Date.now() + delay
          await this.persist()
        }
      }
    } finally {
      this.processing = false
    }
  }

  start(pollMs) {
    const timer = setInterval(() => this.processDue().catch(error => {
      this.logger.error?.('WhatsApp outbox processing failed', String(error?.message || 'unknown error').slice(0, 300))
    }), pollMs)
    return timer
  }

  async waitForIdle() {
    while (this.processing) await sleep(5)
  }
}
