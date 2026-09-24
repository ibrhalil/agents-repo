#!/usr/bin/env python3
"""ingest() mekanik adımları: kaynağı raw/'a kopyala (inbox/clippings: verbatim;
conversations: elle diyalog özeti — script kopyalamaz) + şablondan wiki notu üret
+ log satırı yaz (AGENTS ingest; SCHEMA §1, §5). Git işlemi yapmaz."""
import argparse
import re
import sys
from pathlib import Path

import noma_lib as lib

# ADR-9: untrusted kaynakta bilinen injection desenleri — uyarı + [flag], bloklamaz
INJECTION = re.compile(
    r'ignore (?:all )?(?:previous|prior|above) instructions'
    r'|disregard (?:all )?(?:previous|prior|above)'
    r'|system prompt'
    r'|<\|im_start\|>'
    r'|reveal (?:your )?(?:instructions|prompt)', re.I)


def raw_target(kind, name_hint, attempt=0):
    if kind == 'clippings':
        n = 0
        for f in (lib.ROOT / 'raw' / 'clippings').glob('c-*.md'):
            m = re.fullmatch(r'c-(\d+)', f.stem)
            if m:
                n = max(n, int(m.group(1)))
        return lib.ROOT / 'raw' / 'clippings' / f'c-{n + 1 + attempt:04d}.md'
    stem = Path(name_hint).stem if name_hint else ''
    name = (lib.slugify(stem) or 'kaynak') + (Path(name_hint).suffix if name_hint else '.md')
    p = lib.ROOT / 'raw' / 'inbox' / name
    if attempt:
        p = p.with_name(f'{p.stem}-{lib.now_stamp()}-{attempt}{p.suffix}')
    return p


def write_raw(kind, name_hint, data):
    """Eşzamanlı ingest'lerde bile var olan raw dosyasını asla açıp ezme."""
    attempt = 0
    while True:
        p = raw_target(kind, name_hint, attempt)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with p.open('xb') as stream:
                stream.write(data)
            return p
        except FileExistsError:
            attempt += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', help="kaynak dosya yolu veya '-' (stdin)")
    ap.add_argument('--kind', choices=['inbox', 'conversations', 'clippings'],
                    default='inbox')
    ap.add_argument('--slug')
    ap.add_argument('--title')
    ap.add_argument('--type', dest='type_', default='resource')
    ap.add_argument('--scope', default='common')
    ap.add_argument('--stage', default='inbox')
    ap.add_argument('--status')
    ap.add_argument('--tags', help='virgülle ayrılmış ASCII etiketler')
    ap.add_argument('--no-note', action='store_true', help='yalnız raw kopyası')
    ap.add_argument('--actor', default='cron',
                    help='log aktörü: gerçek session modeli adı (agent çağrısı) | K | cron')
    a = ap.parse_args()
    if a.kind == 'conversations':
        raise SystemExit('conversations/: verbatim kopya yok — kısa K:/<model>: diyalog özeti '
                         'elle yazılır (SCHEMA §1)')
    lib.check_choice('type', a.type_, lib.TYPES)
    lib.check_choice('scope', a.scope, lib.SCOPES)
    lib.check_choice('stage', a.stage, lib.STAGES)
    lib.check_choice('status', a.status, lib.STATUS)

    is_file = a.source != '-'
    data = Path(a.source).read_bytes() if is_file else sys.stdin.buffer.read()
    if not data:
        raise SystemExit('hata: kaynak boş')
    hint = Path(a.source).name if is_file else None
    p = write_raw(a.kind, hint, data)

    rel = p.relative_to(lib.ROOT).as_posix()
    flag = bool(INJECTION.search(data.decode('utf-8', errors='ignore')))
    if flag:
        print(f'UYARI: olası prompt-injection deseni (ADR-9) — {rel}', file=sys.stderr)
    suffix = ' [flag]' if flag else ''
    if a.no_note:
        print(f'{rel} yazıldı')
        lib.append_log('ingest', f'raw-only: {rel}{suffix}', actor=a.actor)
        return

    title = a.title or (Path(a.source).stem if is_file else 'Kaynak')
    slug = lib.check_slug(a.slug or lib.slugify(title))
    note = lib.ROOT / 'wiki' / f'{slug}.md'
    if note.exists():
        print(f'wiki/{slug}.md zaten var — raw kopyası yapıldı, not atlandı '
              '(mevcut notla merge edin, AGENTS R2)', file=sys.stderr)
        lib.append_log('ingest', f'{rel} (not var: {slug}){suffix}', actor=a.actor)
        return
    tags = [t for t in (lib.parse_tags(a.tags) or []) if t != a.scope]
    try:
        with note.open('x', encoding='utf-8') as stream:
            stream.write(lib.render_note(slug, title, a.type_, a.scope, a.stage,
                                         a.status, tags or None, source_path=rel))
    except FileExistsError:
        print(f'wiki/{slug}.md aynı anda üretildi — raw kopyası yapıldı, '
              'mevcut notla merge edin (AGENTS R2)', file=sys.stderr)
        lib.append_log('ingest', f'{rel} (not var: {slug}){suffix}', actor=a.actor)
        return
    print(f'{rel} yazıldı\nwiki/{slug}.md üretildi')
    lib.append_log('ingest', f'{slug} <- {rel}{suffix}', actor=a.actor)


if __name__ == '__main__':
    main()
