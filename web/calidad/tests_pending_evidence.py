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

    def add_evidence(self, sender_id='one@lid', message_id=None, color=(20, 40, 60), batch_key=''):
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
            receipt_batch_key=batch_key,
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

    def test_pending_group_uses_carousel_and_compact_registration_panel(self):
        evidence = self.add_evidence()
        group = self.create_group(evidence)

        response = self.client.get(
            reverse('pending_evidence'), {'grupo': str(group.id)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'wa-workspace')
        self.assertContains(response, 'Registros en preparación')
        self.assertContains(response, 'Visor fotográfico')
        self.assertContains(response, 'Envíos de WhatsApp')
        self.assertContains(response, 'pending-work-data')

    def test_pending_page_groups_only_confirmed_batches_and_keeps_legacy_rows_separate(self):
        first = self.add_evidence(message_id='album-1', batch_key='album:one')
        second = self.add_evidence(message_id='album-2', batch_key='album:one')
        legacy = self.add_evidence(message_id='legacy-photo')

        response = self.client.get(reverse('pending_evidence'), {'grupo_origen': 'group-1'})

        self.assertEqual(response.status_code, 200)
        batches = response.context['available_batches']
        self.assertEqual(sorted(len(batch['evidences']) for batch in batches), [1, 2])
        self.assertContains(response, 'Visor fotográfico')
        self.assertContains(response, 'Tandas recibidas')
        self.assertContains(response, 'wa-batches-list')
        self.assertContains(response, 'Incorporar tanda completa')
        html = response.content.decode()
        self.assertLess(html.index('wa-batches-title'), html.index('wa-viewer-title'))
        self.assertLess(html.index('wa-viewer-title'), html.index('wa-drafts-title'))
        self.assertEqual({e.id for batch in batches for e in batch['evidences']}, {first.id, second.id, legacy.id})

    def test_draft_workspace_api_assigns_saves_and_removes_evidence(self):
        evidence = self.add_evidence()

        created = self.client.post(reverse('create_pending_group_draft'))
        self.assertEqual(created.status_code, 201)
        group_id = created.json()['group']['id']

        assigned = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'add', 'evidence_ids': [str(evidence.id)]},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()['group']['evidence_ids'], [str(evidence.id)])

        saved = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {
                'action': 'save_fields',
                'model': 'M-1',
                'line': 'L-1',
                'quantity': '2',
                'responsible': 'QA',
                'description': 'Defecto',
            },
        )
        self.assertEqual(saved.status_code, 200)
        group = PendingEvidenceGroup.objects.get(pk=group_id)
        self.assertEqual((group.model, group.line, group.quantity, group.responsible), ('M-1', 'L-1', 2, 'QA'))

        removed = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'remove', 'evidence_ids': [str(evidence.id)]},
        )
        self.assertEqual(removed.status_code, 200)
        evidence.refresh_from_db()
        self.assertIsNone(evidence.group_id)

    def test_draft_order_exclusion_and_recovery_are_reversible(self):
        first = self.add_evidence(message_id='order-1')
        second = self.add_evidence(message_id='order-2')
        third = self.add_evidence(message_id='order-3')
        created = self.client.post(reverse('create_pending_group_draft'))
        group_id = created.json()['group']['id']
        ids = [str(first.id), str(second.id), str(third.id)]

        self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'add', 'evidence_ids': ids},
        )
        reordered = [str(third.id), str(first.id), str(second.id)]
        response = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'reorder', 'evidence_ids': reordered},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['group']['included_evidence_ids'], reordered)
        self.assertEqual(
            list(PendingEvidence.objects.filter(group_id=group_id).order_by('draft_order').values_list('id', flat=True)),
            [third.id, first.id, second.id],
        )

        response = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {
                'action': 'exclude',
                'evidence_ids': [str(first.id)],
                'exclusion_reason': 'No corresponde',
            },
        )
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertTrue(first.is_excluded)
        self.assertEqual(first.exclusion_reason, 'No corresponde')

        response = self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'restore', 'evidence_ids': [str(first.id)]},
        )
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertFalse(first.is_excluded)

        self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'exclude', 'evidence_ids': [str(first.id)]},
        )
        self.client.post(
            reverse('update_pending_group', args=[group_id]),
            {'action': 'remove', 'evidence_ids': [str(first.id)]},
        )
        first.refresh_from_db()
        self.assertIsNone(first.group_id)
        self.assertFalse(first.is_excluded)
        self.assertEqual(first.draft_order, 0)

    def test_confirmation_preserves_draft_order_and_keeps_excluded_file_available(self):
        first = self.add_evidence(message_id='confirm-1')
        second = self.add_evidence(message_id='confirm-2')
        third = self.add_evidence(message_id='confirm-3')
        group = self.create_group(first, second, third)
        self.client.post(
            reverse('update_pending_group', args=[group.id]),
            {'action': 'reorder', 'evidence_ids': [str(third.id), str(first.id), str(second.id)]},
        )
        self.client.post(
            reverse('update_pending_group', args=[group.id]),
            {'action': 'exclude', 'evidence_ids': [str(second.id)]},
        )
        with patch('calidad.tasks.generar_thumbnails_lote_task.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('pending_evidence'), self.confirm_data(group)
                )

        self.assertEqual(response.status_code, 302)
        record = RegistroDefecto.objects.get()
        pending_ids = list(
            record.evidencias_v2.order_by('orden').values_list('metadatos__pending_evidence_id', flat=True)
        )
        self.assertEqual(pending_ids, [str(third.id), str(first.id)])
        second.refresh_from_db()
        self.assertIsNone(second.group_id)
        self.assertTrue(second.is_excluded)
        self.assertTrue((self.pending_root / second.file_path).is_file())

    def test_unassigned_excluded_evidence_can_be_restored(self):
        evidence = self.add_evidence(message_id='excluded-unassigned')
        PendingEvidence.objects.filter(pk=evidence.pk).update(
            is_excluded=True,
            exclusion_reason='Prueba reversible',
        )

        response = self.client.post(
            reverse('restore_pending_evidence'),
            {'evidence_ids': [str(evidence.id)]},
        )

        self.assertEqual(response.status_code, 200)
        evidence.refresh_from_db()
        self.assertFalse(evidence.is_excluded)
        self.assertEqual(evidence.exclusion_reason, '')
        self.assertTrue((self.pending_root / evidence.file_path).is_file())

    def test_unassigned_evidence_can_be_excluded_without_a_draft(self):
        evidence = self.add_evidence(message_id='exclude-from-batch')

        response = self.client.post(
            reverse('exclude_pending_evidence'),
            {'evidence_ids': [str(evidence.id)], 'exclusion_reason': 'Imagen incorrecta'},
        )

        self.assertEqual(response.status_code, 200)
        evidence.refresh_from_db()
        self.assertTrue(evidence.is_excluded)
        self.assertEqual(evidence.exclusion_reason, 'Imagen incorrecta')
        self.assertTrue((self.pending_root / evidence.file_path).is_file())

    def test_draft_workspace_api_keeps_other_operator_draft_private(self):
        other = User.objects.create_user('draft-owner', password='test-pass')
        PerfilUsuario.objects.create(usuario=other)
        group = PendingEvidenceGroup.objects.create(operator=other, created_by=other)
        operator = User.objects.create_user('draft-reader', password='test-pass')
        PerfilUsuario.objects.create(usuario=operator)
        self.client.force_login(operator)
        response = self.client.post(
            reverse('update_pending_group', args=[group.id]),
            {'action': 'save_fields', 'model': 'No autorizado'},
        )
        self.assertEqual(response.status_code, 409)
        group.refresh_from_db()
        self.assertEqual(group.model, '')

    def test_pending_page_can_filter_by_sender_and_order(self):
        first = self.add_evidence(sender_id='first@lid', message_id='first-photo')
        self.add_evidence(sender_id='second@lid', message_id='second-photo')

        response = self.client.get(
            reverse('pending_evidence'),
            {'grupo_origen': 'group-1', 'remitente': 'first@lid', 'orden': 'oldest'},
        )

        self.assertEqual(response.status_code, 200)
        visible = [evidence for batch in response.context['available_batches'] for evidence in batch['evidences']]
        self.assertEqual([evidence.id for evidence in visible], [first.id])

    def test_operation_panel_exposes_pending_whatsapp_evidence(self):
        self.add_evidence()

        page = self.client.get(reverse('panel_operativo'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '<strong id="pending-evidence-count">1</strong>', html=True)
        self.assertContains(page, 'evidencias de WhatsApp pendientes de asignar')
        self.assertContains(page, reverse('pending_evidence'))

        updates = self.client.get(reverse('api_check_updates'), {'last_id': 0})
        self.assertEqual(updates.status_code, 200)
        self.assertEqual(updates.json()['pending_evidence_count'], 1)

    def test_anonymous_and_profileless_users_cannot_open_basket(self):
        self.add_evidence()
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse('pending_evidence')).status_code, 302)

        profileless = User.objects.create_user('profileless', password='test-pass')
        client = Client()
        client.force_login(profileless)
        self.assertEqual(client.get(reverse('pending_evidence')).status_code, 403)

    def test_operator_can_read_media_stored_under_django_user_id(self):
        operator = User.objects.create_user('operator', password='test-pass')
        PerfilUsuario.objects.create(
            usuario=operator,
            turno='A',
            departamento='IQA',
        )
        thumb_dir = self.media_root / 'thumbs' / str(operator.id)
        thumb_dir.mkdir(parents=True)
        (thumb_dir / 'sample.jpg').write_bytes(_jpeg_bytes())

        client = Client()
        client.force_login(operator)
        response = client.get(
            f'/media-protegida/thumbs/{operator.id}/sample.jpg'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['X-Accel-Redirect'],
            f'/protected/thumbs/{operator.id}/sample.jpg',
        )

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
        self.assertContains(gallery, f'/media-protegida/fotos/{self.user.id}/wa_{first.id}.jpg')
        reports = self.client.get(reverse('reportes'))
        self.assertEqual(reports.status_code, 200)
        self.assertContains(reports, 'MODEL-1')
        self.assertEqual(reports.context['latest_record_id'], record.id)

        operation = self.client.get(reverse('panel_operativo'))
        self.assertEqual(operation.status_code, 200)
        self.assertContains(operation, 'WhatsApp')
        self.assertContains(operation, 'whatsapp_evidence_count')
        self.assertContains(operation, 'whatsapp_sender_count')

        new_records = self.client.get(
            reverse('api_get_nuevos'), {'last_id': 0}
        )
        self.assertEqual(new_records.status_code, 200)
        self.assertEqual(new_records.json()['registros'][0]['whatsapp_evidence_count'], 2)
        self.assertEqual(new_records.json()['registros'][0]['whatsapp_sender_count'], 2)

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
