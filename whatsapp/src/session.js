import { chmod, mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { useMultiFileAuthState } from '@whiskeysockets/baileys'

const LOCK_DIR = '.lock'
const OWNER_FILE = 'owner.json'
const STALE_LOCK_GRACE_MS = 30_000
const PROCESS_STARTED_AT = Date.now() - process.uptime() * 1000

async function harden(directory) {
  await chmod(directory, 0o700)
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name === LOCK_DIR) continue
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await chmod(path, 0o700)
    else if (entry.isFile()) await chmod(path, 0o600)
  }
}

async function validateJsonFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith('.json')) continue
    try {
      JSON.parse(await readFile(join(directory, entry.name), 'utf8'))
    } catch {
      throw new Error('WhatsApp auth state is corrupt; restore a backup or remove the session manually')
    }
  }
}

async function lockIsStale(lockPath) {
  let owner
  try {
    owner = JSON.parse(await readFile(join(lockPath, OWNER_FILE), 'utf8'))
  } catch {
    const details = await stat(lockPath).catch(() => null)
    return Boolean(details && Date.now() - details.mtimeMs > STALE_LOCK_GRACE_MS)
  }

  if (!Number.isInteger(owner.pid) || owner.pid <= 0) return true
  if (owner.pid === process.pid) {
    const ownerStartedAt = Date.parse(owner.startedAt || '')
    if (!Number.isFinite(ownerStartedAt) || Math.abs(ownerStartedAt - PROCESS_STARTED_AT) > 2_000) return true
  }
  try {
    process.kill(owner.pid, 0)
    return false
  } catch (error) {
    return error.code === 'ESRCH'
  }
}

async function acquireLock(directory) {
  const lockPath = join(directory, LOCK_DIR)
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await mkdir(lockPath, { mode: 0o700 })
      await writeFile(join(lockPath, OWNER_FILE), JSON.stringify({ pid: process.pid, startedAt: new Date(PROCESS_STARTED_AT).toISOString() }), { mode: 0o600, flag: 'wx' })
      return async () => rm(lockPath, { recursive: true, force: true })
    } catch (error) {
      if (error.code !== 'EEXIST' || attempt > 0 || !(await lockIsStale(lockPath))) {
        throw new Error('WhatsApp auth state is already in use by another adapter process')
      }
      await rm(lockPath, { recursive: true, force: true })
    }
  }
  throw new Error('unable to acquire WhatsApp auth state lock')
}

export async function openPersistentSession(directory) {
  await mkdir(directory, { recursive: true, mode: 0o700 })
  const releaseLock = await acquireLock(directory)
  try {
    await harden(directory)
    await validateJsonFiles(directory)
    const auth = await useMultiFileAuthState(directory)
    const saveCreds = async () => {
      await auth.saveCreds()
      await harden(directory)
    }
    const setKeys = auth.state.keys.set
    auth.state.keys.set = async values => {
      await setKeys(values)
      await harden(directory)
    }
    let released = false
    return {
      state: auth.state,
      saveCreds,
      release: async () => {
        if (released) return
        released = true
        await releaseLock()
      },
    }
  } catch (error) {
    await releaseLock()
    throw error
  }
}
