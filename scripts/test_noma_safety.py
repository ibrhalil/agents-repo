"""Güvenlik regresyonları: şifreli kasa, atomik raw yazımı, aktör dürüstlüğü,
kurulum betiği. Hiçbir test gerçek wiki/raw/log/.env verisine dokunmaz."""
import concurrent.futures
import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import noma_hermes_context as context
import noma_ingest as ingest
import noma_lib as lib
import noma_new_note as new_note
import noma_tend_report as tend

SENTINEL_TEMPLATE = (
    '---\ntitle: "{{Tam Başlık}}"\ncreated: {{YYYY-MM-DDTHH:mm:ss+ZZ:ZZ}}\n'
    'updated: {{YYYY-MM-DDTHH:mm:ss+ZZ:ZZ}}\n---\n# {{Görünen Başlık}}\n'
    '## Links\n`[[ust-not]]`\n## Summary\nÖzet.\n## Body\nGövde.\n')
SENTINEL_ENV = ('# şablon\nNODE_ID=hermes # düğüm kimliği\n'
                 'ANTHROPIC_API_KEY=\nOPENAI_API_KEY=\n')


def make_note(path, title, *, parents=(), stage='done', updated='2026-09-25T00:00:00+03:00'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: concept\nstage: {stage}\nscope: systems\n'
        f'status: established\ncreated: 2026-09-25T00:00:00+03:00\n'
        f'updated: {updated}\n---\n# {title}\n## Links\n'
        + ''.join(f'[[{p}]]\n' for p in parents)
        + '## Summary\nÖzet.\n', encoding='utf-8')


class SyntheticNode(unittest.TestCase):
    """tmp/ altında sahte bir düğüm kökü: wiki, raw, log, şablon."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-safety-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        (self.root / 'log').mkdir()
        (self.root / 'raw' / 'inbox').mkdir(parents=True)
        (self.root / 'wiki').mkdir()
        tpl = self.root / 'docs' / 'templates' / 'wiki_note.md'
        tpl.parent.mkdir(parents=True)
        tpl.write_text(SENTINEL_TEMPLATE, encoding='utf-8')
        self.source = self.root / 'kaynak.txt'
        self.source.write_text('sentetik ham içerik', encoding='utf-8')

    def raw_files(self):
        return sorted(p.name for p in (self.root / 'raw').rglob('*') if p.is_file())

    def staging_leftovers(self):
        return sorted(p.name for p in (self.root / 'tmp').rglob('*') if p.is_file())


class RawAtomicityTests(SyntheticNode):
    def test_disk_full_write_leaves_raw_untouched(self):
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('os.fsync', side_effect=OSError('disk dolu')):
            with self.assertRaises(OSError):
                ingest.write_raw('inbox', 'kaynak.txt', b'x' * 512)
        self.assertEqual([], self.raw_files())
        self.assertEqual([], self.staging_leftovers())

    def test_short_write_is_never_published(self):
        real_fsync = os.fsync
        staging = self.root / 'tmp'

        def truncating_fsync(fd):
            victim = next(p for p in staging.rglob('*') if p.is_file())
            os.truncate(victim, max(victim.stat().st_size // 2, 1))
            return real_fsync(fd)

        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('os.fsync', truncating_fsync):
            with self.assertRaises(OSError):
                ingest.write_raw('inbox', 'kaynak.txt', b'y' * 512)
        self.assertEqual([], self.raw_files())
        self.assertEqual([], self.staging_leftovers())

    def test_existing_raw_file_is_never_replaced(self):
        keeper = self.root / 'raw' / 'inbox' / 'kaynak.txt'
        keeper.write_bytes(b'onceki kaynak')
        with mock.patch.object(lib, 'ROOT', self.root):
            p = ingest.write_raw('inbox', 'kaynak.txt', b'yeni kaynak')
        self.assertNotEqual(keeper, p)
        self.assertEqual(b'onceki kaynak', keeper.read_bytes())
        self.assertEqual(b'yeni kaynak', p.read_bytes())
        self.assertEqual([], self.staging_leftovers())

    def test_concurrent_writes_get_distinct_complete_files(self):
        barrier = threading.Barrier(8)

        def create(i):
            barrier.wait(timeout=10)
            return ingest.write_raw('inbox', 'kaynak.txt', f'girdi-{i}'.encode())

        with mock.patch.object(lib, 'ROOT', self.root):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                paths = list(pool.map(create, range(8)))
        self.assertEqual(8, len(set(paths)))
        self.assertEqual({f'girdi-{i}'.encode() for i in range(8)},
                         {p.read_bytes() for p in paths})
        self.assertEqual(8, len(self.raw_files()))
        self.assertEqual([], self.staging_leftovers())


class IngestExitCodeTests(SyntheticNode):
    def run_ingest(self, *args):
        out = io.StringIO()
        argv = ['noma_ingest.py', str(self.source), *args]
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', argv), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            code = ingest.main()
        return code, out.getvalue()

    def logged(self):
        return (self.root / 'log' / f'{lib.today()}.md').read_text(encoding='utf-8')

    def test_verify_failure_exits_nonzero(self):
        with mock.patch.object(ingest, 'verify_text', return_value=(['FM:title'], [])):
            code, _ = self.run_ingest('--slug', 'kotu-not', '--actor', 'K')
        self.assertEqual(1, code)
        self.assertIn('[verify-fail]', self.logged())

    def test_clean_run_exits_zero(self):
        code, _ = self.run_ingest('--slug', 'iyi-not', '--actor', 'K')
        self.assertEqual(0, code)
        self.assertNotIn('[verify-fail]', self.logged())
        self.assertEqual([], list(lib.log_issues(self.root / 'log' / f'{lib.today()}.md')))

    def test_warning_only_run_exits_zero(self):
        with mock.patch.object(ingest, 'verify_text', return_value=([], ['NO-HUB'])):
            code, _ = self.run_ingest('--slug', 'uyari-not', '--actor', 'K')
        self.assertEqual(0, code)

    def test_completed_stage_skeleton_is_refused_upfront(self):
        for stage in ('done', 'archived'):
            with self.subTest(stage=stage):
                with self.assertRaises(SystemExit) as err:
                    self.run_ingest('--slug', 'bitmis-not', '--stage', stage, '--actor', 'K')
                self.assertIn('done/archived olamaz', str(err.exception))
        self.assertEqual([], self.raw_files())
        self.assertFalse((self.root / 'wiki' / 'bitmis-not.md').exists())

    def test_invalid_slug_fails_before_any_raw_write(self):
        """Kırmızı kanıt: slug ham kopyadan SONRA doğrulanırdı; artık önce."""
        with mock.patch.object(ingest, 'write_raw',
                               side_effect=AssertionError('write_raw erken çağrıldı')):
            with self.assertRaises(SystemExit):
                self.run_ingest('--slug', 'Geçersiz Slug', '--actor', 'K')
        self.assertEqual([], self.raw_files())

    def test_render_failure_leaves_no_partial_note(self):
        with mock.patch.object(lib, 'render_note', side_effect=OSError('şablon okunamadı')):
            with self.assertRaises(OSError):
                self.run_ingest('--slug', 'bos-not', '--actor', 'K')
        self.assertFalse((self.root / 'wiki' / 'bos-not.md').exists())

    def test_verify_failed_note_is_written_as_inbox(self):
        # Şablon Links bölümü kod aralığında: hedef yok → hata değil NO-HUB uyarısı;
        # hata yolunu sentetik kırık hedefle zorla.
        broken = SENTINEL_TEMPLATE.replace('`[[ust-not]]`', '[[yok-hedef]]')
        (self.root / 'docs' / 'templates' / 'wiki_note.md').write_text(broken,
                                                                       encoding='utf-8')
        code, _ = self.run_ingest('--slug', 'kirik-not', '--stage', 'next', '--actor', 'K')
        self.assertEqual(1, code)
        note = self.root / 'wiki' / 'kirik-not.md'
        self.assertTrue(note.exists())
        self.assertIn('stage: inbox', note.read_text(encoding='utf-8'))
        self.assertIn('[verify-fail]', self.logged())

    def test_new_note_refuses_completed_stage(self):
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', ['noma_new_note.py', 'bitmis',
                                        '--stage', 'done']):
            with self.assertRaises(SystemExit) as err:
                new_note.main()
        self.assertIn('done/archived olamaz', str(err.exception))
        self.assertFalse((self.root / 'wiki' / 'bitmis.md').exists())

    def test_render_note_escapes_title_for_yaml(self):
        content = lib.render_note('kacis-not', 'C:\\q "tırnak" ve\nyeni satır',
                                  'concept', 'systems')
        fm = content.split('\n---', 1)[0]
        title_line = next(l for l in fm.splitlines() if l.startswith('title:'))
        raw = title_line[len('title: '):]
        self.assertEqual('C:\\q "tırnak" ve yeni satır', json.loads(raw))
        self.assertNotIn('\n', raw)


class ActorProvenanceTests(SyntheticNode):
    """SCHEMA §5: aktör gerçek session modeli | K | cron — varsayılan 'cron' DEĞİLDİR."""

    def without_actor_env(self):
        env = {k: v for k, v in os.environ.items() if k != 'NOMA_ACTOR'}
        return mock.patch.dict(os.environ, env, clear=True)

    def test_missing_actor_names_both_options(self):
        with self.without_actor_env():
            with self.assertRaises(SystemExit) as err:
                lib.resolve_actor(None)
        message = str(err.exception)
        self.assertIn('--actor', message)
        self.assertIn('NOMA_ACTOR', message)
        self.assertNotIn('cron', message)

    def test_env_actor_is_used_and_explicit_actor_wins(self):
        with mock.patch.dict(os.environ, {'NOMA_ACTOR': 'some/model'}):
            self.assertEqual('some/model', lib.resolve_actor(None))
            self.assertEqual('K', lib.resolve_actor('K'))

    def test_scripts_never_default_to_cron(self):
        for name in ('noma_ingest.py', 'noma_new_note.py', 'noma_tend_report.py'):
            with self.subTest(script=name):
                source = (lib.ROOT / 'scripts' / name).read_text(encoding='utf-8')
                self.assertNotIn("default='cron'", source)
                self.assertNotIn('default="cron"', source)

    def test_ingest_without_actor_writes_nothing(self):
        argv = ['noma_ingest.py', str(self.source), '--slug', 'aktorsuz']
        with self.without_actor_env(), mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', argv), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ingest.main()
        self.assertEqual([], self.raw_files())
        self.assertEqual([], sorted(p.name for p in (self.root / 'log').iterdir()))

    def test_ingest_logs_env_actor(self):
        argv = ['noma_ingest.py', str(self.source), '--slug', 'env-aktor', '--actor', 'some/model']
        with mock.patch.dict(os.environ, {'NOMA_ACTOR': 'some/model'}), \
                mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', argv), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, ingest.main())
        logged = (self.root / 'log' / f'{lib.today()}.md').read_text(encoding='utf-8')
        self.assertIn(' some/model | ', logged)
        self.assertNotIn(' cron | ', logged)

    def test_new_note_and_tend_require_actor_only_when_logging(self):
        with self.without_actor_env(), mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', ['noma_new_note.py', 'aktorsuz-not', '--log-op', 'tend']), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                new_note.main()
        self.assertFalse((self.root / 'wiki' / 'aktorsuz-not.md').exists())
        with self.without_actor_env(), mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', ['noma_tend_report.py', '--no-log', '--json']), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, tend.main())


class TendHubPageTests(SyntheticNode):
    def findings(self, slug):
        with mock.patch.object(lib, 'ROOT', self.root):
            idx = lib.load_wiki_index()
        results, summary = tend.collect(idx)
        return [f for f in results if f['kind'] == 'HUB-FULL'], summary

    def test_paged_hub_with_subhub_is_not_hub_full(self):
        for i in range(39):
            make_note(self.root / 'wiki' / f'yaprak-{i:02d}.md', f'Yaprak {i}',
                      parents=('dev-hub',))
        make_note(self.root / 'wiki' / 'alt-hub.md', 'Alt Hub', parents=('dev-hub',))
        make_note(self.root / 'wiki' / 'alt-yaprak.md', 'Alt Yaprak', parents=('alt-hub',))
        make_note(self.root / 'wiki' / 'dev-hub.md', 'Dev Hub')
        hubs, summary = self.findings('dev-hub')
        self.assertEqual([], hubs)
        self.assertEqual(0, summary['HUB-FULL'])

    def test_paged_hub_without_subhub_is_hub_full(self):
        for i in range(40):
            make_note(self.root / 'wiki' / f'yaprak-{i:02d}.md', f'Yaprak {i}',
                      parents=('dev-hub',))
        make_note(self.root / 'wiki' / 'dev-hub.md', 'Dev Hub')
        hubs, summary = self.findings('dev-hub')
        self.assertEqual(1, len(hubs))
        self.assertEqual('dev-hub', hubs[0]['slug'])
        self.assertEqual(40, hubs[0]['measure'])
        self.assertEqual(2, hubs[0]['pages'])
        self.assertEqual(1, summary['HUB-FULL'])

    def test_hub_within_page_size_is_never_flagged(self):
        for i in range(32):
            make_note(self.root / 'wiki' / f'yaprak-{i:02d}.md', f'Yaprak {i}',
                      parents=('dev-hub',))
        make_note(self.root / 'wiki' / 'dev-hub.md', 'Dev Hub')
        hubs, _ = self.findings('dev-hub')
        self.assertEqual([], hubs)

    def test_json_keys_stay_compatible(self):
        make_note(self.root / 'wiki' / 'tek.md', 'Tek Not')
        out = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', ['noma_tend_report.py', '--json', '--no-log']), \
                contextlib.redirect_stdout(out):
            self.assertEqual(0, tend.main())
        payload = json.loads(out.getvalue())
        self.assertEqual(['findings', 'summary'], sorted(payload))
        self.assertEqual(['HUB-FULL', 'INBOX', 'NO-HUB', 'STALE'],
                         sorted(payload['summary']))
        for finding in payload['findings']:
            self.assertLessEqual({'kind', 'slug', 'measure'}, set(finding))


class BootstrapScriptTests(SyntheticNode):
    """noma-bootstrap.sh kendi konumundan ROOT türetir: sentetik düğüm ağacına kopyalanır."""

    def setUp(self):
        super().setUp()
        self.node = self.root / 'node'
        (self.node / 'scripts').mkdir(parents=True)
        (self.node / '.git').mkdir()
        (self.node / 'raw' / 'inbox').mkdir(parents=True)
        (self.node / 'wiki').mkdir()
        (self.node / 'index.md').write_text('# sentetik\n', encoding='utf-8')
        (self.node / '.env.example').write_text(SENTINEL_ENV, encoding='utf-8')
        script = self.node / 'scripts' / 'noma-bootstrap.sh'
        shutil.copy2(lib.ROOT / 'scripts' / 'noma-bootstrap.sh', script)
        self.script = script

    def bootstrap(self, node_id='test-node'):
        return subprocess.run(['bash', str(self.script), '--id', node_id],
                              capture_output=True, text=True)

    def test_locked_fixture_aborts_before_creating_env(self):
        (self.node / 'wiki' / 'not.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        result = self.bootstrap()
        self.assertNotEqual(0, result.returncode, result.stderr)
        self.assertIn('kilitli', result.stderr)
        self.assertFalse((self.node / '.env').exists())

    def test_unlocked_fixture_creates_private_env_with_node_id(self):
        (self.node / 'wiki' / 'not.md').write_text('# sentetik\n', encoding='utf-8')
        result = self.bootstrap()
        self.assertEqual(0, result.returncode, result.stderr)
        env = self.node / '.env'
        self.assertEqual(0o600, stat.S_IMODE(env.stat().st_mode))
        text = env.read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^NODE_ID=test-node(\s|$)')
        self.assertNotIn('NODE_ID=hermes', text)
        self.assertIn('ANTHROPIC_API_KEY', text)

    def test_renamed_node_id_literal_still_rewrites(self):
        """Eski replace('NODE_ID=hermes') sessizce no-op olurdu; satır eşlemesi dayanıklı."""
        (self.node / '.env.example').write_text(
            SENTINEL_ENV.replace('NODE_ID=hermes', 'export NODE_ID="taslak"'),
            encoding='utf-8')
        self.assertEqual(0, self.bootstrap('ev').returncode)
        self.assertRegex((self.node / '.env').read_text(encoding='utf-8'),
                         r'(?m)^export NODE_ID=ev(\s|$)')

    def test_missing_node_id_line_fails_loudly(self):
        (self.node / '.env.example').write_text('# NODE_ID yok\nAPI=x\n', encoding='utf-8')
        result = self.bootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('NODE_ID', result.stderr)
        self.assertNotIn('oluşturuldu', result.stdout)


class HermesHookTests(SyntheticNode):
    def setUp(self):
        super().setUp()
        (self.root / 'index.md').write_text('# sentetik\n', encoding='utf-8')

    def hook(self, payload):
        out = io.StringIO()
        with mock.patch.object(context, 'SCRIPT_ROOT', self.root), \
                mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                contextlib.redirect_stdout(out):
            code = context.main()
        return code, json.loads(out.getvalue())['context']

    def test_plain_index_with_encrypted_wiki_is_restricted(self):
        (self.root / 'wiki' / 'not.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        code, text = self.hook({'cwd': str(self.root)})
        self.assertEqual(0, code)
        self.assertEqual(context.RESTRICTED_CONTEXT, text)

    def test_partially_locked_wiki_is_restricted(self):
        """Kırmızı kanıt: ilk dosya düz olsa bile tek şifreli not LOCAL açmaz."""
        (self.root / 'wiki' / 'aaa-duz.md').write_text('# duz\n', encoding='utf-8')
        (self.root / 'wiki' / 'zzz-sifreli.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        code, text = self.hook({'cwd': str(self.root)})
        self.assertEqual(0, code)
        self.assertEqual(context.RESTRICTED_CONTEXT, text)

    def test_payload_cwd_cannot_forge_local_branch(self):
        (self.root / 'wiki' / 'not.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        forged = self.root / 'sahte'
        (forged / 'wiki').mkdir(parents=True)
        (forged / 'index.md').write_text('# sahte\n', encoding='utf-8')
        (forged / 'wiki' / 'not.md').write_text('# sahte\n', encoding='utf-8')
        code, text = self.hook({'cwd': str(forged)})
        self.assertEqual(0, code)
        self.assertEqual(context.RESTRICTED_CONTEXT, text)

    def test_unlocked_vault_keeps_local_branch(self):
        (self.root / 'wiki' / 'not.md').write_text('# sentetik\n', encoding='utf-8')
        code, text = self.hook({'cwd': str(self.root)})
        self.assertEqual(0, code)
        self.assertEqual(context.LOCAL_CONTEXT, text)

    def test_tty_and_broken_payload_exit_zero(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

            def read(self, *args):
                raise AssertionError('TTY akışı okunmamalı')

        with mock.patch.object(context, 'SCRIPT_ROOT', self.root), \
                mock.patch('sys.stdin', Tty()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual({}, context.read_payload())
        for payload in ('', '{bozuk', '[]', 'null'):
            out = io.StringIO()
            with mock.patch.object(context, 'SCRIPT_ROOT', self.root), \
                    mock.patch('sys.stdin', io.StringIO(payload)), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(0, context.main())
            self.assertIn('context', json.loads(out.getvalue()))

    def test_unexpected_hook_error_falls_back_to_restricted(self):
        out = io.StringIO()
        with mock.patch.object(context, 'unlocked_index', side_effect=RuntimeError), \
                mock.patch('sys.stdin', io.StringIO('{}')), \
                contextlib.redirect_stdout(out):
            self.assertEqual(0, context.main())
        self.assertEqual(context.RESTRICTED_CONTEXT, json.loads(out.getvalue())['context'])
        self.assertNotIn('Traceback', out.getvalue())

    def test_hook_never_prints_note_body(self):
        (self.root / 'wiki' / 'not.md').write_text(
            '---\ntitle: "Gizli"\n---\n## Summary\nSENTINEL_PRIVATE_VALUE\n',
            encoding='utf-8')
        code, text = self.hook({'cwd': str(self.root)})
        self.assertEqual(0, code)
        self.assertNotIn('SENTINEL_PRIVATE_VALUE', text)


if __name__ == '__main__':
    unittest.main()
