import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase, override_settings
from django.test import skipUnlessDBFeature
from django.urls import reverse

from calidad.models import PendingEvidence
from calidad.tests_whatsapp import image_upload


@skipUnlessDBFeature('supports_transactions')
class WhatsAppIngestConcurrencyTests(TransactionTestCase):
    """These races are meaningful only with a transactional database such as PostgreSQL."""

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != 'postgresql':
            cls._skip_reason = 'requires PostgreSQL; SQLite locks the shared test database'

    def setUp(self):
        if hasattr(self, '_skip_reason'):
            self.skipTest(self._skip_reason)
        self.temp_dir = tempfile.mkdtemp(prefix='whatsapp-pending-concurrency-')
        self.settings_override = override_settings(
            WHATSAPP_INGEST_API_KEY='test-key-that-is-not-a-default',
            WHATSAPP_ALLOWED_GROUP_IDS=frozenset({'group-1'}),
            WHATSAPP_PENDING_ROOT=Path(self.temp_dir),
            WHATSAPP_MAX_IMAGE_BYTES=1024 * 1024,
            WHATSAPP_PROCESSING_LEASE_SECONDS=300,
        )
        self.settings_override.enable()
        self.url = reverse('whatsapp_ingest')

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def post_once(self, message_id):
        client = Client()
        try:
            return client.post(
                self.url,
                {
                    'group_id': 'group-1',
                    'group_name': 'Incoming 2024',
                    'message_id': message_id,
                    'media_index': '0',
                    'sender_id': 'contact@s.whatsapp.net',
                    'sender_name': 'Inspector',
                    'caption': 'Concurrent test',
                    'file': image_upload(),
                },
                HTTP_X_WHATSAPP_INGEST_KEY='test-key-that-is-not-a-default',
            ).status_code
        finally:
            close_old_connections()

    def run_two_posts(self, message_id):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.post_once, message_id) for _ in range(2)]
            return sorted(future.result() for future in futures)

    def test_simultaneous_duplicate_message_creates_one_evidence(self):
        statuses = self.run_two_posts('concurrent-message')

        evidence = PendingEvidence.objects.get(source_message_id='concurrent-message')
        self.assertEqual(statuses, [200, 201])
        self.assertEqual(PendingEvidence.objects.count(), 1)
        self.assertEqual(evidence.status, PendingEvidence.STATUS_READY)
        self.assertTrue((Path(self.temp_dir) / evidence.file_path).is_file())

    def test_simultaneous_retries_claim_one_failed_evidence(self):
        with patch('calidad.api.whatsapp._write_pending_file', side_effect=OSError('temporary')):
            self.assertEqual(self.post_once('retry-message'), 503)

        statuses = self.run_two_posts('retry-message')

        evidence = PendingEvidence.objects.get(source_message_id='retry-message')
        self.assertEqual(statuses, [200, 201])
        self.assertEqual(PendingEvidence.objects.count(), 1)
        self.assertEqual(evidence.status, PendingEvidence.STATUS_READY)
        self.assertEqual(evidence.attempts, 2)
