#!/usr/bin/env python3
"""Şifreli plan dosyasındaki sorguları değerlendir; yalnız toplu sayıları bas."""
import argparse
import json
import sys

import noma_lib as lib

# Ölçülen ilk-3 oranı 0.80–0.83 (24–25/30). Varsayılan eşik bu tabandır; yükseltmek
# kasıtlıysa gerilemeyi CI'da kırar (örn. --min 0.90).
DEFAULT_MIN_FIRST3 = 0.8


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--min', type=float, default=DEFAULT_MIN_FIRST3,
                    help=f'ilk-3 oranı için alt sınır (varsayılan {DEFAULT_MIN_FIRST3})')
    args = ap.parse_args()
    if not 0 <= args.min <= 1:
        print('hata: --min 0..1 aralığında olmalı', file=sys.stderr)
        return 2
    try:
        cases = json.loads((lib.ROOT / 'plans/wiki-erisim-sorgulari.json').read_text(encoding='utf-8'))
        idx = lib.load_wiki_index(with_body=True)
    except (OSError, ValueError, UnicodeError):
        print('değerlendirme girdisi okunamadı (özel içerik gizlendi)', file=sys.stderr)
        return 2
    top1 = top3 = top5 = retried = absent = 0
    misses = []
    for number, case in enumerate(cases, 1):
        slugs = lib.filter_wiki(idx, list(idx), hub=case.get('hub'))
        ranked = [s for _, s in lib.rank_wiki(idx, slugs, [case['query']])]
        target = case.get('expect')
        if target is None:
            absent += not ranked
            ok = not ranked
        else:
            top1 += target in ranked[:1]
            top3 += target in ranked[:3]
            top5 += target in ranked[:5]
            ok = target in ranked[:3]
            if not ok and case.get('retry'):
                slugs = lib.filter_wiki(idx, list(idx), hub=case.get('retry_hub'))
                second = [s for _, s in lib.rank_wiki(idx, slugs, [case['retry']])]
                retried += target in second[:3]
                ok = target in second[:3]
        if not ok:
            misses.append(number)
    count = sum(case.get('expect') is not None for case in cases)
    first3 = top3 / count if count else 1.0
    print(f'{len(cases)} soru · ilk1 {top1}/{count} · ilk3 {top3}/{count} · '
          f'ilk5 {top5}/{count} · ikinci rota +{retried} · '
          f'kayıtsız {absent}/{len(cases) - count}')
    print('iki rotada/kayıtsız kaçırılan sıra numaraları: ' +
          (', '.join(map(str, misses)) if misses else 'yok'))
    if first3 < args.min - 1e-9:
        print(f'hata: ilk-3 oranı {first3:.3f} < eşik {args.min:.3f} '
              f'({top3}/{count})', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
