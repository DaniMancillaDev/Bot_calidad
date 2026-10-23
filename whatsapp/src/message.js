import { createHash } from 'node:crypto'

const WRAPPERS = [
  'ephemeralMessage',
  'viewOnceMessage',
  'viewOnceMessageV2',
  'viewOnceMessageV2Extension',
  'documentWithCaptionMessage',
]

export function unwrapMessage(message) {
  let current = message
  for (let count = 0; count < 8; count += 1) {
    const wrapper = WRAPPERS.find(name => current?.[name]?.message)
    if (!wrapper) return current
    current = current[wrapper].message
  }
  return current
}

export function messageTimestampToIso(value, fallback = new Date()) {
  const seconds = typeof value?.toNumber === 'function' ? value.toNumber() : Number(value)
  if (!Number.isFinite(seconds) || seconds <= 0) return fallback.toISOString()
  return new Date(seconds * 1000).toISOString()
}

function jidPhone(jid) {
  if (typeof jid !== 'string' || !jid.endsWith('@s.whatsapp.net')) return ''
  return jid.slice(0, -'@s.whatsapp.net'.length)
}

function stableBatchHash(...parts) {
  return createHash('sha256').update(parts.join('\u0000')).digest('hex')
}

function batchDescriptor(unwrapped, groupId, messageId) {
  const association = unwrapped?.messageContextInfo?.messageAssociation
    || unwrapped?.imageMessage?.contextInfo?.messageAssociation
  const parent = association?.parentMessageKey
  const associationType = association?.associationType
  const mediaIndex = Number(association?.messageIndex)
  const hasMediaIndex = Number.isSafeInteger(mediaIndex) && mediaIndex >= 0
  const isAlbum = Boolean(
    parent?.id
    && hasMediaIndex
    && (associationType == null || Number(associationType) === 1 || associationType === 'MEDIA_ALBUM'),
  )

  if (isAlbum) {
    return {
      receiptBatchKey: `album:${stableBatchHash(groupId, parent.id)}`,
      receiptBatchType: 'album',
      albumParentMessageId: parent.id,
      mediaIndex,
    }
  }

  return {
    receiptBatchKey: `message:${stableBatchHash(groupId, messageId)}`,
    receiptBatchType: 'single',
    albumParentMessageId: '',
    mediaIndex: 0,
  }
}

export function extractImage(message, receivedAt = new Date(), { allowFromMe = false } = {}) {
  const key = message?.key || {}
  const groupId = key.remoteJid
  const unwrapped = unwrapMessage(message?.message)
  const image = unwrapped?.imageMessage
  if (!groupId || !key.id || !image || (!allowFromMe && key.fromMe) || !groupId.endsWith('@g.us')) return null

  const senderId = key.participant || key.participantAlt || key.senderPn || key.senderLid || ''
  const alternateSenderId = [key.participantAlt, key.senderPn, key.senderLid]
    .find(value => value && value !== senderId) || ''
  const batch = batchDescriptor(unwrapped, groupId, key.id)

  return {
    message,
    groupId,
    messageId: key.id,
    mediaIndex: batch.mediaIndex,
    receiptBatchKey: batch.receiptBatchKey,
    receiptBatchType: batch.receiptBatchType,
    albumParentMessageId: batch.albumParentMessageId,
    senderId,
    senderAltId: alternateSenderId,
    senderName: message.pushName || '',
    phoneNumber: jidPhone(senderId),
    phoneNumberVerified: Boolean(jidPhone(senderId)),
    caption: image.caption || '',
    messageAt: messageTimestampToIso(message.messageTimestamp, receivedAt),
    imageMessage: image,
  }
}

export function queueKey(image) {
  return `${image.groupId}\u0000${image.messageId}\u0000${image.mediaIndex}`
}
