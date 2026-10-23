const boolean = (value, fallback = false) => {
  if (value == null || value === '') return fallback
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase())
}

const positiveInt = (value, fallback) => {
  const parsed = Number.parseInt(value ?? '', 10)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function configFromEnv(env = process.env) {
  const enabled = boolean(env.WHATSAPP_ENABLED)
  const groups = new Set((env.WHATSAPP_ALLOWED_GROUP_IDS || '').split(',').map(value => value.trim()).filter(Boolean))
  const config = {
    enabled,
    groups,
    discoveryOnly: boolean(env.WHATSAPP_DISCOVERY_ONLY),
    acceptOwnMessages: boolean(env.WHATSAPP_ACCEPT_OWN_MESSAGES),
    sessionDir: env.WHATSAPP_SESSION_DIR || '/app/data/whatsapp_session',
    queueDir: env.WHATSAPP_QUEUE_DIR || '/app/data/whatsapp_queue',
    ingestUrl: env.WHATSAPP_INGEST_URL || 'http://web:8000/api/v1/whatsapp/ingest/',
    ingestKey: env.WHATSAPP_INGEST_API_KEY || '',
    maxBytes: positiveInt(env.WHATSAPP_MAX_IMAGE_BYTES, 25 * 1024 * 1024),
    retryBaseMs: positiveInt(env.WHATSAPP_RETRY_BASE_MS, 1000),
    retryMaxMs: positiveInt(env.WHATSAPP_RETRY_MAX_MS, 15 * 60 * 1000),
    pollMs: positiveInt(env.WHATSAPP_QUEUE_POLL_MS, 1000),
    httpTimeoutMs: positiveInt(env.WHATSAPP_HTTP_TIMEOUT_MS, 30 * 1000),
    qrInTerminal: boolean(env.WHATSAPP_QR_IN_TERMINAL),
  }
  if (enabled && !groups.size && !config.discoveryOnly) throw new Error('WHATSAPP_ALLOWED_GROUP_IDS is required when WhatsApp is enabled')
  if (enabled && !config.ingestKey) throw new Error('WHATSAPP_INGEST_API_KEY is required when WhatsApp is enabled')
  return config
}
