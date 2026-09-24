#!/usr/bin/env python3
"""Wiki Tree ile gövde wikilink komşularını aynı sorularda karşılaştır.

Gerçek soru/kanıt kümesi şifreli plans/ altında kalır. Yalnız toplu ölçümler ve
anonim vaka ID'leri stdout'a çıkar; bu bir LLM yanıt doğruluğu testi değildir.
"""
import argparse
import json
import math
import re
import sys
from collections import defaultdict

import noma_lib as lib

SCOPES = {'systems', 'learning'}
CASE_FILE = 'plans/wiki-iliski-sorulari.json'
CONTEXT_LIMIT = 4
SEED_WIDTH = 2
ASSOCIATION_HOPS = 2
MAX_EXPANSION = 16
NAVIGATION_SECTIONS = {'alt temalar', 'tema notlari', 'agac haritasi',
                       'child notlar', 'politika kumesi', 'scripts', 'docs',
                       'yonetim', 'kaynaklar'}
QUESTION_WORDS = {'acaba', 'bir', 'bu', 'bunun', 'icin', 'ile', 've', 'veya', 'mi',
                  'mu', 'ne', 'neden', 'nasil', 'hangi', 'hangisi', 'kim', 'nerede',
                  'artik', 'bugun', 'gibi', 'olur', 'olarak', 'nedir', 'neye', 'neyi',
                  'once', 'sonra', 'daha', 'ise', 'bile', 'var', 'yok', 'biz',
                  'bizim', 'agentin'}


def body_associations(text):
    """Yalnız ## Summary sonrasındaki gövde wikilink hedeflerini döndür."""
    clean = lib.strip_code(text)
    summary = re.search(r'^## Summary\s*\n.*?(?=^## |\Z)', clean, re.M | re.S)
    if not summary:
        return set()
    targets = set()
    ignored = False
    for line in clean[summary.end():].splitlines():
        heading = re.match(r'^## ([^\n]+)$', line)
        if heading:
            ignored = lib.fold_tr(heading.group(1)).strip() in NAVIGATION_SECTIONS
            continue
        if not ignored:
            targets.update(s.strip().rstrip('\\') for s in lib.LINK_RE.findall(line))
    return targets


def association_graph(idx, eligible):
    """Üst hub Links'i olmayan, gövdeye dayalı out/in komşuları türet."""
    outgoing = {}
    incoming = defaultdict(set)
    for slug in eligible:
        text = (lib.ROOT / 'wiki' / f'{slug}.md').read_text(encoding='utf-8')
        targets = (body_associations(text) & eligible) - set(idx[slug]['parents']) - {slug}
        outgoing[slug] = targets
        for target in targets:
            incoming[target].add(slug)
    return outgoing, incoming


def association_candidates(seeds, outgoing, incoming, *, hops=ASSOCIATION_HOPS):
    """Köklü adaylardan sınırlı uzaklıktaki gövde ilişkilerini toplar."""
    seen = set(seeds)
    frontier = set(seeds)
    distances = {}
    for distance in range(1, hops + 1):
        next_frontier = set()
        for slug in frontier:
            next_frontier.update(outgoing.get(slug, ()))
            next_frontier.update(incoming.get(slug, ()))
        next_frontier -= seen
        next_frontier = set(sorted(next_frontier)[:MAX_EXPANSION])
        for slug in next_frontier:
            distances[slug] = distance
        seen.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break
    return distances


def lexical_shortlist(idx, eligible, query):
    """Türkçe ek toleranslı, üst bölge/başlık temelli adil kısa aday listesi.

    Çalışma kopyası için: mevcut CLI'yi değiştirmeden yöntem karşılaştırmasını
    yapar. Kişisel notlar `eligible` dışında kalır.
    """
    terms = [w for w in re.findall(r'[a-z0-9]+', lib.fold_tr(query))
             if w not in QUESTION_WORDS and len(w) >= 3]
    terms = list(dict.fromkeys(terms))
    if not terms:
        return [], {}
    weights = {'slug': 12, 'title': 10, 'tags': 6, 'summary': 4}
    fields = {slug: {key: re.findall(r'[a-z0-9]+', idx[slug]['fields'].get(key, ''))
                     for key in weights} for slug in eligible}

    def matched(term, words):
        stem = term[:5] if len(term) >= 6 else term
        return any(word.startswith(stem) or (len(word) >= 5 and stem.startswith(word))
                   for word in words)

    document_frequency = {term: sum(any(matched(term, words) for words in note.values())
                                    for note in fields.values()) for term in terms}
    terms = [term for term in terms if document_frequency[term]]
    scored = {}
    for slug, note in fields.items():
        hits = []
        for term in terms:
            best = max((weight for key, weight in weights.items()
                        if matched(term, note[key])), default=0)
            if best:
                idf = 1 + math.log((len(fields) + 1) / (document_frequency[term] + 1))
                hits.append(best * idf)
        if hits:
            scored[slug] = 3 * len(hits) + sum(hits)
    ranked = sorted(scored, key=lambda s: (-scored[s], s))
    return ranked, scored


def tree_context(idx, eligible, ranked, scores):
    """Yakın/özgül üst hub'ı değerlendir; çok büyük register'ı ezbere ekleme."""
    selected = ranked[:SEED_WIDTH]
    child_counts = defaultdict(int)
    for slug in eligible:
        for parent in idx[slug]['parents']:
            child_counts[parent] += 1
    proposals = set()
    for seed in selected:
        proposals.update(parent for parent in idx[seed]['parents']
                         if parent in eligible and parent not in selected
                         and child_counts[parent] <= 5)
    if proposals:
        best = max(proposals, key=lambda s: (scores.get(s, 0),
                                            -child_counts[s], s))
        if best not in selected:
            selected.append(best)
    selected += [slug for slug in ranked if slug not in selected][:CONTEXT_LIMIT - len(selected)]
    return selected


def choose_context(idx, eligible, graph, query):
    """A: sözcüksel + özgül üst hub; B: gerekçeli komşu ancak alakalıysa."""
    ranked, scores = lexical_shortlist(idx, eligible, query)
    baseline = tree_context(idx, eligible, ranked, scores)
    seeds = baseline[:SEED_WIDTH]
    outgoing, incoming = graph
    distances = association_candidates(seeds, outgoing, incoming)
    neighbors = [s for s in distances if s not in baseline and scores.get(s, 0)]
    neighbors.sort(key=lambda s: (distances[s], -scores[s], s))
    augmented = list(baseline)
    if neighbors and augmented and scores[neighbors[0]] > scores.get(augmented[-1], 0):
        augmented[-1] = neighbors[0]
    return baseline, augmented, distances


def evaluate(cases, idx, graph):
    eligible = sorted(s for s, e in idx.items() if e['fm'].get('scope') in SCOPES)
    details = []
    per_split = defaultdict(lambda: {'count': 0, 'answerable': 0, 'a': 0, 'b': 0,
                                     'a_evidence': 0, 'b_evidence': 0,
                                     'a_reads': 0, 'b_reads': 0, 'a_chars': 0,
                                     'b_chars': 0, 'b_graph_selected': 0,
                                     'negative_with_candidates': 0,
                                     'a_miss': [], 'b_miss': []})
    for case in cases:
        bucket = per_split[case['split']]
        bucket['count'] += 1
        gold = set(case['required'])
        a, b, distances = choose_context(idx, eligible, graph, case['query'])
        details.append({'id': case['id'], 'required': sorted(gold),
                        'baseline': a, 'associative': b,
                        'graph_candidates': sorted(distances)})
        if not gold:
            bucket['negative_with_candidates'] += bool(a or b)
            continue
        if not gold <= set(eligible):
            raise ValueError('değerlendirme kanıtı kapsam dışında veya eksik')
        bucket['answerable'] += 1
        for name, selected in (('a', a), ('b', b)):
            bucket[name] += gold <= set(selected)
            bucket[f'{name}_evidence'] += len(gold & set(selected))
            bucket[f'{name}_reads'] += len(selected)
            bucket[f'{name}_chars'] += sum(len(idx[s]['fields']['summary']) for s in selected)
            if not gold <= set(selected):
                bucket[f'{name}_miss'].append(case['id'])
        bucket['b_graph_selected'] += sum(s in distances for s in b)
    return per_split, details


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--diagnostic', action='store_true',
                    help='şifreli plans/ altına vaka yollarını dosyala; stdout yalnız sayılar')
    ap.add_argument('--fresh', action='store_true',
                    help='algoritma dondurulduktan sonraki ayrı soru kümesini ölç')
    args = ap.parse_args()
    try:
        case_file = 'plans/wiki-iliski-son-kontrol.json' if args.fresh else CASE_FILE
        cases = json.loads((lib.ROOT / case_file).read_text(encoding='utf-8'))
        idx = lib.load_wiki_index(with_body=True)
        eligible = {s for s, e in idx.items() if e['fm'].get('scope') in SCOPES}
        graph = association_graph(idx, eligible)
        result, details = evaluate(cases, idx, graph)
        if args.diagnostic:
            (lib.ROOT / 'plans/wiki-iliski-tanisi.json').write_text(
                json.dumps(details, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (OSError, UnicodeError, ValueError, KeyError):
        print('değerlendirme başarısız (özel içerik gizlendi)', file=sys.stderr)
        return 2
    print(f'scope notları={len(eligible)} gövde bağı={sum(map(len, graph[0].values()))}')
    for split, r in sorted(result.items()):
        print(f'{split}: soru={r["count"]} kaynaklı={r["answerable"]} '
              f'A tam={r["a"]}/{r["answerable"]} B tam={r["b"]}/{r["answerable"]} '
              f'A kaynak={r["a_evidence"]} B kaynak={r["b_evidence"]} '
              f'A okuma={r["a_reads"]} B okuma={r["b_reads"]} '
              f'A özet-karakter={r["a_chars"]} B özet-karakter={r["b_chars"]} '
              f'B ilişki-adayı={r["b_graph_selected"]} '
              f'cevapsız-adaylı={r["negative_with_candidates"]}')
        print(f'{split} eksik vaka ID: A={r["a_miss"]} B={r["b_miss"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
