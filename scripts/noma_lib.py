"""Agent scriptlerinin paylaşılan yardımcıları (stdlib only).
Sabitler SCHEMA.md'den alınmıştır; noma_lint.py ile tutarlı tutulur."""
import os
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = 'concept project task issue resource person decision'.split()
STAGES = 'inbox next in_progress waiting done archived'.split()
SCOPES = 'work personal learning systems creator media common'.split()
STATUS = 'unverified established stub'.split()
LOG_OPS = 'ingest query tend lint sync'.split()
MSG_LIMIT = 120
LOG_LINE = re.compile(r'\d{2}:\d{2} (ingest|query|tend|lint|sync) @[\w-]+(?: [\w./-]+)? \| (.+)')
SLUG_RE = re.compile(r'[a-z0-9]+(-[a-z0-9]+)*')
TR = str.maketrans({'ı': 'i', 'İ': 'I', 'ş': 's', 'Ş': 'S', 'ğ': 'g', 'Ğ': 'G',
                    'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'})


def slugify(text):
    s = text.translate(TR).lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def check_slug(slug):
    if not SLUG_RE.fullmatch(slug) or re.search(r'_v[0-9]|_yeni', slug):
        raise SystemExit(f'hata: slug="{slug}" ASCII kebab-case olmalı (_v2/_yeni yasak)')
    return slug


def check_choice(name, value, ok):
    if value is not None and value not in ok:
        raise SystemExit(f'hata: {name}={value} (geçerli: {"|".join(ok)})')


def today():
    return date.today().isoformat()


def iso_now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def now_stamp():
    return datetime.now().strftime('%Y-%m-%d-%H%M')


def now_hhmm():
    return datetime.now().strftime('%H:%M')


def node_id():
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            m = re.match(r'\s*(?:export\s+)?NODE_ID\s*=\s*(\S+)', line)
            if m:
                return m.group(1)
    return os.environ.get('NODE_ID', 'local')


def parse_fm(text):
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not m:
        return None
    d = {}
    for line in m.group(1).splitlines():
        if line.startswith((' ', '#')):
            continue
        mm = re.match(r'^([A-Za-z_][\w-]*):(.*)$', line)
        if mm:
            d[mm.group(1)] = mm.group(2).strip()
    return d


def needs_updated_bump(current, previous):
    """Gövde aynı gün değişse bile eski updated damgasını kabul etme."""
    old = parse_fm(previous)
    new = parse_fm(current)
    return bool(old and new and current != previous
                and new.get('updated', '') <= old.get('updated', ''))


def parse_tags(raw):
    if not raw:
        return None
    seen = []
    for t in raw.split(','):
        t = slugify(t)
        if t and t not in seen:
            seen.append(t)
    return seen or None


LINK_RE = re.compile(r'\[\[([^\]|#]+)')


def strip_code(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    return re.sub(r'`[^`\n]*`', '', text)


def fold_tr(text):
    """Türkçe karakter katlama: 'yapıtaşları' → 'yapitaslari'."""
    return text.translate(TR).lower()


def load_wiki_index(with_body=False):
    """wiki/*.md → {slug: {fm, tags, out, parents[, fields]}}.
    out: koddan arındırılmış tüm [[link]] hedefleri;
    parents: ## Links bölümündeki hedefler (ağaç yönü);
    fields: with_body=True ise skorlama için katlanmış alan metinleri."""
    idx = {}
    for p in sorted((ROOT / 'wiki').glob('*.md')):
        text = p.read_text(encoding='utf-8')
        fm = parse_fm(text) or {}
        clean = strip_code(text)
        links_m = re.search(r'## Links\n(.*?)(?=\n## |\Z)', clean, re.S)
        parents = [s.strip() for s in LINK_RE.findall(links_m.group(1))] if links_m else []
        entry = {'fm': fm,
                 'tags': [t.strip() for t in fm.get('tags', '').strip('[]')
                          .replace('"', '').split(',') if t.strip()],
                 'out': {s.strip() for s in LINK_RE.findall(clean)} | set(parents),
                 'parents': parents}
        if with_body:
            summary_m = re.search(r'## Summary\n(.*?)(?=\n## |\Z)', clean, re.S)
            entry['fields'] = {
                'slug': fold_tr(p.stem),
                'title': fold_tr(fm.get('title', '').strip('"')),
                'tags': fold_tr(fm.get('tags', '')),
                'summary': fold_tr(summary_m.group(1) if summary_m else ''),
                'body': fold_tr(clean),
            }
        idx[p.stem] = entry
    return idx


def append_log(op, msg, actor=None):
    if op not in LOG_OPS:
        raise SystemExit(f'hata: op={op} (geçerli: {"|".join(LOG_OPS)})')
    if actor is not None and not re.fullmatch(r'[\w./-]+', actor):
        raise SystemExit('hata: aktör biçimi geçersiz (harf/rakam/nokta/tire/slash)')
    msg = ' '.join(msg.split())
    if len(msg) > MSG_LIMIT:
        raise SystemExit(f'hata: log mesajı {len(msg)} karakter (> {MSG_LIMIT})')
    p = ROOT / 'log' / f'{today()}.md'
    if not p.exists():
        p.write_text(f'# {today()}\n', encoding='utf-8')
    who = f' {actor}' if actor else ''
    with p.open('a', encoding='utf-8') as f:
        f.write(f'{now_hhmm()} {op} @{node_id()}{who} | {msg}\n')
    return p


def log_issues(path):
    """Günlük biçimini denetle; özel satır metnini tanıya ASLA ekleme."""
    in_comment = False
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        s = line.strip()
        if '<!--' in s:
            in_comment = True
        if in_comment:
            if '-->' in s:
                in_comment = False
            continue
        if not s or s.startswith('#'):
            continue
        match = LOG_LINE.fullmatch(s)
        if not match:
            yield ('LOGF', number)
        elif len(match.group(2)) > MSG_LIMIT:
            yield ('LOGB', number)


def render_note(slug, title, type_, scope, stage='inbox', status=None,
                tags=None, source_path=None):
    """docs/templates/wiki_note.md'den doldurulmuş not içeriği üretir (AGENTS R5).
    Verilmeyen opsiyonel alanlar yazılmaz — yalnız anlamlı alan (SCHEMA §6)."""
    title = title.replace('"', "'")
    tpl = (ROOT / 'docs/templates/wiki_note.md').read_text(encoding='utf-8')
    body = tpl.split('---', 2)[2].lstrip('\n').replace('{{Görünen Başlık}}', title)
    if source_path:
        body = body.rstrip('\n') + f'\n\nKaynak: {source_path}\n'
    fm = ['---', f'title: "{title}"', f'type: {type_}', f'stage: {stage}',
          f'scope: {scope}']
    if status:
        fm.append(f'status: {status}')
    if tags:
        fm.append('tags: [' + ', '.join(tags) + ']')
    fm += [f'created: {iso_now()}', f'updated: {iso_now()}', '---']
    return '\n'.join(fm) + '\n' + body
