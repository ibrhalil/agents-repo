#!/usr/bin/env python3
"""Cooperative, checkout-local coordination. See scripts/README.md and AGENTS.md.

BOARD.md is the only state store. A stable local lock protects read/check/replace;
claims do not intercept editors or grant permission to stage existing changes.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
STATE = re.compile(r'^```json\n(.*?)\n```$', re.M | re.S)
KEY = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
FIELDS = {'run_id', 'task_key', 'source', 'started_at', 'working_files'}
LOCK_TIMEOUT = 2.0


class BoardError(Exception):
    """Only fixed diagnostic codes may reach stdout."""


def valid_key(value):
    return isinstance(value, str) and len(value) <= 100 and KEY.fullmatch(value)


def valid_path(value):
    if not isinstance(value, str) or not value or value.startswith('/'):
        return False
    if '\\' in value or value.endswith('//') or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    parts = value.rstrip('/').split('/')
    return (all(part not in ('', '.', '..', '.git') for part in parts)
            and parts[0] not in ('BOARD.md', 'tmp'))


def overlaps(left, right):
    left, right = left.rstrip('/'), right.rstrip('/')
    return left == right or left.startswith(right + '/') or right.startswith(left + '/')


def validate(entries):
    if not isinstance(entries, list):
        raise BoardError('invalid-board')
    ids, keys, claims = set(), set(), []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise BoardError('invalid-board')
        if (not valid_key(entry['run_id']) or not valid_key(entry['task_key'])
                or entry['source'] not in ('manual', 'cron')):
            raise BoardError('invalid-board')
        try:
            stamp = datetime.fromisoformat(entry['started_at'])
        except (ValueError, TypeError):
            raise BoardError('invalid-board') from None
        if stamp.tzinfo is None:
            raise BoardError('invalid-board')
        paths = entry['working_files']
        if (not isinstance(paths, list) or not all(valid_path(p) for p in paths)
                or len(set(paths)) != len(paths)):
            raise BoardError('invalid-board')
        if entry['run_id'] in ids or entry['task_key'] in keys:
            raise BoardError('invalid-board')
        if any(overlaps(path, claimed) for path in paths for claimed in claims):
            raise BoardError('invalid-board')
        ids.add(entry['run_id'])
        keys.add(entry['task_key'])
        claims.extend(paths)


def parse_state(text):
    matches = list(STATE.finditer(text))
    if len(matches) != 1:
        raise BoardError('invalid-board')
    match = matches[0]
    try:
        entries = json.loads(match.group(1))
    except ValueError:
        raise BoardError('invalid-board') from None
    validate(entries)
    return match, entries


class Board:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.path = self.root / 'BOARD.md'

    def _read(self):
        if self.path.is_symlink():
            raise BoardError('invalid-board')
        text = self.path.read_text(encoding='utf-8')
        match, entries = parse_state(text)
        return text, match, entries

    @contextmanager
    def _lock(self):
        scratch = self.root / 'tmp'
        if scratch.is_symlink():
            raise BoardError('invalid-lock')
        scratch.mkdir(exist_ok=True)
        lock_path = scratch / '.noma-board.lock'
        if lock_path.is_symlink():
            raise BoardError('invalid-lock')
        # Never unlink this file: replacing its inode would split the lock domain.
        with lock_path.open('a+b') as handle:
            deadline = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise BoardError('busy') from None
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _write(self, text, match, entries):
        validate(entries)
        state = json.dumps(entries, ensure_ascii=False, indent=2)
        content = text[:match.start(1)] + state + text[match.end(1):]
        if content == text:
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.root, prefix='.noma-board-',
                                             suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def status(self):
        # Atomic publication makes reads safe without creating any local state.
        entries = self._read()[2]
        return {'status': 'ok', 'runs': [
            {key: entry[key] for key in ('run_id', 'task_key', 'working_files')}
            for entry in entries]}

    def change(self, action, *, run_id=None, task_key=None, source='manual', paths=()):
        if action not in ('begin', 'claim', 'release', 'finish'):
            raise BoardError('invalid-action')
        if action == 'begin' and run_id is None:
            run_id = 'run-' + uuid.uuid4().hex
        if not valid_key(run_id):
            raise BoardError('invalid-run-id')
        if action == 'begin' and (not valid_key(task_key) or source not in ('manual', 'cron')):
            raise BoardError('invalid-task')
        if action in ('claim', 'release') and (not paths or not all(valid_path(p) for p in paths)):
            raise BoardError('invalid-path')
        if action == 'claim':
            for path in paths:
                target = self.root / path
                if any(p.is_symlink() for p in (target, *target.parents) if p != self.root):
                    raise BoardError('symlink-path')
        with self._lock():
            text, match, entries = self._read()
            own = next((e for e in entries if e['run_id'] == run_id), None)
            if action == 'begin':
                if own:
                    if own['task_key'] != task_key or own['source'] != source:
                        raise BoardError('run-mismatch')
                    return {'status': 'already-active', 'run_id': run_id}
                duplicate = next((e for e in entries if e['task_key'] == task_key), None)
                if duplicate:
                    return {'status': 'duplicate', 'run_id': duplicate['run_id']}
                entries.append({'run_id': run_id, 'task_key': task_key, 'source': source,
                                'started_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                                'working_files': []})
                status = 'started'
            elif action == 'finish':
                if own is None:
                    return {'status': 'already-finished', 'run_id': run_id}
                entries.remove(own)
                status = 'finished'
            else:
                if own is None:
                    raise BoardError('unknown-run')
                if action == 'claim':
                    conflicts = sorted({p for p in paths for e in entries if e is not own
                                        for other in e['working_files'] if overlaps(p, other)})
                    if conflicts:
                        return {'status': 'conflict', 'paths': conflicts}
                    own['working_files'] = sorted(set(own['working_files']).union(paths))
                    status = 'claimed'
                else:
                    own['working_files'] = [p for p in own['working_files'] if p not in paths]
                    status = 'released'
            self._write(text, match, entries)
            return {'status': status, 'run_id': run_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('status', help='read state without writing files')
    begin = commands.add_parser('begin', help='atomically check and register a task')
    begin.add_argument('task_key')
    begin.add_argument('--run-id', help='reuse only to resume your own registered run')
    begin.add_argument('--source', choices=('manual', 'cron'), default='manual')
    for action in ('claim', 'release'):
        command = commands.add_parser(action)
        command.add_argument('run_id')
        command.add_argument('paths', nargs='+', help='repo-relative paths; directories include descendants')
    finish = commands.add_parser('finish', help='remove only the specified run; leave worktree untouched')
    finish.add_argument('run_id')
    args = vars(parser.parse_args())
    action = args.pop('action')
    try:
        board = Board()
        result = board.status() if action == 'status' else board.change(action, **args)
    except BoardError as exc:
        result = {'status': 'busy' if str(exc) == 'busy' else 'error', 'rule': str(exc)}
    except (OSError, UnicodeError):
        result = {'status': 'error', 'rule': 'board-io'}
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] == 'error':
        return 2
    return 3 if result['status'] in ('duplicate', 'conflict', 'busy') else 0


if __name__ == '__main__':
    sys.exit(main())
