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
