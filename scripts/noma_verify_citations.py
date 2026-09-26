#!/usr/bin/env python3
"""Yanıt atıf doğrulayıcı: yanıt metnindeki wiki/raw/log/plans atıflarını
mekanik denetler.

Kural tabanlıdır, LLM yargısı yoktur (üretici-doğrulayıcı ayrımı). Not içeriği
çıktıya asla taşınmaz (AGENTS R4); yalnız yol + kural adı + toplam sayı basılır.
Kırık/ilgisiz/dışarı atıf exit 1; negatif iddia hatırlatması exit 0.
"""
import argparse
import json
import re
import sys
from pathlib import PurePosixPath

import noma_lib as lib

CITATION = re.compile(r'\b(?:wiki|raw|log|plans)/[\w./-]+\.\w+')
# Uzantısız kaçış denemeleri de yakalanır; hiçbiri okunmaz.
TRAVERSAL = re.compile(r'\b(?:wiki|raw|log|plans)/[\w./-]*\.\.[\w./-]*')
NEGATIVE_CLAIM = re.compile(r'kay[iı]tl[iı] deg[iı]l', re.I)
# Gerekçeleme yalnız not/ham kaynak için anlamlı; log ve plans kayıt defteridir.
RELEVANCE_DIRS = ('wiki/', 'raw/')


def _resolve(path):
    """(hedef, kök_dışı_mı) — '..' taşıyan veya kökü aşan atıf asla okunmaz."""
    if '..' in PurePosixPath(path).parts or PurePosixPath(path).is_absolute():
        return None, True
    try:
        root = lib.ROOT.resolve()
        resolved = (lib.ROOT / path).resolve()
    except OSError:
        return None, True
    if resolved != root and root not in resolved.parents:
        return None, True
    return lib.ROOT / path, False


def _upper_region(text):
    clean = lib.strip_code(text)
    fm = lib.parse_fm(text) or {}
    summary_m = re.search(r'## Summary\n(.*?)(?=\n## |\Z)', clean, re.S)
    parts = [text.split('---', 2)[0], fm.get('title', ''), fm.get('tags', ''),
             summary_m.group(1) if summary_m else '']
    return lib.fold_tr(' '.join(parts))


def _sentence_terms(sentence):
    words = re.findall(r'[a-z0-9]+', lib.fold_tr(sentence))
    return [w for w in dict.fromkeys(words)
            if len(w) >= 4 and w not in lib.SEARCH_STOPWORDS]


def _overlap(term, region):
    if term in region:
        return True
    stem = term[:5] if len(term) >= 6 else term
    return any(word.startswith(stem) for word in re.findall(r'[a-z0-9]+', region))


def verify(text, idx=None):
    """Yanıt metnini denetle → (bulgular, negatif_iddia). idx geçmiş uyumluluk
    için kabul edilir; gerekçeleme dosyanın kendi üst bölgesinden türetilir,
    içerik döndürülmez."""
    upper = {}
    findings, cited = [], []
    for sentence in re.split(r'(?<=[.!?\n])\s+', text):
        candidates = list(CITATION.findall(sentence))
        candidates += [t.rstrip('.,;:)\'"') for t in TRAVERSAL.findall(sentence)]
        for path in dict.fromkeys(candidates):
            if path in cited:
                continue
            cited.append(path)
            target, outside = _resolve(path)
            if outside:
                findings.append({'path': path, 'status': 'FAIL', 'rule': 'yol-dışı-atıf'})
                continue
            if not target.is_file():
                findings.append({'path': path, 'status': 'FAIL', 'rule': 'kırık-atıf'})
                continue
            if path.startswith(RELEVANCE_DIRS):
                if path not in upper:
                    try:
                        upper[path] = _upper_region(target.read_text(encoding='utf-8'))
                    except (OSError, UnicodeError):
                        upper[path] = None
                region = upper[path]
                if region is None:
                    # Hedef VAR ama okunamıyor (izin/kilitli blob): doğrulanmış
                    # sayılmaz — sessiz OK yanlış güven üretir.
                    findings.append({'path': path, 'status': 'WARN',
                                     'rule': 'okunamayan-atıf'})
                    continue
                terms = _sentence_terms(sentence)
                related = any(_overlap(t, region) for t in terms) if terms else True
                if not related:
                    findings.append({'path': path, 'status': 'WARN',
                                     'rule': 'ilgisiz-atıf'})
                    continue
            findings.append({'path': path, 'status': 'OK', 'rule': ''})
    return findings, bool(NEGATIVE_CLAIM.search(lib.fold_tr(text)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file', nargs='?', help='yanıt dosyası; verilmezse stdin')
    ap.add_argument('--json', action='store_true', help='makine okunur çıktı')
    a = ap.parse_args()
    try:
        if a.file:
            with open(a.file, encoding='utf-8') as handle:
                text = handle.read()
        else:
            text = sys.stdin.read()
    except (OSError, UnicodeError):
        print('yanıt okunamadı', file=sys.stderr)
        return 2
    findings, negative = verify(text)
    broken = sum(f['status'] == 'FAIL' for f in findings)
    warned = sum(f['status'] == 'WARN' for f in findings)
    if a.json:
        print(json.dumps({'citations': findings,
                          'negative_claim': negative,
                          'broken': broken, 'warned': warned}, ensure_ascii=False))
    else:
        for f in findings:
            mark = {'OK': 'OK', 'FAIL': 'FAIL', 'WARN': 'WARN'}[f['status']]
            print(f"{mark:4} {f['path']}" + (f" · {f['rule']}" if f['rule'] else ''))
        if negative:
            print('BİLGİ: negatif iddia var — "kayıtlı değil" ancak kanıt okunarak söylenir')
        print(f'== {len(findings)} atıf · {broken} kırık · {warned} uyarı ==')
    return 1 if broken or warned else 0


if __name__ == '__main__':
    sys.exit(main())
