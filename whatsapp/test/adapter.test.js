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
