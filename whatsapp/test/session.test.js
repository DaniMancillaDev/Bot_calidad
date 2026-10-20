import assert from 'node:assert/strict'
import { chmod, mkdtemp, readFile, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawn } from 'node:child_process'
import { test } from 'node:test'
import { openPersistentSession } from '../src/session.js'

function runChildSession(directory) {
  const moduleUrl = new URL('../src/session.js', import.meta.url).href
  const source = `import { openPersistentSession } from ${JSON.stringify(moduleUrl)}; await openPersistentSession(process.env.SESSION_DIR)`
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['--input-type=module', '-e', source], {
      env: { ...process.env, SESSION_DIR: directory },
      stdio: ['ignore', 'ignore', 'pipe'],
    })
    let stderr = ''
    child.stderr.on('data', chunk => { stderr += chunk })
    child.on('close', code => resolve({ code, stderr }))
  })
}

test('persists auth files privately and prevents a second process in the same session', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-session-'))
  const first = await openPersistentSession(directory)
  try {
    const rootMode = (await stat(directory)).mode & 0o777
    assert.equal(rootMode, 0o700)
    await first.saveCreds()
    const credsMode = (await stat(join(directory, 'creds.json'))).mode & 0o777
    assert.equal(credsMode, 0o600)
    await assert.rejects(openPersistentSession(directory), /already in use/)
    const child = await runChildSession(directory)
    assert.notEqual(child.code, 0)
    assert.match(child.stderr, /already in use/)
  } finally {
    await first.release()
  }

  const second = await openPersistentSession(directory)
  await second.release()
})

test('fails closed when a persisted auth JSON file is corrupt', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'bot-calidad-wa-session-corrupt-'))
  await chmod(directory, 0o700)
  await writeFile(join(directory, 'creds.json'), '{not-json', { mode: 0o600 })
  await assert.rejects(openPersistentSession(directory), /auth state is corrupt/)
  assert.equal(await readFile(join(directory, 'creds.json'), 'utf8'), '{not-json')
})
