import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from calidad.models import (
    PendingEvidence,
    PendingEvidenceGroup,
    WhatsAppContact,
    RegistroDefecto,
    EvidenciaFotografica,
    PerfilUsuario,
)
from calidad.services.pending_evidence import (
    PendingEvidenceConflict,
    confirm_pending_group,
)


def _jpeg_bytes(color=(20, 40, 60)):
    output = BytesIO()
    Image.new('RGB', (24, 16), color).save(output, format='JPEG')
    return output.getvalue()


class PendingEvidenceWebTests(TestCase):
    def setUp(self):
        self.pending_root = Path(tempfile.mkdtemp(prefix='pending-web-'))
        self.media_root = Path(tempfile.mkdtemp(prefix='pending-media-'))
        self.settings_override = override_settings(
            WHATSAPP_PENDING_ROOT=self.pending_root,
            MEDIA_ROOT=self.media_root,
            FOTOS_ROOT=self.media_root / 'fotos',
            THUMBS_ROOT=self.media_root / 'thumbs',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.pending_root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.user = User.objects.create_superuser(
            username='pending-admin', password='test-pass', email='pending@example.test'
        )
        self.client.force_login(self.user)

    def add_evidence(self, sender_id='one@lid', message_id=None, color=(20, 40, 60)):
        evidence_id = uuid4()
        folder = self.pending_root / str(evidence_id)
        folder.mkdir(parents=True)
        (folder / 'original.jpg').write_bytes(_jpeg_bytes(color))
        contact, _ = WhatsAppContact.objects.get_or_create(
            whatsapp_id=sender_id,
            defaults={'display_name': sender_id.split('@')[0]},
        )
        return PendingEvidence.objects.create(
            id=evidence_id,
            source_group_id='group-1',
            source_group_name='Incoming 2024',
            source_message_id=message_id or str(evidence_id),
            media_index=0,
            sender=contact,
            sender_whatsapp_id=sender_id,
            caption='Defecto en contenedor',
            file_path=f'{evidence_id}/original.jpg',
            sha256='a' * 64,
            mime_type='image/jpeg',
            size_bytes=100,
            status=PendingEvidence.STATUS_READY,
        )

    def create_group(self, *evidences):
        response = self.client.post(
            reverse('pending_evidence'),
            {
                'action': 'create_group',
                'evidence_ids': [str(evidence.id) for evidence in evidences],
            },
        )
        self.assertEqual(response.status_code, 302)
        return PendingEvidenceGroup.objects.get()

    def confirm_data(self, group):
        return {
            'action': 'confirm_group',
            'group_id': str(group.id),
            'model': 'MODEL-1',
            'line': 'T01',
            'quantity': '4',
            'responsible': 'QA',
            'description': 'Defecto visible',
        }

    def test_pending_page_and_protected_thumbnail(self):
        evidence = self.add_evidence()

        response = self.client.get(reverse('pending_evidence'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incoming 2024')
        image = self.client.get(
            reverse('pending_evidence_image', args=[evidence.id]) + '?size=thumb'
        )
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Content-Type'], 'image/jpeg')
        self.assertEqual(image['Cache-Control'], 'private, no-store')
        self.assertEqual(
            self.client.get('/media/whatsapp_pending/original.jpg').status_code,
            404,
        )

    def test_anonymous_and_profileless_users_cannot_open_basket(self):
        self.add_evidence()
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse('pending_evidence')).status_code, 302)

        profileless = User.objects.create_user('profileless', password='test-pass')
        client = Client()
        client.force_login(profileless)
        self.assertEqual(client.get(reverse('pending_evidence')).status_code, 403)

    def test_csrf_is_required_for_group_and_contact_changes(self):
        evidence = self.add_evidence()
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.user)
        response = strict_client.post(
            reverse('pending_evidence'),
            {'action': 'create_group', 'evidence_ids': [str(evidence.id)]},
        )
        self.assertEqual(response.status_code, 403)

    def test_group_can_contain_two_senders_and_confirmation_creates_gallery_data(self):
        first = self.add_evidence('first@lid', 'message-1')
        second = self.add_evidence('second@lid', 'message-2', color=(80, 20, 10))
        group = self.create_group(first, second)

        with patch('calidad.tasks.generar_thumbnails_lote_task.delay') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('pending_evidence'), self.confirm_data(group)
                )

        self.assertEqual(response.status_code, 302)
        group.refresh_from_db()
        record = RegistroDefecto.objects.get()
        self.assertEqual(group.status, PendingEvidenceGroup.STATUS_CONFIRMED)
        self.assertEqual(group.definitive_record_id, record.id)
        self.assertEqual(group.confirmed_by_id, self.user.id)
        self.assertEqual(record.modelo, 'MODEL-1')
        self.assertEqual(record.user_id, self.user.id)
        self.assertEqual(record.evidencias_v2.count(), 2)
        self.assertEqual(
            set(record.evidencias_v2.values_list('metadatos__sender_whatsapp_id', flat=True)),
            {'first@lid', 'second@lid'},
        )
        self.assertEqual(
            PendingEvidence.objects.values_list('status', flat=True).distinct().get(),
            PendingEvidence.STATUS_ARCHIVED,
        )
        for evidence in (first, second):
            evidence.refresh_from_db()
            self.assertTrue((self.pending_root / evidence.file_path).is_file())
        self.assertEqual(enqueue.call_count, 1)
        self.assertEqual(enqueue.call_args.args[0], self.user.id)
        self.assertEqual(len(enqueue.call_args.args[1]), 2)

        gallery = self.client.get(reverse('galeria_fotos'))
        self.assertEqual(gallery.status_code, 200)
        self.assertContains(gallery, 'MODEL-1')
        reports = self.client.get(reverse('reportes'))
        self.assertEqual(reports.status_code, 200)
        self.assertContains(reports, 'MODEL-1')

    def test_confirm_requires_complete_fields_and_does_not_copy_files(self):
        evidence = self.add_evidence()
        group = self.create_group(evidence)
        response = self.client.post(
            reverse('pending_evidence'),
            {**self.confirm_data(group), 'description': ''},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroDefecto.objects.count(), 0)
        group.refresh_from_db()
        self.assertEqual(group.status, PendingEvidenceGroup.STATUS_DRAFT)
        self.assertFalse((self.media_root / 'fotos').exists())

    def test_double_confirmation_does_not_create_second_record(self):
        evidence = self.add_evidence()
        group = self.create_group(evidence)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('pending_evidence'), self.confirm_data(group))

        response = self.client.post(reverse('pending_evidence'), self.confirm_data(group))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroDefecto.objects.count(), 1)
        self.assertEqual(EvidenciaFotografica.objects.count(), 1)

    def test_contact_name_can_be_edited_without_web_account(self):
        evidence = self.add_evidence('operator@lid')
        contact = evidence.sender
        response = self.client.post(
            reverse('rename_pending_contact', args=[contact.id]),
            {'display_name': 'Inspector de Incoming'},
        )

        self.assertEqual(response.status_code, 302)
        contact.refresh_from_db()
        self.assertEqual(contact.display_name, 'Inspector de Incoming')

    def test_contact_from_another_operator_group_cannot_be_renamed(self):
        evidence = self.add_evidence('other-operator@lid')
        other = User.objects.create_user('other-operator', password='test-pass')
        PerfilUsuario.objects.create(usuario=other)
        group = PendingEvidenceGroup.objects.create(operator=other, created_by=other)
        evidence.group = group
        evidence.save(update_fields=['group'])

        operator = User.objects.create_user('local-operator', password='test-pass')
        PerfilUsuario.objects.create(usuario=operator)
        client = Client()
        client.force_login(operator)
        response = client.post(
            reverse('rename_pending_contact', args=[evidence.sender_id]),
            {'display_name': 'No autorizado'},
        )

        self.assertEqual(response.status_code, 403)
        evidence.sender.refresh_from_db()
        self.assertNotEqual(evidence.sender.display_name, 'No autorizado')


class PendingEvidenceConfirmationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != 'postgresql':
            cls._skip_reason = 'requires PostgreSQL for row-lock concurrency'

    def setUp(self):
        if hasattr(self, '_skip_reason'):
            self.skipTest(self._skip_reason)
        self.pending_root = Path(tempfile.mkdtemp(prefix='pending-race-'))
        self.media_root = Path(tempfile.mkdtemp(prefix='pending-race-media-'))
        self.settings_override = override_settings(
            WHATSAPP_PENDING_ROOT=self.pending_root,
            MEDIA_ROOT=self.media_root,
            FOTOS_ROOT=self.media_root / 'fotos',
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.pending_root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.user = User.objects.create_superuser(
            username='pending-race', password='test-pass', email='race@example.test'
        )
        evidence_id = uuid4()
        folder = self.pending_root / str(evidence_id)
        folder.mkdir(parents=True)
        (folder / 'original.jpg').write_bytes(_jpeg_bytes())
        evidence = PendingEvidence.objects.create(
            id=evidence_id,
            source_group_id='group-race',
            source_message_id='message-race',
            file_path=f'{evidence_id}/original.jpg',
            mime_type='image/jpeg',
            status=PendingEvidence.STATUS_READY,
        )
        self.group = PendingEvidenceGroup.objects.create(
            operator=self.user,
            created_by=self.user,
        )
        PendingEvidence.objects.filter(pk=evidence.pk).update(group=self.group)

    def confirm_in_thread(self):
        close_old_connections()
        try:
            user = User.objects.get(pk=self.user.pk)
            return confirm_pending_group(user, self.group.id, {
                'model': 'MODEL-RACE',
                'line': 'T01',
                'quantity': '1',
                'responsible': 'QA',
                'description': 'Concurrent confirmation',
            })
        except Exception as exc:
            return exc
        finally:
            close_old_connections()

    def test_only_one_concurrent_confirmation_wins(self):
        with patch('calidad.tasks.generar_thumbnails_lote_task.delay'):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _item: self.confirm_in_thread(), (1, 2)))

        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [result for result in results if isinstance(result, PendingEvidenceConflict)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(RegistroDefecto.objects.count(), 1)
        self.assertEqual(EvidenciaFotografica.objects.count(), 1)
