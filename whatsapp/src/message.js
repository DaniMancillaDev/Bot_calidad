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

export function extractImage(message, receivedAt = new Date()) {
  const key = message?.key || {}
  const groupId = key.remoteJid
  const unwrapped = unwrapMessage(message?.message)
  const image = unwrapped?.imageMessage
  if (!groupId || !key.id || !image || key.fromMe || !groupId.endsWith('@g.us')) return null

  const senderId = key.participant || key.participantAlt || key.senderPn || key.senderLid || ''
  const alternateSenderId = [key.participantAlt, key.senderPn, key.senderLid]
    .find(value => value && value !== senderId) || ''

  return {
    message,
    groupId,
    messageId: key.id,
    mediaIndex: 0,
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
