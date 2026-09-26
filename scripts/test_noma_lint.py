"""noma_lint.py sentetik regresyonları: CYCLE tespiti, şifreli düğüm, STRUCT/BUMP.

Gerçek wiki'ye, ağa veya modele bağlı değildir; notlar TemporaryDirectory içinde
üretilir, git çağrıları lint._head_payload/subprocess.run ile mock'lanır. check_index
gerçek wiki/ ve index/ ağacına dokunduğu için testte devre dışı bırakılır; R4 gereği
çıktı yalnız bulgu metnidir, not içeriği basılmaz.
"""
import contextlib
import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_lib as lib
import noma_lint as lint

GITCRYPT = b'\x00GITCRYPT\x00\x01\x8b\x01\x00s\x9cmimi'
FILLER = tuple(f'ark-adasi-{i:02d}' for i in range(12))


def note(slug, *, links=(), title='Yaprak Not',
         updated='2026-09-20T10:00:00+03:00', summary='Tek cümlelik özet.'):
    """docs/templates/wiki_note.md düzeninde sentetik not üretir."""
    return (f'---\ntitle: "{title}"\ntype: concept\nstage: done\nscope: systems\n'
            f'status: established\ntags: [sentetik]\n'
            f'created: 2026-09-19T09:00:00+03:00\nupdated: {updated}\n---\n'
            f'# {title}\n## Links\n' + ''.join(f'[[{s}]]\n' for s in links) +
            f'## Summary\n{summary}\n')


class LintTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-lint-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        (self.root / 'wiki').mkdir()
        (self.root / 'log').mkdir()
        for f in ('AGENTS.md', 'SCHEMA.md', 'README.md', '.env.example'):
            (self.root / f).write_text('sentetik\n', encoding='utf-8')
        (self.root / '.gitattributes').write_text(
            '# sentetik\nindex.md filter=git-crypt diff=git-crypt\n' +
            ''.join(f'{d} filter=git-crypt diff=git-crypt\n'
                    for d in lint.ENCRYPTED if d.endswith('/')), encoding='utf-8')
        for attr, value in (('ROOT', self.root),
                            ('check_index', lambda: None),
                            ('_head_payload', mock.Mock(return_value=None))):
            patcher = mock.patch.object(lint, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.head = lint._head_payload
        self.git_calls = []

    def write(self, slug, text):
        (self.root / 'wiki' / f'{slug}.md').write_text(text, encoding='utf-8')
        return text

    def run_lint(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = lint.main()
        return code, list(lint.out)

    def mock_git(self, tracked=(), check_attr='git-crypt'):
        """ls-files ve check-attr çağrılarını sabit yanıtla; gerisi gerçek git."""
        real = subprocess.run

        def fake(cmd, **kw):
            self.git_calls.append(cmd)
            if cmd[:2] == ['git', 'ls-files']:
                return subprocess.CompletedProcess(
                    cmd, 0, ''.join(f'{r}\0' for r in tracked).encode('utf-8'))
            if cmd[:2] == ['git', 'check-attr']:
                paths = [p for p in kw['input'].split('\0') if p]
                return subprocess.CompletedProcess(
                    cmd, 0, ''.join(f'{p}\0filter\0{check_attr}\0' for p in paths))
            return real(cmd, **kw)

        return mock.patch.object(subprocess, 'run', fake)

    def links_section(self, text, legacy=False):
        body = lint.strip_code(text)
        m = re.search(r'^## Links[ \t]*$', body, re.M)
        tail = body[m.end():]
        nxt = re.search(r'^## ([^\n]+)', tail, re.M)
        sec = (body[m.end():nxt.start()] if legacy and nxt
               else tail[:nxt.start()] if nxt else tail)
        return set(re.findall(r'\[\[([^\]|#]+)', sec))

    # --- B1: CYCLE kuralı ölü koddu -------------------------------------

    def test_mutual_links_section_fires_cycle(self):
        for s in FILLER:
            self.write(s, note(s))
        self.write('not-a', note('not-a', title='Not A',
                                 links=[*FILLER, 'not-b']))
        self.write('not-b', note('not-b', title='Not B',
                                 links=[*FILLER, 'not-a']))
        code, out = self.run_lint()
        self.assertEqual(['WRN CYCLE: wiki/not-a.md <-> wiki/not-b.md '
                          'karşılıklı Links (Tree ihlali)'],
                         [o for o in out if 'CYCLE' in o])
        self.assertEqual(0, code)

    def test_legacy_slice_truncated_the_links_section(self):
        """Kırmızı kanıt: eski kesim karşılıklı bağlantıyı göremiyordu."""
        text = note('not-a', title='Not A', links=[*FILLER, 'not-b'])
        self.assertIn('not-b', self.links_section(text))
        self.assertNotIn('not-b', self.links_section(text, legacy=True))
        self.assertLess(len(self.links_section(text, legacy=True)),
                        len(self.links_section(text)))

    # --- B2: kilitli / CI düğümünde sahte yeşil --------------------------

    def test_encrypted_previous_version_is_not_a_diff(self):
        self.write('kilitli-not', note('kilitli-not', title='Kilitli Not'))
        self.head.return_value = GITCRYPT
        code, out = self.run_lint()
        self.assertIn('ERR CRYPT: wiki/kilitli-not.md: HEAD sürümü çözülemedi; '
                      'BUMP/LOCKED doğrulanamadı', out)
        self.assertEqual([o for o in out if o.startswith(('ERR BUMP', 'WRN LOCKED'))], [])
        self.assertEqual(1, code)

    def test_encrypted_previous_version_makes_no_false_append(self):
        (self.root / 'raw').mkdir()
        (self.root / 'raw' / 'kaynak-01.md').write_text('değişmiş\n', encoding='utf-8')
        self.head.return_value = GITCRYPT
        with self.mock_git(['raw/kaynak-01.md']):
            code, out = self.run_lint()
        self.assertIn('ERR CRYPT: raw/kaynak-01.md: HEAD sürümü çözülemedi; '
                      'APPEND doğrulanamadı', out)
        self.assertEqual([o for o in out if o.startswith('ERR APPEND')], [])
        self.assertEqual(1, code)

    def test_undecodable_previous_version_makes_no_false_append(self):
        (self.root / 'log' / '2026-09-20.md').write_text('# 2026-09-20\n', encoding='utf-8')
        self.head.return_value = b'\xff\xfe\x00not-utf8'
        with self.mock_git(['log/2026-09-20.md']):
            code, out = self.run_lint()
        self.assertIn('ERR CRYPT: log/2026-09-20.md: HEAD sürümü çözülemedi; '
                      'APPEND doğrulanamadı', out)
        self.assertEqual([o for o in out if o.startswith('ERR APPEND')], [])
        self.assertEqual(1, code)

    # --- gerçek kapılar bozulmadı ---------------------------------------

    def test_body_change_without_updated_bump_fires(self):
        old = note('guncel-not', title='Güncel Not')
        new = note('guncel-not', title='Güncel Not', summary='Değişen özet cümlesi.')
        self.write('guncel-not', new)
        self.head.return_value = old.encode('utf-8')
        code, out = self.run_lint()
        self.assertIn('ERR BUMP: wiki/guncel-not.md: değişiklik var, '
                      'updated artırılmadı', out)
        self.assertEqual([o for o in out if 'CRYPT' in o], [])
        self.assertEqual(1, code)

    def test_unchanged_note_passes_cleanly(self):
        text = note('sade-not', title='Sade Not')
        self.write('sade-not', text)
        self.head.return_value = text.encode('utf-8')
        code, out = self.run_lint()
        self.assertEqual([o for o in out if o.startswith(('ERR', 'WRN'))], [])
        self.assertEqual(0, code)

    def test_links_then_non_summary_heading_reports_struct(self):
        self.write('kok-not', note('kok-not', title='Kök Not'))
        self.write('yaprak-not', note('yaprak-not', title='Yaprak Not',
                                      links=['[[kok-not]]']).replace('## Summary',
                                                                     '## Özet'))
        code, out = self.run_lint()
        self.assertIn('ERR STRUCT: wiki/yaprak-not.md: ## Links sonrası Özet — '
                      '## Summary beklenir (SCHEMA §4)', out)
        self.assertEqual(1, code)

    def test_note_without_links_section_reports_struct(self):
        text = note('bolum-siz', title='Bölümsüz Not').split('## Links')[0] + \
            '## Summary\nÖzet.\n'
        self.write('bolum-siz', text)
        code, out = self.run_lint()
        self.assertIn('ERR STRUCT: wiki/bolum-siz.md: ## Links bölümü yok '
                      '(SCHEMA §4)', out)
        self.assertEqual(1, code)

    # --- B3/B4: tek check-attr çağrısı ve budanmış yürüyüş ---------------

    def test_check_attr_is_batched_into_one_call(self):
        (self.root / 'raw').mkdir()
        (self.root / 'raw' / 'kaynak-01.md').write_text('kaynak\n', encoding='utf-8')
        self.write('kok-not', note('kok-not', title='Kök Not'))
        with self.mock_git(['raw/kaynak-01.md', 'raw/kaynak-02.md', 'wiki/kok-not.md']):
            code, out = self.run_lint()
        self.assertEqual(1, len([c for c in self.git_calls
                                 if c[:2] == ['git', 'check-attr']]))
        self.assertEqual([o for o in out if 'CRYPT' in o], [])
        self.assertEqual(0, code)

    def test_check_attr_reports_missing_git_crypt_filter(self):
        with self.mock_git(['wiki/kok-not.md'], check_attr='unspecified'):
            code, out = self.run_lint()
        self.assertIn('ERR CRYPT: wiki/kok-not.md: git-crypt filtresi etkin değil', out)
        self.assertEqual(1, code)

    def test_suffix_check_prunes_vendor_dirs(self):
        (self.root / 'node_modules' / 'paket').mkdir(parents=True)
        (self.root / 'node_modules' / 'paket' / 'kaynak_v2.md').write_text('x', encoding='utf-8')
        (self.root / '.git' / 'nesne').mkdir(parents=True)
        (self.root / '.git' / 'nesne' / 'kaynak_yeni.md').write_text('x', encoding='utf-8')
        self.write('not_v2', note('not_v2', title='Sürümlü'))
        code, out = self.run_lint()
        self.assertEqual(['ERR SUFFIX: wiki/not_v2.md'],
                         [o for o in out if 'SUFFIX' in o])
        self.assertEqual(1, code)


if __name__ == '__main__':
    unittest.main()
