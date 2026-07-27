import os
import zipfile
import tempfile
import shutil
import pandas as pd
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from PIL import Image

from workspace.models import ImportSession, DraftRegistro
from workspace.services.processing import process_upload_logic

User = get_user_model()

class ProcessingCharacterizationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="test_supervisor")
        self.session = ImportSession.objects.create(
            supervisor=self.user,
            status='PROCESSING'
        )
        
        # Crear un MEDIA_ROOT temporal
        self.test_media_root = tempfile.mkdtemp()
        self.patcher = patch('workspace.services.processing.settings.MEDIA_ROOT', self.test_media_root)
        self.patcher.start()
        
        # Crear estructura base esperada
        self.tmp_dir = os.path.join(self.test_media_root, 'workspace', 'tmp')
        os.makedirs(self.tmp_dir, exist_ok=True)
        
    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_media_root)

    def _create_dummy_image(self, path):
        img = Image.new('RGB', (100, 100), color='red')
        img.save(path)

    def _create_valid_zip(self, session_uuid):
        zip_path = os.path.join(self.tmp_dir, f"{session_uuid}.zip")
        with zipfile.ZipFile(zip_path, 'w') as z:
            # Crear una imagen temporal y meterla
            img_path = os.path.join(self.tmp_dir, "test_foto.jpg")
            self._create_dummy_image(img_path)
            z.write(img_path, "test_foto.jpg")
            os.remove(img_path)
        return zip_path

    def _create_valid_csv(self, session_uuid, data):
        csv_path = os.path.join(self.tmp_dir, f"{session_uuid}_excel.csv")
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_1_upload_correcto(self):
        """Caso 1: Archivo válido, crea registro esperado y procesa correctamente."""
        self._create_valid_zip(self.session.uuid)
        self._create_valid_csv(self.session.uuid, [
            {"Modelo": "T01", "Foto": "test_foto.jpg"}
        ])
        
        process_upload_logic(self.session.uuid)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'DRAFT')
        self.assertEqual(self.session.total_rows, 1)
        
        # Validar registros Draft creados
        drafts = DraftRegistro.objects.filter(session=self.session)
        self.assertEqual(drafts.count(), 1)
        
        draft = drafts.first()
        self.assertEqual(draft.mapped_data['modelo'], "T01")
        self.assertEqual(draft.assigned_photos, ["test_foto.jpg"])
        
        # Validar archivos físicos
        extract_dir = os.path.join(self.test_media_root, 'workspace', 'sessions', str(self.session.uuid))
        self.assertTrue(os.path.exists(os.path.join(extract_dir, 'photos', 'test_foto.jpg')))
        self.assertTrue(os.path.exists(os.path.join(extract_dir, 'thumbs', 'test_foto.jpg')))

    def test_2_archivo_invalido(self):
        """Caso 2: Archivo inválido (falta el Excel), falla y marca la sesión como FAILED."""
        # Solo creamos el ZIP
        self._create_valid_zip(self.session.uuid)
        
        process_upload_logic(self.session.uuid)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'FAILED')
        self.assertIn("Archivo Excel no encontrado.", self.session.error_message)

    @patch('workspace.services.processing.os.makedirs')
    def test_3_error_almacenamiento(self, mock_makedirs):
        """Caso 3: Storage falla, confirma comportamiento actual de FAILED con el error capturado."""
        # Simulamos un fallo al intentar crear directorios
        mock_makedirs.side_effect = PermissionError("Acceso denegado")
        
        self._create_valid_zip(self.session.uuid)
        self._create_valid_csv(self.session.uuid, [{"Foto": "test_foto.jpg"}])
        
        process_upload_logic(self.session.uuid)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'FAILED')
        self.assertIn("Acceso denegado", self.session.error_message)

    def test_4_duplicado_colision_fotos(self):
        """Caso 4: El ZIP contiene archivos con nombres que colisionan. Valida renombramiento."""
        zip_path = os.path.join(self.tmp_dir, f"{self.session.uuid}.zip")
        with zipfile.ZipFile(zip_path, 'w') as z:
            img_path = os.path.join(self.tmp_dir, "test_foto.jpg")
            self._create_dummy_image(img_path)
            # Insertar dos fotos con el mismo nombre (fuerza colisión al extraer)
            z.writestr("foto_repetida.jpg", open(img_path, 'rb').read())
            z.writestr("subcarpeta/foto_repetida.jpg", open(img_path, 'rb').read())
            os.remove(img_path)
            
        self._create_valid_csv(self.session.uuid, [{"Foto": "foto_repetida.jpg"}])
        
        process_upload_logic(self.session.uuid)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'DRAFT')
        
        # Deben existir foto_repetida.jpg y foto_repetida_1.jpg
        extract_dir = os.path.join(self.test_media_root, 'workspace', 'sessions', str(self.session.uuid))
        self.assertTrue(os.path.exists(os.path.join(extract_dir, 'photos', 'foto_repetida.jpg')))
        self.assertTrue(os.path.exists(os.path.join(extract_dir, 'photos', 'foto_repetida_1.jpg')))

    def test_5_caso_limite_datos_incompletos(self):
        """Caso 5: Datos incompletos o vacíos, debe crear el draft de todos modos."""
        self._create_valid_zip(self.session.uuid)
        
        # Un CSV con un campo en None/NaN y sin la columna Foto o con foto vacía
        self._create_valid_csv(self.session.uuid, [
            {"Modelo": "T01", "Cantidad": None},
            {"Modelo": "T02", "Foto": ""},
            {"Modelo": "T03", "Foto": float('nan')},
        ])
        
        process_upload_logic(self.session.uuid)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'DRAFT')
        self.assertEqual(self.session.total_rows, 3)
        
        drafts = DraftRegistro.objects.filter(session=self.session).order_by('row_index')
        self.assertEqual(drafts.count(), 3)
        
        # EL DESCUBRIMIENTO AHORA RESUELTO:
        # Pandas lee celdas vacías como float('nan').
        # Django jsonb serializer no soporta 'NaN' nativo. 
        # Ahora se sanitizan a None, permitiendo que la importación sea exitosa.
        d1, d2, d3 = drafts
        
        # d1 tiene cantidad: None -> al mapear raw_data items:
        # mapped_data convierte `None` a string vacío porque `str(v) if pd.notna(v) else ""`
        # 'cantidad' era NaN en el df original, se volvió None, y pd.notna(None) es False.
        # Por tanto mapped_data['cantidad'] será "".
        self.assertEqual(d1.mapped_data['cantidad'], "")
        self.assertEqual(d2.assigned_photos, [])
        self.assertEqual(d3.assigned_photos, [])

