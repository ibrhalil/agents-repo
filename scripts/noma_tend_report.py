#!/usr/bin/env python3
"""Tend öneri raporu: bakım adaylarını mekanik listeler (AGENTS §2 tend).

Yalnız slug/yol + sayı basılır; not içeriği çıktıya taşınmaz (AGENTS R4).
Cron'a hazır --json; koşusu log'a tend satırı yazar.
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta

import noma_lib as lib
from noma_build_index import PAGE_SIZE

STALE_DAYS = 30


def child_map(idx):
    """hub slug → doğrudan çocuk slug kümesi (yön: çocuk → ## Links üstü)."""
    children = {}
    for slug, entry in idx.items():
        for parent in entry['parents']:
            children.setdefault(parent, set()).add(slug)
    return children


def collect(idx):
    """(bulgular, özet) — bulgu: tür, yol/slug, ölçü."""
    children = child_map(idx)
    child_counts = {hub: len(kids) for hub, kids in children.items()}
    findings = []
    for slug, count in sorted(child_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count <= PAGE_SIZE:
            continue
        # Çok sayfalı hub desteklenen tasarımdır; yalnız doğal alt-hub yoksa bölünmeli.
        if any(child_counts.get(child, 0) for child in children[slug]):
            continue
        findings.append({'kind': 'HUB-FULL', 'slug': slug, 'measure': count,
                         'pages': -(-count // PAGE_SIZE)})
    for slug in sorted(idx):
        if idx[slug]['fm'].get('stage') == 'inbox':
            findings.append({'kind': 'INBOX', 'slug': slug, 'measure': ''})
    for slug in sorted(idx):
        if not idx[slug]['parents'] and not child_counts.get(slug):
            findings.append({'kind': 'NO-HUB', 'slug': slug, 'measure': ''})
    cutoff = (date.today() - timedelta(days=STALE_DAYS)).isoformat()
    for slug in sorted(idx):
        stage = idx[slug]['fm'].get('stage', '')
        updated = (idx[slug]['fm'].get('updated') or '')[:10]
        if stage in ('inbox', 'next', 'in_progress', 'waiting') and updated < cutoff:
            findings.append({'kind': 'STALE', 'slug': slug, 'measure': updated})
    summary = {kind: sum(f['kind'] == kind for f in findings)
               for kind in ('HUB-FULL', 'INBOX', 'NO-HUB', 'STALE')}
    return findings, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--json', action='store_true', help='makine okunur çıktı')
    ap.add_argument('--no-log', action='store_true', help='log satırı yazma')
    ap.add_argument('--actor',
                    help='gerçek oturum modeli | K | cron (zamanlanmış iş); '
                         'verilmezse NOMA_ACTOR')
    a = ap.parse_args()
    actor = lib.resolve_actor(a.actor) if not a.no_log else None
    idx = lib.load_wiki_index()
    findings, summary = collect(idx)
    if a.json:
        print(json.dumps({'summary': summary, 'findings': findings},
                         ensure_ascii=False))
    else:
        for f in findings:
            extra = f' · {f["pages"]} sayfa' if 'pages' in f else ''
            print(f"{f['kind']:8} wiki/{f['slug']}.md"
                  + (f' · {f["measure"]}' if f['measure'] else '') + extra)
        print('== ' + ' · '.join(f'{k}={v}' for k, v in summary.items()) + ' ==')
    if actor:
        lib.append_log('tend', 'bakım raporu: ' +
                       ' '.join(f'{k}={v}' for k, v in summary.items()), actor=actor)
    return 0


if __name__ == '__main__':
    sys.exit(main())
