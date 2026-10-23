import assert from 'node:assert/strict'
import { test } from 'node:test'
import { installSignalSessionLogFilter } from '../src/logging.js'

test('filters libsignal session dumps but keeps normal info logs', () => {
  const calls = []
  const output = { info: (...args) => calls.push(args) }

  installSignalSessionLogFilter(output)
  output.info('Closing session:', { privKey: 'secret' })
  output.info('Opening session:', { rootKey: 'secret' })
  output.info('normal message')

  assert.deepEqual(calls, [['normal message']])
})
