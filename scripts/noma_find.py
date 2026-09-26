#!/usr/bin/env python3
"""query() retrieval: metadata filtre → full-text (rg; yoksa fallback) →
[[wikilink]] traversal (AGENTS query).
Varsayılan çıktı YALNIZ YOLDUR (kural 4): başlık, tag ve link hedefi basılmaz.
`--human` güvenilir yerel terminal içindir; agent/cron stdout'una kullanılmaz."""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import noma_lib as lib

HUMAN_HELP = 'güvenilir yerel terminal için başlık/metadata gösterir (kural 4 istisnası)'


def matches_fulltext(query):
    try:
        re.compile(query)
    except re.error:
        raise SystemExit('hata: geçersiz regex') from None
    if shutil.which('rg'):
        r = subprocess.run(['rg', '-l', '-S', '--', query, 'wiki/'],
                           cwd=lib.ROOT, capture_output=True, text=True)
        if r.returncode == 2:
            raise SystemExit('hata: rg araması başarısız')
        return {Path(l).stem for l in r.stdout.splitlines() if l.strip()}
    pat = re.compile(query, re.I)
    return {p.stem for p in (lib.ROOT / 'wiki').glob('*.md')
            if pat.search(lib.strip_code(p.read_text(encoding='utf-8')))}


def _incoming(idx):
    inc = {}
    for s, d in idx.items():
        for t in d['out']:
            inc.setdefault(t, set()).add(s)
    return inc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('query', nargs='?', help='regex; verilmezse yalnız metadata filtre')
    ap.add_argument('--type', dest='type_')
    ap.add_argument('--stage')
    ap.add_argument('--scope')
    ap.add_argument('--status')
    ap.add_argument('--tag')
    ap.add_argument('--hop', type=int, choices=[1, 2], default=1)
    ap.add_argument('--limit', type=int, default=20, help='en çok bu çok sayıda sonuç (>=1)')
    ap.add_argument('--human', action='store_true', help=HUMAN_HELP)
    a = ap.parse_args()
    if a.limit < 1:
        ap.error('--limit >= 1 olmalı')
    for name, val, ok in (('type', a.type_, lib.TYPES), ('stage', a.stage, lib.STAGES),
                          ('scope', a.scope, lib.SCOPES), ('status', a.status, lib.STATUS)):
        lib.check_choice(name, val, ok)
    if not (a.query or a.type_ or a.stage or a.scope or a.status or a.tag):
        ap.error('en az biri gerekli: query veya bir metadata filtresi')

    idx = lib.load_wiki_index(with_body=bool(a.query))
    hits = lib.filter_wiki(idx, list(idx), {'type': a.type_, 'stage': a.stage,
                                           'scope': a.scope, 'status': a.status},
                           tag=a.tag)
    if a.query:
        found = matches_fulltext(a.query)
        hits = [s for s in hits if s in found]
    hits = lib.rank_wiki(idx, hits, pattern=a.query)
    if not hits:
        print('eşleşme yok', file=sys.stderr)
        sys.exit(1)

    incoming = _incoming(idx)
    shown = hits[:a.limit]
    for _, s in shown:
        print(f'wiki/{s}.md')
        if not a.human:
            continue
        fm = idx[s]['fm']
        title = fm.get('title', '?').strip('"')
        tags = ' '.join(idx[s]['tags'])
        line = f"  {title} · {fm.get('type', '?')}/{fm.get('scope', '?')}"
        if tags:
            line += f' [{tags}]'
        print(line)
        outs = sorted(t for t in idx[s]['out'] if t in idx and t != s)
        ins = sorted(x for x in incoming.get(s, ()) if x != s)
        if outs:
            print('  out: ' + ', '.join(outs))
        if ins:
            print('  in: ' + ', '.join(ins))
        if a.hop == 2:
            for t in outs:
                t2 = sorted(x for x in idx[t]['out'] if x in idx and x not in (s, t))
                if t2:
                    print(f'  hop2: {t} -> ' + ', '.join(t2))
    rest = len(hits) - len(shown)
    tail = f' (ilk {len(shown)})' if rest else ''
    print(f'== {len(hits)} eşleşme{tail} ==')


if __name__ == '__main__':
    main()
