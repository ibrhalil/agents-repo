#!/usr/bin/env python3
"""Küçük index.md kökü + şifreli sayfalı hub haritaları üretir.

Kanonik notlar wiki'dedir; index.md tek giriş, index/hubs/ silinebilir türevdir.
generate_all() linter'ın bayatlık denetimine de hizmet eder.
"""
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "wiki"
INDEX_FILE = ROOT / "index.md"
HUB_DIR = ROOT / "index" / "hubs"
PAGE_SIZE = 32
ROOT_MAX_BYTES = 8192
HUB_PAGE_MAX_BYTES = 16384


def _strip_code(text):
    """Kod bloğu/satır içi kodu kaldır — şablon yer tutucu linkleri hub olmasın."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def _latest_log_stem():
    if not (ROOT / "log").is_dir():
        return None
    names = [f for f in os.listdir(ROOT / "log")
             if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f)]
    return sorted(names)[-1][:-3] if names else None


def generate_all():
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

        stage = ""
        if fm_match:
            stage_match = re.search(r"^stage:\s*(\S+)", fm_match.group(1), re.M)
            if stage_match:
                stage = stage_match.group(1).strip('"')
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

        # ## Links bölümünü bul (yapı sözleşmesi: Links'i ## Summary takip eder;
        # uymayan not "Kategorize Edilmemiş" kuyruğuna düşer — tend adayı)
        links_match = re.search(r"## Links\n(.*?)(?=\n## Summary)", content, re.DOTALL)
        if links_match:
            links_text = _strip_code(links_match.group(1).strip())
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
    uncategorized = sorted(u for u in uncategorized if u[0] not in hubs)

    parts = []
    parts.append("# index — Vault Kökü")
    parts.append("> Wiki `## Links` yönünden üretilir; yalnız kök giriş burada, hub sayfaları `index/hubs/` altındadır.\n")
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

    pages = {}
    titles = sorted((slug, title) for slug, title, _ in
                    list(uncategorized) + [u for u in root_hubs]
                    + [leaf for leaves in hubs.values() for leaf in leaves])
    titles = list(dict.fromkeys(titles))
    for offset in range(0, len(titles), PAGE_SIZE):
        page = offset // PAGE_SIZE + 1
        lines = [f"# Wiki Not Başlıkları — Sayfa {page}",
                 "> Damıtma sözlüğü: kavramlar bu başlıklarla hizalanır. Üretilmiştir, kanonik değildir.\n"]
        lines += [f"- [[{slug}|{title}]]" for slug, title in
                  titles[offset:offset + PAGE_SIZE]]
        content = '\n'.join(lines) + '\n'
        if len(content.encode('utf-8')) > HUB_PAGE_MAX_BYTES:
            raise ValueError('başlık sözlüğü sayfası sınırı aşıldı')
        pages[f'index/hubs/_basliklar/{page:06d}.md'] = content

    for hub_slug in sorted(hubs.keys()):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', hub_slug):
            raise ValueError('geçersiz hub slug; önce wiki lint çalıştırılmalı')
        leaves = sorted(hubs[hub_slug])
        for offset in range(0, len(leaves), PAGE_SIZE):
            page = offset // PAGE_SIZE + 1
            lines = [f"# [[{hub_slug}]] — Sayfa {page}",
                     "> `scripts/noma_build_index.py` tarafından üretilen hub haritası.\n"]
            for leaf_slug, leaf_title, leaf_desc in leaves[offset:offset + PAGE_SIZE]:
                line = f"- [[{leaf_slug}|{leaf_title}]]"
                if leaf_desc:
                    line += f" — {leaf_desc}"
                lines.append(line)
            content = '\n'.join(lines) + '\n'
            if len(content.encode('utf-8')) > HUB_PAGE_MAX_BYTES:
                raise ValueError('hub sayfası sınırı aşıldı; başlık/slug kısaltılmalı')
            pages[f'index/hubs/{hub_slug}/{page:06d}.md'] = content

    if uncategorized:
        parts.append("## Kategorize Edilmemiş (Tend Adayları)")
        parts.append(f"- {len(uncategorized)} not: `index/hubs/_uncategorized/` (tend kuyruğu)")
        parts.append("")
        for offset in range(0, len(uncategorized), PAGE_SIZE):
            page = offset // PAGE_SIZE + 1
            lines = [f"# Kategorize Edilmemiş — Sayfa {page}",
                     "> `scripts/noma_build_index.py` tarafından üretilen tend kuyruğu.\n"]
            for leaf_slug, leaf_title, leaf_desc in uncategorized[offset:offset + PAGE_SIZE]:
                line = f"- [[{leaf_slug}|{leaf_title}]]"
                if leaf_desc:
                    line += f" — {leaf_desc}"
                lines.append(line)
            content = '\n'.join(lines) + '\n'
            if len(content.encode('utf-8')) > HUB_PAGE_MAX_BYTES:
                raise ValueError('tend sayfası sınırı aşıldı; başlık/slug kısaltılmalı')
            pages[f'index/hubs/_uncategorized/{page:06d}.md'] = content

    root = "\n".join(parts)
    if len(root.encode('utf-8')) > ROOT_MAX_BYTES:
        raise ValueError('kök hub haritası sınırı aşıldı; üst hub yapısı düzenlenmeli')
    return root, pages


def generate():
    """Geriye dönük uyumluluk: yalnız kök haritasını döndür."""
    return generate_all()[0]


def build_index():
    root, pages = generate_all()
    for relative, content in pages.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding='utf-8') != content:
            path.write_text(content, encoding='utf-8')
    if HUB_DIR.is_dir():
        for path in HUB_DIR.glob('*/*.md'):
            if re.fullmatch(r'[0-9]{6,}\.md', path.name) and path.relative_to(ROOT).as_posix() not in pages:
                path.unlink()
        for directory in HUB_DIR.iterdir():
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    if not INDEX_FILE.is_file() or INDEX_FILE.read_text(encoding='utf-8') != root:
        INDEX_FILE.write_text(root, encoding='utf-8')


if __name__ == "__main__":
    build_index()
    print("Kök indeks ve hub sayfaları üretildi (içerik gizlendi).")
