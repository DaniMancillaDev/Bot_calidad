import { mkdir, writeFile, rename, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { extractImage, queueKey } from './message.js'

function safeError(error) {
  return String(error?.message || 'media download failed').slice(0, 300)
}

export class WhatsAppReceiver {
  constructor({ groups, queue, mediaDir, downloadMediaMessage, updateMediaMessage = null, maxBytes, acceptOwnMessages = false, logger = console }) {
    this.groups = groups
    this.queue = queue
    this.mediaDir = mediaDir
    this.downloadMediaMessage = downloadMediaMessage
    this.updateMediaMessage = updateMediaMessage
    this.maxBytes = maxBytes
    this.acceptOwnMessages = acceptOwnMessages
    this.getGroupName = async groupId => groupId
    this.logger = logger
    this.chain = Promise.resolve()
  }

  setMediaUpdater(updateMediaMessage) {
    this.updateMediaMessage = updateMediaMessage
  }

  setGroupNameResolver(getGroupName) {
    this.getGroupName = getGroupName
  }

  async download(image) {
    try {
      return await this.downloadMediaMessage(image.message, 'buffer', {})
    } catch (error) {
      const status = error?.status || error?.output?.statusCode
      if (!this.updateMediaMessage || ![404, 410].includes(status)) throw error
      const refreshed = await this.updateMediaMessage(image.message)
      return this.downloadMediaMessage(refreshed, 'buffer', {})
    }
  }

  handleUpsert({ messages = [], type }) {
    // Baileys emits messages sent by this device as append; history remains ignored.
    const ownAppend = type === 'append' && this.acceptOwnMessages
    if (type !== 'notify' && !ownAppend) return this.chain
    const acceptedMessages = ownAppend ? messages.filter(message => message.key?.fromMe) : messages
    this.chain = this.chain.then(async () => {
      for (const message of acceptedMessages) await this.handleMessage(message)
    }).catch(error => this.logger.error?.('WhatsApp message processing failed', safeError(error)))
    return this.chain
  }

  async handleMessage(message) {
    const image = extractImage(message, new Date(), { allowFromMe: this.acceptOwnMessages })
    if (!image || !this.groups.has(image.groupId)) return { ignored: true }
    let groupName = image.groupId
    try {
      groupName = await this.getGroupName(image.groupId) || groupName
    } catch (error) {
      this.logger.warn?.('WhatsApp group metadata unavailable; using group ID', safeError(error))
    }
    const key = queueKey(image)
    const fields = {
      group_id: image.groupId,
      group_name: groupName,
      message_id: image.messageId,
      media_index: image.mediaIndex,
      receipt_batch_key: image.receiptBatchKey,
      sender_id: image.senderId,
      sender_alt_id: image.senderAltId,
      sender_name: image.senderName,
      caption: image.caption,
      message_at: image.messageAt,
      phone_number: image.phoneNumber,
      phone_number_verified: image.phoneNumberVerified,
      historical: false,
      mime_type: image.imageMessage.mimetype || 'image/jpeg',
    }
    const known = this.queue.items.get(key)
    if (known && known.state !== 'download_failed') return { duplicate: true }

    const announcedSize = Number(image.imageMessage.fileLength)
    if (Number.isFinite(announcedSize) && announcedSize > this.maxBytes) {
      await this.queue.addDownloadFailure({ key, fields, error: new Error('media exceeds configured size limit') })
      return { rejected: true }
    }

    let bytes
    try {
      bytes = await this.download(image)
      if (!Buffer.isBuffer(bytes) || bytes.length === 0 || bytes.length > this.maxBytes) throw new Error('downloaded media is empty or too large')
    } catch (error) {
      await this.queue.addDownloadFailure({ key, fields, error })
      return { failed: true }
    }

    const digest = createHash('sha256').update(bytes).digest('hex')
    const directory = join(this.mediaDir, createHash('sha256').update(key).digest('hex'))
    const temporary = join(directory, '.original.tmp')
    const finalPath = join(directory, 'original')
    await mkdir(directory, { recursive: true, mode: 0o700 })
    try {
      const staged = await this.queue.stage({ key, fields, filePath: finalPath })
      if (staged.duplicate) return staged
      await writeFile(temporary, bytes, { mode: 0o600 })
      await rename(temporary, finalPath)
      const item = await this.queue.activate(key, { ...fields, sha256: digest, size_bytes: bytes.length })
      this.logger.info?.({ batchType: image.receiptBatchType, batchKey: image.receiptBatchKey, mediaIndex: image.mediaIndex }, 'WhatsApp image accepted')
      return { item, duplicate: false }
    } catch (error) {
      await rm(directory, { recursive: true, force: true })
      await this.queue.markDownloadFailure(key, error)
      throw error
    }
  }
}
