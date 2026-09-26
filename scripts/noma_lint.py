#!/usr/bin/env python3
"""AGENTS lint() mekanik kontrolleri (ERR=ihlal, WRN=yorum insan'a, INFO=bilgi).
Exit 1 iff ERR > 0; cron ve pre-commit bu sözleşmeye bağlanır."""
import os, re, subprocess, sys
from datetime import date, datetime, timedelta
from pathlib import Path

import noma_lib as lib

ROOT = Path(__file__).resolve().parent.parent
# B5 drift riski: aşağıdaki sabitler ve parse_fm, noma_lib kopyalarıdır. Birleştirilecek
# semboller: lib.TYPES, lib.STAGES, lib.SCOPES, lib.STATUS, lib.parse_fm — parse_fm dönüş
# şekli bile ayrışık (burada (dict, order), lib'de dict | None).
TYPES = 'concept project task issue resource person decision'.split()
STAGES = 'inbox next in_progress waiting done archived'.split()
SCOPES = 'work personal learning systems creator media common'.split()
STATUS = 'unverified established stub'.split()
ORDER = 'title type stage scope status tags created updated locked'.split()
ISO_DT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)')
ENCRYPTED = ['index.md', 'index/', 'raw/', 'wiki/', 'agent/prompts/', 'agent/sessions/', 'plans/', 'log/']
BUDGETS = {'AGENTS.md': 100, 'SCHEMA.md': 140}
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[A-Za-z]{2,}')
PHONE = re.compile(r'\b0?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b')
GITCRYPT_MAGIC = b'\x00GITCRYPT\x00'
SKIP_DIRS = {'.git', 'node_modules', 'tmp'}
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

def _gitcrypt_blob(data):
    return data.startswith(GITCRYPT_MAGIC)

def _unverifiable(data):
    """Şifreli ya da çözülemeyen yük kanıt değildir: doğrulama yapılamadı demektir."""
    if _gitcrypt_blob(data):
        return True
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return True
    return False

def _head_payload(rel):
    """HEAD:<rel> sürümünü bayt olarak döndürür; HEAD'de yoksa None."""
    r = subprocess.run(['git', 'cat-file', '--filters', f'HEAD:{rel}'],
                       cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None

def check_budgets():
    for f, n in BUDGETS.items():
        c = len((ROOT / f).read_text(encoding='utf-8').splitlines())
        sev = 'ERR' if c > n else 'INFO'
        add(sev, 'BUDGET', f'{f}: {c}/{n} satır')

def check_wiki(wiki):
    links_in, links_out, tree_out = {}, {}, {}
    for p in wiki:
        rel = f'wiki/{p.name}'
        text = p.read_text(encoding='utf-8')
        fm, order = parse_fm(text)
        if fm is None:
            add('ERR', 'FM', f'{rel}: frontmatter yok'); continue
        for k in ('title', 'type', 'stage', 'scope', 'created', 'updated'):
            if not fm.get(k): add('ERR', 'FM', f'{rel}: zorunlu alan {k} yok')
        for k, ok in (('type', TYPES), ('stage', STAGES), ('scope', SCOPES),
                      ('status', STATUS)):
            v = fm.get(k, '').strip('"')
            if v and v not in ok: add('ERR', 'ENUM', f'{rel}: geçersiz {k}')
        idx = [ORDER.index(f2) for f2 in order if f2 in ORDER]
        if idx != sorted(idx): add('ERR', 'ORDER', f'{rel}: frontmatter sırası {order}')
        for k in ('created', 'updated'):
            if fm.get(k):
                try:
                    if not ISO_DT.fullmatch(fm[k]): raise ValueError
                    datetime.fromisoformat(fm[k].replace('Z', '+00:00'))
                except ValueError:
                    add('ERR', 'DATE', f'{rel}: {k} geçerli ISO 8601 zaman damgası değil')
        if fm.get('created') and fm.get('updated') and fm['updated'] < fm['created']:
            add('ERR', 'DATE', f'{rel}: updated created öncesinde')
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*\.md', p.name):
            add('ERR', 'SLUG', f'{rel}: ASCII kebab-case değil')
        body = strip_code(text)
        links_out[rel] = {s.strip().rstrip('\\') for s in re.findall(r'\[\[([^\]|#]+)', body)}
        for s in links_out[rel]: links_in.setdefault(s.lower(), set()).add(rel)
        links_m = re.search(r'^## Links[ \t]*$', body, re.M)
        if not links_m:
            add('ERR', 'STRUCT', f'{rel}: ## Links bölümü yok (SCHEMA §4)')
        else:
            tail = body[links_m.end():]
            nxt = re.search(r'^## ([^\n]+)', tail, re.M)
            if not nxt or nxt.group(1).strip() != 'Summary':
                got = nxt.group(1).strip() if nxt else '(son)'
                add('ERR', 'STRUCT', f'{rel}: ## Links sonrası {got} — ## Summary beklenir (SCHEMA §4)')
            sec_text = tail[:nxt.start()] if nxt else tail
            tree_out[p.stem] = {s.strip().rstrip('\\') for s in re.findall(r'\[\[([^\]|#]+)', sec_text)}
        st = fm.get('stage', '')
        upd = (fm.get('updated') or '')[:10]
        if st in ('inbox', 'next', 'in_progress', 'waiting'):
            try:
                if date.fromisoformat(upd) < date.today() - timedelta(days=30):
                    add('WRN', 'STALE', f'{rel}: stage={st} ama updated={upd} (30+ gün, tend adayı)')
            except ValueError: pass
        # Git'in şifre çözme filtresi üzerinden önceki notu içeride karşılaştır;
        # eski notun hiçbir satırını stdout/stderr'e yansıtma.
        payload = _head_payload(rel)
        if payload is not None and _unverifiable(payload):
            # smudge kapalı düğümde blob şifreli gelir; sahte yeşil yerine ERR CRYPT
            # (aynı sertlikte: "git-crypt filtresi etkin değil").
            add('ERR', 'CRYPT', f'{rel}: HEAD sürümü çözülemedi; BUMP/LOCKED doğrulanamadı')
        elif payload is not None and payload.decode('utf-8') != text:
            previous_text = payload.decode('utf-8')
            previous, _ = parse_fm(previous_text)
            if lib.needs_updated_bump(text, previous_text):
                add('ERR', 'BUMP', f'{rel}: değişiklik var, updated artırılmadı')
            if previous and previous.get('locked') == 'true':
                add('WRN', 'LOCKED', f'{rel}: locked not değişmiş; insan değişikliği doğrulansın')
    return links_in, links_out, tree_out

def check_graph(wiki, links_in, links_out, tree_out):
    existing = {p.stem for p in wiki}
    for p in wiki:
        if not (links_out.get(f'wiki/{p.name}', set()) & existing) and not links_in.get(p.stem):
            add('INFO', 'ORPHAN', f'wiki/{p.name} (bilgi: bağlantısız not)')
    for rel, slugs in links_out.items():
        for s in slugs:
            if not (ROOT / 'wiki' / f'{s}.md').exists():
                add('ERR', 'LINK', f'{rel}: [[{s}]] hedefi yok')
    for a, outs in tree_out.items():
        for b in outs:
            if b in tree_out and a in tree_out[b] and a < b:
                add('WRN', 'CYCLE', f'wiki/{a}.md <-> wiki/{b}.md karşılıklı Links (Tree ihlali)')

def walk_md(root):
    """node_modules/.git/tmp ve nokta dizinlerine inmeden md dosyalarını verir."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and not d.startswith('.'))
        for name in sorted(filenames):
            if name.endswith('.md'):
                yield Path(dirpath) / name

def check_suffixes():
    for p in walk_md(ROOT):
        if re.fullmatch(r'.*_v[0-9].*\.md', p.name) or re.fullmatch(r'.*_yeni.*\.md', p.name):
            add('ERR', 'SUFFIX', str(p.relative_to(ROOT)))

def check_logs():
    for p in sorted((ROOT / 'log').glob('*.md')):
        if p.name == 'log.md': continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.md', p.name):
            add('ERR', 'LOGF', f'log/{p.name}: dosya adı YYYY-MM-DD.md değil'); continue
        for code, number in lib.log_issues(p):
            detail = 'satır formatı hatalı' if code == 'LOGF' else 'mesaj >120 karakter'
            add('ERR', code, f'log/{p.name}:{number}: {detail}')

def check_gitattributes():
    ga = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    crypt_globs = [l.split()[0] for l in ga.splitlines()
                   if 'git-crypt' in l and not l.startswith('#') and l.strip()]
    for d in ENCRYPTED:
        if not any(c.rstrip('*').rstrip('/') == d.rstrip('/') for c in crypt_globs):
            add('ERR', 'CRYPT', f'.gitattributes: {d} şifreli globu yok')
    for c in crypt_globs:
        if c.rstrip('*').rstrip('/') not in [d.rstrip('/') for d in ENCRYPTED]:
            add('WRN', 'CRYPT', f'.gitattributes: beklenmedik glob {c}')

def check_tracked():
    tracked = [rel for rel in subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                                             capture_output=True).stdout.decode('utf-8').split('\0')
               if rel and not rel.endswith('.gitkeep')]
    crypted = [rel for rel in tracked
               if rel == 'index.md' or any(rel.startswith(d) for d in ENCRYPTED if d.endswith('/'))]
    if crypted:
        r = subprocess.run(['git', 'check-attr', '--stdin', '-z', 'filter'], cwd=ROOT,
                           input='\0'.join(crypted) + '\0', capture_output=True, encoding='utf-8')
        fields = r.stdout.split('\0')
        filters = {fields[i]: fields[i + 2] for i in range(0, len(fields) - 2, 3)}
        for rel in crypted:
            if filters.get(rel) != 'git-crypt':
                add('ERR', 'CRYPT', f'{rel}: git-crypt filtresi etkin değil')
    for rel in tracked:
        if not rel.startswith(('raw/', 'log/')):
            continue
        previous = _head_payload(rel)
        if previous is None:
            continue
        if _unverifiable(previous):
            # Şifreli önceki sürüm fark kanıtı değildir; sahte APPEND yerine ERR CRYPT.
            add('ERR', 'CRYPT', f'{rel}: HEAD sürümü çözülemedi; APPEND doğrulanamadı')
            continue
        current = ROOT / rel
        if not current.is_file():
            add('ERR', 'APPEND', f'{rel}: izlenen kaynak silinmiş')
            continue
        data = current.read_bytes()
        if rel.startswith('raw/') and data != previous:
            add('ERR', 'APPEND', f'{rel}: raw dosyası değiştirilmiş')
        if rel.startswith('log/') and not data.startswith(previous):
            add('ERR', 'APPEND', f'{rel}: günlük log kısaltılmış/değiştirilmiş')
    staged_index = subprocess.run(['git', 'cat-file', 'blob', ':index.md'],
                                  cwd=ROOT, capture_output=True).stdout
    if staged_index and not _gitcrypt_blob(staged_index):
        add('ERR', 'CRYPT', 'index.md: staged Git blob şifreli değil; git add --renormalize index.md')

def check_privacy():
    files = [ROOT / f for f in ('README.md', 'AGENTS.md', 'SCHEMA.md', '.env.example')]
    for d in ('docs', 'scripts'):
        files += [q for q in (ROOT / d).rglob('*') if q.is_file()]
    for p in files:
        if not p.exists(): continue
        t = strip_code(p.read_text(encoding='utf-8', errors='ignore'))
        for m in EMAIL.finditer(t):
            if 'example' not in m.group():
                add('WRN', 'PRIV', f'{p.relative_to(ROOT)}: e-posta benzeri metin')
        for m in PHONE.finditer(t):
            add('WRN', 'PRIV', f'{p.relative_to(ROOT)}: telefon benzeri metin')

def check_index():
    try:
        import noma_build_index as build_index
        expected_root, expected_pages = build_index.generate_all()
        if (ROOT / 'index.md').read_text(encoding='utf-8') != expected_root:
            add('WRN', 'INDEX', 'index.md bayat — python3 scripts/noma_build_index.py ile yeniden üretilmeli')
        actual_pages = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / 'index/hubs').glob('*/*.md')}
        missing = set(expected_pages) - set(actual_pages)
        extra = set(actual_pages) - set(expected_pages)
        stale = sum(actual_pages[rel].read_text(encoding='utf-8') != content
                    for rel, content in expected_pages.items() if rel in actual_pages)
        if missing or extra or stale:
            add('WRN', 'INDEX', f'hub haritaları bayat: eksik={len(missing)} fazla={len(extra)} farklı={stale}')
    except Exception:
        add('WRN', 'INDEX', 'index denetlenemedi (ayrıntı özel çıktıya taşınmaz)')

def main():
    global err, wrn
    err = wrn = 0
    del out[:]
    check_budgets()
    wiki = sorted((ROOT / 'wiki').glob('*.md'))
    links_in, links_out, tree_out = check_wiki(wiki)
    check_graph(wiki, links_in, links_out, tree_out)
    check_suffixes()
    check_logs()
    check_gitattributes()
    check_tracked()
    check_privacy()
    check_index()
    print('\n'.join(out) if out else 'temiz')
    print(f'\n== {err} ERR · {wrn} WRN · {sum(o.startswith("INFO") for o in out)} INFO ==')
    return 1 if err else 0

if __name__ == '__main__':
    sys.exit(main())
