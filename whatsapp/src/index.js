import makeWASocket, {
  DisconnectReason,
  downloadMediaMessage,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import { mkdir } from 'node:fs/promises'
import { configFromEnv } from './config.js'
import { PersistentOutbox } from './outbox.js'
import { WhatsAppReceiver } from './receiver.js'

const config = configFromEnv()
if (!config.enabled) {
  console.log('WhatsApp adapter disabled (set WHATSAPP_ENABLED=true to enable)')
  process.exit(0)
}

const logger = pino({ level: process.env.WHATSAPP_LOG_LEVEL || 'warn' })
const { state, saveCreds } = await useMultiFileAuthState(config.sessionDir)
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
outbox.start(config.pollMs)

let reconnectTimer
async function connect() {
  const socket = makeWASocket({
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    markOnlineOnConnect: false,
    syncFullHistory: false,
    logger,
  })
  socket.ev.on('creds.update', saveCreds)
  socket.ev.on('messages.upsert', event => receiver.handleUpsert(event))
  socket.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr && config.qrInTerminal) qrcode.generate(qr, { small: true })
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
await connect()
