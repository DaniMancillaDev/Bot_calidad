from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from calidad.models import PerfilUsuario, Turno, Departamento

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
        


    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_limpiar_fotos_view_reinicia_contador(self, _mock_workflow):
        """Prueba que /limpiar-fotos NO reinicia el ContadorUsuario a 1."""
        url = reverse('workflow_sesion_limpiar_fotos')
        response = self.client.post(url, {'telegram_id': self.telegram_id}, HTTP_AUTHORIZATION='Api-Key test-api-key')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'analysis')
        


    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_limpiar_view_reinicia_contador(self, _mock_workflow):
        """Prueba que /limpiar NO reinicia el ContadorUsuario a 1."""
        url = reverse('workflow_sesion_limpiar')
        response = self.client.post(url, {'telegram_id': self.telegram_id}, HTTP_AUTHORIZATION='Api-Key test-api-key')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'cleaned')
        


class ContadorGlobalConReutilizacionTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create(username='op_1')
        self.user2 = User.objects.create(username='op_2')
        self.telegram_id_1 = 111
        self.telegram_id_2 = 222
        
        # Ambos en el MISMO turno y depto
        PerfilUsuario.objects.create(usuario=self.user1, telegram_user_id=self.telegram_id_1, turno=Turno.A, departamento=Departamento.PROD)
        PerfilUsuario.objects.create(usuario=self.user2, telegram_user_id=self.telegram_id_2, turno=Turno.A, departamento=Departamento.PROD)

    def test_global_counter_con_reutilizacion(self):
        from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository
        from calidad.models import NumeroReutilizable
        repo = DjangoContadorRepository()

        # Usuario 1 pide 1 foto
        c1 = repo.obtener_y_avanzar(self.telegram_id_1)
        self.assertEqual(c1, 1)

        # Usuario 2 pide 1 foto (debe ser 2)
        c2 = repo.obtener_y_avanzar(self.telegram_id_2)
        self.assertEqual(c2, 2)

        # Usuario 1 pide un lote de 3 fotos (debe ser 3, 4, 5)
        lote1 = repo.obtener_y_avanzar_lote(self.telegram_id_1, 3)
        self.assertEqual(lote1, [3, 4, 5])

        # Simulamos que Usuario 2 cancela su foto 2 y la libera
        NumeroReutilizable.objects.create(numero=2)

        # Usuario 1 pide 2 fotos. Debe recibir el hueco (2) y el siguiente global (6)
        lote2 = repo.obtener_y_avanzar_lote(self.telegram_id_1, 2)
        self.assertEqual(lote2, [2, 6])

        # Verificar valor global actual
        self.assertEqual(repo.obtener_actual(self.telegram_id_1), 7)
        self.assertEqual(repo.obtener_actual(self.telegram_id_2), 7)

class SesionCancelarViewsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Token default-internal-secret-key-123')
        self.user = User.objects.create(username='test_op')
        self.telegram_id = 999
        self.perfil = PerfilUsuario.objects.create(usuario=self.user, telegram_user_id=self.telegram_id, turno=Turno.A, departamento=Departamento.PROD)


    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_cancelar_view_revierte_contador(self, _mock_workflow):
        """Si un usuario subió fotos 15, 16, 17 y cancela, esos números deben liberarse en NumeroReutilizable."""
        url = reverse('workflow_sesion_cancelar')
        response = self.client.post(url, {'telegram_id': self.telegram_id, 'fotos': [15, 16, 17]}, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'cancelled')
        self.assertEqual(response.data['numeros_liberados'], [15, 16, 17])
        self.assertEqual(response.data['contador_revertido'], 15)
        
        from calidad.models import NumeroReutilizable
        liberados = list(NumeroReutilizable.objects.values_list('numero', flat=True))
        self.assertCountEqual(liberados, [15, 16, 17])

    @patch('calidad.application.workflows.defecto_workflow.DefectoWorkflow')
    def test_cancelar_view_sin_fotos(self, _mock_workflow):
        """Cancelar sin fotos no debe romper nada ni liberar números."""
        url = reverse('workflow_sesion_cancelar')
        response = self.client.post(url, {'telegram_id': self.telegram_id, 'fotos': []}, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numeros_liberados'], [])
        self.assertIsNone(response.data['contador_revertido'])
        
        from calidad.models import NumeroReutilizable
        self.assertEqual(NumeroReutilizable.objects.count(), 0)

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

