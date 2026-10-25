"""Compare identified source snapshots without applying changes or reading runtime data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT_FILES = (
    'main.py', 'pyproject.toml', 'uv.lock',
    'plantilla_reporte.xlsx', 'Daily Tracking Box Condition.xlsx',
)

def allowed(name):
    path = PurePosixPath(name)
    return (
        not path.is_absolute() and '..' not in path.parts
        and not any(part.startswith('.') or part == '__pycache__' for part in path.parts)
        and (
            (path.parts[0] in ('web', 'shared', 'bot') and path.suffix in ('.py', '.html', '.css', '.js'))
            or name in (*ROOT_FILES, 'shared/infrastructure/ai/defect_catalog.json')
        )
    ) if path.parts else False


def digest(root, name):
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f'Unsafe source path: {name}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root, identifier):
    files = {}
    paths = [root / name for name in ROOT_FILES if (root / name).is_file()]
    for directory in ('web', 'shared', 'bot'):
        paths.extend((root / directory).rglob('*'))
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        if path.is_file() and allowed(name):
            files[name] = digest(root, name)
    if not files:
        raise ValueError('Snapshot has no allow-listed source files')
    return {'version': 1, 'snapshot_id': identifier, 'files': files}


def compare(snapshot, recorded, dev, baseline=None):
    if recorded.get('version') != 1 or not recorded.get('snapshot_id') or not recorded.get('files'):
        raise ValueError('Expected an identified version-1 source manifest')
    actual_files = manifest(snapshot, recorded['snapshot_id'])['files']
    if set(actual_files) != set(recorded['files']):
        raise ValueError('Snapshot integrity check failed: source inventory changed')
    results = []
    for name, expected in sorted(recorded['files'].items()):
        if not allowed(name):
            raise ValueError(f'Path outside source allow-list: {name}')
        actual = actual_files[name]
        if actual != expected:
            raise ValueError(f'Snapshot integrity check failed: {name}')
        target = dev / name
        dev_hash = digest(dev, name) if target.is_file() else None
        results.append({
            'path': name, 'prod_sha256': actual, 'dev_sha256': dev_hash,
            'status': 'missing_in_dev' if dev_hash is None else 'equal' if dev_hash == actual else 'different',
        })
    dev_files = manifest(dev, 'dev')['files']
    report = {
        'snapshot_id': recorded['snapshot_id'],
        'files': results,
        'dev_only': sorted(set(dev_files) - set(recorded['files'])),
    }
    if baseline is not None:
        old = baseline['files']
        report['prod_changed_since_baseline'] = sorted(
            name for name in set(old) | set(recorded['files'])
            if old.get(name) != recorded['files'].get(name)
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('manifest', 'compare'))
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--id')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--dev', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.snapshot.resolve()):
        parser.error('Write reports outside the source snapshot')
    if args.action == 'manifest':
        if not args.id:
            parser.error('--id is required for manifest')
        result = manifest(args.snapshot, args.id)
    else:
        if not args.manifest or not args.dev:
            parser.error('--manifest and --dev are required for compare')
        result = compare(
            args.snapshot, json.loads(args.manifest.read_text()), args.dev,
            json.loads(args.baseline.read_text()) if args.baseline else None,
        )
    # Exclusive output creation prevents accidental replacement of source or earlier reports.
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
