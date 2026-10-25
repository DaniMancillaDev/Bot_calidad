import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('audit', Path(__file__).parents[1] / 'audit_prod_dev.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_allowlist_excludes_data_credentials_and_traversal(self):
        for name in ('../web/a.py', '/web/a.py', '.env', 'web/.env.py', 'media_files/a.py',
                     'web/backup_evidencias.json', 'shared/keys.json', 'web/__pycache__/a.py'):
            self.assertFalse(audit.allowed(name), name)
        self.assertTrue(audit.allowed('web/calidad/tasks.py'))
        self.assertTrue(audit.allowed('shared/infrastructure/ai/defect_catalog.json'))

    def test_reports_drift_both_directions_and_verifies_integrity_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prod, dev = root / 'prod', root / 'dev'
            for path in (prod, dev):
                (path / 'web').mkdir(parents=True)
                (path / '.env').write_text('SECRET=never-report-this')
                (path / 'web/equal.py').write_text('same')
            (prod / 'web/only_prod.py').write_text('old')
            (dev / 'web/only_dev.py').write_text('new')
            recorded = audit.manifest(prod, 'image@sha256:example')
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            report = audit.compare(prod, recorded, dev, recorded)
            self.assertEqual(report['dev_only'], ['web/only_dev.py'])
            self.assertEqual(report['prod_changed_since_baseline'], [])
            self.assertEqual(report['files'][1]['status'], 'missing_in_dev')
            self.assertNotIn('SECRET', str(report))
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            (prod / 'web/equal.py').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                audit.compare(prod, recorded, dev)

    def test_symlinks_outside_snapshot_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'web').mkdir()
            (root / 'outside.py').write_text('sensitive')
            (root / 'web/link.py').symlink_to(root / 'outside.py')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                audit.manifest(root, 'snapshot')

    def test_unrecorded_new_source_cannot_hide_in_a_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'web').mkdir()
            (root / 'web/initial.py').write_text('initial')
            recorded = audit.manifest(root, 'snapshot')
            (root / 'web/new.py').write_text('unrecorded')
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                audit.compare(root, recorded, root)
