#!/usr/bin/env python3
"""wiki arama CLI (insan yüzü): search/pick/hub/recent/links/stats.
Türkçe karakter katlamalı skorlı arama; çıktı yalnız yol + başlık + metadata
— gövde/Summary stdout'a çıkmaz (AGENTS R4)."""
import argparse
import json
import sys
from datetime import date

import noma_lib as lib

WEIGHTS = (('slug', 8), ('title', 6), ('tags', 4), ('summary', 2), ('body', 1))
FILTERS = ('type', 'stage', 'scope', 'status')


def up_key(idx, s):
    fm = idx[s]['fm']
    return fm.get('updated') or fm.get('created') or ''


def recency_bonus(fm):
    try:
        d = date.fromisoformat((fm.get('updated') or fm.get('created') or '')[:10])
    except ValueError:
        return 0
    return 2 if (date.today() - d).days <= 14 else 0


def score_entry(entry, tokens):
    fields = entry['fields']
    total = 0
    for t in tokens:
        best = max((w for name, w in WEIGHTS if t in fields[name]), default=0)
        if not best:
            return 0
        total += best
    return total + recency_bonus(entry['fm'])


def has_filter(a):
    return any(getattr(a, k, None) for k in FILTERS) or getattr(a, 'tag', None)


def apply_filters(idx, slugs, a):
    for key in FILTERS:
        val = getattr(a, key, None)
        if val:
            slugs = [s for s in slugs if idx[s]['fm'].get(key) == val]
    if getattr(a, 'tag', None):
        slugs = [s for s in slugs if a.tag in idx[s]['tags']]
    return slugs


def ranked(idx, slugs, tokens):
    if tokens:
        toks = [lib.fold_tr(t) for t in tokens]
        hits = [(score_entry(idx[s], toks), s) for s in slugs]
        hits = [h for h in hits if h[0] > 0]
    else:
        hits = [(0, s) for s in slugs]
    hits.sort(key=lambda h: h[1])
    hits.sort(key=lambda h: up_key(idx, h[1]), reverse=True)
    if tokens:
        hits.sort(key=lambda h: -h[0])
    return hits


def incoming(idx):
    inc = {}
    for s, e in idx.items():
        for t in e['out']:
            inc.setdefault(t, set()).add(s)
    return inc


def line_for(idx, slug, extra=''):
    fm = idx[slug]['fm']
    title = fm.get('title', '?').strip('"')
    line = f"wiki/{slug}.md · {title} · {fm.get('type', '?')}/{fm.get('scope', '?')}"
    tags = idx[slug]['tags']
    if tags:
        line += ' [' + ' '.join(tags) + ']'
    if extra:
        line += f' · {extra}'
    return line


def show_detail(idx, slug, hop=1):
    e = idx[slug]
    fm = e['fm']
    print(f"wiki/{slug}.md")
    print(fm.get('title', '?').strip('"'))
    print(' · '.join(f"{k}: {fm.get(k, '?')}" for k in FILTERS))
    if e['tags']:
        print('tags: ' + ', '.join(e['tags']))
    print(f"created: {fm.get('created', '?')} · updated: {fm.get('updated', '?')}")
    outs = sorted(t for t in e['out'] if t in idx and t != slug)
    ins = sorted(x for x in incoming(idx).get(slug, ()) if x != slug)
    if outs:
        print('out: ' + ', '.join(outs))
    if ins:
        print('in: ' + ', '.join(ins))
    if hop == 2:
        for t in outs:
            t2 = sorted(x for x in idx[t]['out'] if x in idx and x not in (slug, t))
            if t2:
                print(f'hop2: {t} -> ' + ', '.join(t2))


def cmd_search(idx, a):
    if not (a.tokens or has_filter(a)):
        print('en az biri gerekli: token veya bir filtre', file=sys.stderr)
        return 2
    hits = ranked(idx, apply_filters(idx, list(idx), a), a.tokens)
    if not hits:
        print('eşleşme yok', file=sys.stderr)
        return 1
    shown = hits[:a.limit]
    if a.json:
        rows = [{'path': f'wiki/{s}.md', 'slug': s,
                 'title': idx[s]['fm'].get('title', '').strip('"'),
                 'type': idx[s]['fm'].get('type'), 'stage': idx[s]['fm'].get('stage'),
                 'scope': idx[s]['fm'].get('scope'), 'status': idx[s]['fm'].get('status'),
                 'tags': idx[s]['tags'], 'score': sc,
                 'created': idx[s]['fm'].get('created'), 'updated': idx[s]['fm'].get('updated')}
                for sc, s in shown]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for sc, s in shown:
        print(line_for(idx, s, f'skor {sc}' if a.tokens else ''))
    rest = len(hits) - len(shown)
    print(f"== {len(hits)} eşleşme{' (ilk %d)' % len(shown) if rest else ''} ==")
    return 0


def cmd_pick(idx, a):
    hits = ranked(idx, apply_filters(idx, list(idx), a), a.tokens)
    if not hits:
        print('eşleşme yok', file=sys.stderr)
        return 1
    shown = hits[:a.limit]
    for i, (sc, s) in enumerate(shown, 1):
        print(f'{i:>2}. {line_for(idx, s)}')
    if sys.stdin.isatty():
        sys.stderr.write('numara (q=çık): ')
    try:
        sel = sys.stdin.readline().strip()
    except KeyboardInterrupt:
        sys.stderr.write('\n')
        return 0
    if not sel or sel.lower() == 'q':
        return 0
    if not sel.isdigit() or not (1 <= int(sel) <= len(shown)):
        print('geçersiz seçim', file=sys.stderr)
        return 1
    show_detail(idx, shown[int(sel) - 1][1], hop=a.hop)
    return 0


def cmd_hub(idx, a):
    slug = a.slug
    leaves = sorted(s for s in idx if s != slug and slug in idx[s]['parents'])
    if slug not in idx and not leaves:
        print('hub bulunamadı', file=sys.stderr)
        return 1
    if slug in idx:
        print(line_for(idx, slug, 'HUB'))
    for s in leaves:
        stage = idx[s]['fm'].get('stage', '')
        extra = f'[{stage}]' if stage and stage != 'done' else ''
        print('  ' + line_for(idx, s, extra))
    print(f'== {len(leaves)} yaprak ==')
    return 0


def cmd_recent(idx, a):
    slugs = apply_filters(idx, list(idx), a)
    if not slugs:
        print('not yok', file=sys.stderr)
        return 1
    shown = [s for _, s in ranked(idx, slugs, [])[:a.limit]]
    for s in shown:
        print(line_for(idx, s, up_key(idx, s)[:10] or '?'))
    print(f'== {len(shown)} not ==')
    return 0


def cmd_links(idx, a):
    if a.slug not in idx:
        print('not bulunamadı', file=sys.stderr)
        return 1
    show_detail(idx, a.slug, hop=a.hop)
    return 0


def cmd_stats(idx, a):
    print(f'toplam: {len(idx)} not')
    for key in FILTERS:
        c = {}
        for s in idx:
            v = idx[s]['fm'].get(key, '?')
            c[v] = c.get(v, 0) + 1
        ranked_items = sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))
        print(key + ': ' + ', '.join(f'{k}={v}' for k, v in ranked_items))
    inc = incoming(idx)
    orphans = sorted(s for s in idx if not (idx[s]['out'] & set(idx)) and not inc.get(s))
    stubs = sorted(s for s in idx if idx[s]['fm'].get('status') == 'stub')
    print(f'stub: {len(stubs)} · orphan: {len(orphans)}')
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog='noma_wiki.py', description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def filtered(p, limit):
        for f in FILTERS:
            p.add_argument(f'--{f}')
        p.add_argument('--tag')
        p.add_argument('--limit', type=int, default=limit)
        return p

    s = filtered(sub.add_parser('search', aliases=['s'],
                                help='skorlı full-text arama (AND token)'), 10)
    s.add_argument('tokens', nargs='*', help='arama tokenları (Türkçe katlamalı)')
    s.add_argument('--json', action='store_true', help='makine okunur çıktı')

    p = filtered(sub.add_parser('pick', aliases=['p'],
                                help='numaralı liste → seçim → detay kartı'), 20)
    p.add_argument('tokens', nargs='*')
    p.add_argument('--hop', type=int, choices=[1, 2], default=1)

    sub.add_parser('hub', help='hub yaprakları').add_argument('slug')

    lk = sub.add_parser('links', help='out/in komşular')
    lk.add_argument('slug')
    lk.add_argument('--hop', type=int, choices=[1, 2], default=1)

    filtered(sub.add_parser('recent', aliases=['r'],
                            help='updated alanına göre en güncel notlar'), 10)
    sub.add_parser('stats', help='metadata dağılımı + orphan/stub sayıları')
    return ap


def main():
    a = build_parser().parse_args()
    for key, ok in (('type', lib.TYPES), ('stage', lib.STAGES),
                    ('scope', lib.SCOPES), ('status', lib.STATUS)):
        lib.check_choice(key, getattr(a, key, None), ok)
    idx = lib.load_wiki_index(with_body=True)
    cmds = {'search': cmd_search, 's': cmd_search, 'pick': cmd_pick, 'p': cmd_pick,
            'hub': cmd_hub, 'links': cmd_links, 'recent': cmd_recent, 'r': cmd_recent,
            'stats': cmd_stats}
    sys.exit(cmds[a.cmd](idx, a))


if __name__ == '__main__':
    main()
