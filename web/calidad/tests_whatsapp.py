import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from PIL import Image

from calidad.models import PendingEvidence, PendingEvidenceGroup, WhatsAppContact


def image_upload(name='photo.jpg', image_format='JPEG', color=(20, 40, 60)):
    buffer = BytesIO()
    Image.new('RGB', (12, 8), color).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class WhatsAppIngestTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='whatsapp-pending-test-')
        self.settings_override = override_settings(
            WHATSAPP_INGEST_API_KEY='test-key-that-is-not-a-default',
            WHATSAPP_ALLOWED_GROUP_IDS=frozenset({'group-1'}),
            WHATSAPP_PENDING_ROOT=Path(self.temp_dir),
            WHATSAPP_MAX_IMAGE_BYTES=1024 * 1024,
            WHATSAPP_ALLOW_HISTORICAL=False,
        )
        self.settings_override.enable()
        enqueue_patch = patch('calidad.api.whatsapp._enqueue_pending_derivatives')
        self.enqueue_derivatives = enqueue_patch.start()
        self.addCleanup(enqueue_patch.stop)
        self.client = Client()
        self.url = reverse('whatsapp_ingest')

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def post_image(self, **overrides):
        data = {
            'group_id': 'group-1',
            'group_name': 'Incoming 2024',
            'message_id': 'message-1',
            'receipt_batch_key': 'album:test-batch',
            'media_index': '0',
            'sender_id': 'contact@s.whatsapp.net',
            'sender_alt_id': 'contact-alt@lid',
            'sender_name': 'Inspector',
            'caption': 'Defecto en contenedor',
            'message_at': '2026-10-19T10:20:30Z',
            'phone_number': '15551234567',
            'phone_number_verified': 'false',
            'file': image_upload(),
        }
        data.update(overrides)
        return self.client.post(
            self.url,
            data,
            HTTP_X_WHATSAPP_INGEST_KEY='test-key-that-is-not-a-default',
        )

    def test_valid_image_is_persisted_without_definitive_record(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_image()

        self.assertEqual(response.status_code, 201)
        evidence = PendingEvidence.objects.get()
        self.assertEqual(evidence.status, PendingEvidence.STATUS_READY)
        self.assertEqual(evidence.caption, 'Defecto en contenedor')
        self.assertEqual(evidence.source_group_id, 'group-1')
        self.assertEqual(evidence.sender_whatsapp_id, 'contact@s.whatsapp.net')
        self.assertEqual(evidence.receipt_batch_key, 'album:test-batch')
        self.assertEqual(evidence.sender_alt_whatsapp_id, 'contact-alt@lid')
        self.assertIsNone(evidence.sender.phone_number)
        self.assertTrue((Path(self.temp_dir) / evidence.file_path).is_file())
        self.assertEqual(len(evidence.sha256), 64)
        self.enqueue_derivatives.assert_called_once_with(evidence.id)

    def test_authentication_and_group_allowlist_are_mandatory(self):
        data = {
            'group_id': 'group-1',
            'message_id': 'message-auth',
            'file': image_upload(),
        }
        self.assertEqual(self.client.post(self.url, data).status_code, 401)
        self.assertEqual(
            self.client.post(self.url, data, HTTP_X_WHATSAPP_INGEST_KEY='wrong').status_code,
            401,
        )
        data['group_id'] = 'not-allowed'
        self.assertEqual(
            self.client.post(
                self.url,
                data,
                HTTP_X_WHATSAPP_INGEST_KEY='test-key-that-is-not-a-default',
            ).status_code,
            403,
        )

    def test_missing_configured_key_is_not_replaced_by_a_default(self):
        with override_settings(WHATSAPP_INGEST_API_KEY=None):
            self.assertEqual(self.post_image().status_code, 401)

    def test_same_message_and_media_position_is_idempotent(self):
        first = self.post_image()
        second = self.post_image()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['duplicate'])
        self.assertEqual(PendingEvidence.objects.count(), 1)

    def test_missing_batch_key_gets_a_stable_individual_key(self):
        first = self.post_image(message_id='message-without-batch', receipt_batch_key='')
        self.assertEqual(first.status_code, 201)
        evidence = PendingEvidence.objects.get()
        self.assertTrue(evidence.receipt_batch_key.startswith('message:'))

    def test_two_senders_can_share_one_pending_evidence_group(self):
        first = self.post_image(message_id='message-a', sender_id='a@lid', sender_name='A')
        second = self.post_image(message_id='message-b', sender_id='b@lid', sender_name='B')
        operator = User.objects.create_user('operator')
        group = PendingEvidenceGroup.objects.create(operator=operator, created_by=operator)
        PendingEvidence.objects.update(group=group)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(WhatsAppContact.objects.count(), 2)
        self.assertEqual(PendingEvidence.objects.filter(group=group).count(), 2)
        self.assertSetEqual(
            set(PendingEvidence.objects.values_list('sender_whatsapp_id', flat=True)),
            {'a@lid', 'b@lid'},
        )

    def test_unverified_number_is_not_associated_with_lid(self):
        response = self.post_image(
            message_id='message-lid',
            sender_id='123456789@lid',
            phone_number='15551234567',
            phone_number_verified='false',
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(WhatsAppContact.objects.get(whatsapp_id='123456789@lid').phone_number)

    def test_invalid_and_oversized_files_are_rejected(self):
        invalid = self.post_image(
            file=SimpleUploadedFile('bad.jpg', b'not-an-image', content_type='image/jpeg'),
        )
        self.assertEqual(invalid.status_code, 400)

        with override_settings(WHATSAPP_MAX_IMAGE_BYTES=10):
            oversized = self.post_image(message_id='message-large')
        self.assertEqual(oversized.status_code, 400)
        self.assertEqual(PendingEvidence.objects.count(), 0)

    def test_public_media_root_cannot_be_used_for_pending_files(self):
        with override_settings(WHATSAPP_PENDING_ROOT=Path(settings.MEDIA_ROOT)):
            response = self.post_image(message_id='message-public-root')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            PendingEvidence.objects.get(source_message_id='message-public-root').status,
            PendingEvidence.STATUS_FAILED,
        )

    def test_storage_error_is_retryable_without_creating_a_second_evidence(self):
        with patch('calidad.api.whatsapp._write_pending_file', side_effect=OSError('temporary')):
            failed = self.post_image(message_id='message-retry')

        self.assertEqual(failed.status_code, 503)
        evidence = PendingEvidence.objects.get(source_message_id='message-retry')
        self.assertEqual(evidence.status, PendingEvidence.STATUS_FAILED)

        retried = self.post_image(message_id='message-retry')
        evidence.refresh_from_db()
        self.assertEqual(retried.status_code, 201)
        self.assertEqual(evidence.status, PendingEvidence.STATUS_READY)
        self.assertEqual(evidence.attempts, 2)

    def test_stale_processing_evidence_can_be_reclaimed_after_a_crash(self):
        self.post_image(message_id='message-stale')
        evidence = PendingEvidence.objects.get(source_message_id='message-stale')
        (Path(self.temp_dir) / evidence.file_path).unlink()
        PendingEvidence.objects.filter(pk=evidence.pk).update(
            status=PendingEvidence.STATUS_PROCESSING,
            file_path='',
            processing_started_at=timezone.now() - timedelta(seconds=601),
        )

        with override_settings(WHATSAPP_PROCESSING_LEASE_SECONDS=600):
            response = self.post_image(message_id='message-stale')

        evidence.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(evidence.status, PendingEvidence.STATUS_READY)
        self.assertEqual(evidence.attempts, 2)

    def test_historical_messages_are_rejected_by_default(self):
        self.assertEqual(self.post_image(historical='true').status_code, 400)
