import assert from 'node:assert/strict'
import { test } from 'node:test'
import { configFromEnv } from '../src/config.js'

test('discovery mode may connect without an allowlist but remains non-ingesting', () => {
  const config = configFromEnv({
    WHATSAPP_ENABLED: 'true',
    WHATSAPP_DISCOVERY_ONLY: 'true',
    WHATSAPP_INGEST_API_KEY: 'test-only-key',
  })
  assert.equal(config.discoveryOnly, true)
  assert.equal(config.groups.size, 0)
})

test('normal enabled mode still requires an allowlist', () => {
  assert.throws(
    () => configFromEnv({ WHATSAPP_ENABLED: 'true', WHATSAPP_INGEST_API_KEY: 'test-only-key' }),
    /WHATSAPP_ALLOWED_GROUP_IDS is required/,
  )
})

test('own messages are rejected unless explicitly enabled', () => {
  const disabled = configFromEnv({
    WHATSAPP_ENABLED: 'true',
    WHATSAPP_ALLOWED_GROUP_IDS: 'group-1',
    WHATSAPP_INGEST_API_KEY: 'key',
  })
  const enabled = configFromEnv({
    WHATSAPP_ENABLED: 'true',
    WHATSAPP_ALLOWED_GROUP_IDS: 'group-1',
    WHATSAPP_INGEST_API_KEY: 'key',
    WHATSAPP_ACCEPT_OWN_MESSAGES: 'true',
  })
  assert.equal(disabled.acceptOwnMessages, false)
  assert.equal(enabled.acceptOwnMessages, true)
})
