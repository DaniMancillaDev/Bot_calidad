import makeWASocket, {
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from '@whiskeysockets/baileys'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import { mkdir } from 'node:fs/promises'
import { configFromEnv } from './config.js'
import { PersistentOutbox } from './outbox.js'
import { WhatsAppReceiver } from './receiver.js'
import { openPersistentSession } from './session.js'
import { installSignalSessionLogFilter } from './logging.js'

installSignalSessionLogFilter()
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
  acceptOwnMessages: config.acceptOwnMessages,
  maxBytes: config.maxBytes,
  logger,
})
if (!config.discoveryOnly) outbox.start(config.pollMs)

let reconnectTimer
let discoveryStarted = false
let baileysVersion
let baileysVersionLoaded = false
const groupNames = new Map()

async function getGroupName(socket, groupId) {
  if (groupNames.has(groupId)) return groupNames.get(groupId)
  const metadata = await socket.groupMetadata(groupId)
  const name = String(metadata.subject || '').trim() || groupId
  groupNames.set(groupId, name)
  return name
}
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
  if (!baileysVersionLoaded) {
    baileysVersionLoaded = true
    try {
      const latest = await fetchLatestBaileysVersion()
      baileysVersion = latest.version
    } catch (error) {
      logger.warn({ err: error }, 'Baileys version lookup failed; using the installed default')
    }
  }
  const socket = makeWASocket({
    ...(baileysVersion ? { version: baileysVersion } : {}),
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    markOnlineOnConnect: false,
    syncFullHistory: false,
    logger,
  })
  receiver.setMediaUpdater(message => socket.updateMediaMessage(message))
  receiver.setGroupNameResolver(groupId => getGroupName(socket, groupId))
  socket.ev.process(async events => {
    // Baileys can emit creds.update immediately before the 515 restart.
    // Awaiting this in the same event processor prevents reconnecting with stale auth.
    if (events['creds.update']) await saveCreds()

    if (events['connection.update']) {
      const { connection, lastDisconnect, qr } = events['connection.update']
      if (qr && config.qrInTerminal) qrcode.generate(qr, { small: true })
      if (connection === 'open') {
        console.log('CONNECTION\topen')
        if (config.discoveryOnly) void discoverGroups(socket)
      }
      if (connection === 'close') {
        const status = lastDisconnect?.error?.output?.statusCode
        console.log(`CONNECTION\tclose\tstatus=${status ?? 'unknown'}`)
        if (status === DisconnectReason.loggedOut) {
          logger.error('WhatsApp session logged out; manual re-pairing is required')
        } else {
          clearTimeout(reconnectTimer)
          const delay = status === DisconnectReason.restartRequired ? 0 : 3000
          reconnectTimer = setTimeout(() => connect().catch(error => logger.error({ err: error }, 'WhatsApp reconnect failed')), delay)
        }
      }
    }

    if (!config.discoveryOnly && events['messages.upsert']) {
      await receiver.handleUpsert(events['messages.upsert'])
    }
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
