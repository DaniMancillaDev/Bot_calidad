import json
from django.test import TestCase, Client
from django.utils import timezone
from calidad.models import RegistroDefecto, EvidenciaFotografica, EstadoRevision
from shared.infrastructure.database.django_registro_repository import DjangoRegistroRepository

class Fase1BackendV2Tests(TestCase):
    def setUp(self):
        self.client = Client()
        # Crear un registro inicial con Dual-Write usando el repositorio
        repo = DjangoRegistroRepository()
        repo.guardar(
            fotos=[101, 102],
            modelo="TEST_MODEL",
            linea="T01",
            cantidad=5,
            responsable="QA",
            descripcion="Fallo de inyección",
            user_id=999,
            turno="A",
            departamento="IQA",
            numero_parte="P-TEST"
        )
        self.registro = RegistroDefecto.objects.filter(modelo="TEST_MODEL").last()

    def test_dual_write_success(self):
        """Valida que el repositorio legacy crea el registro y sincroniza a EvidenciaFotografica."""
        self.assertIsNotNone(self.registro)
        self.assertEqual(self.registro.fotos_nums, [101, 102])
        
        evidencias = self.registro.evidencias_v2.all().order_by('orden')
        self.assertEqual(evidencias.count(), 2)
        
        self.assertEqual(evidencias[0].ruta_archivo, "fotos/999/101.jpg")
        self.assertTrue(evidencias[0].es_portada)
        
        self.assertEqual(evidencias[1].ruta_archivo, "fotos/999/102.jpg")
        self.assertFalse(evidencias[1].es_portada)

    def test_state_machine_valid_transitions(self):
        """Valida que la máquina de estados respete los flujos permitidos."""
        # PENDIENTE -> APROBADO
        self.registro.aprobar(comentarios="Aprobado Test")
        self.assertEqual(self.registro.estado_revision, EstadoRevision.APROBADO)
        
        # PENDIENTE -> RECHAZADO
        self.registro.estado_revision = EstadoRevision.PENDIENTE
        self.registro.save()
        self.registro.rechazar(comentarios="Rechazado Test")
        self.assertEqual(self.registro.estado_revision, EstadoRevision.RECHAZADO)

    def test_state_machine_invalid_transition(self):
        """Valida que se bloqueen transiciones inválidas."""
        self.registro.estado_revision = EstadoRevision.APROBADO
        self.registro.save()
        
        with self.assertRaises(ValueError):
            self.registro.rechazar(comentarios="Rechazo desde aprobado") # Aprobado a Rechazado no está permitido
            
    def test_api_get_lotes(self):
        """Valida el endpoint de obtención de lotes."""
        res = self.client.get('/api/v2/lotes/')
        self.assertEqual(res.status_code, 200)
        
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(len(data['lotes']), 1)
        
        lote = data['lotes'][0]
        self.assertIn("T01", lote['id'])
        self.assertEqual(lote['cantidad_registros'], 1)
        self.assertEqual(lote['portada_url'], "/media/fotos/999/101.jpg")

    def test_api_get_registros_por_lote(self):
        """Valida obtener registros de un lote específico."""
        res_lotes = self.client.get('/api/v2/lotes/').json()
        lote_id = res_lotes['lotes'][0]['id']
        
        res = self.client.get(f'/api/v2/lotes/{lote_id}/registros/')
        self.assertEqual(res.status_code, 200)
        
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(len(data['registros']), 0)
        if len(data['registros']) > 0:
            self.assertEqual(data['registros'][0]['modelo'], "TEST_MODEL")

    def test_api_patch_registro(self):
        """Valida la actualización de un registro vía PATCH (incluyendo máquina de estado)."""
        payload = {
            "numero_parte": "P-MODIFIED",
            "estado_revision": "aprobado",
            "comentarios": "Aprobado por API"
        }
        res = self.client.patch(
            f'/api/v2/registros/{self.registro.id}/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.numero_parte, "P-MODIFIED")
        self.assertEqual(self.registro.estado_revision, EstadoRevision.APROBADO)
        self.assertEqual(self.registro.comentarios_supervisor, "Aprobado por API")

    def test_api_rotar_evidencia(self):
        """Valida la rotación vía POST."""
        evidencia = self.registro.evidencias_v2.first()
        payload = {"angulo_rotacion": 180}
        
        res = self.client.post(
            f'/api/v2/evidencias/{evidencia.id}/rotar/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        
        evidencia.refresh_from_db()
        self.assertEqual(evidencia.angulo_rotacion, 180)
