"""Public çalışma ağacında e-posta/telefon benzeri metinleri güvenle denetle.

Yalnız Git'in izlediği veya ignore edilmeyen public dosyalar okunur. Bulgular
eşleşen içeriği, satırı veya metadata değerini hiçbir zaman dışarı taşımaz.
"""
import re
import subprocess
from pathlib import Path

import noma_lib as lib


PRIVATE = ('index.md', 'index/', 'raw/', 'wiki/', 'agent/prompts/',
           'agent/sessions/', 'plans/', 'log/')
EXCLUDED = ('tmp/', '.git/', '.env')
BINARY_SUFFIXES = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico',
                   '.zip', '.gz', '.sqlite', '.db', '.pyc', '.woff', '.woff2',
                   '.ttf', '.otf', '.mp3', '.mp4'}
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[A-Za-z]{2,}')
PHONE = re.compile(r'\b0?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b')


def _public(rel):
    """Git yolu (POSIX) özel bir konuma ya da yerel sırlara işaret etmemeli."""
    if not rel or rel.startswith('/') or any(part in ('.', '..') for part in rel.split('/')):
        return False
    name = rel.rsplit('/', 1)[-1]
    if (name == '.env' or name.startswith('.env.')) and name != '.env.example':
        return False
    return not (rel == 'index.md' or rel == '.env' or
                any(rel.startswith(p) for p in PRIVATE if p.endswith('/')) or
                any(rel.startswith(p) for p in EXCLUDED if p.endswith('/')))


def public_paths(root):
    """Git index + ignore edilmeyen untracked dosyalar; gerçek dosya sistemi değil."""
    paths = set()
    for args in (('ls-files', '-z', '--cached'),
                 ('ls-files', '-z', '--others', '--exclude-standard')):
        result = subprocess.run(['git', *args], cwd=root, capture_output=True)
        if result.returncode:
            raise RuntimeError('public Git dosya listesi alınamadı')
        paths.update(p.decode('utf-8', errors='surrogateescape')
                     for p in result.stdout.split(b'\0') if p)
    for rel in sorted(p for p in paths if _public(p)):
        path = root / rel
        # Symlink'leri (dizin bileşenleri dahil) izlemeyerek özel alana kaçışı önle.
        if any(part.is_symlink() for part in (root / rel).parents if part != root):
            continue
        if not path.is_symlink() and path.is_file():
            yield rel, path


def _strip_code(text):
    return lib.strip_code(text)


def _binary(data):
    return any(byte < 32 and byte not in (9, 10, 12, 13) for byte in data)


def scan_public(root):
    """(public yol, sabit tanı) çiftleri döndür; özel içeriği hiçbir zaman döndürme."""
    root = Path(root)
    findings = []
    for rel, path in public_paths(root):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            # Okunamayan public aday sessizce temiz sayılmamalı.
            findings.append((rel, 'public dosya okunamadı'))
            continue
        if _binary(data):
            continue
        try:
            text = _strip_code(data.decode('utf-8'))
        except UnicodeDecodeError:
            continue  # binary / UTF-8 olmayan dosya
        if any('example' not in m.group().lower() for m in EMAIL.finditer(text)):
            findings.append((rel, 'e-posta benzeri metin'))
        if PHONE.search(text):
            findings.append((rel, 'telefon benzeri metin'))
    return findings
