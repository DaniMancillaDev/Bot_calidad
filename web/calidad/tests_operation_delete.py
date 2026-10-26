import hashlib
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from calidad.models import EvidenciaFotografica, RegistroDefecto


class OperationDeleteTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='delete-admin', is_superuser=True, is_staff=True)
        self.record = RegistroDefecto.objects.create(
            fotos='1', fotos_nums=[1], modelo='DELETE-TEST', linea='T01',
            cantidad=1, responsable='QA', descripcion='Synthetic test', user_id=123,
        )
        self.url = reverse('api_delete_registro', args=[self.record.pk])

    def test_admin_deletes_record_but_not_original_file_or_other_records(self):
        other = RegistroDefecto.objects.create(
            fotos='2', fotos_nums=[2], modelo='KEEP', linea='T02',
            cantidad=1, responsable='QA', descripcion='Keep', user_id=124,
        )
        with tempfile.TemporaryDirectory(prefix='iqa-delete-test-', dir='/dev/shm') as scratch:
            original = Path(scratch) / 'original.jpg'
            original.write_bytes(b'synthetic-original-never-delete')
            checksum = hashlib.sha256(original.read_bytes()).hexdigest()
            evidence = EvidenciaFotografica.objects.create(registro=self.record, ruta_archivo=str(original))
            self.client.force_login(self.admin)
            response = self.client.post(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'success': True})
            self.assertFalse(RegistroDefecto.objects.filter(pk=self.record.pk).exists())
            self.assertFalse(EvidenciaFotografica.objects.filter(pk=evidence.pk).exists())
            self.assertTrue(RegistroDefecto.objects.filter(pk=other.pk).exists())
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), checksum)
            self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_non_superuser_cannot_delete_even_if_staff(self):
        for is_staff in (False, True):
            actor = get_user_model().objects.create_user(username=f'normal-{is_staff}', is_staff=is_staff)
            self.client.force_login(actor)
            self.assertEqual(self.client.post(self.url).status_code, 403)
            self.assertTrue(RegistroDefecto.objects.filter(pk=self.record.pk).exists())

    def test_anonymous_and_get_do_not_delete(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(RegistroDefecto.objects.filter(pk=self.record.pk).exists())

    def test_csrf_still_required_for_admin(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.assertTrue(RegistroDefecto.objects.filter(pk=self.record.pk).exists())

    def test_accidental_model_delete_stays_blocked(self):
        with self.assertRaises(PermissionError):
            self.record.delete()
        self.assertTrue(RegistroDefecto.objects.filter(pk=self.record.pk).exists())
