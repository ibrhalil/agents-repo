"""noma_lint.py sentetik regresyonları: CYCLE tespiti, şifreli düğüm, STRUCT/BUMP.

Gerçek wiki'ye, ağa veya modele bağlı değildir; notlar TemporaryDirectory içinde
üretilir, git çağrıları lint._head_payload/subprocess.run ile mock'lanır. check_index
gerçek wiki/ ve index/ ağacına dokunduğu için testte devre dışı bırakılır; R4 gereği
çıktı yalnız bulgu metnidir, not içeriği basılmaz.
"""
import contextlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_lib as lib
import noma_lint as lint
import noma_policy as policy

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
                            ('check_board', lambda: None),  # Covered in test_noma_board.
                            # Policy gate is isolated here; meaningful policy-lint
                            # integration lives in PolicyLintTests below.
                            ('check_policy', lambda: None),
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

    @contextlib.contextmanager
    def staged(self, snapshot):
        """Synthetic index snapshot; no private payload enters git/stdout."""
        with mock.patch.object(lint, '_staged_wiki_paths', return_value=sorted(snapshot)), \
                mock.patch.object(lint, '_staged_payload', side_effect=snapshot.get):
            yield

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
        self.assertEqual(['WRN CYCLE: wiki/not-a.md -> wiki/not-b.md -> wiki/not-a.md '
                          '(Tree ihlali)'],
                         [o for o in out if 'CYCLE' in o])
        self.assertEqual(0, code)

    def test_longer_cycle_chain_fires_cycle(self):
        """Kırmızı kanıt: eski yalnız-2'lü kural A→B→C→A döngüsünü göremiyordu."""
        for s in FILLER:
            self.write(s, note(s))
        self.write('not-a', note('not-a', title='Not A', links=[*FILLER, 'not-b']))
        self.write('not-b', note('not-b', title='Not B', links=[*FILLER, 'not-c']))
        self.write('not-c', note('not-c', title='Not C', links=[*FILLER, 'not-a']))
        code, out = self.run_lint()
        self.assertEqual(['WRN CYCLE: wiki/not-a.md -> wiki/not-b.md -> wiki/not-c.md '
                          '-> wiki/not-a.md (Tree ihlali)'],
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

    def test_multiple_backtick_code_span_does_not_create_link(self):
        text = note('kod-ornek') + '\n## Body\nÇift ayraç: ``[[olmayan-not]]``.\n'
        self.write('kod-ornek', text)
        code, out = self.run_lint()
        self.assertFalse(any(o.startswith('ERR LINK:') for o in out))
        self.assertEqual(0, code)

    def test_immutable_legacy_log_exceptions_do_not_hide_new_errors(self):
        path = self.root / 'log' / '2026-09-26.md'
        old = '# günlük\n' + '# boş\n' * 57 + 'eski biçim\n# ara\neski biçim iki\n'
        path.write_text(old, encoding='utf-8')
        self.head.return_value = old.encode('utf-8')
        self.assertTrue(lint._committed_legacy_log_line(path, 59))
        self.assertTrue(lint._committed_legacy_log_line(path, 61))
        path.write_text(old + 'yeni biçim hatası\n', encoding='utf-8')
        self.assertFalse(lint._committed_legacy_log_line(path, 62))
        path.write_text(old.replace('eski biçim iki', 'değişen satır'), encoding='utf-8')
        self.assertFalse(lint._committed_legacy_log_line(path, 61))

    def test_links_then_non_summary_heading_reports_struct(self):
        self.write('kok-not', note('kok-not', title='Kök Not'))
        self.write('yaprak-not', note('yaprak-not', title='Yaprak Not',
                                      links=['[[kok-not]]']).replace('## Summary',
                                                                     '## Özet'))
        code, out = self.run_lint()
        self.assertIn('ERR STRUCT: wiki/yaprak-not.md: ## Links sonrası beklenmeyen '
                      'bölüm — ## Summary beklenir (SCHEMA §4)', out)
        self.assertNotIn('Özet —', ' '.join(out))
        self.assertEqual(1, code)

    def test_struct_diagnostic_hides_private_heading(self):
        sentinel = note('gizli-not', title='Gizli',
                        summary='SENTINEL_PRIVATE_VALUE.')
        self.write('gizli-not', sentinel.replace('## Summary', '## Gizli Başlık'))
        code, out = self.run_lint()
        self.assertTrue(any(o.startswith('ERR STRUCT: wiki/gizli-not.md') for o in out))
        self.assertNotIn('Gizli Başlık', ' '.join(out))
        self.assertEqual(1, code)

    def test_stale_diagnostic_hides_stage_and_date_values(self):
        text = note('bayat-not', title='Bayat',
                    updated='2026-08-01T00:00:00+03:00')
        text = text.replace('stage: done', 'stage: in_progress').replace(
            'created: 2026-09-19T09:00:00+03:00', 'created: 2026-07-01T09:00:00+03:00')
        self.write('bayat-not', text)
        code, out = self.run_lint()
        stale = [o for o in out if o.startswith('WRN STALE')]
        self.assertEqual(1, len(stale))
        self.assertNotIn('stage=', stale[0])
        self.assertNotIn('updated=', stale[0])
        self.assertEqual(0, code)

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
        with self.mock_git(['raw/kaynak-01.md', 'raw/kaynak-02.md', 'wiki/kok-not.md']), \
                self.staged({'wiki/kok-not.md': (self.root / 'wiki' / 'kok-not.md').read_bytes()}):
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

    # --- commit kapısı: staged silme / plaintext blob / okunamadan sürüm ---

    def test_staged_deletion_of_raw_fires_append(self):
        """Kırmızı kanıt: silinen yol ls-files'tan düşer, eski kural görmezdi."""
        (self.root / 'raw').mkdir()
        with mock.patch.object(lint, '_head_paths',
                               return_value={'raw/kaynak-01.md'}), \
                self.mock_git(tracked=()):
            code, out = self.run_lint()
        self.assertIn("ERR APPEND: raw/kaynak-01.md: HEAD'de vardı, stage'den "
                      'silinmiş (append-only)', out)
        self.assertEqual(1, code)

    def test_plaintext_staged_blob_fires_crypt_beyond_index(self):
        """Attribute doğru görünsün; index dışı özel blob plaintext ise ERR."""
        self.write('kok-not', note('kok-not', title='Kök Not'))
        with self.mock_git(tracked=['wiki/kok-not.md']), \
                mock.patch.object(lint, '_staged_exists', return_value=True), \
                mock.patch.object(lint, '_staged_blob',
                                  return_value=b'plaintext icerik'), \
                mock.patch.object(lint, '_staged_payload', mock.Mock(return_value=None)):
            code, out = self.run_lint()
        self.assertIn('ERR CRYPT: wiki/kok-not.md: staged Git blob şifreli değil',
                      ' '.join(out))
        self.assertEqual(1, code)

    def test_unreadable_head_payload_is_not_treated_as_absent(self):
        """Git okuma hatası 'HEAD\'de yok' sayılıp atlanamaz."""
        self.write('kilitli-not', note('kilitli-not', title='Kilitli Not'))
        self.head.return_value = lint.UNREADABLE
        code, out = self.run_lint()
        self.assertIn('ERR CRYPT: wiki/kilitli-not.md: HEAD sürümü okunamadı; '
                      'BUMP/LOCKED doğrulanamadı', out)
        self.assertEqual(1, code)

    def test_staged_note_version_is_checked_for_bump(self):
        """İhlal stage edilip worktree HEAD'e döndürülse bile BUMP yakalanır."""
        old = note('guncel-not', title='Güncel Not')
        new = note('guncel-not', title='Güncel Not', summary='Değişen özet cümlesi.')
        self.write('guncel-not', old)  # worktree HEAD ile aynı
        self.head.return_value = old.encode('utf-8')
        with mock.patch.object(lint, '_staged_payload',
                               mock.Mock(return_value=new.encode('utf-8'))), \
                mock.patch.object(lint, '_staged_wiki_paths',
                                  return_value=['wiki/guncel-not.md']):
            code, out = self.run_lint()
        self.assertIn('ERR BUMP: wiki/guncel-not.md (staged): değişiklik var, '
                      'updated artırılmadı', out)
        self.assertEqual(1, code)

    def test_staged_new_note_validates_structure_and_links(self):
        self.write('kok-not', note('kok-not'))
        bad = note('yeni-not', links=['olmayan-not']).replace('## Summary', '## Gizli Başlık')
        with self.staged({'wiki/kok-not.md': (self.root / 'wiki/kok-not.md').read_bytes(),
                          'wiki/yeni-not.md': bad.encode()}):
            code, out = self.run_lint()
        self.assertIn('ERR STRUCT: wiki/yeni-not.md (staged): ## Links sonrası beklenmeyen '
                      'bölüm — ## Summary beklenir (SCHEMA §4)', out)
        self.assertIn('ERR LINK: wiki/yeni-not.md (staged): [[olmayan-not]] hedefi yok', out)
        self.assertNotIn('Gizli Başlık', ' '.join(out))
        self.assertEqual(1, code)

    def test_staged_changed_note_validates_frontmatter_and_cycle(self):
        self.write('not-a', note('not-a', links=['not-b']))
        self.write('not-b', note('not-b'))
        changed = note('not-b', links=['not-a'], updated='2026-09-21T10:00:00+03:00')
        changed = changed.replace('type: concept', 'type: SECRET_INVALID')
        with self.staged({'wiki/not-a.md': (self.root / 'wiki/not-a.md').read_bytes(),
                          'wiki/not-b.md': changed.encode()}):
            code, out = self.run_lint()
        self.assertIn('ERR ENUM: wiki/not-b.md (staged): geçersiz type', out)
        self.assertTrue(any(o.startswith('WRN CYCLE:') and '(staged)' in o for o in out))
        self.assertNotIn('SECRET_INVALID', ' '.join(out))
        self.assertEqual(1, code)

    def test_staged_deletion_breaks_link_even_if_worktree_retains_target(self):
        self.write('not-a', note('not-a', links=['not-b']))
        self.write('not-b', note('not-b'))
        with self.staged({'wiki/not-a.md': (self.root / 'wiki/not-a.md').read_bytes()}):
            code, out = self.run_lint()
        self.assertIn('ERR LINK: wiki/not-a.md (staged): [[not-b]] hedefi yok', out)
        self.assertEqual(1, code)

    def test_unstaged_link_does_not_contaminate_staged_graph(self):
        self.write('not-a', note('not-a', links=['not-b']))
        self.write('not-b', note('not-b', links=['not-a']))
        with self.staged({'wiki/not-a.md': note('not-a', links=['not-b']).encode(),
                          'wiki/not-b.md': note('not-b').encode()}):
            code, out = self.run_lint()
        self.assertEqual(1, len([o for o in out if o.startswith('WRN CYCLE')]))
        self.assertFalse(any('(staged)' in o for o in out if 'CYCLE' in o))
        self.assertEqual(0, code)

    def test_staged_unreadable_note_fails_without_partial_graph_claims(self):
        self.write('not-a', note('not-a', links=['not-b']))
        with self.staged({'wiki/not-a.md': (self.root / 'wiki' / 'not-a.md').read_bytes(),
                          'wiki/not-b.md': lint.UNREADABLE}):
            code, out = self.run_lint()
        self.assertTrue(any(o.startswith('ERR CRYPT: wiki/not-b.md (staged)') for o in out))
        self.assertFalse(any('(staged)' in o for o in out if o.startswith('ERR LINK')))
        self.assertEqual(1, code)

    # --- KRR: insan karar defteri anchor/referans sözleşmesi --------------

    def krr_registry(self, anchors):
        text = note('insan-karar-defteri', title='İnsan Karar Defteri',
                    links=list(FILLER), summary='Sentetik KRR defteri.')
        return text + '\n## Kayıtlar\n' + ''.join(
            f'### KRR-{a}\ngövde satırı\n' for a in anchors)

    def test_valid_krr_ref_passes_cleanly(self):
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                     links=[*FILLER, 'insan-karar-defteri'],
                                     summary='Karar ([[insan-karar-defteri#KRR-01|KRR-01]]).'))
        code, out = self.run_lint()
        self.assertEqual([o for o in out if 'KRR' in o], [])
        self.assertEqual(0, code)

    def test_krr_ref_without_registry_fires(self):
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                     links=list(FILLER),
                                     summary='Karar ([[insan-karar-defteri#KRR-01|KRR-01]]).'))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md: KRR atfı var '
                          'ama wiki/insan-karar-defteri.md yok'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_krr_ref_to_missing_anchor_fires(self):
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                     links=[*FILLER, 'insan-karar-defteri'],
                                     summary='Karar ([[insan-karar-defteri#KRR-02|KRR-02]]).'))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md: '
                          '[[insan-karar-defteri#KRR-02]] kaydı defterde yok'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_krr_duplicate_anchor_fires(self):
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01', '01')))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/insan-karar-defteri.md: mükerrer kayıt KRR-01'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_krr_heading_with_description_is_not_an_anchor(self):
        """Kırmızı kanıt: `### KRR-01 — açıklama` tam hedef biçimi değil (Obsidian
        heading link tam başlık metni ister); ref artık tanımsız kalır."""
        for s in FILLER:
            self.write(s, note(s))
        registry = self.krr_registry(('01',)).replace(
            '### KRR-01\ngövde satırı\n', '### KRR-01 — açıklamalı başlık\ngövde satırı\n')
        self.write('insan-karar-defteri', registry)
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                     links=[*FILLER, 'insan-karar-defteri'],
                                     summary='Karar ([[insan-karar-defteri#KRR-01|KRR-01]]).'))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md: '
                          '[[insan-karar-defteri#KRR-01]] kaydı defterde yok'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_staged_krr_ref_without_staged_registry_fires(self):
        """Staged snapshot, kendi defteri olmadan KRR atfı taşıyamaz."""
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        karar = note('karar-not', title='Karar Notu',
                     links=[*FILLER, 'insan-karar-defteri'],
                     summary='Karar ([[insan-karar-defteri#KRR-01|KRR-01]]).')
        self.write('karar-not', karar)
        with self.staged({'wiki/karar-not.md': karar.encode()}):
            code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md (staged): KRR atfı var '
                          'ama wiki/insan-karar-defteri.md yok'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_staged_krr_ref_to_missing_anchor_fires(self):
        """Worktree temiz olsa bile staged sürümdeki tanımsız KRR yakalanır."""
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        temiz = note('karar-not', title='Karar Notu',
                     links=[*FILLER, 'insan-karar-defteri'],
                     summary='Karar ([[insan-karar-defteri#KRR-01|KRR-01]]).')
        bozuk = temiz.replace('#KRR-01|KRR-01', '#KRR-02|KRR-02')
        self.write('karar-not', temiz)
        with self.staged({'wiki/insan-karar-defteri.md':
                          (self.root / 'wiki' / 'insan-karar-defteri.md').read_bytes(),
                          'wiki/karar-not.md': bozuk.encode()}):
            code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md (staged): '
                          '[[insan-karar-defteri#KRR-02]] kaydı defterde yok'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_krr_target_with_malformed_suffix_fires(self):
        """Kırmızı kanıt: `#KRR-01-invalid` hedefi 01 yakalayıp geçerli
        sayılamaz — tam hedef parçası biçim doğrulamasından geçmelidir."""
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                     links=[*FILLER, 'insan-karar-defteri'],
                                     summary='Karar ([[insan-karar-defteri#KRR-01-invalid|KRR-01]]).'))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md: hatalı KRR hedef biçimi '
                          '(KRR-NN beklenir): 01-invalid'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)

    def test_krr_nonnumeric_and_short_targets_do_not_escape(self):
        """Kırmızı kanıt: `#KRR-invalid` hiç eşleşme üretmez, `#KRR-1` tek hane —
        ikisi de artık yakalanıp reddedilir."""
        for s in FILLER:
            self.write(s, note(s))
        self.write('insan-karar-defteri', self.krr_registry(('01',)))
        self.write('karar-not', note('karar-not', title='Karar Notu',
                                      links=[*FILLER, 'insan-karar-defteri'],
                                      summary='A ([[insan-karar-defteri#KRR-invalid|x]]) '
                                             'B ([[insan-karar-defteri#KRR-1|y]]).'))
        code, out = self.run_lint()
        self.assertEqual(['ERR KRR: wiki/karar-not.md: hatalı KRR hedef biçimi '
                          '(KRR-NN beklenir): 1',
                          'ERR KRR: wiki/karar-not.md: hatalı KRR hedef biçimi '
                          '(KRR-NN beklenir): invalid'],
                         [o for o in out if o.startswith('ERR KRR')])
        self.assertEqual(1, code)


def seed_active_policy(root):
    """Lint-compatible synthetic root with a fully activated policy bundle."""
    for path in policy.CONTROL:
        if path == '.gitattributes':
            continue
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('synthetic control\n', encoding='utf-8')
    register = note('agent-policy', title='Agent Policy') + \
        '\n## Aktif Policy Kümesi\n- [[agent-read-policy]]\n'
    (root / 'wiki' / 'agent-policy.md').write_text(register, encoding='utf-8')
    (root / 'wiki' / 'agent-read-policy.md').write_text(
        note('agent-read-policy', title='Agent Read Policy'), encoding='utf-8')
    key = policy.propose(root, 'author-session')
    policy.record_review(root, key, 'independent-session')
    policy.activate(root, key, key)
    return key


class PolicyLintTests(unittest.TestCase):
    """check_policy() meaningful integration: staged receipts, snapshot closure,
    older staged activations, staged edits and deletions fail closed."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-policy-lint-',
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
                            ('check_board', lambda: None),
                            ('_head_payload', mock.Mock(return_value=None)),
                            ('_head_paths', mock.Mock(return_value=set())),
                            ('_staged_wiki_paths', mock.Mock(return_value=[])),
                            ('_staged_payload', mock.Mock(return_value=None))):
            patcher = mock.patch.object(lint, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.key = seed_active_policy(self.root)

    def run_lint(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = lint.main()
        return code, list(lint.out)

    def mock_policy_git(self, staged_names):
        """ls-files/check-attr sabit; git diff --cached staged_names döndürür."""
        real = subprocess.run

        def fake(cmd, **kw):
            if cmd[:2] == ['git', 'ls-files']:
                return subprocess.CompletedProcess(cmd, 0, b'')
            if cmd[:2] == ['git', 'check-attr']:
                paths = [p for p in kw['input'].split('\0') if p]
                return subprocess.CompletedProcess(
                    cmd, 0, ''.join(f'{p}\0filter\0git-crypt\0' for p in paths))
            if cmd[:3] == ['git', 'diff', '--cached']:
                return subprocess.CompletedProcess(
                    cmd, 0, ''.join(f'{p}\0' for p in staged_names).encode('utf-8'))
            return real(cmd, **kw)

        return mock.patch.object(subprocess, 'run', fake)

    @contextlib.contextmanager
    def policy_staged(self, snapshot):
        wiki_paths = sorted(p for p in snapshot if p.startswith('wiki/'))
        with mock.patch.object(lint, '_staged_wiki_paths',
                               return_value=wiki_paths), \
                mock.patch.object(lint, '_staged_payload', side_effect=snapshot.get):
            yield

    def snapshot_bytes(self, key):
        _, bundle = policy.approved(self.root)
        return {f'{policy.SNAPSHOTS}/{key}/{path}':
                policy.read_bytes(self.root, f'{policy.SNAPSHOTS}/{key}/{path}')
                for path in bundle['files']}

    def full_staged_snapshot(self, key):
        """Complete staged activation: state + snapshot copies + staged file paths."""
        snapshot = {policy.STATE: (self.root / policy.STATE).read_bytes(),
                    **self.snapshot_bytes(key)}
        _, bundle = policy.approved(self.root)
        for path in bundle['files']:
            snapshot[path] = policy.read_bytes(self.root, f'{policy.SNAPSHOTS}/{key}/{path}')
        return snapshot

    def activate_changed_proposal(self):
        path = self.root / 'wiki' / 'agent-read-policy.md'
        path.write_text(path.read_text(encoding='utf-8') + 'New rule.\n',
                        encoding='utf-8')
        key = policy.propose(self.root, 'author-session')
        policy.record_review(self.root, key, 'independent-session')
        policy.activate(self.root, key, key)
        return key

    def test_active_policy_state_keeps_lint_clean(self):
        with self.mock_policy_git([]):
            code, out = self.run_lint()
        self.assertEqual([o for o in out if 'POLICY' in o], [])
        self.assertEqual(0, code)

    def test_worktree_policy_edit_fires_unapproved_change(self):
        path = self.root / 'wiki' / 'agent-read-policy.md'
        path.write_text(path.read_text(encoding='utf-8') + 'UNAPPROVED', encoding='utf-8')
        with self.mock_policy_git([]):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: wiki/agent-read-policy.md: unapproved worktree change', out)
        self.assertEqual(1, code)

    def test_control_file_drift_blocks_policy_status(self):
        (self.root / 'scripts' / 'noma_hermes_context.py').write_text(
            'BYPASS\n', encoding='utf-8')
        with self.mock_policy_git([]):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: CONTROL-DRIFT', out)
        self.assertEqual(1, code)

    def test_state_deletion_fails_closed(self):
        (self.root / policy.STATE).unlink()
        with self.mock_policy_git([]):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: UNREADABLE', out)
        self.assertEqual(1, code)

    def test_staged_activation_requires_matching_snapshot_closure(self):
        snapshot = self.full_staged_snapshot(self.key)
        with self.mock_policy_git(list(snapshot)), self.policy_staged(snapshot):
            code, out = self.run_lint()
        self.assertEqual([o for o in out if 'POLICY' in o], [])
        self.assertEqual(0, code)

    def test_staged_older_activation_fires_staged_activation(self):
        self.activate_changed_proposal()  # current active is now a newer key
        state = policy.load_state(self.root)
        state['active'] = self.key
        snapshot = {policy.STATE: (json.dumps(state, sort_keys=True, indent=2)
                                   + '\n').encode('utf-8'),
                    **self.snapshot_bytes(self.key)}
        with self.mock_policy_git(list(snapshot)), self.policy_staged(snapshot):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: STAGED-ACTIVATION', out)
        self.assertEqual(1, code)

    def test_staged_snapshot_content_mismatch_fires_snapshot(self):
        snapshot = self.full_staged_snapshot(self.key)
        snapshot[f'{policy.SNAPSHOTS}/{self.key}/wiki/agent-read-policy.md'] += b' '
        with self.mock_policy_git(list(snapshot)), self.policy_staged(snapshot):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: SNAPSHOT', out)
        self.assertEqual(1, code)

    def test_staged_file_differs_from_approved_snapshot_fires_mismatch(self):
        snapshot = self.full_staged_snapshot(self.key)
        snapshot['wiki/agent-read-policy.md'] += b'unapproved edit'
        with self.mock_policy_git(list(snapshot)), self.policy_staged(snapshot):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: wiki/agent-read-policy.md: staged approval mismatch', out)
        self.assertEqual(1, code)

    def test_staged_snapshot_deletion_fires_staged_missing(self):
        snapshot = self.full_staged_snapshot(self.key)
        del snapshot[f'{policy.SNAPSHOTS}/{self.key}/wiki/agent-read-policy.md']
        with self.mock_policy_git(list(snapshot)), self.policy_staged(snapshot):
            code, out = self.run_lint()
        self.assertIn('ERR POLICY: STAGED-MISSING', out)
        self.assertEqual(1, code)


if __name__ == '__main__':
    unittest.main()
