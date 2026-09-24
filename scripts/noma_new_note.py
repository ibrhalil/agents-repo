#!/usr/bin/env python3
"""Şablondan yeni wiki notu iskeleti üretir (AGENTS R5; SCHEMA §3).
Git işlemi yapmaz — commit ve conflict çözümü periyodik cron'a aittir."""
import argparse

import noma_lib as lib


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('slug')
    ap.add_argument('--title', help='varsayılan: slug\'dan türetilir')
    ap.add_argument('--type', dest='type_', default='concept')
    ap.add_argument('--stage', default='inbox')
    ap.add_argument('--scope', default='common')
    ap.add_argument('--status')
    ap.add_argument('--tags', help='virgülle ayrılmış ASCII etiketler')
    ap.add_argument('--log-op', choices=lib.LOG_OPS,
                    help='verilirse log satırı da yazar')
    ap.add_argument('--actor', default='cron',
                    help='log aktörü: gerçek session modeli adı (agent çağrısı) | K | cron')
    a = ap.parse_args()
    lib.check_slug(a.slug)
    lib.check_choice('type', a.type_, lib.TYPES)
    lib.check_choice('stage', a.stage, lib.STAGES)
    lib.check_choice('scope', a.scope, lib.SCOPES)
    lib.check_choice('status', a.status, lib.STATUS)
    title = a.title or a.slug.replace('-', ' ').title()
    tags = [t for t in (lib.parse_tags(a.tags) or []) if t != a.scope]
    out = lib.ROOT / 'wiki' / f'{a.slug}.md'
    if out.exists():
        raise SystemExit(f'hata: wiki/{a.slug}.md zaten var — blind-overwrite yasak (AGENTS R2)')
    try:
        with out.open('x', encoding='utf-8') as stream:
            stream.write(lib.render_note(a.slug, title, a.type_, a.scope, a.stage,
                                         a.status, tags or None))
    except FileExistsError:
        raise SystemExit(f'hata: wiki/{a.slug}.md zaten var — blind-overwrite yasak (AGENTS R2)')
    print(f'wiki/{a.slug}.md üretildi (stage: {a.stage})')
    msg = f'not üretildi: wiki/{a.slug}.md'
    if a.log_op:
        lib.append_log(a.log_op, msg, actor=a.actor)
    else:
        print(f'log önerisi: {lib.now_hhmm()} tend @{lib.node_id()} <aktör> | {msg}')


if __name__ == '__main__':
    main()
