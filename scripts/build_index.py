#!/usr/bin/env python3
"""index.md üretici (cron): wiki ## Links (özelden genele) yönünden ağacı kurar.
generate() içerik döndürür (lint bayatlık denetimi için); build_index() yazar."""
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
INDEX_FILE = ROOT / "index.md"


def _latest_log_stem():
    if not (ROOT / "log").is_dir():
        return None
    names = [f for f in os.listdir(ROOT / "log")
             if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f)]
    return sorted(names)[-1][:-3] if names else None


def generate():
    hubs = defaultdict(list)
    uncategorized = []

    for filepath in sorted(WIKI_DIR.glob("*.md")):
        slug = filepath.stem
        content = filepath.read_text(encoding="utf-8")

        title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
        title = title_match.group(1) if title_match else slug

        # ## Links bölümünü bul
        links_match = re.search(r"## Links\n(.*?)(?=\n## Summary)", content, re.DOTALL)
        if links_match:
            links_text = links_match.group(1).strip()
            # [[hedef]] veya [[hedef|Alias]] yakala
            extracted_links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", links_text)

            if extracted_links:
                for link in extracted_links:
                    hubs[link].append((slug, title))
            else:
                uncategorized.append((slug, title))
        else:
            uncategorized.append((slug, title))

    parts = []
    parts.append("# index — Vault Kökü")
    parts.append("> Bu dosya `scripts/build_index.py` (cron) tarafından wiki notlarındaki `## Links` (özelden genele) yönünden otomatik üretilir.\n")
    parts.append("## Sözleşmeler ve Kök Dizinler")
    parts.append("- [[AGENTS]] · [[SCHEMA]] · [[README]]")
    log_stem = _latest_log_stem()
    if log_stem:
        parts.append(f"- [[log/{log_stem}]] (Günlük Log)\n")
    else:
        parts.append("")
    parts.append("## Ağaç (Tree) — Hub'lar ve Yapraklar\n")

    for hub_slug in sorted(hubs.keys()):
        parts.append(f"### [[{hub_slug}]]")
        for leaf_slug, leaf_title in sorted(hubs[hub_slug]):
            parts.append(f"- [[{leaf_slug}|{leaf_title}]]")
        parts.append("")

    if uncategorized:
        parts.append("## Kategorize Edilmemiş (Tend Adayları)")
        for leaf_slug, leaf_title in sorted(uncategorized):
            parts.append(f"- [[{leaf_slug}|{leaf_title}]]")
        parts.append("")

    return "\n".join(parts)


def build_index():
    INDEX_FILE.write_text(generate(), encoding="utf-8")


if __name__ == "__main__":
    build_index()
    print("index.md başarıyla üretildi.")
