#!/usr/bin/env python3
"""Sentetik wiki ile kök/hub gezinme ve tam üretim maliyetini toplu ölç.

Gerçek wiki metni okunmaz; fixture'lar yalnız tmp/ altında oluşturulup silinir.
Çıktı yalnız sayı/süre/bellektir, not metni veya dosya yolu değildir.
"""
import argparse
import contextlib
import io
import json
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import noma_build_index as build
import noma_lib as lib
import noma_wiki as wiki


def benchmark(count, search=False):
    with tempfile.TemporaryDirectory(prefix='noma-index-bench-', dir=lib.ROOT / 'tmp') as tmp:
        root = Path(tmp)
        source = root / 'wiki'
        source.mkdir()
        (source / 'root.md').write_text('---\ntitle: "Sentetik Kök"\nstage: done\n---\n'
                                        '# Kök\n## Links\n## Summary\nSentetik kök.\n',
                                        encoding='utf-8')
        note = ('---\ntitle: "Sentetik Not"\nstage: done\n---\n'
                '# Not\n## Links\n[[root]]\n## Summary\nSentetik bilgi.\n')
        for number in range(count):
            (source / f'not-{number:08d}.md').write_text(note, encoding='utf-8')

        with mock.patch.object(build, 'ROOT', root), \
                mock.patch.object(build, 'WIKI_DIR', source), \
                mock.patch.object(build, 'INDEX_FILE', root / 'index.md'), \
                mock.patch.object(build, 'HUB_DIR', root / 'index/hubs'), \
                mock.patch.object(lib, 'ROOT', root):
            start = time.perf_counter()
            build.build_index()
            build_time = time.perf_counter() - start
            samples = []
            for command in (lambda: wiki.cmd_root(SimpleNamespace(json=True)),
                            lambda: wiki.cmd_hub(SimpleNamespace(slug='root', page=1, json=True))):
                timings = []
                result = None
                for _ in range(10):
                    output = io.StringIO()
                    start = time.perf_counter()
                    with contextlib.redirect_stdout(output):
                        if command() != 0:
                            raise RuntimeError('sentetik gezinme başarısız')
                    timings.append((time.perf_counter() - start) * 1000)
                    result = json.loads(output.getvalue())
                p95 = statistics.quantiles(timings, n=20, method='inclusive')[18]
                samples.append((statistics.median(timings), p95, result))
            page_dir = root / 'index/hubs/root'
            page = page_dir / '000001.md'
            search_time = None
            if search:
                start = time.perf_counter()
                idx = lib.load_wiki_index(with_body=True)
                hits = lib.rank_wiki(idx, list(idx), ['not-00000001'])
                search_time = time.perf_counter() - start
                if not hits or hits[0][1] != 'not-00000001':
                    raise RuntimeError('sentetik arama isabeti başarısız')
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss_mb = rss / (1024 * 1024 if sys.platform == 'darwin' else 1024)
            print(f'not={count} kok_bayt={(root / "index.md").stat().st_size} '
                  f'page_bayt={page.stat().st_size} page_sayisi={len(list(page_dir.glob("*.md")))} '
                  f'page_yol={len(samples[1][2]["paths"])} '
                  f'uret_s={build_time:.3f} root_medyan_ms={samples[0][0]:.3f} '
                  f'root_p95_ms={samples[0][1]:.3f} hub_medyan_ms={samples[1][0]:.3f} '
                  f'hub_p95_ms={samples[1][1]:.3f} islem_tepe_bellek_mb={rss_mb:.1f}'
                  + (f' tam_arama_s={search_time:.3f}' if search_time is not None else ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('counts', nargs='*', type=int, default=[1000, 10000],
                    help='sentetik not sayıları (örn. 1000 10000 100000)')
    ap.add_argument('--search', action='store_true', help='tam wiki aramasını da ölç')
    args = ap.parse_args()
    if any(n < 1 for n in args.counts):
        ap.error('not sayısı pozitif olmalı')
    for count in args.counts:
        benchmark(count, search=args.search)


if __name__ == '__main__':
    main()
