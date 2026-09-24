"""Sentetik Noma regresyonları; gerçek wiki/raw/log verisine yazmaz."""
import concurrent.futures
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import noma_hermes_context as context
import noma_ingest as ingest
import noma_lib as lib
import noma_new_note as new_note


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-guardrails-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def test_concurrent_ingest_never_replaces_raw(self):
        with mock.patch.object(lib, 'ROOT', self.root):
            for kind in ('inbox', 'clippings'):
                with self.subTest(kind=kind):
                    barrier = threading.Barrier(12)

                    def create(i):
                        barrier.wait(timeout=10)
                        return ingest.write_raw(kind, 'same.md', f'fixture-{i}'.encode())

                    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                        paths = list(pool.map(create, range(12)))
                    self.assertEqual(12, len(set(paths)))
                    self.assertEqual({f'fixture-{i}'.encode() for i in range(12)},
                                     {p.read_bytes() for p in paths})

    def test_existing_wiki_note_is_never_overwritten(self):
        note = self.root / 'wiki' / 'fixture.md'
        note.parent.mkdir(parents=True)
        original = b'---\nlocked: true\n---\nfixture only\n'
        note.write_bytes(original)
        with mock.patch.object(lib, 'ROOT', self.root), mock.patch(
                'sys.argv', ['noma_new_note.py', 'fixture']):
            with self.assertRaises(SystemExit):
                new_note.main()
        self.assertEqual(original, note.read_bytes())

    def test_bad_log_diagnostics_do_not_reveal_content(self):
        log = self.root / 'synthetic-log.md'
        log.write_text('# sentetik\nprivate SENTINEL_PRIVATE_VALUE\n'
                       '12:30 query @local openai/gpt-6-sol | geçerli\n'
                       '12:31 query @local | ' + 'x' * 121 + '\n', encoding='utf-8')
        issues = list(lib.log_issues(log))
        self.assertEqual([('LOGF', 2), ('LOGB', 4)], issues)
        self.assertNotIn('SENTINEL_PRIVATE_VALUE', str(issues))

    def test_same_day_edit_requires_updated_bump(self):
        original = ('---\ntitle: "fixture"\nupdated: 2026-09-24T08:00:00+03:00\n'
                    '---\n# fixture\n')
        edited = original + 'new body\n'
        self.assertTrue(lib.needs_updated_bump(edited, original))
        bumped = edited.replace('08:00:00', '08:01:00')
        self.assertFalse(lib.needs_updated_bump(bumped, original))

    def test_locked_index_does_not_enable_local_context(self):
        index = self.root / 'index.md'
        index.write_bytes(b'\x00GITCRYPT\x00synthetic')
        with mock.patch.object(context.Path, 'cwd', return_value=self.root):
            self.assertFalse(context.unlocked_index({'cwd': str(self.root)}))
            index.write_text('# synthetic index', encoding='utf-8')
            self.assertTrue(context.unlocked_index({'cwd': str(self.root)}))
        self.assertNotIn('## Summary', context.LOCAL_CONTEXT + context.RESTRICTED_CONTEXT)


if __name__ == '__main__':
    unittest.main()
