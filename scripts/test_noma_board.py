"""Synthetic process-level coordination tests; never touch the real board or Git."""
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
import fcntl
import io
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import noma_board as board
import noma_lint as lint

EMPTY = '# Board\n\nKeep this instruction.\n\n```json\n[]\n```\n'


def worker(root, barrier, action, kwargs):
    barrier.wait(timeout=20)
    return board.Board(root).change(action, **kwargs)


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-board-', dir=board.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / 'BOARD.md'
        self.path.write_text(EMPTY, encoding='utf-8')
        self.board = board.Board(self.root)

    def begin(self, run='owner', task='fixture'):
        return self.board.change('begin', run_id=run, task_key=task)

    def race(self, jobs):
        # Independent processes prove the filesystem lock, not a Python thread lock.
        context = multiprocessing.get_context('spawn')
        with context.Manager() as manager:
            barrier = manager.Barrier(len(jobs))
            with ProcessPoolExecutor(max_workers=len(jobs), mp_context=context) as pool:
                futures = [pool.submit(worker, str(self.root), barrier, action, kwargs)
                           for action, kwargs in jobs]
                return [future.result(timeout=30) for future in futures]

    def test_status_is_read_only(self):
        before = self.path.stat().st_mtime_ns
        self.assertEqual({'status': 'ok', 'runs': []}, self.board.status())
        self.assertEqual(before, self.path.stat().st_mtime_ns)
        self.assertEqual(['BOARD.md'], sorted(p.name for p in self.root.iterdir()))

    def test_duplicate_task_has_exactly_one_winner(self):
        results = self.race([('begin', {'task_key': 'same-task'}) for _ in range(6)])
        self.assertEqual(1, sum(r['status'] == 'started' for r in results))
        self.assertEqual(5, sum(r['status'] == 'duplicate' for r in results))
        self.assertEqual(1, len(self.board.status()['runs']))

    def test_parallel_distinct_tasks_do_not_lose_entries(self):
        results = self.race([('begin', {'task_key': f'task-{i}'}) for i in range(6)])
        self.assertTrue(all(r['status'] == 'started' for r in results))
        self.assertEqual(6, len(self.board.status()['runs']))

    def test_competing_claims_have_one_winner(self):
        self.begin('first', 'first-task')
        self.begin('second', 'second-task')
        results = self.race([('claim', {'run_id': run, 'paths': ['scripts/fixture.py']})
                             for run in ('first', 'second')])
        self.assertEqual(['claimed', 'conflict'], sorted(r['status'] for r in results))
        self.assertEqual(1, sum(bool(e['working_files']) for e in self.board.status()['runs']))

    def test_disjoint_claims_and_finish_preserve_other_work(self):
        self.begin('first', 'first-task')
        self.begin('second', 'second-task')
        results = self.race([('claim', {'run_id': run, 'paths': [f'{run}.md']})
                             for run in ('first', 'second')])
        self.assertTrue(all(r['status'] == 'claimed' for r in results))
        other = self.board.status()['runs'][1]
        content = self.root / 'first.md'
        content.write_text('unfinished or completed work', encoding='utf-8')
        self.assertEqual('finished', self.board.change('finish', run_id='first')['status'])
        self.assertEqual([other], self.board.status()['runs'])
        self.assertEqual('unfinished or completed work', content.read_text(encoding='utf-8'))
        self.assertEqual('already-finished', self.board.change('finish', run_id='first')['status'])
        self.board.change('finish', run_id='second')
        self.assertEqual(EMPTY, self.path.read_text(encoding='utf-8'))

    def test_resume_is_idempotent_and_cannot_change_task(self):
        self.begin()
        before = self.path.read_bytes()
        self.assertEqual('already-active', self.begin()['status'])
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaisesRegex(board.BoardError, 'run-mismatch'):
            self.begin(task='different')

    def test_directory_claim_conflicts_in_both_directions_and_batch_is_atomic(self):
        self.begin('first', 'first-task')
        self.begin('second', 'second-task')
        self.board.change('claim', run_id='first', paths=['index/hubs/'])
        before = self.path.read_bytes()
        for paths in (['index/hubs/fixture/000001.md', 'free.md'], ['index/']):
            self.assertEqual('conflict', self.board.change('claim', run_id='second', paths=paths)['status'])
            self.assertEqual(before, self.path.read_bytes())
        self.board.change('release', run_id='first', paths=['index/hubs/'])
        self.assertEqual('claimed', self.board.change('claim', run_id='second', paths=['index/'])['status'])

    def test_unknown_run_cannot_claim_or_release(self):
        for action in ('claim', 'release'):
            with self.assertRaisesRegex(board.BoardError, 'unknown-run'):
                self.board.change(action, run_id='unknown', paths=['fixture.md'])

    def test_invalid_paths_and_symlink_aliases_are_rejected(self):
        self.begin()
        for path in ('../outside', '/absolute', '.', './file', 'a/../b', 'a//b',
                     'a\\b', 'a//', 'BOARD.md', '.git/index', 'tmp/fixture', 'a\nb'):
            with self.subTest(path=path), self.assertRaisesRegex(board.BoardError, 'invalid-path'):
                self.board.change('claim', run_id='owner', paths=[path])
        (self.root / 'alias').symlink_to(self.root / 'target', target_is_directory=True)
        with self.assertRaisesRegex(board.BoardError, 'symlink-path'):
            self.board.change('claim', run_id='owner', paths=['alias/file.md'])

    def test_corrupt_board_is_preserved_and_diagnostics_hide_contents(self):
        for state in ('SENTINEL_PRIVATE_VALUE', '{"unexpected": "SENTINEL_PRIVATE_VALUE"}',
                      '[{"run_id": "SENTINEL_PRIVATE_VALUE"}]'):
            self.path.write_text(EMPTY.replace('[]', state), encoding='utf-8')
            before = self.path.read_bytes()
            output = io.StringIO()
            with mock.patch.object(board, 'Board', return_value=self.board), mock.patch(
                    'sys.argv', ['noma_board.py', 'begin', 'fixture']), redirect_stdout(output):
                self.assertEqual(2, board.main())
            self.assertEqual('invalid-board', json.loads(output.getvalue())['rule'])
            self.assertNotIn('SENTINEL_PRIVATE_VALUE', output.getvalue())
            self.assertEqual(before, self.path.read_bytes())

    def test_old_entry_is_not_automatically_removed(self):
        self.begin()
        text, match, entries = self.board._read()
        entries[0]['started_at'] = '2000-01-01T00:00:00+00:00'
        self.board._write(text, match, entries)
        self.assertEqual('duplicate', self.begin('other')['status'])
        self.assertEqual(1, len(self.board.status()['runs']))

    def test_failed_publication_preserves_state_and_releases_lock(self):
        with mock.patch.object(board.os, 'replace', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                self.begin()
        self.assertEqual(EMPTY, self.path.read_text(encoding='utf-8'))
        self.assertEqual([], list(self.root.glob('.noma-board-*.tmp')))
        self.assertEqual('started', self.begin()['status'])

    def test_lock_wait_is_bounded(self):
        scratch = self.root / 'tmp'
        scratch.mkdir()
        with (scratch / '.noma-board.lock').open('a+b') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            with mock.patch.object(board, 'LOCK_TIMEOUT', 0):
                with self.assertRaisesRegex(board.BoardError, 'busy'):
                    self.begin()
        self.assertEqual('started', self.begin()['status'])

    def test_cli_exit_codes_distinguish_conflict_from_error(self):
        self.begin()
        for args, code, status in ((['begin', 'fixture'], 3, 'duplicate'),
                                   (['claim', 'missing', 'fixture.md'], 2, 'error'),
                                   (['finish', 'owner'], 0, 'finished')):
            with mock.patch.object(board, 'Board', return_value=self.board), mock.patch(
                    'sys.argv', ['noma_board.py', *args]), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(code, board.main())
            self.assertEqual(status, json.loads(output.getvalue())['status'])

    def lint_board(self, staged, head=b'legacy board'):
        with mock.patch.object(lint, 'ROOT', self.root), mock.patch.object(
                lint, '_staged_payload', return_value=staged), mock.patch.object(
                lint, '_head_payload', return_value=head), mock.patch.object(lint, 'add') as add:
            lint.check_board()
        return add.call_args_list

    def test_lint_rejects_staged_active_runs_but_accepts_local_work(self):
        self.begin()
        active = self.path.read_bytes()
        self.assertEqual([], self.lint_board(EMPTY.encode()))
        findings = self.lint_board(active)
        self.assertEqual(1, len(findings))
        self.assertEqual(('ERR', 'BOARD'), findings[0].args[:2])
        self.assertIn('active runs', findings[0].args[2])

    def test_lint_rejects_invalid_local_and_staged_state_without_contents(self):
        self.path.write_text('SENTINEL_PRIVATE_VALUE', encoding='utf-8')
        findings = self.lint_board(b'SENTINEL_PRIVATE_VALUE')
        self.assertEqual(2, len(findings))
        self.assertNotIn('SENTINEL_PRIVATE_VALUE', str(findings))

    def test_lint_allows_unchanged_legacy_index_during_migration(self):
        self.assertEqual([], self.lint_board(b'legacy board', head=b'legacy board'))

    def test_lint_rejects_staged_deletion_or_unreadable_board(self):
        for staged in (None, lint.UNREADABLE):
            self.assertEqual(1, len(self.lint_board(staged)))


if __name__ == '__main__':
    unittest.main()
