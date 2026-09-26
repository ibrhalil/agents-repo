#!/usr/bin/env python3
"""Hermes düğümünün LLM'siz güvenlik smoke testi.

Tam salt-okunur DEĞİLDİR: tmp/ altına sentetik indeks/not fixture'ları yazar
ve sonunda temizler; Docker/localhost mevcutsa compose çözümleme ve dashboard
HTTP denetimi yapar (--no-llm bunları kapatmaz, yalnız geriye dönük uyumluluk).
Gerçek wiki/raw/log içeriğine yazmaz; hata halinde özel çıktı basmaz.
Docker yoksa Docker'a bağlı kontroller WARN olur; çekirdek testler çalışır.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = ROOT / 'scripts/docker-compose.hermes.yml'
PRIVATE = {'/workspace/index.md', '/workspace/index', '/workspace/wiki', '/workspace/raw',
           '/workspace/log', '/workspace/plans', '/workspace/.env', '/workspace/.git'}
PUBLIC = {'/workspace/AGENTS.md', '/workspace/SCHEMA.md', '/workspace/README.md',
          '/workspace/docs', '/workspace/scripts'}
HOOK_COMMAND = 'python3 /workspace/scripts/noma_hermes_context.py'


def run(args, cwd=ROOT, data=None):
    return subprocess.run(args, cwd=cwd, input=data, capture_output=True, text=True)


def t_index_crypt():
    attr = run(['git', 'check-attr', 'filter', '--', 'index.md'])
    staged = subprocess.run(['git', 'cat-file', 'blob', ':index.md'], cwd=ROOT,
                            capture_output=True)
    ok = (attr.returncode == 0 and attr.stdout.endswith('filter: git-crypt\n')
          and staged.returncode == 0 and staged.stdout.startswith(b'\x00GITCRYPT\x00'))
    return ('PASS' if ok else 'FAIL', 'index.md git-crypt + şifreli staged blob' if ok
            else 'index.md şifreleme denetimi başarısız')


def t_hook_contract():
    """Yerel düğüm LOCAL verir; karar payload cwd'sine DEĞİL hook'un ait olduğu
    köke bağlıdır, bu yüzden kısıtlı dal sentetik şifreli klonla sınanır."""
    hook = str(ROOT / 'scripts/noma_hermes_context.py')
    local = run([sys.executable, '-B', hook], data=json.dumps({'cwd': str(ROOT)}))
    forged = run([sys.executable, '-B', hook], cwd=ROOT / 'scripts',
                 data=json.dumps({'cwd': '/tmp'}))
    locked = None
    with tempfile.TemporaryDirectory(prefix='noma-node-', dir=ROOT / 'tmp') as tmp:
        base = pathlib.Path(tmp) / 'node'
        (base / 'wiki').mkdir(parents=True)
        (base / 'index.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        (base / 'wiki' / 'not.md').write_bytes(b'\x00GITCRYPT\x00sentetik')
        probe = ('import json,sys,runpy,pathlib;'
                 'sys.argv=["hook"];'
                 f'sys.path.insert(0,{str(ROOT / "scripts")!r});'
                 'import noma_hermes_context as h;'
                 f'h.SCRIPT_ROOT=pathlib.Path({str(base)!r});'
                 'sys.stdin=open("/dev/null");'
                 'print(json.dumps({"context":h.LOCAL_CONTEXT if h.unlocked_index({})'
                 ' else h.RESTRICTED_CONTEXT},ensure_ascii=False))')
        locked = subprocess.run([sys.executable, '-B', '-c', probe],
                                cwd=ROOT, capture_output=True, text=True)
    try:
        a = json.loads(local.stdout)['context']
        b = json.loads(forged.stdout)['context']
        c = json.loads(locked.stdout)['context']
    except (ValueError, KeyError):
        return 'FAIL', 'hook JSON sözleşmesi geçersiz'
    ok = (local.returncode == forged.returncode == 0
          and 'index.md' in a and 'yerel düğüm gerekli' in c
          and b == a
          and '## Summary' not in a + b + c and len(a) < 600 and len(b) < 600)
    return ('PASS' if ok else 'FAIL', 'statik context + kısıtlı düğüm yanıtı')


def t_hook_registration():
    """Script testi yetmez: çalışan Hermes hook'u ayrıca onaylamış olmalı."""
    try:
        active = run(['docker', 'ps', '--filter', 'name=^/hermes-dashboard$',
                      '--format', '{{.Names}}'])
        if active.returncode or active.stdout.strip() != 'hermes-dashboard':
            return 'WARN', 'dashboard çalışmıyor; hook kaydı denetlenemedi'
        p = run(['docker', 'exec', 'hermes-dashboard', 'hermes', 'hooks', 'list'])
    except FileNotFoundError:
        return 'WARN', 'Docker kurulu değil; hook kaydı denetlenemedi'
    if p.returncode:
        return 'FAIL', 'Hermes hook listesi okunamadı (özel çıktı gizlendi)'
    block = p.stdout.partition('[pre_llm_call]')[2].split('\n  [', 1)[0]
    ok = any(f'- {HOOK_COMMAND} (' in line and '✓ allowed' in line
             for line in block.splitlines())
    return ('PASS' if ok else 'FAIL', 'Hermes kısıtlı context hook onaylı' if ok
            else 'Hermes context hook eksik veya onaysız')


def t_hub_map():
    """Sayfalı harita ve git-crypt sınırını içerik basmadan doğrula."""
    cli = str(ROOT / 'scripts/noma_wiki.py')
    root = run([sys.executable, '-B', cli, 'root', '--json'])
    try:
        paths = json.loads(root.stdout)
        slug = pathlib.Path(paths[0]).stem
        hub = run([sys.executable, '-B', cli, 'hub', slug, '--json'])
        page = json.loads(hub.stdout)
        attr = run(['git', 'check-attr', 'filter', '--',
                    f'index/hubs/{slug}/000001.md'])
        ok = (root.returncode == hub.returncode == attr.returncode == 0
              and (ROOT / 'index.md').stat().st_size <= 8192
              and attr.stdout.endswith('filter: git-crypt\n')
              and isinstance(page['paths'], list) and len(page['paths']) <= 32
              and all(p.startswith('wiki/') and p.endswith('.md') for p in page['paths'])
              and (page['next_page'] is None or isinstance(page['next_page'], int)))
    except (IndexError, KeyError, OSError, TypeError, ValueError):
        ok = False
    return ('PASS' if ok else 'FAIL', 'kısa kök + şifreli sayfalı hub haritası'
            if ok else 'hub haritası/sınırı geçersiz')


def t_compose():
    try:
        p = run(['docker', 'compose', '-f', str(COMPOSE), '--env-file', '.env',
                 'config', '--format', 'json'])
    except FileNotFoundError:
        return 'WARN', 'Docker kurulu değil'
    if p.returncode:
        return 'FAIL', 'compose config geçersiz (özel çıktı gizlendi)'
    try:
        services = json.loads(p.stdout)['services']
        paths = []
        homes = []
        for name in ('hermes', 'dashboard'):
            mounts = services[name]['volumes']
            mounted = {v['target'] for v in mounts}
            paths.append(mounted == PUBLIC | {'/opt/data'}
                         and not mounted & PRIVATE
                         and all(v['read_only'] for v in mounts
                                 if v['target'].startswith('/workspace')))
            homes.extend(v['source'] for v in mounts if v['target'] == '/opt/data')
        ok = all(paths) and all(home.endswith('.hermes-cloud') for home in homes)
    except (KeyError, TypeError, ValueError):
        ok = False
    return ('PASS' if ok else 'FAIL', 'bulut mount sınırı' if ok
            else 'özel mount/home saptandı')


def t_lint():
    p = run([sys.executable, '-B', str(ROOT / 'scripts/noma_lint.py')])
    return ('PASS' if p.returncode == 0 else 'FAIL',
            'linter ERR=0' if p.returncode == 0 else 'linter hata verdi (özel çıktı gizlendi)')


def t_dashboard():
    try:
        with urllib.request.urlopen('http://127.0.0.1:9119', timeout=3) as response:
            return ('PASS', 'yerel dashboard HTTP 200') if response.status == 200 else (
                'WARN', 'dashboard beklenmeyen HTTP durumu')
    except Exception:
        return 'WARN', 'dashboard çalışmıyor veya erişilemiyor'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--no-llm', action='store_true', help='geriye dönük uyumluluk; test zaten LLM kullanmaz')
    ap.parse_args()
    checks = [('index_crypt', t_index_crypt), ('hub_map', t_hub_map),
              ('hook', t_hook_contract), ('hook_runtime', t_hook_registration),
              ('compose_cloud', t_compose), ('lint', t_lint), ('dashboard', t_dashboard)]
    failed = False
    for name, check in checks:
        try:
            status, detail = check()
        except Exception:
            status, detail = 'FAIL', 'istisna (özel çıktı gizlendi)'
        print(f'{status:4} {name:18} {detail}')
        failed |= status == 'FAIL'
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
