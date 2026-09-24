#!/usr/bin/env python3
"""query() retrieval: metadata filtre → full-text (rg; yoksa fallback) →
[[wikilink]] traversal (AGENTS query). Gövde içeriği stdout'a çıkmaz (kural 4)."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import noma_lib as lib


def matches_fulltext(query):
    if shutil.which('rg'):
        r = subprocess.run(['rg', '-l', '-S', '--', query, 'wiki/'],
                           cwd=lib.ROOT, capture_output=True, text=True)
        if r.returncode == 2:
            raise SystemExit(f'hata: rg — {r.stderr.strip()}')
        return {Path(l).stem for l in r.stdout.splitlines() if l.strip()}
    pat = re.compile(query, re.I)
    return {p.stem for p in (lib.ROOT / 'wiki').glob('*.md')
            if pat.search(lib.strip_code(p.read_text(encoding='utf-8')))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('query', nargs='?', help='regex; verilmezse yalnız metadata filtre')
    ap.add_argument('--type', dest='type_')
    ap.add_argument('--stage')
    ap.add_argument('--scope')
    ap.add_argument('--status')
    ap.add_argument('--tag')
    ap.add_argument('--hop', type=int, choices=[1, 2], default=1)
    ap.add_argument('--limit', type=int, default=20)
    a = ap.parse_args()
    for name, val, ok in (('type', a.type_, lib.TYPES), ('stage', a.stage, lib.STAGES),
                          ('scope', a.scope, lib.SCOPES), ('status', a.status, lib.STATUS)):
        lib.check_choice(name, val, ok)
    if not (a.query or a.type_ or a.stage or a.scope or a.status or a.tag):
        ap.error('en az biri gerekli: query veya bir metadata filtresi')

    idx = lib.load_wiki_index()
    hits = set(idx)
    for key, val in (('type', a.type_), ('stage', a.stage), ('scope', a.scope),
                     ('status', a.status)):
        if val:
            hits &= {s for s in hits if idx[s]['fm'].get(key) == val}
    if a.tag:
        hits &= {s for s in hits if a.tag in idx[s]['tags']}
    if a.query:
        hits &= matches_fulltext(a.query)
    hits = sorted(hits)
    if not hits:
        print('eşleşme yok', file=sys.stderr)
        sys.exit(1)

    incoming = {}
    for s, d in idx.items():
        for t in d['out']:
            incoming.setdefault(t, set()).add(s)

    shown = hits[:a.limit]
    for s in shown:
        fm = idx[s]['fm']
        title = fm.get('title', '?').strip('"')
        line = f"wiki/{s}.md · {title} · {fm.get('type', '?')}/{fm.get('scope', '?')}"
        tags = ' '.join(idx[s]['tags'])
        if tags:
            line += f' [{tags}]'
        print(line)
        outs = sorted(t for t in idx[s]['out'] if t in idx)
        ins = sorted(x for x in incoming.get(s, ()) if x != s)
        if outs:
            print('  out: ' + ', '.join(outs))
        if ins:
            print('  in: ' + ', '.join(ins))
        if a.hop == 2:
            for t in outs:
                t2 = sorted(x for x in idx[t]['out'] if x in idx and x != s)
                if t2:
                    print(f'  hop2: {t} -> ' + ', '.join(t2))
    rest = len(hits) - len(shown)
    tail = f' (ilk {len(shown)})' if rest else ''
    print(f'== {len(hits)} eşleşme{tail} ==')


if __name__ == '__main__':
    main()
