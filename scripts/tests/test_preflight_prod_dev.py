import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import preflight_prod_dev as gate
from audit_prod_dev import manifest
from run_conservation_checks import isolated_environment


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.prod = root / 'dev', root / 'prod'
        for path in (self.repo, self.prod):
            (path / 'web/calidad/migrations').mkdir(parents=True)
            (path / 'web/calidad/migrations/0001_initial.py').write_text('pass\n')
            (path / 'web/main.py').write_text('print("source")\n')
        self.git('init', '-q')
        self.commit()
        self.recorded = manifest(self.prod, 'known-image')
        self.manifest_path = root / 'manifest.json'
        self.manifest_path.write_text(json.dumps(self.recorded))
        self.scope = {'name': 'web', 'container': 'known-prod', 'image': 'known-image',
                      'paths': ['web'], 'root': str(self.prod), 'manifest': str(self.manifest_path)}
        self.policy = {
            'scopes': {'web': {**{k: self.scope[k] for k in ('container', 'image', 'paths')},
                'files': {name: {'prod_sha256': value, 'dev_sha256': value,
                                 'decision': 'equivalent', 'reason': 'reviewed identical capability'}
                          for name, value in self.recorded['files'].items()}}},
            'required_files': ['web/main.py'], 'conflicts': [], 'migration_target': {},
        }
        self.evidence = {'checks': {}, 'source_fingerprint': gate.source_fingerprint(self.repo),
                         'source_unchanged_during_checks': True,
                         'image': {'image_id': 'verified-image', 'files': gate.image_sources(self.repo)}}
        for name in gate.REQUIRED_CHECKS:
            log = root / f'{name}.log'
            log.write_text('synthetic unit-test evidence')
            self.evidence['checks'][name] = {'exit_code': 0, 'log': str(log),
                'log_sha256': gate.hashlib.sha256(log.read_bytes()).hexdigest()}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'test')

    def check(self, **overrides):
        return gate.evaluate(self.repo, {'scopes': [self.scope]}, overrides.get('policy', self.policy),
            overrides.get('evidence', self.evidence),
            live_reader=overrides.get('live_reader', lambda scope: {'image': scope['image'], 'files': self.recorded['files']}),
            migration_reader=lambda target: {'calidad:0001_initial'},
            runtime_reader=overrides.get('runtime_reader', lambda policy: []))

    def test_reviewed_clean_tree_with_current_tests_can_pass(self):
        self.assertTrue(self.check()['ready'])

    def test_service_failure_or_redis_persistence_failure_blocks(self):
        failures = ['runtime:celery: exited', 'redis-persistence:rdb_last_bgsave_status=err']
        result = self.check(runtime_reader=lambda policy: failures)
        self.assertFalse(result['ready'])
        self.assertTrue(set(failures).issubset(result['blockers']))

    def test_snapshot_corruption_and_live_drift_are_blocked(self):
        live = lambda scope: {'image': scope['image'], 'files': {}}
        self.assertTrue(any(b.startswith('live-prod:') for b in self.check(live_reader=live)['blockers']))
        (self.prod / 'web/main.py').write_text('unreviewed change')
        self.assertTrue(any(b.startswith('snapshot-integrity:') for b in self.check()['blockers']))

    def test_fresh_snapshot_with_unreviewed_prod_change_is_blocked(self):
        (self.prod / 'web/main.py').write_text('unreviewed change')
        self.recorded = manifest(self.prod, 'known-image')
        self.manifest_path.write_text(json.dumps(self.recorded))
        self.assertTrue(any(b.startswith('unreviewed-prod:') for b in self.check()['blockers']))

    def test_critical_file_and_image_dependency_failures_block(self):
        evidence = copy.deepcopy(self.evidence)
        evidence['image']['files'] = {}
        self.assertTrue(any(b.startswith('image-dependencies:') for b in self.check(evidence=evidence)['blockers']))
        (self.repo / 'web/main.py').unlink()
        self.assertIn('missing-critical-file:web/main.py', self.check()['blockers'])

    def test_pending_migrations_and_dirty_git_are_blocked(self):
        (self.repo / 'web/calidad/migrations/0002_pending.py').write_text('pass')
        blockers = self.check()['blockers']
        self.assertTrue(any(b.startswith('pending-migrations:') for b in blockers))
        self.assertTrue(any(b.startswith('git-dirty:') for b in blockers))

    def test_conflicts_need_resolution_or_documented_authorization(self):
        policy = copy.deepcopy(self.policy)
        conflict = {'id': 'grouping', 'status': 'pending', 'reason': 'business decision pending'}
        policy['conflicts'] = [conflict]
        self.assertFalse(self.check(policy=policy)['ready'])
        conflict.update(status='authorized_exception')
        self.assertFalse(self.check(policy=policy)['ready'])
        conflict.update(authorized_by='operator', authorization_ref='documented test authorization')
        self.assertTrue(self.check(policy=policy)['ready'])

    def test_failed_stale_or_tampered_test_evidence_blocks(self):
        evidence = copy.deepcopy(self.evidence)
        evidence['checks']['django']['exit_code'] = 1
        self.assertIn('required-test:django: missing, failed or unverifiable', self.check(evidence=evidence)['blockers'])
        evidence = copy.deepcopy(self.evidence)
        evidence['source_fingerprint'] = 'old'
        self.assertTrue(any(b.startswith('stale-tests:') for b in self.check(evidence=evidence)['blockers']))
        Path(evidence['checks']['django']['log']).write_text('tampered')
        self.assertTrue(any(b.startswith('required-test:django:') for b in self.check()['blockers']))

    def test_test_runner_rejects_production_service_addresses(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user@postgres/calidad_db',
                                    'CELERY_BROKER_URL': 'redis://redis:6379/0'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'dedicated local'):
                isolated_environment(self.repo)
