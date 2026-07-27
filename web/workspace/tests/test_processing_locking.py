import tempfile
import shutil
import threading
import os
import zipfile
import pandas as pd
from unittest.mock import patch
from django.test import TransactionTestCase
from django.db import connection, connections
from django.contrib.auth import get_user_model

from workspace.models import ImportSession, DraftRegistro
from workspace.services.processing import process_upload_logic

User = get_user_model()

class ProcessingLockingTest(TransactionTestCase):
    # Usamos TransactionTestCase porque probamos locks de base de datos
    
    def setUp(self):
        self.user = User.objects.create(username="test_supervisor")
        # Inicia en un estado previo (ej. PENDING)
        self.session = ImportSession.objects.create(
            supervisor=self.user,
            status='PENDING'
        )
        
        self.test_media_root = tempfile.mkdtemp()
        self.patcher = patch('workspace.services.processing.settings.MEDIA_ROOT', self.test_media_root)
        self.patcher.start()
        
        self.tmp_dir = os.path.join(self.test_media_root, 'workspace', 'tmp')
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        self._create_valid_zip(self.session.uuid)
        self._create_valid_csv(self.session.uuid, [{"Modelo": "T1", "Foto": ""}])

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_media_root)

    def _create_valid_zip(self, session_uuid):
        zip_path = os.path.join(self.tmp_dir, f"{session_uuid}.zip")
        with zipfile.ZipFile(zip_path, 'w') as z:
            z.writestr("dummy.txt", "dummy")
        return zip_path

    def _create_valid_csv(self, session_uuid, data):
        csv_path = os.path.join(self.tmp_dir, f"{session_uuid}_excel.csv")
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_concurrent_processing_avoids_duplicates(self):
        """
        Si dos workers intentan procesar la misma sesión concurrentemente,
        el bloqueo corto o el check de estado debe prevenir que se procese dos veces.
        """
        results = []
        def worker():
            try:
                process_upload_logic(self.session.uuid)
                results.append(True)
            except Exception as e:
                results.append(e)
            finally:
                connections.close_all()
                
        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Uno debió procesar correctamente (status DRAFT), el otro debió abortar (o terminar sin efecto)
        self.session.refresh_from_db()
        
        # El estado final debe ser DRAFT
        self.assertEqual(self.session.status, 'DRAFT')
        
        # Y crucialmente, NO deben existir registros duplicados (solo 1 row en el CSV)
        self.assertEqual(DraftRegistro.objects.filter(session=self.session).count(), 1)
