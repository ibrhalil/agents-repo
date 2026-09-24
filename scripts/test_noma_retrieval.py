"""Sentetik wiki sorguları: aday kalitesi ve düşük gürültülü araç çıktısı."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import noma_find as find
import noma_build_index as build_index
import noma_lib as lib
import noma_wiki as wiki


def note(slug, title, *, summary='', body='', parents=(), status='established',
         stage='done', updated='2026-08-01T12:00:00+03:00'):
    fields = {'slug': slug, 'title': title, 'tags': '', 'summary': summary,
              'body': body}
    return {'fm': {'title': title, 'type': 'concept', 'scope': 'systems',
                   'stage': stage, 'status': status, 'updated': updated},
            'tags': [], 'parents': list(parents), 'out': set(parents),
            'fields': {k: lib.fold_tr(v) for k, v in fields.items()}}


class RetrievalTests(unittest.TestCase):
    def test_root_reads_only_generated_index_and_returns_paths(self):
        text = ("# index\n## Kök Hub'lar\n- [[agac|Özel Başlık]] — PRIVATE_SENTINEL\n"
                '## Ağaç (Tree) — Hub\n### [[baska]]\n')
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='noma-root-', dir=lib.ROOT / 'tmp') as tmp:
            (Path(tmp) / 'index.md').write_text(text, encoding='utf-8')
            with mock.patch.object(lib, 'ROOT', Path(tmp)), \
                    mock.patch.object(lib, 'load_wiki_index', side_effect=AssertionError('wiki tarandı')), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(0, wiki.cmd_root(SimpleNamespace(json=True)))
        self.assertEqual(['wiki/agac.md'], json.loads(output.getvalue()))
        self.assertNotIn('PRIVATE_', output.getvalue())

    def test_root_rejects_oversized_map_without_revealing_text(self):
        error = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='noma-root-size-', dir=lib.ROOT / 'tmp') as tmp:
            (Path(tmp) / 'index.md').write_text('PRIVATE_SENTINEL' * 700, encoding='utf-8')
            with mock.patch.object(lib, 'ROOT', Path(tmp)), contextlib.redirect_stderr(error):
                self.assertEqual(1, wiki.cmd_root(SimpleNamespace(json=True)))
        self.assertNotIn('PRIVATE_', error.getvalue())

    def test_natural_turkish_question_finds_title(self):
        idx = {'hafiza': note('hafiza', 'Hafıza yönetimi', body='kararlar')}
        self.assertEqual('hafiza', wiki.ranked(idx, list(idx),
                         ['Hafıza nasıl yönetilir?'])[0][1])

    def test_partial_fallback_when_all_terms_do_not_match(self):
        idx = {'context': note('context', 'Bağlam yönetimi', summary='kararlar'),
               'network': note('network', 'Ağ güvenliği', body='portlar')}
        self.assertEqual('context', wiki.ranked(idx, list(idx),
                         ['bağlam', 'güncel', 'karar'])[0][1])
        self.assertEqual([], wiki.ranked(idx, list(idx), ['eşleşmeyen']))

    def test_reliable_note_wins_recency_tie_without_hiding_history(self):
        idx = {'eski': note('eski', 'VPN kararı', status='established'),
               'taslak': note('taslak', 'VPN kararı', status='stub',
                              updated='2099-09-24T12:00:00+03:00')}
        self.assertEqual('eski', wiki.ranked(idx, list(idx), ['vpn'])[0][1])
        self.assertEqual(2, len(wiki.ranked(idx, list(idx), ['vpn'])))

    def test_hub_filter_keeps_only_immediate_children(self):
        idx = {'child': note('child', 'Ağ kararı', parents=('ag-hub',)),
               'other': note('other', 'Ağ kararı', parents=('other-hub',))}
        a = SimpleNamespace(type=None, stage=None, scope=None, status=None,
                            tag=None, hub='ag-hub')
        self.assertEqual(['child'], wiki.apply_filters(idx, list(idx), a))

    def test_recent_orders_by_date_even_for_unverified_notes(self):
        idx = {'old': note('old', 'Eski', status='established'),
               'new': note('new', 'Yeni', status='unverified',
                           updated='2099-09-24T12:00:00+03:00')}
        output = io.StringIO()
        a = SimpleNamespace(type=None, stage=None, scope=None, status=None,
                            tag=None, limit=2)
        with contextlib.redirect_stdout(output):
            wiki.cmd_recent(idx, a)
        self.assertTrue(output.getvalue().splitlines()[0].startswith('wiki/new.md'))

    def test_find_ranks_regex_title_above_body(self):
        idx = {'aaa': note('aaa', 'Diğer konu', body='network'),
               'zzz': note('zzz', 'Network kararı', body='network')}
        output = io.StringIO()
        with mock.patch.object(lib, 'load_wiki_index', return_value=idx), \
                mock.patch.object(find, 'matches_fulltext', return_value=set(idx)), \
                mock.patch.object(sys, 'argv', ['noma_find.py', 'network']), \
                contextlib.redirect_stdout(output):
            find.main()
        self.assertTrue(output.getvalue().splitlines()[0].startswith('wiki/zzz.md'))

    def test_find_keeps_matches_in_links_section(self):
        idx = {'leaf': note('leaf', 'Başka başlık', body='içerik')}
        output = io.StringIO()
        with mock.patch.object(lib, 'load_wiki_index', return_value=idx), \
                mock.patch.object(find, 'matches_fulltext', return_value={'leaf'}), \
                mock.patch.object(sys, 'argv', ['noma_find.py', 'ornek-hub']), \
                contextlib.redirect_stdout(output):
            find.main()
        self.assertIn('wiki/leaf.md', output.getvalue())

    def test_json_search_omits_body_and_summary(self):
        idx = {'leaf': note('leaf', 'PRIVATE_TITLE_SENTINEL Ağ', summary='PRIVATE_SUMMARY_SENTINEL',
                            body='PRIVATE_BODY_SENTINEL')}
        a = SimpleNamespace(tokens=['ağ'], type=None, stage=None, scope=None,
                            status=None, tag=None, hub=None, limit=10, json=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            wiki.cmd_search(idx, a)
        self.assertEqual('wiki/leaf.md', json.loads(output.getvalue())[0]['path'])
        self.assertNotIn('PRIVATE_', output.getvalue())

    def test_partial_json_hit_is_labelled_as_candidate(self):
        idx = {'leaf': note('leaf', 'Bağlam yönetimi')}
        a = SimpleNamespace(tokens=['bağlam', 'kayıp'], type=None, stage=None,
                            scope=None, status=None, tag=None, hub=None,
                            limit=10, json=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            wiki.cmd_search(idx, a)
        self.assertEqual('partial', json.loads(output.getvalue())[0]['match'])

    def test_json_hub_returns_only_paths(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='noma-hub-', dir=lib.ROOT / 'tmp') as tmp:
            page = Path(tmp) / 'index/hubs/branch/000001.md'
            page.parent.mkdir(parents=True)
            page.write_text('# [[branch]]\n- [[leaf|PRIVATE_LEAF_SENTINEL]] — PRIVATE_SUMMARY_SENTINEL\n',
                            encoding='utf-8')
            with mock.patch.object(lib, 'ROOT', Path(tmp)), \
                    mock.patch.object(lib, 'load_wiki_index', side_effect=AssertionError('wiki tarandı')), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(0, wiki.cmd_hub(SimpleNamespace(slug='branch', json=True, page=1)))
        self.assertEqual({'paths': ['wiki/leaf.md'], 'next_page': None},
                         json.loads(output.getvalue()))
        self.assertNotIn('PRIVATE_', output.getvalue())

    def test_hub_rejects_bad_slug_and_oversized_page(self):
        error = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='noma-hub-size-', dir=lib.ROOT / 'tmp') as tmp:
            page = Path(tmp) / 'index/hubs/root/000001.md'
            page.parent.mkdir(parents=True)
            page.write_text('PRIVATE_SENTINEL' * 1200, encoding='utf-8')
            with mock.patch.object(lib, 'ROOT', Path(tmp)), contextlib.redirect_stderr(error):
                self.assertEqual(1, wiki.cmd_hub(SimpleNamespace(slug='../root', json=True, page=1)))
                self.assertEqual(1, wiki.cmd_hub(SimpleNamespace(slug='root', json=True, page=1)))
        self.assertNotIn('PRIVATE_', error.getvalue())

    def test_index_build_shards_hub_and_removes_obsolete_page(self):
        with tempfile.TemporaryDirectory(prefix='noma-pages-', dir=lib.ROOT / 'tmp') as tmp:
            root = Path(tmp)
            source = root / 'wiki'
            source.mkdir()
            (source / 'root.md').write_text('---\ntitle: "Kök"\nstage: done\n---\n'
                                            '# Kök\n## Links\n## Summary\nKök.\n', encoding='utf-8')
            for i in range(75):
                (source / f'leaf-{i:03d}.md').write_text(
                    f'---\ntitle: "Yaprak {i}"\nstage: done\n---\n'
                    '# Yaprak\n## Links\n[[root]]\n## Summary\nSentetik bilgi.\n', encoding='utf-8')
            with mock.patch.object(build_index, 'ROOT', root), \
                    mock.patch.object(build_index, 'WIKI_DIR', source), \
                    mock.patch.object(build_index, 'INDEX_FILE', root / 'index.md'), \
                    mock.patch.object(build_index, 'HUB_DIR', root / 'index/hubs'):
                build_index.build_index()
                small_root = (root / 'index.md').read_text(encoding='utf-8')
                self.assertIn('[[root|Kök]]', small_root)
                self.assertNotIn('leaf-000', small_root)
                self.assertEqual(3, len(list((root / 'index/hubs/root').glob('*.md'))))
                with mock.patch.object(lib, 'ROOT', root):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        wiki.cmd_hub(SimpleNamespace(slug='root', json=True, page=1))
                    result = json.loads(output.getvalue())
                    self.assertEqual(build_index.PAGE_SIZE, len(result['paths']))
                    self.assertEqual(2, result['next_page'])
                for i in range(40, 75):
                    (source / f'leaf-{i:03d}.md').unlink()
                build_index.build_index()
                self.assertFalse((root / 'index/hubs/root/000003.md').exists())
                self.assertEqual(2, len(list((root / 'index/hubs/root').glob('*.md'))))


if __name__ == '__main__':
    unittest.main()
