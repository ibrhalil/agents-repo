#!/usr/bin/env python3
"""Content-bound policy proposals and isolated approved objects (stdlib only).

Receipts attest a reviewed live-session workflow; they do not authenticate humans
or resist a writer that can replace this program and its state. Never print text.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

import noma_lib as lib
import noma_board

REGISTER = 'wiki/agent-policy.md'
STATE = '.policy/activation.json'
OBJECTS = '.policy/objects'
LEGACY_STATE = 'plans/2026-10-03-policy-activation.json'
LEGACY_SNAPSHOTS = 'plans/2026-10-03-policy-snapshots'
CONTROL_REQUIRED = ('AGENTS.md', 'SCHEMA.md', '.gitattributes', '.pre-commit-config.yaml',
                    'scripts/noma_policy.py', 'scripts/noma_hermes_context.py',
                    'scripts/noma_lint.py', 'scripts/noma_lib.py', 'scripts/noma_board.py')
CONTROL = CONTROL_REQUIRED + ('scripts/noma_privacy.py', 'scripts/noma_build_index.py',
                              'scripts/noma-run-lint.sh', 'scripts/noma-bootstrap.sh', '.ignore')
HASH = re.compile(r'[0-9a-f]{64}')
KRR = re.compile(r'KRR-\d{2,}')


class PolicyError(Exception):
    def __init__(self, rule):
        self.rule = rule
        super().__init__(rule)


class SignalParser(argparse.ArgumentParser):
    def error(self, message):
        raise PolicyError('INPUT')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8'))


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise PolicyError('DUPLICATE-KEY')
        obj[key] = value
    return obj


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise PolicyError('PATH')
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
            p in ('.', '..', '.git', '.env') for p in path.parts):
        raise PolicyError('PATH')
    return path.parts


@contextlib.contextmanager
def parent_fd(root, value, create=False):
    parts = relative(value)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, parts[-1]
    finally:
        os.close(fd)


def read_bytes(root, value):
    try:
        with parent_fd(root, value) as (directory, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise PolicyError('NOT-FILE')
                data = stream.read()
        if data.startswith(lib.CRYPT_MAGIC):
            raise PolicyError('LOCKED')
        return data
    except OSError:
        raise PolicyError('UNREADABLE') from None


def publish(root, value, data, exclusive=False):
    with parent_fd(root, value, create=True) as (directory, name):
        temporary = '.policy-' + uuid.uuid4().hex
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if exclusive:
                os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
                        follow_symlinks=False)
            else:
                # Refuse a symlink even when atomic replacement would be safe.
                try:
                    if stat.S_ISLNK(os.stat(name, dir_fd=directory,
                                          follow_symlinks=False).st_mode):
                        raise PolicyError('PATH')
                except FileNotFoundError:
                    pass
                os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass


def members(text):
    clean = lib.strip_code(text)
    found = re.findall(r'^## Aktif Policy Kümesi\n(.*?)(?=^## |\Z)', clean,
                       re.M | re.S)
    if len(found) != 1:
        raise PolicyError('MEMBERSHIP')
    slugs = re.findall(r'^- \[\[([a-z0-9]+(?:-[a-z0-9]+)*)(?:\|[^\]\n]+)?\]\]',
                       found[0], re.M)
    if not slugs or len(slugs) != len(set(slugs)):
        raise PolicyError('MEMBERSHIP')
    return sorted({REGISTER, *(f'wiki/{slug}.md' for slug in slugs)})


def head(root):
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                            capture_output=True)
    value = result.stdout.decode('ascii', errors='ignore').strip()
    return value if result.returncode == 0 and re.fullmatch(r'[0-9a-f]{40,64}', value) else None


def state_path(root):
    return STATE if (root / STATE).exists() or not (root / LEGACY_STATE).exists() else LEGACY_STATE


def object_path(expected):
    if not isinstance(expected, str) or not HASH.fullmatch(expected):
        raise PolicyError('DIGEST')
    return f'{OBJECTS}/{expected}.txt'


def snapshot_path(root, key, path, expected):
    if state_path(root) == LEGACY_STATE:
        return f'{LEGACY_SNAPSHOTS}/{key}/{path}'
    return object_path(expected)


def load_state(root, reader=read_bytes):
    try:
        value = json.loads(reader(root, state_path(root)), object_pairs_hook=unique_object)
        if value['version'] != 1 or not isinstance(value['proposals'], dict):
            raise PolicyError('STATE')
        return value
    except (ValueError, KeyError, TypeError):
        raise PolicyError('STATE') from None


def save_state(root, state):
    if state_path(root) == LEGACY_STATE:
        raise PolicyError('MIGRATION-REQUIRED')
    publish(root, STATE, (json.dumps(state, sort_keys=True, indent=2) + '\n').encode())


def validate_entry(root, key, entry, reader=read_bytes):
    try:
        bundle = entry['bundle']
        if not HASH.fullmatch(key) or payload_digest(bundle) != key:
            raise PolicyError('DIGEST')
        policies = bundle['policies']
        if bundle['version'] != 1 or not isinstance(policies, list):
            raise PolicyError('BUNDLE')
        if sorted(set(policies)) != policies or REGISTER not in policies:
            raise PolicyError('MEMBERSHIP')
        control = bundle['control']
        if (not isinstance(control, list) or sorted(set(control)) != control
                or not set(CONTROL_REQUIRED) <= set(control)):
            raise PolicyError('SCOPE')
        for path in control:
            relative(path)
            if path.startswith(('wiki/', 'raw/', 'plans/', '.policy/', 'tmp/', 'agent/sessions/')):
                raise PolicyError('SCOPE')
        files = bundle['files']
        if set(files) != set(policies) | set(control):
            raise PolicyError('SCOPE')
        texts = {}
        for path, expected in files.items():
            if path not in control and not re.fullmatch(r'wiki/[a-z0-9]+(?:-[a-z0-9]+)*\.md', path):
                raise PolicyError('PATH')
            if not isinstance(expected, str) or not HASH.fullmatch(expected):
                raise PolicyError('DIGEST')
            data = reader(root, snapshot_path(root, key, path, expected))
            if digest(data) != expected:
                raise PolicyError('SNAPSHOT')
            texts[path] = data
            if path in policies:
                fm = lib.parse_fm(data.decode('utf-8')) or {}
                if fm.get('stage', '').strip('"\'“”') == 'archived':
                    raise PolicyError('ARCHIVED')
        if members(texts[REGISTER].decode('utf-8')) != policies:
            raise PolicyError('MEMBERSHIP')
        return bundle
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise PolicyError('BUNDLE') from None


def validate_receipts(key, bundle, entry):
    try:
        review, human = entry['review'], entry['human']
        reviewer = review['reviewer']
        if (not isinstance(reviewer, str) or not re.fullmatch(r'[a-zA-Z0-9._-]+', reviewer)
                or reviewer == bundle['author'] or review['verdict'] != 'approved'
                or review['digest'] != key or review['base'] != bundle['base']):
            raise PolicyError('REVIEW')
        if (human['digest'] != key or human['base'] != bundle['base']
                or human['source'] != 'live-user-session'):
            raise PolicyError('HUMAN-APPROVAL')
    except (KeyError, TypeError):
        raise PolicyError('RECEIPT') from None


def approved(root, reader=read_bytes):
    state = load_state(root, reader)
    try:
        key = state['active']
        entry = state['proposals'][key]
        bundle = validate_entry(root, key, entry, reader)
        validate_receipts(key, bundle, entry)
        return key, bundle
    except (KeyError, TypeError):
        raise PolicyError('NOT-ACTIVE') from None


def status(root):
    try:
        key, bundle = approved(root)
        drift = []
        for path, expected in bundle['files'].items():
            try:
                unchanged = digest(read_bytes(root, path)) == expected
            except PolicyError:
                unchanged = False
            if not unchanged:
                drift.append(path)
        control_drift = sorted(set(drift) & set(bundle['control']))
        upgrade = set(CONTROL) != set(bundle['control'])
        return {'status': 'blocked' if control_drift or upgrade else 'active',
                'rules': (['CONTROL-DRIFT'] if control_drift else []) + (['SCOPE-UPGRADE'] if upgrade else []),
                'paths': sorted(drift), 'members': len(bundle['policies'])}
    except PolicyError as exc:
        return {'status': 'blocked', 'rules': [exc.rule], 'paths': [], 'members': 0}


def resolve(root, slug):
    if not isinstance(slug, str) or not lib.SLUG_RE.fullmatch(slug):
        raise PolicyError('PATH')
    result = status(root)
    if result['status'] != 'active':
        raise PolicyError('NOT-ACTIVE')
    key, bundle = approved(root)
    path = f'wiki/{slug}.md'
    if path not in bundle['policies']:
        raise PolicyError('NONMEMBER')
    expected = bundle['files'][path]
    try:
        if digest(read_bytes(root, path)) == expected:
            return path
    except PolicyError:
        pass
    return snapshot_path(root, key, path, expected)


def decision_status(root, value):
    if not isinstance(value, str) or not KRR.fullmatch(value):
        raise PolicyError('DECISION')
    if status(root)['status'] != 'active':
        raise PolicyError('NOT-ACTIVE')
    key, bundle = approved(root)
    ledger = 'wiki/insan-karar-defteri.md'
    if ledger not in bundle['policies']:
        raise PolicyError('NONMEMBER')
    text = read_bytes(root, snapshot_path(root, key, ledger, bundle['files'][ledger])).decode('utf-8')
    pattern = rf'^### {re.escape(value)}\n(.*?)(?=^### KRR-|^## |\Z)'
    match = re.search(pattern, text, re.M | re.S)
    if match:
        first = match[1].splitlines()[0]
        paths = sorted({f'wiki/{slug}.md' for slug in
                        re.findall(r'\[\[([a-z0-9]+(?:-[a-z0-9]+)*)(?:[|#][^\]\n]*)?\]\]', first)})
        return {'status': 'active' if paths and all(p in bundle['policies'] for p in paths)
                else 'outside-policy', 'paths': paths}
    draft = read_bytes(root, ledger).decode('utf-8')
    if re.search(pattern, draft, re.M | re.S):
        return {'status': 'pending', 'paths': [ledger]}
    raise PolicyError('DECISION')


def migrate(root):
    """Preserve every bundle and receipt before removing verified legacy copies."""
    if not (root / LEGACY_STATE).exists():
        if (root / STATE).exists():
            approved(root)
            return
        raise PolicyError('STATE')
    legacy = json.loads(read_bytes(root, LEGACY_STATE), object_pairs_hook=unique_object)
    if legacy.get('version') != 1 or not isinstance(legacy.get('proposals'), dict):
        raise PolicyError('STATE')
    expected_files = {f'{LEGACY_SNAPSHOTS}/{key}/{path}': expected
                      for key, entry in legacy['proposals'].items()
                      for path, expected in entry['bundle']['files'].items()}
    # Unknown files must survive; refuse cleanup rather than silently deleting them.
    archive = root / LEGACY_SNAPSHOTS
    actual = set()
    if archive.is_symlink():
        raise PolicyError('PATH')
    for path in archive.rglob('*'):
        if path.is_symlink():
            raise PolicyError('PATH')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if not actual <= set(expected_files):
        raise PolicyError('LEGACY-EXTRA')
    modern = (root / STATE).exists()
    if modern:
        state = load_state(root)
        if any(state['proposals'].get(key) != entry for key, entry in legacy['proposals'].items()):
            raise PolicyError('MIGRATION-CONFLICT')
    else:
        if actual != set(expected_files):
            raise PolicyError('SNAPSHOT')
        for key, entry in legacy['proposals'].items():
            validate_entry(root, key, entry)
        if legacy['active'] is not None:
            approved(root)
        for path, expected in expected_files.items():
            content = read_bytes(root, path)
            target = object_path(expected)
            try:
                publish(root, target, content, exclusive=True)
            except FileExistsError:
                if read_bytes(root, target) != content:
                    raise PolicyError('SNAPSHOT') from None
        publish(root, STATE, (json.dumps(legacy, sort_keys=True, indent=2) + '\n').encode(),
                exclusive=True)
        state = legacy
    # Verify the destination and each remaining source before unlinking anything.
    for key, entry in state['proposals'].items():
        validate_entry(root, key, entry)
    if state['active'] is not None:
        approved(root)
    for path in actual:
        if digest(read_bytes(root, path)) != expected_files[path]:
            raise PolicyError('SNAPSHOT')
    for path in sorted(actual):
        with parent_fd(root, path) as (directory, name):
            os.unlink(name, dir_fd=directory)
    for directory in sorted(archive.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir():
            directory.rmdir()
    if archive.exists():
        archive.rmdir()
    with parent_fd(root, LEGACY_STATE) as (directory, name):
        os.unlink(name, dir_fd=directory)


def propose(root, author):
    if not author or not re.fullmatch(r'[a-zA-Z0-9._-]+', author):
        raise PolicyError('AUTHOR')
    if state_path(root) == LEGACY_STATE:
        raise PolicyError('MIGRATION-REQUIRED')
    if (root / STATE).exists():
        state = load_state(root)
        base = state['active']
        if base is not None:
            approved(root)
    else:
        state = {'version': 1, 'active': None, 'proposals': {}}
        base = None
    policies = members(read_bytes(root, REGISTER).decode('utf-8'))
    data = {path: read_bytes(root, path) for path in sorted(set(policies) | set(CONTROL))}
    bundle = {'version': 1, 'base': base, 'head': head(root), 'author': author,
              'control': sorted(CONTROL),
              'policies': policies, 'files': {p: digest(b) for p, b in data.items()}}
    key = payload_digest(bundle)
    if key in state['proposals']:
        validate_entry(root, key, state['proposals'][key])
        return key
    for path, content in data.items():
        snapshot = object_path(bundle['files'][path])
        try:
            publish(root, snapshot, content, exclusive=True)
        except FileExistsError:
            if read_bytes(root, snapshot) != content:
                raise PolicyError('SNAPSHOT') from None
    entry = {'bundle': bundle, 'review': None, 'human': None}
    validate_entry(root, key, entry)
    state['proposals'][key] = entry
    save_state(root, state)
    return key


def current_proposal(root, state, key):
    try:
        entry = state['proposals'][key]
        bundle = validate_entry(root, key, entry)
        if bundle['base'] != state['active'] or bundle['head'] != head(root):
            raise PolicyError('STALE-BASE')
        if any(digest(read_bytes(root, p)) != value for p, value in bundle['files'].items()):
            raise PolicyError('STALE-CONTENT')
        return entry, bundle
    except (KeyError, TypeError):
        raise PolicyError('PROPOSAL') from None


def record_review(root, key, reviewer):
    state = load_state(root)
    entry, bundle = current_proposal(root, state, key)
    if (not reviewer or not re.fullmatch(r'[a-zA-Z0-9._-]+', reviewer)
            or reviewer == bundle['author']):
        raise PolicyError('INDEPENDENT-REVIEW')
    entry['review'] = {'digest': key, 'base': bundle['base'],
                       'reviewer': reviewer, 'verdict': 'approved'}
    save_state(root, state)


def activate(root, key, confirmation):
    if confirmation != key:
        raise PolicyError('HUMAN-APPROVAL')
    state = load_state(root)
    entry, bundle = current_proposal(root, state, key)
    review = entry['review']
    if (not review or review.get('digest') != key or review.get('base') != bundle['base']
            or review.get('reviewer') == bundle['author']):
        raise PolicyError('REVIEW')
    entry['human'] = {'digest': key, 'base': bundle['base'], 'source': 'live-user-session'}
    validate_receipts(key, bundle, entry)
    state['active'] = key
    save_state(root, state)


@contextlib.contextmanager
def mutation(root, run_id):
    import noma_board
    runs = noma_board.Board(root).status()['runs']
    own = next((run for run in runs if run['run_id'] == run_id), None)
    needed = (STATE, OBJECTS)
    if (root / LEGACY_STATE).exists():
        needed += (LEGACY_STATE, LEGACY_SNAPSHOTS)
    if not own or not all(any(path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/')
                              for p in own['working_files']) for path in needed):
        raise PolicyError('CLAIM')
    with parent_fd(root, 'tmp/.noma-policy.lock', create=True) as (directory, name):
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'a+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def main(argv=None):
    ap = SignalParser(description=__doc__)
    ap.add_argument('mode', choices=('status', 'resolve', 'decision', 'migrate',
                                     'propose', 'review', 'activate'))
    ap.add_argument('value', nargs='?')
    ap.add_argument('--author')
    ap.add_argument('--reviewer')
    ap.add_argument('--human-confirmation')
    ap.add_argument('--run-id')
    ap.add_argument('--json', action='store_true')
    try:
        args = ap.parse_args(argv)
        if args.mode == 'status':
            result = status(lib.ROOT)
        elif args.mode == 'resolve':
            result = {'path': resolve(lib.ROOT, args.value)}
        elif args.mode == 'decision':
            result = decision_status(lib.ROOT, args.value)
        else:
            with mutation(lib.ROOT, args.run_id):
                if args.mode == 'migrate':
                    migrate(lib.ROOT)
                    result = {'status': 'migrated'}
                elif args.mode == 'propose':
                    result = {'proposal': propose(lib.ROOT, args.author)}
                elif args.mode == 'review':
                    record_review(lib.ROOT, args.value, args.reviewer)
                    result = {'status': 'reviewed'}
                else:
                    activate(lib.ROOT, args.value, args.human_confirmation)
                    result = {'status': 'activated'}
        print(json.dumps(result))
        return 1 if result.get('status') == 'blocked' else 0
    except (PolicyError, noma_board.BoardError, OSError, UnicodeError,
            ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, PolicyError):
            rule = exc.rule
        elif isinstance(exc, noma_board.BoardError):
            rule = 'BOARD'
        else:
            rule = 'INPUT'
        print(json.dumps({'status': 'blocked', 'rules': [rule]}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
