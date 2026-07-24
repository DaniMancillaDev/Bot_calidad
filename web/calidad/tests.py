from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from calidad.models import PerfilUsuario, ContadorUsuario, Turno, Departamento

class LimpiezaViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token default-internal-secret-key-123')
        
        self.user = User.objects.create(username='test_op', first_name='Test', last_name='Op')
        self.telegram_id = 123456789
        self.perfil = PerfilUsuario.objects.create(
            usuario=self.user,
            telegram_user_id=self.telegram_id,
            turno=Turno.A,
            departamento=Departamento.PROD
        )
        
        self.contador = ContadorUsuario.objects.create(
            telegram_user_id=self.telegram_id,
            contador_actual=5
        )

    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_limpiar_fotos_view_reinicia_contador(self, mock_workflow):
        """Prueba que /limpiar-fotos NO reinicia el ContadorUsuario a 1."""
        url = reverse('workflow_sesion_limpiar_fotos')
        response = self.client.post(url, {'telegram_id': 12345}, HTTP_AUTHORIZATION='Api-Key test-api-key')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'analysis')
        
        c = ContadorUsuario.objects.get(telegram_user_id=12345)
        self.assertEqual(c.contador_actual, 5, "El contador NO debe reiniciarse al simular limpiar-fotos")

    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_limpiar_view_reinicia_contador(self, mock_workflow):
        """Prueba que /limpiar NO reinicia el ContadorUsuario a 1."""
        url = reverse('workflow_sesion_limpiar')
        response = self.client.post(url, {'telegram_id': 12345}, HTTP_AUTHORIZATION='Api-Key test-api-key')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cleaned')
        
        c = ContadorUsuario.objects.get(telegram_user_id=12345)
        self.assertEqual(c.contador_actual, 5, "El contador NO debe reiniciarse al cancelar sesión con limpiar")

class ContadorUsuarioIsolationTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='op_1')
        self.user2 = User.objects.create(username='op_2')
        self.telegram_id_1 = 111
        self.telegram_id_2 = 222
        
        # Ambos en el MISMO turno y depto para asegurar que ya no colisionan
        PerfilUsuario.objects.create(usuario=self.user1, telegram_user_id=self.telegram_id_1, turno=Turno.A, departamento=Departamento.PROD)
        PerfilUsuario.objects.create(usuario=self.user2, telegram_user_id=self.telegram_id_2, turno=Turno.A, departamento=Departamento.PROD)

    def test_aislamiento_entre_usuarios(self):
        from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository
        repo = DjangoContadorRepository()

        # Usuario 1 pide 1 foto
        c1 = repo.obtener_y_avanzar(self.telegram_id_1)
        self.assertEqual(c1, 1)

        # Usuario 2 pide 1 foto (debe ser 1, no 2)
        c2 = repo.obtener_y_avanzar(self.telegram_id_2)
        self.assertEqual(c2, 1)

        # Usuario 1 pide un lote de 3 fotos (debe ser 2, 3, 4)
        lote1 = repo.obtener_y_avanzar_lote(self.telegram_id_1, 3)
        self.assertEqual(lote1, [2, 3, 4])

        # Usuario 2 pide 1 foto (debe ser 2)
        c2_next = repo.obtener_y_avanzar(self.telegram_id_2)
        self.assertEqual(c2_next, 2)

        # Verificar valores actuales
        self.assertEqual(repo.obtener_actual(self.telegram_id_1), 5)
        self.assertEqual(repo.obtener_actual(self.telegram_id_2), 3)

class SesionCancelarViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token default-internal-secret-key-123')
        self.user = User.objects.create(username='test_op')
        self.telegram_id = 999
        self.perfil = PerfilUsuario.objects.create(usuario=self.user, telegram_user_id=self.telegram_id, turno=Turno.A, departamento=Departamento.PROD)
        self.contador = ContadorUsuario.objects.create(telegram_user_id=self.telegram_id, contador_actual=15)

    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_cancelar_view_revierte_contador(self, mock_workflow):
        """Si un usuario subió fotos 15, 16, 17 y cancela, el contador debe volver a 15."""
        url = reverse('workflow_sesion_cancelar')
        response = self.client.post(url, {'telegram_id': self.telegram_id, 'fotos': [15, 16, 17]}, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'cancelled')
        self.assertEqual(response.data['contador_revertido'], 15)
        
        self.contador.refresh_from_db()
        self.assertEqual(self.contador.contador_actual, 15)

    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_cancelar_view_sin_fotos(self, mock_workflow):
        """Cancelar sin fotos no debe romper nada ni modificar el contador."""
        url = reverse('workflow_sesion_cancelar')
        response = self.client.post(url, {'telegram_id': self.telegram_id, 'fotos': []}, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['contador_revertido'])
        
        self.contador.refresh_from_db()
        self.assertEqual(self.contador.contador_actual, 15)

from pathlib import Path
import tempfile
import shutil
import os
from calidad.utils import get_best_image_path

class UtilsTest(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fotos_dir = Path(self.temp_dir) / "fotos"
        self.fotos_dir.mkdir()
        
        # Override environment variables for tests
        os.environ["PROXIES_PATH"] = str(Path(self.temp_dir) / "proxies")
        os.environ["THUMBS_PATH"] = str(Path(self.temp_dir) / "thumbs")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        if "PROXIES_PATH" in os.environ:
            del os.environ["PROXIES_PATH"]
        if "THUMBS_PATH" in os.environ:
            del os.environ["THUMBS_PATH"]

    def test_get_best_image_path_race_condition(self):
        """Verifica que si hay múltiples fotos con el mismo número, elija la del timestamp más reciente."""
        uid = "123"
        user_fotos = self.fotos_dir / uid
        user_fotos.mkdir()
        
        # Crear fotos simulando colisión
        # 003 de hace 3 días
        (user_fotos / "003_20260613_075945.jpg").touch()
        # 003 de hoy
        (user_fotos / "003_20260615_205548.jpg").touch()
        # 003 del año pasado
        (user_fotos / "003_20250101_100000.jpg").touch()
        
        best = get_best_image_path(self.fotos_dir, uid, 3)
        self.assertIsNotNone(best)
        self.assertEqual(best.name, "003_20260615_205548.jpg", "Debe elegir el timestamp más alto, sin importar orden alfabético ni de creación")

