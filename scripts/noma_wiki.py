#!/usr/bin/env python3
"""wiki arama CLI: root/search/pick/hub/recent/links/stats.
Agent JSON çıktısı yalnız yol/puan döndürür; not metni dosyadan seçilerek okunur.
İnsan çıktısında yol+başlık+metadata vardır, gövde/Summary basılmaz."""
import argparse
import json
import re
import sys

import noma_lib as lib
from noma_build_index import HUB_PAGE_MAX_BYTES, PAGE_SIZE, ROOT_MAX_BYTES

FILTERS = ('type', 'stage', 'scope', 'status')


def cmd_root(a):
    """Üretilmiş index.md'nin yalnız kök hub bölümünü döndür."""
    try:
        path = lib.ROOT / 'index.md'
        if path.stat().st_size > ROOT_MAX_BYTES:
            print('kök indeks boyut sınırını aşıyor', file=sys.stderr)
            return 1
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        print('index okunamadı (özel içerik gizlendi)', file=sys.stderr)
        return 1
    m = re.search(r"^## Kök Hub'lar\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    slugs = re.findall(r'^- \[\[([a-z0-9-]+)(?:\|[^\]]+)?\]\]', m.group(1), re.M) if m else []
    if not slugs:
        print('kök hub bulunamadı', file=sys.stderr)
        return 1
    paths = [f'wiki/{s}.md' for s in slugs]
    print(json.dumps(paths, ensure_ascii=False) if a.json else '\n'.join(paths))
    return 0


def up_key(idx, s):
    fm = idx[s]['fm']
    return fm.get('updated') or fm.get('created') or ''


def has_filter(a):
    return (any(getattr(a, k, None) for k in FILTERS)
            or getattr(a, 'tag', None) or getattr(a, 'hub', None))


def apply_filters(idx, slugs, a):
    return lib.filter_wiki(idx, slugs, {k: getattr(a, k, None) for k in FILTERS},
                           tag=getattr(a, 'tag', None), hub=getattr(a, 'hub', None))


def ranked(idx, slugs, tokens):
    return lib.rank_wiki(idx, slugs, tokens)


def partial_match(entry, tokens):
    terms = lib.search_terms(tokens)
    return bool(terms) and any(not any(term in entry['fields'][field]
                                       for field, _ in lib.SEARCH_WEIGHTS)
                               for term in terms)


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
        rows = [{'path': f'wiki/{s}.md', 'score': sc,
                 'match': 'partial' if partial_match(idx[s], a.tokens) else 'full'}
                for sc, s in shown]
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    for sc, s in shown:
        extra = f'skor {sc}' if a.tokens else ''
        if a.tokens and partial_match(idx[s], a.tokens):
            extra += ' · kısmi'
        print(line_for(idx, s, extra))
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


def cmd_hub(a):
    """Yalnız istenen hub sayfasını oku; wiki külliyatını tarama."""
    slug = a.slug
    if (slug != '_uncategorized' and not lib.SLUG_RE.fullmatch(slug)) or a.page < 1:
        print('geçersiz hub veya sayfa', file=sys.stderr)
        return 1
    directory = lib.ROOT / 'index' / 'hubs' / slug
    page = directory / f'{a.page:06d}.md'
    try:
        if page.stat().st_size > HUB_PAGE_MAX_BYTES:
            print('hub sayfası boyut sınırını aşıyor', file=sys.stderr)
            return 1
        text = page.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        print('hub sayfası bulunamadı; indeks yeniden üretilmeli', file=sys.stderr)
        return 1
    leaves = re.findall(r'^- \[\[([a-z0-9]+(?:-[a-z0-9]+)*)(?:\|[^\]]+)?\]\]', text, re.M)
    if not 0 < len(leaves) <= PAGE_SIZE:
        print('hub sayfası biçimi geçersiz', file=sys.stderr)
        return 1
    next_page = a.page + 1 if (directory / f'{a.page + 1:06d}.md').is_file() else None
    if a.json:
        print(json.dumps({'paths': [f'wiki/{s}.md' for s in leaves],
                          'next_page': next_page}, ensure_ascii=False))
        return 0
    for s in leaves:
        print(f'wiki/{s}.md')
    if next_page:
        print(f'sonraki sayfa: {next_page}')
    return 0


def cmd_recent(idx, a):
    slugs = apply_filters(idx, list(idx), a)
    if not slugs:
        print('not yok', file=sys.stderr)
        return 1
    shown = sorted(slugs, key=lambda s: up_key(idx, s), reverse=True)[:a.limit]
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

    root = sub.add_parser('root', help='index.md kök hub yolları')
    root.add_argument('--json', action='store_true', help='agent için yol listesi')

    def filtered(p, limit):
        for f in FILTERS:
            p.add_argument(f'--{f}')
        p.add_argument('--tag')
        p.add_argument('--limit', type=int, default=limit)
        return p

    s = filtered(sub.add_parser('search', aliases=['s'],
                                help='skorlı arama (tam yoksa kısmi adaylar)'), 10)
    s.add_argument('tokens', nargs='*', help='arama tokenları (Türkçe katlamalı)')
    s.add_argument('--hub', help='yalnız bu hub\'ın doğrudan çocukları')
    s.add_argument('--json', action='store_true', help='makine okunur çıktı')

    p = filtered(sub.add_parser('pick', aliases=['p'],
                                help='numaralı liste → seçim → detay kartı'), 20)
    p.add_argument('tokens', nargs='*')
    p.add_argument('--hub', help='yalnız bu hub\'ın doğrudan çocukları')
    p.add_argument('--hop', type=int, choices=[1, 2], default=1)

    hub = sub.add_parser('hub', help='hub yaprakları')
    hub.add_argument('slug')
    hub.add_argument('--page', type=int, default=1, help='sayfa numarası (1’den başlar)')
    hub.add_argument('--json', action='store_true', help='agent için yalnız yaprak yolları')

    lk = sub.add_parser('links', help='out/in komşular')
    lk.add_argument('slug')
    lk.add_argument('--hop', type=int, choices=[1, 2], default=1)

    filtered(sub.add_parser('recent', aliases=['r'],
                            help='updated alanına göre en güncel notlar'), 10)
    sub.add_parser('stats', help='metadata dağılımı + orphan/stub sayıları')
    return ap


def main():
    a = build_parser().parse_args()
    if a.cmd == 'root':
        sys.exit(cmd_root(a))
    if a.cmd == 'hub':
        sys.exit(cmd_hub(a))
    for key, ok in (('type', lib.TYPES), ('stage', lib.STAGES),
                    ('scope', lib.SCOPES), ('status', lib.STATUS)):
        lib.check_choice(key, getattr(a, key, None), ok)
    idx = lib.load_wiki_index(with_body=a.cmd in ('search', 's', 'pick', 'p'))
    cmds = {'search': cmd_search, 's': cmd_search, 'pick': cmd_pick, 'p': cmd_pick,
            'links': cmd_links, 'recent': cmd_recent, 'r': cmd_recent,
            'stats': cmd_stats}
    sys.exit(cmds[a.cmd](idx, a))


if __name__ == '__main__':
    main()
