"""Graph üreticisinin determinizm, kenar kuralları ve kilit/boş durumları (sentetik).

Beklentiler sentetik notlardan türetilir; gerçek wiki içeriği kullanılmaz.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_build_graph as build
import noma_lib as lib

# tmp/ gitignore'lu olduğu için taze klonda yoktur; geçici dizinler için burada oluşturulur.
(lib.ROOT / 'tmp').mkdir(parents=True, exist_ok=True)

NOTE_A = ('---\ntitle: "A Başlık"\ntype: concept\nstage: done\nscope: systems\n'
          'status: established\ntags: [alfa]\n---\n'
          '# A\n## Links\n[[root]]\n## Summary\nA özeti.\n'
          'Gövde [[b]] ve yine [[b]].\n')
NOTE_ROOT = ('---\ntitle: "Kök"\ntype: concept\nstage: done\nscope: systems\n---\n'
             '# Kök\n## Links\n\n## Summary\nKök özeti.\n')


def write(root, slug, text):
    wiki = root / 'wiki'
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / f'{slug}.md').write_text(text, encoding='utf-8')
    return wiki


def run_build(root):
    with mock.patch.object(build, 'WIKI_DIR', root / 'wiki'), \
            mock.patch.object(lib, 'ROOT', root):
        return build.build_graph()


def by_id(graph, slug):
    return next(n for n in graph['nodes'] if n['id'] == slug)


class BuildGraphTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='noma-graph-',
                                                 dir=lib.ROOT / 'tmp')
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def graph(self):
        return run_build(self.root)

    def test_counts_and_node_fields(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)
        graph = self.graph()
        self.assertEqual(graph['meta']['counts'],
                         {'nodes': 3, 'edges': 2, 'missing': 1})
        node = by_id(graph, 'a')
        self.assertEqual(node['label'], 'A Başlık')
        self.assertEqual(node['path'], 'wiki/a.md')
        self.assertEqual(node['type'], 'concept')
        self.assertEqual(node['stage'], 'done')
        self.assertEqual(node['scope'], 'systems')
        self.assertEqual(node['status'], 'established')
        self.assertEqual(node['tags'], ['alfa'])
        self.assertTrue(node['exists'])

    def test_tree_and_ref_edge_kinds(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)
        edges = {(e['source'], e['target']): e for e in self.graph()['edges']}
        self.assertEqual(edges[('a', 'root')]['kind'], 'tree')
        self.assertEqual(edges[('a', 'b')]['kind'], 'ref')
        for edge in edges.values():
            self.assertEqual(edge['type'], 'wikilink')

    def test_duplicate_wikilink_single_edge(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)  # [[b]] iki kez geçer
        graph = self.graph()
        self.assertEqual([e for e in graph['edges'] if e['target'] == 'b'],
                         [{'source': 'a', 'target': 'b', 'type': 'wikilink',
                           'kind': 'ref'}])

    def test_unresolved_link_creates_missing_node(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)
        node = by_id(self.graph(), 'b')
        self.assertFalse(node['exists'])
        self.assertIsNone(node['path'])
        self.assertEqual(node['label'], 'b')
        self.assertEqual(node['tags'], [])
        self.assertEqual(self.graph()['meta']['counts']['missing'], 1)

    def test_self_link_produces_no_edge(self):
        write(self.root, 'k',
              '---\ntitle: "K"\ntype: concept\nstage: done\nscope: systems\n---\n'
              '# K\n## Links\n[[k]]\n## Summary\nÖz referans.\n')
        graph = self.graph()
        self.assertEqual(graph['edges'], [])
        self.assertEqual(by_id(graph, 'k')['degree'], 0)

    def test_alias_and_heading_links_resolve_to_slug(self):
        write(self.root, 'b', '---\ntitle: "B"\ntype: concept\nstage: done\n'
                              'scope: systems\n---\n# B\n## Links\n\n## Summary\nB.\n')
        write(self.root, 'a', '---\ntitle: "A"\ntype: concept\nstage: done\n'
                              'scope: systems\n---\n# A\n## Links\n\n## Summary\nA.\n'
                              'Görünen [[b|Başlık]] ve [[b#Kisim]].\n')
        graph = self.graph()
        self.assertEqual([(e['source'], e['target']) for e in graph['edges']],
                         [('a', 'b')])

    def test_code_fence_link_is_not_an_edge(self):
        write(self.root, 'a', '---\ntitle: "A"\ntype: concept\nstage: done\n'
                              'scope: systems\n---\n# A\n## Links\n\n## Summary\nA.\n'
                              'Örnek:\n\n```\n[[kodsatıriçi]]\n```\n')
        self.assertEqual(run_build(self.root)['edges'], [])

    def test_empty_wiki_is_valid_empty_graph(self):
        (self.root / 'wiki').mkdir(parents=True)
        graph = self.graph()
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])
        self.assertEqual(graph['meta']['counts'],
                         {'nodes': 0, 'edges': 0, 'missing': 0})

    def test_malformed_frontmatter_node_falls_back_to_slug(self):
        write(self.root, 'bozuk', '# Başlıksız\nGövde.\n')
        node = by_id(self.graph(), 'bozuk')
        self.assertTrue(node['exists'])
        self.assertEqual(node['label'], 'bozuk')
        self.assertEqual(node['type'], '')

    def test_degrees(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)  # a → root (tree), a → b (ref, missing)
        write(self.root, 'b', '---\ntitle: "B"\ntype: concept\nstage: done\n'
                              'scope: systems\n---\n# B\n## Links\n[[root]]\n'
                              '## Summary\nB.\nGövde [[a]].\n')
        graph = self.graph()
        self.assertEqual((by_id(graph, 'a')['outgoing'], by_id(graph, 'a')['incoming'],
                          by_id(graph, 'a')['degree']), (2, 1, 3))
        self.assertEqual(by_id(graph, 'root')['incoming'], 2)

    def test_build_is_deterministic(self):
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)
        self.assertEqual(build.serialize(self.graph()), build.serialize(self.graph()))


class OutputTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='noma-graph-out-',
                                                 dir=lib.ROOT / 'tmp')
        self.root = Path(self._tmp.name)
        self.out = self.root / 'web' / 'data'
        self.addCleanup(self._tmp.cleanup)
        write(self.root, 'root', NOTE_ROOT)
        write(self.root, 'a', NOTE_A)

    def test_write_outputs_atomic_and_deterministic(self):
        graph = run_build(self.root)
        build.write_outputs(graph, self.out)
        first = (self.out / 'graph.json').read_text(encoding='utf-8')
        second = (self.out / 'graph.js').read_text(encoding='utf-8')
        self.assertTrue(first.endswith('\n'))
        self.assertTrue(second.startswith(build.JS_PREFIX))
        self.assertTrue(second.endswith(';\n'))
        self.assertIn(first, second)
        build.write_outputs(run_build(self.root), self.out)
        self.assertEqual((self.out / 'graph.json').read_text(encoding='utf-8'), first)
        self.assertFalse(list(self.out.glob('*.tmp')))

    def test_staleness_detection(self):
        graph = run_build(self.root)
        self.assertTrue(build.outputs_stale(graph, self.out))
        build.write_outputs(graph, self.out)
        self.assertFalse(build.outputs_stale(graph, self.out))
        (self.out / 'graph.js').write_text('window.NOMA_GRAPH={};\n', encoding='utf-8')
        self.assertTrue(build.outputs_stale(graph, self.out))


class LockedWikiTests(unittest.TestCase):
    def test_crypt_blob_exits_with_unlock_hint(self):
        with tempfile.TemporaryDirectory(prefix='noma-graph-lock-',
                                         dir=lib.ROOT / 'tmp') as tmp:
            root = Path(tmp)
            wiki = root / 'wiki'
            wiki.mkdir(parents=True)
            (wiki / 'kilitli.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
            with mock.patch.object(build, 'WIKI_DIR', wiki):
                with self.assertRaises(SystemExit) as ctx:
                    build.build_graph()
            self.assertIn('kilitli', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
