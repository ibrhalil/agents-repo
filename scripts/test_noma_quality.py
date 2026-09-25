"""Yanıt doğrulama ve bakım raporu araçlarının sentetik regresyonları."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import noma_lib as lib
import noma_tend_report as tend
import noma_verify_citations as verify


def make_note(path, title, *, parents=(), stage='done', status='established',
              updated='2026-09-25T00:00:00+03:00', summary='Özet.'):
    links = ', '.join(f'[[{p}]]' for p in parents)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: concept\nstage: {stage}\nscope: systems\n'
        f'status: {status}\ncreated: 2026-09-25T00:00:00+03:00\n'
        f'updated: {updated}\n---\n# {title}\n## Links\n{links}\n'
        f'## Summary\n{summary}\n', encoding='utf-8')


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
                mock.patch('sys.argv', ['noma_tend_report.py']), \
                contextlib.redirect_stdout(output):
            self.assertEqual(0, tend.main())
        logged = (log / f"{lib.today()}.md").read_text(encoding='utf-8')
        self.assertIn('bakım raporu', logged)
        self.assertIn('NO-HUB=1', output.getvalue() + logged)


if __name__ == '__main__':
    unittest.main()
