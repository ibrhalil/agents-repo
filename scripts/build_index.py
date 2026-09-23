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

        title = slug
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.S)
        if fm_match:
            title_match = re.search(r'^title:\s*(.+?)\s*$', fm_match.group(1), re.M)
            if title_match:
                title = title_match.group(1).strip('"')

        stage_match = re.search(r"^stage:\s*(\S+)", content, re.MULTILINE)
        stage = stage_match.group(1) if stage_match else ""
        summary_match = re.search(r"## Summary\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
        desc = ""
        if summary_match:
            first_line = next((l.strip() for l in summary_match.group(1).splitlines() if l.strip()), "")
            sentence = re.match(r"(.+?[.!?])", first_line)
            desc = (sentence.group(1) if sentence else first_line).strip()
            if len(desc) > 110:
                desc = desc[:107].rstrip() + "…"
        if stage and stage != "done":
            desc = f"{desc} [{stage}]" if desc else f"[{stage}]"

        # ## Links bölümünü bul
        links_match = re.search(r"## Links\n(.*?)(?=\n## Summary)", content, re.DOTALL)
        if links_match:
            links_text = links_match.group(1).strip()
            # [[hedef]] veya [[hedef|Alias]] yakala
            extracted_links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", links_text)

            if extracted_links:
                for link in extracted_links:
                    hubs[link].append((slug, title, desc))
            else:
                uncategorized.append((slug, title, desc))
        else:
            uncategorized.append((slug, title, desc))

    root_hubs = [u for u in uncategorized if u[0] in hubs]
    uncategorized = [u for u in uncategorized if u[0] not in hubs]

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
    if root_hubs:
        parts.append("## Kök Hub'lar")
        for leaf_slug, leaf_title, leaf_desc in sorted(root_hubs):
            line = f"- [[{leaf_slug}|{leaf_title}]]"
            if leaf_desc:
                line += f" — {leaf_desc}"
            parts.append(line)
        parts.append("")

    parts.append("## Ağaç (Tree) — Hub'lar ve Yapraklar\n")

    for hub_slug in sorted(hubs.keys()):
        parts.append(f"### [[{hub_slug}]]")
        for leaf_slug, leaf_title, leaf_desc in sorted(hubs[hub_slug]):
            line = f"- [[{leaf_slug}|{leaf_title}]]"
            if leaf_desc:
                line += f" — {leaf_desc}"
            parts.append(line)
        parts.append("")

    if uncategorized:
        parts.append("## Kategorize Edilmemiş (Tend Adayları)")
        for leaf_slug, leaf_title, leaf_desc in sorted(uncategorized):
            line = f"- [[{leaf_slug}|{leaf_title}]]"
            if leaf_desc:
                line += f" — {leaf_desc}"
            parts.append(line)
        parts.append("")

    return "\n".join(parts)


def build_index():
    INDEX_FILE.write_text(generate(), encoding="utf-8")


if __name__ == "__main__":
    build_index()
    print("index.md başarıyla üretildi.")
