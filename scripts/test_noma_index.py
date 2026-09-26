"""İndeks üreticisinin atomikliği, temizliği ve hata çıkışları (sentetik)."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import noma_build_index as build
import noma_lib as lib
import noma_verify_citations as verify

# tmp/ gitignore'lu olduğu için taze klonda yoktur; kardeş test modüllerinin de
# geçici dizin açabilmesi için burada oluşturulur.
(lib.ROOT / 'tmp').mkdir(parents=True, exist_ok=True)

HUB_NOTE = ('---\ntitle: "Kök"\nstage: done\n---\n'
            '# Kök\n## Links\n\n## Summary\nKök hub özeti.\n')
LEAF_NOTE = ('---\ntitle: "Yaprak {n}"\nstage: done\n---\n'
             '# Yaprak\n## Links\n[[root]]\n## Summary\n'
             'Sentetik yaprak bilgisi {n}.\n')


def write_wiki(root, leaves=3):
    source = root / 'wiki'
    source.mkdir(parents=True, exist_ok=True)
    (source / 'root.md').write_text(HUB_NOTE, encoding='utf-8')
    for number in range(leaves):
        (source / f'leaf-{number:03d}.md').write_text(LEAF_NOTE.format(n=number),
                                                      encoding='utf-8')
    return source


def run_build(root):
    with mock.patch.object(build, 'ROOT', root), \
            mock.patch.object(build, 'WIKI_DIR', root / 'wiki'), \
            mock.patch.object(build, 'INDEX_FILE', root / 'index.md'), \
            mock.patch.object(build, 'HUB_DIR', root / 'index/hubs'):
        return build.build_index()


def build_in(root, leaves=3):
    write_wiki(root, leaves)
    return run_build(root)


def huge_root_wiki(root, hubs=140):
    """Kök haritası 8 KiB'yi aşan sentetik wiki (her hub kök hub)."""
    source = root / 'wiki'
    source.mkdir(parents=True)
    summary = 'Bu çok uzun bir kök hub özetidir ve kök haritasını sınırın üstüne taşır. '
    for number in range(hubs):
        (source / f'hub-{number:03d}.md').write_text(
            f'---\ntitle: "Hub {number:03d} Uzun Başlık"\nstage: done\n---\n'
            f'# Hub\n## Links\n\n## Summary\n{summary}{number:03d}.\n', encoding='utf-8')
    links = ', '.join(f'[[hub-{number:03d}]]' for number in range(hubs))
    (source / 'connector.md').write_text(
        '---\ntitle: "Bağlayıcı"\nstage: done\n---\n# Bağlayıcı\n'
        f'## Links\n{links}\n## Summary\nBağlayıcı not.\n', encoding='utf-8')
    return source


class IndexBuildTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-index-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / 'repo'
        self.root.mkdir()

    def test_index_writes_never_truncate_a_final_path(self):
        write_wiki(self.root, leaves=75)
        writes, replaces = [], []
        real_write, real_replace = Path.write_text, os.replace

        def spy_write(path, *args, **kwargs):
            writes.append(Path(path))
            return real_write(path, *args, **kwargs)

        def spy_replace(src, dst):
            replaces.append((Path(src), Path(dst)))
            return real_replace(src, dst)

        with mock.patch.object(Path, 'write_text', spy_write), \
                mock.patch.object(build.os, 'replace', spy_replace):
            self.assertEqual(0, run_build(self.root))
        direct = sorted({str(p) for p in writes if p.suffix != '.tmp'})
        self.assertEqual([], direct, 'son dosya yerinde kırpılarak yazıldı')
        page = self.root / 'index/hubs/root/000001.md'
        destinations = [dst for _, dst in replaces]
        self.assertIn(self.root / 'index.md', destinations)
        self.assertIn(page, destinations)
        self.assertEqual([], [str(p) for p in writes if not p.name.endswith('.md.tmp')])
        self.assertFalse((page.parent / (page.name + '.tmp')).exists())
        self.assertEqual(build.PAGE_SIZE, len(
            [l for l in page.read_text(encoding='utf-8').splitlines() if l.startswith('- [[')]))

    def test_second_build_of_identical_content_writes_nothing(self):
        self.assertEqual(0, build_in(self.root))
        before = (self.root / 'index/hubs/root/000001.md').read_text(encoding='utf-8')
        writes, replaces = [], []
        real_write, real_replace = Path.write_text, os.replace
        with mock.patch.object(Path, 'write_text',
                               lambda p, *a, **k: (writes.append(Path(p)),
                                                   real_write(p, *a, **k))[1]), \
                mock.patch.object(build.os, 'replace',
                                  lambda s, d: (replaces.append(d), real_replace(s, d))[1]):
            self.assertEqual(0, run_build(self.root))
        self.assertEqual([], writes)
        self.assertEqual([], replaces)
        self.assertEqual(before,
                         (self.root / 'index/hubs/root/000001.md').read_text(encoding='utf-8'))

    def test_oversized_root_fails_cleanly_without_writing_any_page(self):
        source = huge_root_wiki(self.root)
        with mock.patch.object(build, 'ROOT', self.root), \
                mock.patch.object(build, 'WIKI_DIR', source), \
                mock.patch.object(build, 'INDEX_FILE', self.root / 'index.md'), \
                mock.patch.object(build, 'HUB_DIR', self.root / 'index/hubs'), \
                redirect_stderr(io.StringIO()) as error:
            code = build.build_index()
        self.assertEqual(1, code)
        self.assertIn(build.LIMIT_ERROR, error.getvalue())
        self.assertFalse((self.root / 'index').exists())
        self.assertFalse((self.root / 'index.md').exists())

    def test_limit_error_message_leaks_no_note_content(self):
        source = huge_root_wiki(self.root, hubs=140)
        with mock.patch.object(build, 'ROOT', self.root), \
                mock.patch.object(build, 'WIKI_DIR', source), \
                mock.patch.object(build, 'INDEX_FILE', self.root / 'index.md'), \
                mock.patch.object(build, 'HUB_DIR', self.root / 'index/hubs'), \
                redirect_stderr(io.StringIO()) as error:
            build.build_index()
        for line in error.getvalue().splitlines():
            self.assertNotIn('hub-', line)
            self.assertNotIn('Uzun Başlık', line)
            self.assertNotIn('sınırın üstüne', line)

    def test_stale_pages_and_tmp_leftovers_are_pruned(self):
        self.assertEqual(0, build_in(self.root))
        stale = self.root / 'index/hubs/root/000009.md'
        stale.write_text('# bayat\n', encoding='utf-8')
        leftover = self.root / 'index/hubs/root/000001.md.tmp'
        leftover.write_text('# yarım\n', encoding='utf-8')
        orphan = self.root / 'index/hubs/bos'
        orphan.mkdir()
        (orphan / '000001.md.tmp').write_text('# yarım\n', encoding='utf-8')
        self.assertEqual(0, build_in(self.root))
        self.assertFalse(stale.exists())
        self.assertFalse(leftover.exists())
        self.assertFalse(orphan.exists())

    def test_cleanup_tolerates_parallel_directory_removal(self):
        self.assertEqual(0, build_in(self.root))
        orphan = self.root / 'index/hubs/bos'
        orphan.mkdir()
        real_rmdir = Path.rmdir

        def race(path, *args, **kwargs):
            raise FileNotFoundError(2, 'No such file or directory', str(path))

        with mock.patch.object(Path, 'rmdir', race), \
                redirect_stderr(io.StringIO()) as error:
            self.assertEqual(0, run_build(self.root))
        self.assertEqual('', error.getvalue())
        self.assertTrue((self.root / 'index/hubs/root/000001.md').is_file())

    def test_lock_is_released_when_generation_fails(self):
        source = write_wiki(self.root, leaves=1)
        with mock.patch.object(build, 'ROOT', self.root), \
                mock.patch.object(build, 'WIKI_DIR', source), \
                mock.patch.object(build, 'INDEX_FILE', self.root / 'index.md'), \
                mock.patch.object(build, 'HUB_DIR', self.root / 'index/hubs'), \
                mock.patch.object(build, '_prune', side_effect=OSError('kilit hatası')), \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(OSError):
                build.build_index()
        lock = self.root / 'tmp' / build.LOCK_FILE
        self.assertTrue(lock.is_file())
        with mock.patch.object(build, 'ROOT', self.root), \
                mock.patch.object(build, 'WIKI_DIR', source), \
                mock.patch.object(build, 'INDEX_FILE', self.root / 'index.md'), \
                mock.patch.object(build, 'HUB_DIR', self.root / 'index/hubs'):
            self.assertEqual(0, build.build_index())


class CitationPathTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='noma-index-verify-',
                                                   dir=lib.ROOT / 'tmp')
        self.addCleanup(self.scratch.cleanup)
        outside = Path(self.scratch.name)
        # Sızan hedefler KÖK DIŞINDA ama mevcut: eski kod varlık kâhini çalıştırırdı.
        (outside / '.env.example').write_text('PRIVATE_ENV_SENTINEL', encoding='utf-8')
        (outside / 'etc').mkdir()
        (outside / 'etc' / 'passwd').write_text('PRIVATE_PASSWD_SENTINEL', encoding='utf-8')
        self.root = outside / 'repo'
        (self.root / 'wiki').mkdir(parents=True)
        (self.root / 'raw').mkdir()
        (self.root / 'log').mkdir()
        (self.root / 'plans').mkdir()

    def test_escaping_citations_fail_and_target_is_never_read(self):
        reads, probed = [], []
        real_read, real_is_file = Path.read_text, Path.is_file
        text = ('Sızıntı denemesi wiki/../../.env.example ve raw/../../etc/passwd '
                'adresleriyle yapıldı.')
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(Path, 'read_text',
                                  lambda p, *a, **k: (reads.append(Path(p)),
                                                      real_read(p, *a, **k))[1]), \
                mock.patch.object(Path, 'is_file',
                                  lambda p: (probed.append(Path(p)),
                                             real_is_file(p))[1]):
            findings, _ = verify.verify(text, idx={})
        self.assertEqual(2, len(findings))
        for finding in findings:
            self.assertEqual('FAIL', finding['status'])
            self.assertEqual('yol-dışı-atıf', finding['rule'])
        touched = {p for p in reads + probed if p.name in ('.env.example', 'passwd')}
        self.assertEqual(set(), touched, 'kök dışı dosya okundu ya da yoklandı')

    def test_escape_citations_exit_one_in_json_mode(self):
        text = 'Dışarı çıkma wiki/../../.env.example adresinde deneniyor.\n'
        output, error = io.StringIO(), io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', ['noma_verify_citations.py', '--json']), \
                mock.patch.object(sys, 'stdin', io.StringIO(text)), \
                mock.patch.object(sys, 'stdout', output), \
                mock.patch.object(sys, 'stderr', error):
            import contextlib
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(1, verify.main())
        self.assertEqual(1, len(output.getvalue().splitlines()))
        self.assertIn('yol-dışı-atıf', output.getvalue())

    def test_non_utf8_cited_note_does_not_traceback(self):
        (self.root / 'wiki' / 'bozuk.md').write_bytes(b'bozuk kodlama: \xff\xfe not\n')
        text = 'Bozuk kodlamalı not wiki/bozuk.md dosyasında.'
        with mock.patch.object(lib, 'ROOT', self.root):
            findings, negative = verify.verify(text, idx={'bozuk': {'fm': {}}})
        self.assertEqual('OK', findings[0]['status'])
        self.assertFalse(negative)

    def test_non_utf8_response_file_exits_two_without_traceback(self):
        broken = self.root / 'yanit.md'
        broken.write_bytes(b'bozuk: \xff\xfe\n')
        output, error = io.StringIO(), io.StringIO()
        with mock.patch.object(lib, 'ROOT', self.root), \
                mock.patch.object(sys, 'argv', ['noma_verify_citations.py', str(broken)]), \
                mock.patch.object(sys, 'stdout', output), \
                mock.patch.object(sys, 'stderr', error):
            import contextlib
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(2, verify.main())
        self.assertNotIn('Traceback', error.getvalue())
        self.assertIn('yanıt okunamadı', error.getvalue())


if __name__ == '__main__':
    unittest.main()
