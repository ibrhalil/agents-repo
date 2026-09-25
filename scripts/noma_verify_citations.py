#!/usr/bin/env python3
"""Yanıt atıf doğrulayıcı: yanıt metnindeki wiki/raw atıflarını mekanik denetler.

Kural tabanlıdır, LLM yargısı yoktur (üretici-doğrulayıcı ayrımı). Not içeriği
çıktıya asla taşınmaz (AGENTS R4); yalnız yol + kural adı + toplam sayı basılır.
Kırık atıf exit 1; ilgisiz-atıf uyarısı ve negatif iddia hatırlatması exit 0.
"""
import argparse
import json
import re
import sys

import noma_lib as lib

CITATION = re.compile(r'\b(?:wiki|raw)/[\w./-]+\.\w+')
NEGATIVE_CLAIM = re.compile(r'kay[iı]tl[iı] deg[iı]l', re.I)


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
    """Yanıt metnini denetle → (bulgular, negatif_iddia). idx verilirse üst-bölge
    eşleşmeleri önbellekten kullanılır; içerik döndürülmez."""
    idx = idx if idx is not None else lib.load_wiki_index()
    upper = {}
    findings, cited = [], []
    for sentence in re.split(r'(?<=[.!?\n])\s+', text):
        for path in dict.fromkeys(CITATION.findall(sentence)):
            if path in cited:
                continue
            cited.append(path)
            target = lib.ROOT / path
            if not target.is_file():
                findings.append({'path': path, 'status': 'FAIL', 'rule': 'kırık-atıf'})
                continue
            slug = target.stem
            if path.startswith('wiki/') and slug in idx:
                if slug not in upper:
                    upper[slug] = _upper_region(target.read_text(encoding='utf-8'))
                terms = _sentence_terms(sentence)
                related = any(_overlap(t, upper[slug]) for t in terms) if terms else True
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
        text = open(a.file, encoding='utf-8').read() if a.file else sys.stdin.read()
    except OSError:
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
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
