"""Fail-closed pre-deployment checks. Reads PROD, never deploys or changes it."""
import argparse
import hashlib
import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

from audit_prod_dev import allowed, compare, digest, manifest

REQUIRED_CHECKS = ('django', 'shared', 'scripts', 'whatsapp_adapter', 'migration_consistency', 'diff_check')
DECISIONS = {'equivalent', 'integrated', 'intentional', 'historical', 'conflict'}


def docker_command():
    return shlex.split(os.environ.get('DOCKER_COMMAND', 'docker'))


def source_fingerprint(repo):
    tracked = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0')
    values = {}
    for name in sorted(filter(None, tracked)):
        if Path(name).suffix.lower() != '.md':
            values[name] = digest(repo, name) if (repo / name).is_file() else None
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def read_live(scope):
    command = docker_command()
    image = subprocess.check_output(command + ['inspect', '--format', '{{.Image}}', scope['container']], text=True).strip()
    data = subprocess.check_output(command + [
        'exec', scope['container'], 'tar', '-C', '/app', '--exclude=__pycache__',
        '--exclude=*.log', '--exclude=.env*', '--exclude=backup*.json', '-cf', '-', *scope['paths'],
    ])
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for item in archive:
            name = item.name.removeprefix('./')
            if item.isfile() and allowed(name):
                files[name] = hashlib.sha256(archive.extractfile(item).read()).hexdigest()
    return {'image': image, 'files': files}


def read_migrations(target):
    rows = subprocess.check_output(docker_command() + [
        'exec', target['container'], 'psql', '-U', target['user'], '-d', target['database'], '-At', '-c',
        "SELECT app || ':' || name FROM django_migrations WHERE app IN ('calidad','workspace') ORDER BY app,name",
    ], text=True)
    return set(rows.splitlines())


def read_runtime(policy):
    problems = []
    for name in policy.get('runtime_services', []):
        state = subprocess.check_output(docker_command() + ['inspect', '--format',
            '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}', name], text=True).split()
        if not state or state[0] != 'running' or 'unhealthy' in state:
            problems.append(f'runtime:{name}: ' + ' '.join(state))
    if policy.get('redis_container'):
        info = subprocess.check_output(docker_command() + ['exec', policy['redis_container'],
            'redis-cli', 'INFO', 'persistence'], text=True)
        values = dict(line.strip().split(':', 1) for line in info.splitlines() if ':' in line)
        for field in ('rdb_last_bgsave_status', 'aof_last_write_status'):
            if values.get(field) == 'err':
                problems.append(f'redis-persistence:{field}=err')
    return problems


def image_sources(repo):
    # The common web/Celery image contains bot/, but main.py belongs to Dockerfile.bot.
    return {name: value for name, value in manifest(repo, 'dev')['files'].items() if name != 'main.py'}


def evaluate(repo, inventory, policy, evidence, *, live_reader=read_live, migration_reader=read_migrations,
             runtime_reader=read_runtime):
    blockers, observations = [], []
    try:
        blockers.extend(runtime_reader(policy))
    except (OSError, subprocess.SubprocessError) as error:
        blockers.append(f'runtime-unavailable: {type(error).__name__}')
    scopes = inventory.get('scopes', [])
    if not scopes or len(scopes) != len(policy.get('scopes', {})) or {s['name'] for s in scopes} != set(policy.get('scopes', {})):
        blockers.append('snapshot-scopes: inventory does not cover every reviewed PROD service/resource')
    for scope in scopes:
        name = scope['name']
        try:
            recorded = json.loads(Path(scope['manifest']).read_text())
            report = compare(Path(scope['root']), recorded, repo)
            live = live_reader(scope)
            reviewed = policy['scopes'].get(name, {})
            if any(scope.get(field) != reviewed.get(field) for field in ('container', 'image', 'paths')):
                blockers.append(f'prod-identity:{name}: service/image/source scope differs from the review')
            if live['files'] != recorded['files'] or live['image'] != scope['image']:
                blockers.append(f'live-prod:{name}: PROD changed since the supplied snapshot; capture and review again')
            if set(recorded['files']) != set(reviewed.get('files', {})):
                blockers.append(f'unreviewed-inventory:{name}: PROD source inventory is not fully evaluated')
            for item in report['files']:
                decision = reviewed.get('files', {}).get(item['path'], {})
                key = f"{name}:{item['path']}"
                if decision.get('prod_sha256') != item['prod_sha256']:
                    blockers.append(f'unreviewed-prod:{key}: new or changed production content')
                elif decision.get('decision') not in DECISIONS or not decision.get('reason'):
                    blockers.append(f'unreviewed-decision:{key}')
                elif item['status'] == 'missing_in_dev' and decision['decision'] != 'historical':
                    blockers.append(f'missing-dependency:{key}')
                elif decision.get('dev_sha256') != item['dev_sha256']:
                    blockers.append(f'dev-review-stale:{key}: DEV evolved; re-evaluate capability preservation')
                else:
                    observations.append({'scope': name, 'path': item['path'], 'decision': decision['decision']})
        except (KeyError, ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
            blockers.append(f'snapshot-integrity:{name}: {type(error).__name__}: {error}')
    for name in policy.get('required_files', []):
        if not (repo / name).is_file():
            blockers.append(f'missing-critical-file:{name}')
    for conflict in policy.get('conflicts', []):
        authorized = conflict.get('status') == 'authorized_exception' and all(
            conflict.get(field) for field in ('authorized_by', 'authorization_ref', 'reason'))
        resolved = conflict.get('status') == 'resolved' and conflict.get('decision_ref')
        if not (authorized or resolved):
            blockers.append(f"unresolved-conflict:{conflict['id']}: {conflict['reason']}")
    try:
        applied = migration_reader(policy['migration_target'])
        source_migrations = {
            f'{app}:{path.stem}' for app in ('calidad', 'workspace')
            for path in (repo / 'web' / app / 'migrations').glob('*.py') if path.name != '__init__.py'
        }
        pending = sorted(source_migrations - applied)
        if pending:
            blockers.append('pending-migrations: ' + ', '.join(pending))
    except (KeyError, OSError, subprocess.SubprocessError) as error:
        blockers.append(f'migration-inventory: unavailable ({type(error).__name__})')
        pending = []
    git_state = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True)
    if git_state:
        blockers.append('git-dirty: commit or preserve and review all changes before deployment')
    if evidence.get('source_fingerprint') != source_fingerprint(repo):
        blockers.append('stale-tests: evidence does not match the current tracked source tree')
    if evidence.get('source_unchanged_during_checks') is not True:
        blockers.append('unstable-tests: source changed while the mandatory checks were running')
    for name in REQUIRED_CHECKS:
        check = evidence.get('checks', {}).get(name, {})
        try:
            valid_log = hashlib.sha256(Path(check['log']).read_bytes()).hexdigest() == check['log_sha256']
        except (KeyError, OSError):
            valid_log = False
        if check.get('exit_code') != 0 or not valid_log:
            blockers.append(f'required-test:{name}: missing, failed or unverifiable')
    image = evidence.get('image', {})
    if not image.get('image_id') or image.get('files') != image_sources(repo):
        blockers.append('image-dependencies: verify a built image against current source and templates')
    return {'ready': not blockers, 'blockers': blockers, 'reviewed': observations,
            'pending_migrations': pending, 'source_fingerprint': source_fingerprint(repo)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    policy = args.policy or args.repo / 'docs/prod_dev_reviews.json'
    try:
        result = evaluate(args.repo, json.loads(args.inventory.read_text()),
                          json.loads(policy.read_text()), json.loads(args.evidence.read_text()))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {'ready': False, 'blockers': [f'preflight-input: {type(error).__name__}: {error}']}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print('READY' if result['ready'] else 'BLOCKED')
    for blocker in result['blockers']:
        print(blocker)
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
