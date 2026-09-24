#!/usr/bin/env python3
"""AGENTS lint() mekanik kontrolleri (ERR=ihlal, WRN=yorum insan'a, INFO=bilgi).
Exit 1 iff ERR > 0; cron ve pre-commit bu sözleşmeye bağlanır."""
import re, subprocess, sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = 'concept project task issue resource person decision'.split()
STAGES = 'inbox next in_progress waiting done archived'.split()
SCOPES = 'work personal learning systems creator media common'.split()
STATUS = 'unverified established stub'.split()
ORDER = 'title type stage scope status tags created updated locked'.split()
ISO_DT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)')
ENCRYPTED = ['raw/', 'wiki/', 'agent/prompts/', 'agent/sessions/', 'plans/', 'log/']
BUDGETS = {'AGENTS.md': 100, 'SCHEMA.md': 140}
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[A-Za-z]{2,}')
PHONE = re.compile(r'\b0?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b')
err = wrn = 0
out = []

def add(sev, code, msg):
    global err, wrn
    if sev == 'ERR': err += 1
    elif sev == 'WRN': wrn += 1
    out.append(f'{sev} {code}: {msg}')

def parse_fm(text):
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not m: return None, None
    d, order = {}, []
    for line in m.group(1).splitlines():
        if line.startswith((' ', '#')): continue
        mm = re.match(r'^([A-Za-z_][\w-]*):(.*)$', line)
        if mm: d[mm.group(1)] = mm.group(2).strip(); order.append(mm.group(1))
    return d, order

def strip_code(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    return re.sub(r'`[^`\n]*`', '', text)

for f, n in BUDGETS.items():
    c = len((ROOT / f).read_text(encoding='utf-8').splitlines())
    sev = 'ERR' if c > n else 'INFO'
    add(sev, 'BUDGET', f'{f}: {c}/{n} satır')

wiki = sorted((ROOT / 'wiki').glob('*.md'))
links_in, links_out, tree_out = {}, {}, {}
for p in wiki:
    rel = f'wiki/{p.name}'
    text = p.read_text(encoding='utf-8')
    fm, order = parse_fm(text)
    if fm is None:
        add('ERR', 'FM', f'{rel}: frontmatter yok'); continue
    for k in ('title', 'type', 'stage', 'scope'):
        if not fm.get(k): add('ERR', 'FM', f'{rel}: zorunlu alan {k} yok')
    for k, ok in (('type', TYPES), ('stage', STAGES), ('scope', SCOPES),
                  ('status', STATUS)):
        v = fm.get(k, '').strip('"')
        if v and v not in ok: add('ERR', 'ENUM', f'{rel}: {k}={v}')
    idx = [ORDER.index(f2) for f2 in order if f2 in ORDER]
    if idx != sorted(idx): add('ERR', 'ORDER', f'{rel}: frontmatter sırası {order}')
    for k in ('created', 'updated'):
        if fm.get(k) and not ISO_DT.fullmatch(fm[k]):
            add('ERR', 'DATE', f'{rel}: {k}={fm.get(k)} (ISO 8601 date/datetime değil)')
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*\.md', p.name):
        add('ERR', 'SLUG', f'{rel}: ASCII kebab-case değil')
    body = strip_code(text)
    links_out[rel] = {s.strip().rstrip('\\') for s in re.findall(r'\[\[([^\]|#]+)', body)}
    for s in links_out[rel]: links_in.setdefault(s.lower(), set()).add(rel)
    sec = re.search(r'## Links\n(.*?)(?=\n## )', text, re.S)
    if sec: tree_out[p.stem] = {s.strip().rstrip('\\') for s in re.findall(r'\[\[([^\]|#]+)', sec.group(1))}
    st = fm.get('stage', '')
    upd = (fm.get('updated') or '')[:10]
    if st in ('inbox', 'next', 'in_progress', 'waiting'):
        try:
            if date.fromisoformat(upd) < date.today() - timedelta(days=30):
                add('WRN', 'STALE', f'{rel}: stage={st} ama updated={upd} (30+ gün, tend adayı)')
        except ValueError: pass
    r = subprocess.run(['git', 'log', '-1', '--format=%as', '--', str(p)],
                       cwd=ROOT, capture_output=True, text=True)
    last = r.stdout.strip()
    if last and fm.get('updated', '') < last:
        add('ERR', 'BUMP', f'{rel}: updated={fm.get("updated")} < son commit {last}')

for p in wiki:
    if not links_out.get(f'wiki/{p.name}') and not links_in.get(p.stem):
        add('INFO', 'ORPHAN', f'wiki/{p.name} (bilgi: bağlantısız not)')

for rel, slugs in links_out.items():
    for s in slugs:
        if not (ROOT / 'wiki' / f'{s}.md').exists():
            add('ERR', 'LINK', f'{rel}: [[{s}]] hedefi yok')

for a, outs in tree_out.items():
    for b in outs:
        if b in tree_out and a in tree_out[b] and a < b:
            add('WRN', 'CYCLE', f'wiki/{a}.md <-> wiki/{b}.md karşılıklı Links (Tree ihlali)')

for p in ROOT.rglob('*_v[0-9]*.md'):
    if '.git' not in p.parts: add('ERR', 'SUFFIX', str(p.relative_to(ROOT)))
for p in ROOT.rglob('*_yeni*.md'):
    if '.git' not in p.parts: add('ERR', 'SUFFIX', str(p.relative_to(ROOT)))

LOG_LINE = re.compile(r'\d{2}:\d{2} (ingest|query|tend|lint|sync) @[\w-]+(?: [\w.-]+)? \| (.+)')
for p in sorted((ROOT / 'log').glob('*.md')):
    if p.name == 'log.md': continue
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.md', p.name):
        add('ERR', 'LOGF', f'log/{p.name}: dosya adı YYYY-MM-DD.md değil'); continue
    in_comment = False
    for line in p.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if '<!--' in s: in_comment = True
        if in_comment:
            if '-->' in s: in_comment = False
            continue
        if not s or s.startswith('#'): continue
        m = LOG_LINE.fullmatch(s)
        if not m: add('ERR', 'LOGF', f'log/{p.name}: satır formatı hatalı: {s[:60]}')
        elif len(m.group(2)) > 120: add('ERR', 'LOGB', f'log/{p.name}: mesaj >120 karakter')

ga = (ROOT / '.gitattributes').read_text(encoding='utf-8')
crypt_globs = [l.split()[0] for l in ga.splitlines()
               if 'git-crypt' in l and not l.startswith('#') and l.strip()]
for d in ENCRYPTED:
    if not any(c.rstrip('*').rstrip('/') == d.rstrip('/') for c in crypt_globs):
        add('ERR', 'CRYPT', f'.gitattributes: {d} şifreli globu yok')
for c in crypt_globs:
    if c.rstrip('*').rstrip('/') + '/' not in ENCRYPTED:
        add('WRN', 'CRYPT', f'.gitattributes: beklenmedik glob {c}')

files = [ROOT / f for f in ('README.md', 'AGENTS.md', 'SCHEMA.md', '.env.example')]
for d in ('docs', 'scripts'):
    files += [q for q in (ROOT / d).rglob('*') if q.is_file()]
for p in files:
    if not p.exists(): continue
    t = strip_code(p.read_text(encoding='utf-8', errors='ignore'))
    for m in EMAIL.finditer(t):
        if 'example' not in m.group():
            add('WRN', 'PRIV', f'{p.relative_to(ROOT)}: e-posta benzeri {m.group()}')
    for m in PHONE.finditer(t):
        add('WRN', 'PRIV', f'{p.relative_to(ROOT)}: telefon benzeri {m.group()}')

try:
    import build_index
    if (ROOT / 'index.md').read_text(encoding='utf-8') != build_index.generate():
        add('WRN', 'INDEX', 'index.md bayat — python3 scripts/build_index.py ile yeniden üretilmeli')
except Exception as e:
    add('WRN', 'INDEX', f'denetlenemedi: {e}')

print('\n'.join(out) if out else 'temiz')
print(f'\n== {err} ERR · {wrn} WRN · {sum(o.startswith("INFO") for o in out)} INFO ==')
sys.exit(1 if err else 0)
