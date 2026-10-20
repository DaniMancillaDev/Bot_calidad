import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { extractImage } from '../src/message.js'
import { PersistentOutbox } from '../src/outbox.js'
import { WhatsAppReceiver } from '../src/receiver.js'

const image = (id, overrides = {}) => ({
  key: {
    id,
    remoteJid: '120363000000@g.us',
    participant: '12345@lid',
    participantAlt: '15551234567@s.whatsapp.net',
    ...overrides.key,
  },
  pushName: 'Inspector',
  messageTimestamp: 1_760_000_000,
  message: { imageMessage: { mimetype: 'image/jpeg', caption: 'defecto', ...overrides.image } },
  ...overrides,
})

async function makeReceiver(fetchImpl = async () => new Response('{}', { status: 201 })) {
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-'))
  const queue = await new PersistentOutbox({
    directory: join(root, 'queue'),
    ingestUrl: 'http://django.test/api/v1/whatsapp/ingest/',
    ingestKey: 'test-only-key',
    retryBaseMs: 1,
    retryMaxMs: 10,
    fetchImpl,
  }).init()
  return {
    root,
    queue,
    receiver: new WhatsAppReceiver({
      groups: new Set(['120363000000@g.us']),
      queue,
      mediaDir: join(root, 'media'),
      downloadMediaMessage: async () => Buffer.from('image-bytes'),
      maxBytes: 1024,
      logger: { error() {} },
    }),
  }
}

test('extracts image metadata without equating LID and phone JID', () => {
  const extracted = extractImage(image('message-1'))
  assert.equal(extracted.senderId, '12345@lid')
  assert.equal(extracted.senderAltId, '15551234567@s.whatsapp.net')
  assert.equal(extracted.phoneNumber, '')
  assert.equal(extracted.caption, 'defecto')
})

test('processes each live image, ignores history and non-allowlisted groups', async () => {
  const { receiver, queue } = await makeReceiver()
  await receiver.handleUpsert({ type: 'append', messages: [image('history')] })
  await receiver.handleUpsert({ type: 'notify', messages: [image('one'), image('two')] })
  await receiver.handleUpsert({ type: 'notify', messages: [image('other', { key: { remoteJid: 'other@g.us' } })] })
  assert.equal(queue.items.size, 2)
})

test('deduplicates reconnect delivery by group, message and media position', async () => {
  const { receiver, queue } = await makeReceiver()
  const message = image('same-message')
  await receiver.handleUpsert({ type: 'notify', messages: [message, message] })
  assert.equal(queue.items.size, 1)
})

test('persists queue, retries transient errors, and retains bytes until Django confirms', async () => {
  let calls = 0
  const first = await makeReceiver(async () => {
    calls += 1
    throw new Error('network unavailable')
  })
  await first.receiver.handleUpsert({ type: 'notify', messages: [image('retry-message')] })
  const item = [...first.queue.items.values()][0]
  await first.queue.processDue()
  assert.equal(item.state, 'failed')
  await stat(item.filePath)
  assert.equal(calls, 1)

  first.queue.fetchImpl = async () => new Response(JSON.stringify({ duplicate: true }), { status: 200 })
  await first.queue.processDue(Date.now() + 1000)
  assert.equal(item.state, 'delivered')
  await assert.rejects(stat(item.filePath), { code: 'ENOENT' })

  const reloaded = await new PersistentOutbox({ directory: first.queue.directory }).init()
  assert.equal(reloaded.items.get(item.key).state, 'delivered')
  assert.ok((await readFile(join(first.queue.directory, 'outbox.json'), 'utf8')).includes('retry-message'))
})

test('a failed media download is durable and can be retried when WhatsApp redelivers it', async () => {
  let attempts = 0
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-download-'))
  const queue = await new PersistentOutbox({ directory: join(root, 'queue') }).init()
  const receiver = new WhatsAppReceiver({
    groups: new Set(['120363000000@g.us']), queue, mediaDir: join(root, 'media'), maxBytes: 1024,
    downloadMediaMessage: async () => { attempts += 1; if (attempts === 1) throw new Error('expired')
      return Buffer.from('image') }, logger: { error() {} },
  })
  const message = image('download-retry')
  await receiver.handleUpsert({ type: 'notify', messages: [message] })
  assert.equal([...queue.items.values()][0].state, 'download_failed')
  await receiver.handleUpsert({ type: 'notify', messages: [message] })
  assert.equal([...queue.items.values()][0].state, 'pending')
  assert.equal(attempts, 2)
})

test('recovers a staged file after restart without exposing a half-written queue item', async () => {
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-stage-'))
  const directory = join(root, 'queue')
  const filePath = join(root, 'media', 'original')
  const queue = await new PersistentOutbox({ directory }).init()
  await queue.stage({ key: 'staged', fields: {}, filePath })
  await mkdir(join(root, 'media'), { recursive: true })
  await writeFile(filePath, 'bytes')
  const recovered = await new PersistentOutbox({ directory }).init()
  assert.equal(recovered.items.get('staged').state, 'pending')
})

test('requeues an HTTP delivery interrupted by an adapter restart', async () => {
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-restart-'))
  const first = await makeReceiver()
  first.queue.directory = join(root, 'queue')
  await first.queue.init()
  await first.receiver.handleUpsert({ type: 'notify', messages: [image('restart-delivery')] })
  const item = [...first.queue.items.values()][0]
  item.state = 'sending'
  await first.queue.persist()

  const recovered = await new PersistentOutbox({ directory: first.queue.directory, fetchImpl: async () => new Response('{}', { status: 201 }) }).init()
  assert.equal(recovered.items.get(item.key).state, 'pending')
  await recovered.processDue()
  assert.equal(recovered.items.get(item.key).state, 'delivered')
})

test('keeps different senders as separate source events in one group', async () => {
  const { receiver, queue } = await makeReceiver()
  await receiver.handleUpsert({ type: 'notify', messages: [
    image('sender-one', { key: { id: 'sender-one', remoteJid: '120363000000@g.us', participant: 'one@lid', participantAlt: '' } }),
    image('sender-two', { key: { id: 'sender-two', remoteJid: '120363000000@g.us', participant: 'two@lid', participantAlt: '' } }),
  ] })
  assert.equal(queue.items.size, 2)
  assert.deepEqual([...queue.items.values()].map(item => item.fields.sender_id).sort(), ['one@lid', 'two@lid'])
})

test('times out a hung Django request and leaves the item retryable', async () => {
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-timeout-'))
  const queue = await new PersistentOutbox({
    directory: join(root, 'queue'), httpTimeoutMs: 1, retryBaseMs: 1,
    fetchImpl: async (_url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')))
    }),
  }).init()
  const receiver = new WhatsAppReceiver({
    groups: new Set(['120363000000@g.us']), queue, mediaDir: join(root, 'media'), maxBytes: 1024,
    downloadMediaMessage: async () => Buffer.from('image'), logger: { error() {} },
  })
  await receiver.handleUpsert({ type: 'notify', messages: [image('timeout')] })
  await queue.processDue()
  assert.equal([...queue.items.values()][0].state, 'failed')
})

test('refreshes expired media once through Baileys before recording failure', async () => {
  let downloads = 0
  let refreshes = 0
  const root = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-refresh-'))
  const queue = await new PersistentOutbox({ directory: join(root, 'queue') }).init()
  const receiver = new WhatsAppReceiver({
    groups: new Set(['120363000000@g.us']), queue, mediaDir: join(root, 'media'), maxBytes: 1024,
    downloadMediaMessage: async message => {
      downloads += 1
      if (downloads === 1) throw Object.assign(new Error('expired'), { status: 410 })
      return Buffer.from(message.refreshed ? 'image' : 'wrong')
    },
    updateMediaMessage: async message => { refreshes += 1; return { ...message, refreshed: true } },
    logger: { error() {} },
  })
  await receiver.handleUpsert({ type: 'notify', messages: [image('refresh')] })
  assert.equal(refreshes, 1)
  assert.equal(downloads, 2)
  assert.equal([...queue.items.values()][0].state, 'pending')
})
