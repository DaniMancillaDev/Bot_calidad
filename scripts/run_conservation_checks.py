"""Run mandatory regressions on local isolated services and record reproducible evidence."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from preflight_prod_dev import source_fingerprint, image_sources

DJANGO_MODULES = (
    'calidad.tests', 'calidad.tests_v2', 'calidad.tests_concurrency',
    'calidad.tests_whatsapp', 'calidad.tests_pending_evidence', 'calidad.tests_whatsapp_concurrency',
    'calidad.tests_prod_sync', 'calidad.tests_box_template', 'calidad.tests_report_grouping',
    'workspace.tests.test_processing_characterization', 'workspace.tests.test_processing_locking',
)


def isolated_environment(repo):
    env = dict(os.environ)
    database = urlparse(env.get('DATABASE_URL', ''))
    redis = urlparse(env.get('CELERY_BROKER_URL', ''))
    if database.hostname not in ('127.0.0.1', 'localhost') or not database.path.lstrip('/').startswith('sync_test'):
        raise ValueError('Use a dedicated local sync_test* PostgreSQL database, never PROD')
    if redis.hostname not in ('127.0.0.1', 'localhost') or redis.path != '/15':
        raise ValueError('Use dedicated local Redis database 15, never PROD')
    env.update(PYTHON_DOTENV_DISABLED='1', DJANGO_SETTINGS_MODULE='config.settings',
               DJANGO_SECRET_KEY='isolated-conservation-checks',
               PYTHONPATH=str(repo / 'web') + os.pathsep + str(repo),
               CELERY_RESULT_BACKEND=env['CELERY_BROKER_URL'])
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--image-proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.repo.resolve()):
        parser.error('Create new evidence outside the repository')
    env = isolated_environment(args.repo)
    before = source_fingerprint(args.repo)
    commands = {
        'django': [sys.executable, '-c', 'import django;django.setup();from django.core.management import call_command;'
                   + f'call_command("test",*{DJANGO_MODULES!r},verbosity=1,interactive=False)'],
        'shared': [sys.executable, '-m', 'unittest', 'discover', '-s', 'shared/utils/tests', '-v'],
        'scripts': [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-v'],
        'whatsapp_adapter': ['npm', 'test', '--prefix', 'whatsapp'],
        'migration_consistency': [sys.executable, '-c', 'import django;django.setup();from django.core.management import call_command;call_command("makemigrations",check=True,dry_run=True)'],
        'diff_check': ['git', 'diff', '--check'],
    }
    checks = {}
    for name, command in commands.items():
        log = args.output.with_name(args.output.stem + '-' + name + '.log')
        with log.open('xb') as target:
            result = subprocess.run(command, cwd=args.repo, env=env, stdout=target, stderr=subprocess.STDOUT)
        checks[name] = {'exit_code': result.returncode, 'log': str(log.resolve()),
                        'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
        print(name, result.returncode, flush=True)
    image = json.loads(args.image_proof.read_text())
    if image.get('files') != image_sources(args.repo):
        raise ValueError('Image verification does not match current DEV sources/resources')
    after = source_fingerprint(args.repo)
    evidence = {'created_at': datetime.now(timezone.utc).isoformat(), 'source_fingerprint': before,
                'checks': checks, 'image': image, 'source_unchanged_during_checks': before == after}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(evidence, output, indent=2)
        output.write('\n')
    return 0 if before == after and all(check['exit_code'] == 0 for check in checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
