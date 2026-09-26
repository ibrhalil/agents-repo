"""Yanıt doğrulama ve bakım raporu araçlarının sentetik regresyonları."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import noma_eval_context as ctx
import noma_eval_retrieval as evalr
import noma_lib as lib
import noma_tend_report as tend
import noma_verify_citations as verify

# tmp/ gitignore'lu olduğu için taze klonda yoktur; test geçici dizinleri için
# gereken üst dizin burada oluşturulur.
(lib.ROOT / 'tmp').mkdir(parents=True, exist_ok=True)


def make_note(path, title, *, parents=(), stage='done', status='established',
              updated='2026-09-25T00:00:00+03:00', summary='Özet.'):
    links = ', '.join(f'[[{p}]]' for p in parents)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: concept\nstage: {stage}\nscope: systems\n'
        f'status: {status}\ncreated: 2026-09-25T00:00:00+03:00\n'
        f'updated: {updated}\n---\n# {title}\n## Links\n{links}\n'
        f'## Summary\n{summary}\n', encoding='utf-8')


def eval_root(root):
    """ctx/evalr için sentetik wiki + plans/ kümesi."""
    (root / 'plans').mkdir()
    make_note(root / 'wiki' / 'a.md', 'Bağlam Yönetimi', summary='Karar bağlamı.')
    make_note(root / 'wiki' / 'b.md', 'Ağ Güvenliği', summary='Port güvenliği.')
    return root


class QualityToolTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-quality-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        (self.root / 'wiki').mkdir()

    def test_citation_verifier_paths_and_relevance(self):
        make_note(self.root / 'wiki' / 'hafiza.md', 'Hafıza Yönetimi',
                  summary='Hafıza karar altyapısıdır, kararlar versiyonlanır.')
        (self.root / 'raw').mkdir()
        (self.root / 'raw' / 'kaynak.md').write_text('kaynak', encoding='utf-8')
        text = ('Hafıza karar altyapısıdır (wiki/hafiza.md); ayrıca ham kaynak '
                'raw/kaynak.md ve kırık atıf wiki/yok-not.md ile turşu tarifi '
                'soyulmuş wiki/hafiza.md.')
        with mock.patch.object(lib, 'ROOT', self.root):
            findings, negative = verify.verify(text, idx={'hafiza': {'fm': {}}})
        by_path = {f['path']: f for f in findings}
        self.assertEqual('OK', by_path['wiki/hafiza.md']['status'])
        self.assertEqual('OK', by_path['raw/kaynak.md']['status'])
        self.assertEqual('FAIL', by_path['wiki/yok-not.md']['status'])
        self.assertFalse(negative)

    def test_citation_verifier_flags_unrelated_and_negative(self):
        make_note(self.root / 'wiki' / 'ag.md', 'Ağ Güvenliği',
                  summary='Portlar ve güvenlik duvarı ayarları.')
        text = ('Turşu tarifinin kökeni tartışmalıdır (wiki/ag.md). '
                'Bu bilgi wiki\'de kayıtlı değil gibi duruyor.')
        with mock.patch.object(lib, 'ROOT', self.root):
            findings, negative = verify.verify(text, idx={'ag': {'fm': {}}})
        self.assertEqual('WARN', findings[0]['status'])
        self.assertEqual('ilgisiz-atıf', findings[0]['rule'])
        self.assertTrue(negative)

    def test_citation_verifier_rejects_unrelated_citation(self):
        make_note(self.root / 'wiki' / 'ag.md', 'Ağ Güvenliği',
                  summary='Portlar ve güvenlik duvarı ayarları.')
        output = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch('sys.argv', ['noma_verify_citations.py', '--json']), \
                mock.patch('sys.stdin', io.StringIO('Turşu tarifi wiki/ag.md.')), \
                contextlib.redirect_stdout(output):
            self.assertEqual(1, verify.main())
        self.assertEqual(1, json.loads(output.getvalue())['warned'])

    def test_raw_citation_is_relevance_checked(self):
        (self.root / 'raw').mkdir()
        (self.root / 'raw' / 'kaynak.md').write_text('kaynak', encoding='utf-8')
        (self.root / 'raw' / 'deney.md').write_text('ölçüm', encoding='utf-8')
        text = ('Ağ güvenliği kaynağı raw/kaynak.md dosyasındadır. '
                'Turşu tarifi raw/deney.md dosyasındadır.')
        with mock.patch.object(lib, 'ROOT', self.root):
            findings, _ = verify.verify(text, idx={})
        by_path = {f['path']: f for f in findings}
        self.assertEqual('OK', by_path['raw/kaynak.md']['status'])
        self.assertEqual(('WARN', 'ilgisiz-atıf'),
                         (by_path['raw/deney.md']['status'], by_path['raw/deney.md']['rule']))

    def test_log_and_plans_citations_are_recognised(self):
        (self.root / 'log').mkdir()
        (self.root / 'plans').mkdir()
        (self.root / 'log' / '2026-09-25.md').write_text('# 2026-09-25\n', encoding='utf-8')
        (self.root / 'plans' / 'olcum.json').write_text('[]\n', encoding='utf-8')
        text = ('Günlük kaydı log/2026-09-25.md içinde, plan dosyası '
                'plans/olcum.json içindedir; eksik olan plans/yok.json dosyasıdır.')
        with mock.patch.object(lib, 'ROOT', self.root):
            findings, _ = verify.verify(text, idx={})
        by_path = {f['path']: f for f in findings}
        self.assertEqual('OK', by_path['log/2026-09-25.md']['status'])
        self.assertEqual('OK', by_path['plans/olcum.json']['status'])
        self.assertEqual('FAIL', by_path['plans/yok.json']['status'])

    def test_diagnostic_plan_write_is_atomic_and_needs_force(self):
        eval_root(self.root)
        (self.root / 'plans' / 'wiki-iliski-sorulari.json').write_text(
            json.dumps([{'id': 'c01', 'split': 'dev', 'query': 'baglam karar',
                         'required': ['a']}]), encoding='utf-8')
        diag = self.root / 'plans' / 'wiki-iliski-tanisi.json'
        diag.write_text('PRIVATE_PLAN_SENTINEL\n', encoding='utf-8')
        argv = ['noma_eval_context.py', '--diagnostic']
        error = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', argv), \
                contextlib.redirect_stderr(error):
            self.assertEqual(1, ctx.main())
        self.assertIn(ctx.DIAG_ERROR, error.getvalue())
        self.assertEqual('PRIVATE_PLAN_SENTINEL\n', diag.read_text(encoding='utf-8'))

        writes, replaces = [], []
        real_write, real_replace = Path.write_text, os.replace
        output = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', argv + ['--force']), \
                mock.patch.object(Path, 'write_text',
                                  lambda p, *a, **k: (writes.append(Path(p)),
                                                      real_write(p, *a, **k))[1]), \
                mock.patch.object(ctx.os, 'replace',
                                  lambda s, d: (replaces.append(d), real_replace(s, d))[1]), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, ctx.main())
        self.assertEqual([], [str(p) for p in writes if p == diag])
        self.assertIn(diag, replaces)
        self.assertFalse((diag.parent / (diag.name + '.tmp')).exists())
        self.assertNotIn('PRIVATE_PLAN_SENTINEL', diag.read_text(encoding='utf-8'))

    def test_plan_case_id_is_validated_before_printing(self):
        eval_root(self.root)
        make_note(self.root / 'wiki' / 'z.md', 'Büyüyen Kuyruk', summary='Kuyruk adayı.')
        cases = [{'id': 'c01', 'split': 'dev', 'query': 'baglam karar', 'required': ['a']},
                 {'id': 'wiki/gizli-PRIVATE.md', 'split': 'dev', 'query': 'ağ port',
                  'required': ['z']}]
        (self.root / 'plans' / 'wiki-iliski-sorulari.json').write_text(
            json.dumps(cases), encoding='utf-8')
        output = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', ['noma_eval_context.py']), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, ctx.main())
        printed = output.getvalue()
        self.assertNotIn('PRIVATE', printed)
        self.assertIn("eksik vaka: A=1 B=1", printed)
        (self.root / 'plans' / 'wiki-iliski-sorulari.json').write_text(
            json.dumps([cases[0]]), encoding='utf-8')
        output = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', ['noma_eval_context.py']), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, ctx.main())
        self.assertIn("· ID: A=[] B=[]", output.getvalue())

    def test_context_limit_slice_cannot_go_negative(self):
        def entry(slug, title, parents=()):
            return {'fm': {'title': title, 'scope': 'systems', 'status': 'established'},
                    'parents': list(parents), 'out': set(parents), 'tags': [],
                    'fields': {name: lib.fold_tr(v) for name, v in
                               {'slug': slug, 'title': title, 'tags': '',
                                'summary': '', 'body': ''}.items()}}
        idx = {'a': entry('a', 'Bağlam', parents=('focused', 'root')),
               'b': entry('b', 'Diğer', parents=('root',)),
               'c': entry('c', 'Başka', parents=('root',)),
               'd': entry('d', 'Yedek', parents=('root',)),
               'focused': entry('focused', 'Özel üst', parents=('root',)),
               'root': entry('root', 'Genel kök')}
        for slug in ('b', 'c', 'd'):
            idx[slug]['parents'].append('root')
        with mock.patch.object(ctx, 'CONTEXT_LIMIT', 2):
            selected = ctx.tree_context(idx, set(idx), ['a', 'b', 'c', 'd'],
                                        {'a': 30, 'b': 20, 'c': 10, 'd': 9})
        self.assertEqual(['a', 'b', 'focused'], selected)

    def test_retrieval_min_gate_signals_regression(self):
        eval_root(self.root)
        (self.root / 'plans' / 'wiki-erisim-sorgulari.json').write_text(
            json.dumps([{'query': 'ağ port', 'expect': 'b'},
                        {'query': 'bağlam', 'expect': 'a'},
                        {'query': 'bağlam', 'expect': 'b'}]), encoding='utf-8')
        for minimum, expected in (('0.0', 0), ('0.5', 0), ('0.8', 1)):
            error = io.StringIO()
            with mock.patch.object(lib, 'ROOT', self.root), \
                    mock.patch.object(sys, 'argv',
                                      ['noma_eval_retrieval.py', '--min', minimum]), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(error):
                self.assertEqual(expected, evalr.main(), minimum)
            if expected:
                self.assertIn('eşik', error.getvalue())
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', ['noma_eval_retrieval.py', '--min', '2']), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, evalr.main())

    def test_tend_report_hub_inbox_nohub_stale(self):
        for i in range(35):
            make_note(self.root / 'wiki' / f'yaprak-{i:02d}.md', f'Yaprak {i}',
                      parents=('dev-hub',))
        make_note(self.root / 'wiki' / 'dev-hub.md', 'Dev Hub')
        make_note(self.root / 'wiki' / 'kuyruk.md', 'Kuyruk Notu', stage='inbox')
        make_note(self.root / 'wiki' / 'kopuk.md', 'Kopuk Not')
        make_note(self.root / 'wiki' / 'bayat.md', 'Bayat Not', stage='next',
                  updated='2026-01-01T00:00:00+03:00')
        idx = lib.load_wiki_index()
        with mock.patch.object(lib, 'ROOT', self.root):
            idx = lib.load_wiki_index()
            findings, summary = tend.collect(idx)
        kinds = {(f['kind'], f['slug']) for f in findings}
        self.assertIn(('HUB-FULL', 'dev-hub'), kinds)
        self.assertIn(('INBOX', 'kuyruk'), kinds)
        self.assertIn(('NO-HUB', 'kopuk'), kinds)
        self.assertIn(('STALE', 'bayat'), kinds)
        self.assertEqual(1, summary['HUB-FULL'])
        self.assertEqual(1, summary['INBOX'])

    def test_tend_report_cli_writes_log(self):
        make_note(self.root / 'wiki' / 'tek.md', 'Tek Not')
        log = self.root / 'log'
        log.mkdir()
        output = io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.dict(os.environ, {'NOMA_ACTOR': 'test/model'}), \
                mock.patch('sys.argv', ['noma_tend_report.py']), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, tend.main())
        logged = (log / f"{lib.today()}.md").read_text(encoding='utf-8')
        self.assertIn('bakım raporu', logged)
        self.assertIn('NO-HUB=1', output.getvalue() + logged)

    def test_tend_report_without_actor_refuses_to_log(self):
        make_note(self.root / 'wiki' / 'tek.md', 'Tek Not')
        (self.root / 'log').mkdir()
        env = {k: v for k, v in os.environ.items() if k != 'NOMA_ACTOR'}
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch('sys.argv', ['noma_tend_report.py']), \
                self.assertRaises(SystemExit):
            tend.main()
        self.assertEqual([], list((self.root / 'log').iterdir()))


if __name__ == '__main__':
    unittest.main()
