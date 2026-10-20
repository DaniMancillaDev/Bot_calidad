import makeWASocket, {
  DisconnectReason,
  downloadMediaMessage,
  makeCacheableSignalKeyStore,
} from '@whiskeysockets/baileys'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import { mkdir } from 'node:fs/promises'
import { configFromEnv } from './config.js'
import { PersistentOutbox } from './outbox.js'
import { WhatsAppReceiver } from './receiver.js'
import { openPersistentSession } from './session.js'

const config = configFromEnv()
if (!config.enabled) {
  console.log('WhatsApp adapter disabled (set WHATSAPP_ENABLED=true to enable)')
  process.exit(0)
}

const logger = pino({ level: process.env.WHATSAPP_LOG_LEVEL || 'warn' })
const session = await openPersistentSession(config.sessionDir)
const { state, saveCreds } = session
const outbox = await new PersistentOutbox({
  directory: config.queueDir,
  ingestUrl: config.ingestUrl,
  ingestKey: config.ingestKey,
  retryBaseMs: config.retryBaseMs,
  retryMaxMs: config.retryMaxMs,
  httpTimeoutMs: config.httpTimeoutMs,
  logger,
}).init()
const receiver = new WhatsAppReceiver({
  groups: config.groups,
  queue: outbox,
  mediaDir: config.queueDir + '/media',
  downloadMediaMessage,
  maxBytes: config.maxBytes,
  logger,
})
if (!config.discoveryOnly) outbox.start(config.pollMs)

let reconnectTimer
let discoveryStarted = false
async function discoverGroups(socket) {
  if (discoveryStarted) return
  discoveryStarted = true
  try {
    const groups = await socket.groupFetchAllParticipating()
    for (const group of Object.values(groups).sort((left, right) => String(left.subject || '').localeCompare(String(right.subject || '')))) {
      if (!group.id) continue
      console.log(`GROUP\t${JSON.stringify(group.subject || '')}\t${group.id}`)
    }
    await session.release()
    process.exit(0)
  } catch (error) {
    logger.error({ err: error }, 'WhatsApp group discovery failed')
    await session.release()
    process.exit(1)
  }
}

async function connect() {
  const socket = makeWASocket({
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    markOnlineOnConnect: false,
    syncFullHistory: false,
    logger,
  })
  receiver.setMediaUpdater(message => socket.updateMediaMessage(message))
  socket.ev.on('creds.update', saveCreds)
  if (!config.discoveryOnly) socket.ev.on('messages.upsert', event => receiver.handleUpsert(event))
  socket.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr && config.qrInTerminal) qrcode.generate(qr, { small: true })
    if (connection === 'open' && config.discoveryOnly) void discoverGroups(socket)
    if (connection !== 'close') return
    const status = lastDisconnect?.error?.output?.statusCode
    if (status === DisconnectReason.loggedOut) {
      logger.error('WhatsApp session logged out; manual re-pairing is required')
      return
    }
    clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(() => connect().catch(error => logger.error({ err: error }, 'WhatsApp reconnect failed')), 3000)
    reconnectTimer.unref?.()
  })
}

await mkdir(config.queueDir, { recursive: true, mode: 0o700 })
const shutdown = async () => {
  clearTimeout(reconnectTimer)
  await session.release()
  process.exit(0)
}
process.once('SIGINT', shutdown)
process.once('SIGTERM', shutdown)
await connect()
