#!/usr/bin/env python3
import json
import os
import sys

MAX_LINE = 110
MAX_TOTAL = 5000

HEADER = (
    "[Noma wiki ağacı — kanonik bilgi kaynağı. Her bilgi sorusunda ÖNCE aşağıdaki "
    "ağaçtan ilgili yaprağı read_file ile oku, cevabı path atıflı ver (örn. kaynak: "
    "wiki/slug.md). Ağaçta cevap yoksa 'wiki'de kayıtlı değil' de; genel model "
    "bilgisiyle cevap uydurma.]"
)


def find_index(payload):
    candidates = []
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if cwd:
        candidates.append(cwd)
    candidates += ["/workspace", os.getcwd(), os.path.expanduser("~/dev/IdeaProjects/agents-repo")]
    for base in candidates:
        p = os.path.join(base, "index.md")
        if os.path.isfile(p):
            return p
    return None


def build_tree(path):
    lines = []
    total = len(HEADER)
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()
            if "[[" not in line:
                continue
            if len(line) > MAX_LINE:
                line = line[: MAX_LINE - 1] + "…"
            lines.append(line)
            total += len(line)
            if total > MAX_TOTAL:
                break
    return "\n".join(lines)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    index_path = find_index(payload)
    if not index_path:
        print("{}")
        return
    tree = build_tree(index_path)
    if not tree:
        print("{}")
        return
    print(json.dumps({"context": HEADER + "\n" + tree}, ensure_ascii=False))


if __name__ == "__main__":
    main()
