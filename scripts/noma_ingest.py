#!/usr/bin/env python3
"""ingest() mekanik adımları: kaynağı raw/'a kopyala (inbox/clippings: verbatim;
conversations: elle diyalog özeti — script kopyalamaz) + şablondan wiki notu üret
+ log satırı yaz (AGENTS ingest; SCHEMA §1, §5). Git işlemi yapmaz."""
import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import noma_lib as lib

# ADR-9 K3: untrusted kaynakta bilinen injection desenleri (EN+TR) — uyarı + [flag], bloklamaz
INJECTION = re.compile(
    r'ignore (?:all )?(?:previous|prior|above) instructions'
    r'|disregard (?:all )?(?:previous|prior|above)'
    r'|system prompt'
    r'|<\|im_start\|>'
    r'|reveal (?:your )?(?:instructions|prompt)'
    r'|(?:önceki|eski) (?:talimatları|komutları) (?:yoksay|yok say|görmezden|dikkate alma)'
    r'|(?:tüm|butun) talimatları (?:yoksay|yok say|görmezden)'
    r'|sistem (?:istemi|istemini (?:göster|aç))'
    r'|token[ıi]n?[ıi]? (?:yaz|göster|açığa çıkar)'
    r'|[A-Za-z0-9+/]{160,}={0,2}', re.I)


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


def staging_dir():
    """Ham kaynak hazırlığı için geçici dizin (varsayılan repo tmp/; yoksa sistem geçici)."""
    base = lib.ROOT / 'tmp'
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return base


def write_raw(kind, name_hint, data):
    """Eşzamanlı ingest'lerde bile var olan raw dosyasını asla açıp ezme.

    R1: raw/ append-only; önce tmp'ye yaz + fsync + bütünlük denetle, sonra
    os.link ile ATOMİK yayınla (link, ad doluysa FileExistsError verir)."""
    staging = tempfile.mkdtemp(prefix='noma-raw-', dir=staging_dir())
    tmp = Path(staging) / 'payload'
    try:
        with tmp.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if tmp.stat().st_size != len(data):
            raise OSError('kısa yazma: ham kaynak bütünlüğü doğrulanamadı')
        attempt = 0
        while True:
            p = raw_target(kind, name_hint, attempt)
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(tmp, p)
                return p
            except FileExistsError:
                attempt += 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def verify_note(path):
    """Yeni üretilen not için mekanik post-ingest doğrulaması (AGENTS R2/R5).

    Not içeriği hiçbir koşulda döndürülmez/basılmaz; yalnız kural adları.
    Dönen: (hatalar, uyarılar) — hata giderilemezse not stage: inbox kalır ve
    log'a [verify-fail] bayrağı yazılır; uyarı yorum gerektirir (insan/agent).
    """
    errors, warnings = [], []
    text = path.read_text(encoding='utf-8')
    fm = lib.parse_fm(text)
    if fm is None:
        return ['FM'], []
    for key in ('title', 'type', 'stage', 'scope', 'created', 'updated'):
        if not fm.get(key):
            errors.append(f'FM:{key}')
    for name, allowed in (('type', lib.TYPES), ('stage', lib.STAGES),
                          ('scope', lib.SCOPES), ('status', lib.STATUS)):
        value = fm.get(name)
        if value and value not in allowed:
            errors.append(f'ENUM:{name}')
    if not lib.SLUG_RE.fullmatch(path.stem):
        errors.append('SLUG')
    clean = lib.strip_code(text)
    links_m = re.search(r'^## Links[ \t]*$', clean, re.M)
    if not links_m:
        errors.append('STRUCT:Links')
    else:
        nxt = re.search(r'^## ([^\n]+)', clean[links_m.end():], re.M)
        if not nxt or nxt.group(1).strip() != 'Summary':
            errors.append('STRUCT:Summary')
        sec = re.search(r'^## Links[ \t]*$\n(.*?)(?=^## |\Z)', clean, re.M | re.S)
        targets = {s.strip() for s in re.findall(r'\[\[([^\]|#]+)', sec.group(1))} if sec else set()
        for target in sorted(t for t in targets
                             if not (lib.ROOT / 'wiki' / f'{t}.md').exists()):
            errors.append(f'LINK:{target}')
        if not targets and not errors:
            warnings.append('NO-HUB')
    return errors, warnings


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
    ap.add_argument('--actor',
                    help='log aktörü: gerçek session modeli adı (agent çağrısı) | K | '
                         'cron (yalnız zamanlanmış iş); verilmezse NOMA_ACTOR')
    a = ap.parse_args()
    if a.kind == 'conversations':
        raise SystemExit('conversations/: verbatim kopya yok — kısa K:/<model>: diyalog özeti '
                         'elle yazılır (SCHEMA §1)')
    lib.check_choice('type', a.type_, lib.TYPES)
    lib.check_choice('scope', a.scope, lib.SCOPES)
    lib.check_choice('stage', a.stage, lib.STAGES)
    lib.check_choice('status', a.status, lib.STATUS)
    actor = lib.resolve_actor(a.actor)

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
        lib.append_log('ingest', f'raw-only: {rel}{suffix}', actor=actor)
        return 0

    title = a.title or (Path(a.source).stem if is_file else 'Kaynak')
    slug = lib.check_slug(a.slug or lib.slugify(title))
    note = lib.ROOT / 'wiki' / f'{slug}.md'
    if note.exists():
        print(f'wiki/{slug}.md zaten var — raw kopyası yapıldı, not atlandı '
              '(mevcut notla merge edin, AGENTS R2)', file=sys.stderr)
        lib.append_log('ingest', f'{rel} (not var: {slug}){suffix}', actor=actor)
        return 0
    tags = [t for t in (lib.parse_tags(a.tags) or []) if t != a.scope]
    try:
        with note.open('x', encoding='utf-8') as stream:
            stream.write(lib.render_note(slug, title, a.type_, a.scope, a.stage,
                                         a.status, tags or None, source_path=rel))
    except FileExistsError:
        print(f'wiki/{slug}.md aynı anda üretildi — raw kopyası yapıldı, '
              'mevcut notla merge edin (AGENTS R2)', file=sys.stderr)
        lib.append_log('ingest', f'{rel} (not var: {slug}){suffix}', actor=actor)
        return 0
    print(f'{rel} yazıldı\nwiki/{slug}.md üretildi')
    errors, warnings = verify_note(note)
    if warnings:
        print(f'UYARI: {slug}: {", ".join(warnings)} — hub bağlantısı bekleniyor', file=sys.stderr)
    if errors:
        summary = ', '.join(errors[:3]) + (f' (+{len(errors) - 3})' if len(errors) > 3 else '')
        print(f'DOĞRULAMA HATASI: {slug}: {summary} — not stage: inbox kalır', file=sys.stderr)
        lib.append_log('ingest', f'{slug} <- {rel}{suffix} [verify-fail] {summary}',
                       actor=actor)
        return 1
    lib.append_log('ingest', f'{slug} <- {rel}{suffix}', actor=actor)
    return 0


if __name__ == '__main__':
    sys.exit(main())
