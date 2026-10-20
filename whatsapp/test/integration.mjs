import assert from 'node:assert/strict'

const url = process.env.WA_TEST_INGEST_URL
const key = process.env.WA_TEST_INGEST_KEY
assert.ok(url && key)

// 1x1 JPEG: valid content for Django/Pillow, not a production photograph.
const jpeg = Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AX//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AX//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAT8QH//Z', 'base64')

async function post(messageId, groupId = '120363000000@g.us') {
  const body = new FormData()
  body.set('group_id', groupId)
  body.set('group_name', 'Incoming 2024')
  body.set('message_id', messageId)
  body.set('media_index', '0')
  body.set('sender_id', '12345@lid')
  body.set('sender_alt_id', '15551234567@s.whatsapp.net')
  body.set('sender_name', 'Test inspector')
  body.set('caption', 'isolated adapter test')
  body.set('message_at', '2026-10-19T10:20:30Z')
  body.set('phone_number_verified', 'false')
  body.set('file', new Blob([jpeg], { type: 'image/jpeg' }), 'test.jpg')
  return fetch(url, { method: 'POST', headers: { 'X-WhatsApp-Ingest-Key': key }, body })
}

const first = await post('integration-one')
assert.equal(first.status, 201)
const duplicate = await post('integration-one')
assert.equal(duplicate.status, 200)
assert.equal((await duplicate.json()).duplicate, true)
const forbidden = await post('integration-forbidden', 'not-allowed@g.us')
assert.equal(forbidden.status, 403)
console.log('isolated Django ingestion integration passed')
