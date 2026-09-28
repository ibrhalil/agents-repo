#!/usr/bin/env python3
"""wiki/*.md → web/data/graph.{json,js} türev graph verisi üretir.

Kanonik kaynak wiki'dir (SCHEMA §1; [[turetilmis-yuzeyler]]). Çıktı derived
navigation verisidir, elle düzenlenmez; viewer görsel state'i wiki'ye yazmaz.
Node/edge modeli ve kütüphane gerekçesi: [[graph-view-web]].
Stdout yalnız sayı/yol basar (AGENTS.md gizlilik/stdout sınırı).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import noma_lib as lib

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
OUT_DIR = ROOT / "web" / "data"
SCHEMA_VERSION = 1
JS_PREFIX = "window.NOMA_GRAPH="


def wiki_locked(wiki_dir):
    files = sorted(Path(wiki_dir).glob("*.md"))
    if not files:
        return False
    with files[0].open("rb") as f:
        return lib.is_crypt_blob(f)


def _node(slug, entry):
    fm = entry["fm"]
    return {
        "id": slug,
        "label": fm.get("title", "").strip('"') or slug,
        "path": f"wiki/{slug}.md",
        "type": fm.get("type", "").strip('"'),
        "stage": fm.get("stage", "").strip('"'),
        "scope": fm.get("scope", "").strip('"'),
        "status": fm.get("status", "").strip('"'),
        "tags": entry["tags"],
        "exists": True,
    }


def build_graph():
    """wiki taraması → {meta, nodes, edges}; slug/target sırasına göre deterministik.

    Kırık/unresolved hedefler exists=false node olarak korunur (missing notes);
    self-link ve mükerrer wikilink kenar üretmez. `## Links` satırı kind=tree,
    gövde bağlantısı kind=ref taşır ([[yalin-dugum-ilkesi]]: tek yön kayıt).
    """
    if wiki_locked(WIKI_DIR):
        raise SystemExit("hata: wiki kilitli — git-crypt unlock")
    idx = lib.load_wiki_index()
    nodes = {}
    for slug in sorted(idx):
        nodes[slug] = _node(slug, idx[slug])

    edges = []
    for slug in sorted(idx):
        parents = set(idx[slug]["parents"])
        for target in sorted(idx[slug]["out"]):
            if not target or target == slug:
                continue
            if target not in nodes:
                target_node = _node(target, {"fm": {}, "tags": []})
                target_node.update({"label": target, "path": None, "exists": False})
                nodes[target] = target_node
            edges.append({"source": slug, "target": target,
                          "type": "wikilink",
                          "kind": "tree" if target in parents else "ref"})

    for node in nodes.values():
        node["incoming"] = 0
        node["outgoing"] = 0
    for edge in edges:
        nodes[edge["source"]]["outgoing"] += 1
        nodes[edge["target"]]["incoming"] += 1
    for node in nodes.values():
        node["degree"] = node["incoming"] + node["outgoing"]

    ordered = [nodes[slug] for slug in sorted(nodes)]
    return {
        "meta": {"version": SCHEMA_VERSION,
                 "counts": {"nodes": len(ordered), "edges": len(edges),
                            "missing": sum(1 for n in ordered if not n["exists"])}},
        "nodes": ordered,
        "edges": edges,
    }


def serialize(graph):
    return json.dumps(graph, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def js_payload(json_text):
    # file:// üzerinde fetch çalışmadığı için veri script olarak yüklenir.
    return JS_PREFIX + json_text + ";\n"


def _atomic_write(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_outputs(graph, out_dir=None):
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_text = serialize(graph)
    _atomic_write(out_dir / "graph.json", json_text)
    _atomic_write(out_dir / "graph.js", js_payload(json_text))
    return out_dir


def outputs_stale(graph, out_dir=None):
    out_dir = Path(out_dir) if out_dir else OUT_DIR
    json_text = serialize(graph)
    for name, text in (("graph.json", json_text), ("graph.js", js_payload(json_text))):
        try:
            if (out_dir / name).read_text(encoding="utf-8") != text:
                return True
        except OSError:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="wiki/*.md'den deterministik graph verisi üretir (derived).")
    parser.add_argument("--out", default=None, help="çıktı dizini (varsayılan web/data)")
    parser.add_argument("--check", action="store_true",
                        help="yazmadan bayatlık denetle (bayat: exit 1)")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else OUT_DIR
    graph = build_graph()
    counts = graph["meta"]["counts"]
    summary = (f"nodes={counts['nodes']} edges={counts['edges']} "
               f"missing={counts['missing']}")
    if args.check:
        if outputs_stale(graph, out_dir):
            print("graph verisi bayat — yeniden üretin", file=sys.stderr)
            return 1
        print(f"graph güncel: {summary}")
        return 0
    write_outputs(graph, out_dir)
    rel = lambda p: os.path.relpath(p, ROOT)  # noqa: E731
    print(f"graph: {summary} → {rel(out_dir / 'graph.json')} {rel(out_dir / 'graph.js')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
