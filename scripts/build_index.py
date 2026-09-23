#!/usr/bin/env python3
import os
import re
from collections import defaultdict

WIKI_DIR = "wiki"
INDEX_FILE = "index.md"

def build_index():
    hubs = defaultdict(list)
    uncategorized = []
    
    # Wiki dizinindeki tüm md dosyalarını tara
    if not os.path.exists(WIKI_DIR):
        print(f"{WIKI_DIR} bulunamadı.")
        return

    for filename in os.listdir(WIKI_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(WIKI_DIR, filename)
        slug = filename[:-3]
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Başlığı bul
        title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
        title = title_match.group(1) if title_match else slug
        
        # ## Links bölümünü bul
        links_match = re.search(r'## Links\n(.*?)(?=\n## Summary)', content, re.DOTALL)
        if links_match:
            links_text = links_match.group(1).strip()
            # [[hedef]] veya [[hedef|Alias]] yakala
            extracted_links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', links_text)
            
            if extracted_links:
                for link in extracted_links:
                    hubs[link].append((slug, title))
            else:
                uncategorized.append((slug, title))
        else:
            uncategorized.append((slug, title))

    # index.md dosyasını oluştur
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write("# index — Vault Kökü\n")
        f.write("> Bu dosya `scripts/build_index.py` (cron) tarafından wiki notlarındaki `## Links` (özelden genele) yönünden otomatik üretilir.\n\n")
        
        f.write("## Sözleşmeler ve Kök Dizinler\n")
        f.write("- [[AGENTS]] · [[SCHEMA]] · [[README]]\n")
        f.write("- [[log/2026-09-23]] (Günlük Log Örneği)\n\n")
        
        f.write("## Ağaç (Tree) — Hub'lar ve Yapraklar\n\n")
        
        # Hub'ları yazdır
        for hub_slug in sorted(hubs.keys()):
            f.write(f"### [[{hub_slug}]]\n")
            for leaf_slug, leaf_title in sorted(hubs[hub_slug]):
                f.write(f"- [[{leaf_slug}|{leaf_title}]]\n")
            f.write("\n")
            
        if uncategorized:
            f.write("## Kategorize Edilmemiş (Tend Adayları)\n")
            for leaf_slug, leaf_title in sorted(uncategorized):
                f.write(f"- [[{leaf_slug}|{leaf_title}]]\n")
            f.write("\n")

if __name__ == "__main__":
    build_index()
    print("index.md başarıyla üretildi.")
