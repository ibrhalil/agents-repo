#!/usr/bin/env python3
"""Hermes düğümünün salt-okunur, LLM'siz güvenlik smoke testi.

Not oluşturmaz/silmez, bulut modeli çağırmaz ve hata halinde özel çıktı basmaz.
Docker yoksa Docker'a bağlı kontroller WARN olur; çekirdek testler çalışır.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = ROOT / 'scripts/docker-compose.hermes.yml'
PRIVATE = {'/workspace/index.md', '/workspace/wiki', '/workspace/raw',
           '/workspace/log', '/workspace/plans', '/workspace/.env', '/workspace/.git'}
PUBLIC = {'/workspace/AGENTS.md', '/workspace/SCHEMA.md', '/workspace/README.md',
          '/workspace/docs', '/workspace/scripts'}


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
    hook = str(ROOT / 'scripts/noma_hermes_context.py')
    local = run([sys.executable, '-B', hook], data=json.dumps({'cwd': str(ROOT)}))
    restricted = run([sys.executable, '-B', hook], cwd=ROOT / 'scripts',
                     data=json.dumps({'cwd': str(ROOT / 'scripts')}))
    try:
        a = json.loads(local.stdout)['context']
        b = json.loads(restricted.stdout)['context']
    except (ValueError, KeyError):
        return 'FAIL', 'hook JSON sözleşmesi geçersiz'
    ok = (local.returncode == restricted.returncode == 0
          and 'index.md' in a and 'yerel düğüm gerekli' in b
          and '## Summary' not in a + b and len(a) < 600 and len(b) < 600)
    return ('PASS' if ok else 'FAIL', 'statik context + kısıtlı düğüm fail-closed')


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
    checks = [('index_crypt', t_index_crypt), ('hook', t_hook_contract),
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
