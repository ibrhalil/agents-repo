"""Yapısal üst bağ ile açıklamalı gövde çağrışımının ayrımı."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import noma_eval_context as ctx
import noma_lib as lib


def entry(slug, title, parents=(), summary='', body=''):
    return {'fm': {'title': title, 'scope': 'systems', 'status': 'established'},
            'parents': list(parents), 'out': set(parents), 'tags': [],
            'fields': {name: lib.fold_tr(value) for name, value in {
                'slug': slug, 'title': title, 'tags': '',
                'summary': summary, 'body': body}.items()}}


class ContextTests(unittest.TestCase):
    def test_body_links_exclude_summary_navigation_and_code(self):
        text = ('# A\n## Links\n[[parent]]\n## Summary\n[[summary-only]]\n'
                '## Alt Temalar\n- [[navigation]] — yaprak\n'
                '## Fikir\nBu [[relevant]] ile neden ilişkili?\n'
                '```md\n[[example-only]]\n```\n## Kaynaklar\n- [[source-list]]\n')
        self.assertEqual({'relevant'}, ctx.body_associations(text))

    def test_specific_parent_selected_without_expanding_root(self):
        idx = {'a': entry('a', 'Bağlam', parents=('focused', 'root')),
               'b': entry('b', 'Diğer'), 'c': entry('c', 'Başka'),
               'd': entry('d', 'Yedek'),
               'focused': entry('focused', 'Özel üst'),
               'root': entry('root', 'Genel kök')}
        for slug in ('b', 'c', 'd', 'focused', 'root'):
            idx[slug]['parents'].append('root')
        idx['root']['parents'] = []
        selected = ctx.tree_context(idx, set(idx), ['a', 'b', 'c', 'd'],
                                    {'a': 30, 'b': 20, 'c': 10, 'd': 9})
        self.assertEqual(['a', 'b', 'focused', 'c'], selected)

    def test_body_edge_keeps_direction_and_filters_parent(self):
        with tempfile.TemporaryDirectory(prefix='noma-context-', dir=lib.ROOT / 'tmp') as tmp:
            root = Path(tmp)
            wiki = root / 'wiki'
            wiki.mkdir()
            (wiki / 'a.md').write_text('## Links\n[[parent]]\n## Summary\nA.\n'
                                       '## Kanıt\nBunun [[b]] ile gerekçesi.\n', encoding='utf-8')
            (wiki / 'b.md').write_text('## Links\n[[parent]]\n## Summary\nB.\n', encoding='utf-8')
            (wiki / 'parent.md').write_text('## Links\n## Summary\nParent.\n', encoding='utf-8')
            idx = {'a': entry('a', 'A', parents=('parent',)),
                   'b': entry('b', 'B', parents=('parent',)),
                   'parent': entry('parent', 'Parent')}
            with mock.patch.object(lib, 'ROOT', root):
                out, inc = ctx.association_graph(idx, set(idx))
        self.assertEqual({'b'}, out['a'])
        self.assertEqual({'a'}, inc['b'])
        self.assertNotIn('parent', out['a'])

    def test_no_alternative_evidence_means_no_graph_expansion(self):
        idx = {'a': entry('a', 'Bağlam', summary='karar'),
               'b': entry('b', 'Karar', summary='bağlam'),
               'c': entry('c', 'İlgi dışı')}
        a, b, _ = ctx.choose_context(idx, sorted(idx),
                                     ({'a': {'c'}, 'b': set(), 'c': set()}, {'c': {'a'}}),
                                     'bağlam karar')
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
