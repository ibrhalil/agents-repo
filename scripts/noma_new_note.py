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
    ap.add_argument('--actor',
                    help='log aktörü: gerçek session modeli adı (agent çağrısı) | K | '
                         'cron (yalnız zamanlanmış iş); verilmezse NOMA_ACTOR')
    a = ap.parse_args()
    lib.check_slug(a.slug)
    lib.check_choice('type', a.type_, lib.TYPES)
    lib.check_choice('stage', a.stage, lib.STAGES)
    lib.check_choice('scope', a.scope, lib.SCOPES)
    lib.check_choice('status', a.status, lib.STATUS)
    if a.stage in ('done', 'archived'):
        raise SystemExit("hata: bağlantısız şablon iskeleti done/archived olamaz — "
                         'önce inbox ile üret, doldurup hub\'a bağla (AGENTS GENİŞLETME)')
    # Not yazılmadan önce aktörü çöz: yarım kalırsa not log'suz kalmaz.
    actor = lib.resolve_actor(a.actor) if a.log_op else None
    title = a.title or a.slug.replace('-', ' ').title()
    tags = [t for t in (lib.parse_tags(a.tags) or []) if t != a.scope]
    out = lib.ROOT / 'wiki' / f'{a.slug}.md'
    if out.exists():
        raise SystemExit(f'hata: wiki/{a.slug}.md zaten var — blind-overwrite yasak (AGENTS R2)')
    # İçerik önce bellede üretilir; şablon okunamazsa boş dosya kalmasın.
    content = lib.render_note(a.slug, title, a.type_, a.scope, a.stage,
                              a.status, tags or None)
    try:
        with out.open('x', encoding='utf-8') as stream:
            stream.write(content)
    except FileExistsError:
        raise SystemExit(f'hata: wiki/{a.slug}.md zaten var — blind-overwrite yasak (AGENTS R2)')
    except BaseException:
        out.unlink(missing_ok=True)  # yarım not bırakma
        raise
    print(f'wiki/{a.slug}.md üretildi (stage: {a.stage})')
    msg = f'not üretildi: wiki/{a.slug}.md'
    if a.log_op:
        lib.append_log(a.log_op, msg, actor=actor)
    else:
        print(f'log önerisi: {lib.now_hhmm()} tend @{lib.node_id()} <aktör> | {msg}')


if __name__ == '__main__':
    main()
