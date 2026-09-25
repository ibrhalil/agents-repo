#!/usr/bin/env python3
"""Hermes pre_llm_call: yerel gezinme veya kısıtlı düğüm talimatı döndürür.

Wiki başlığı, özeti veya indeks gövdesi hook stdout'una ve her model çağrısına
taşınmaz. Yerel düğüm ihtiyaç duyduğu hub'ı read_file ile açar.
"""
import json
import sys
from pathlib import Path


LOCAL_CONTEXT = (
    "[Noma: bilgi sorusunda scripts/noma_wiki.py root --json ile index.md "
    "kök hub'larından ilgili hub/yaprağa git; "
    "belirsizse scripts/noma_wiki.py s <kavramlar> --json ile yalnız yol adayı bul, "
    "zayıfsa kısa terimle bir kez yinele. "
    "Yalnız seçilen notun frontmatter/Links/Summary ve gereken bölümünü read_file ile aç; "
    "status/updated/önceki kararı denetle, wiki/slug.md ile atıf ver. "
    "Wiki erişilip ilgili kanıt okunduğu halde yanıt yoksa 'wiki'de kayıtlı değil' de. "
    "Kişisel/sağlık/finans notları yalnız yerel modelde işlenir.]"
)
RESTRICTED_CONTEXT = (
    "[Noma: bu düğümde şifreli index/wiki/raw erişimi yok; çalışma alanı yalnız "
    "public ve salt okunurdur. Kişisel/wiki soruları ile wiki notu oluşturma veya "
    "güncelleme isteklerinde 'wiki erişimi için yerel düğüm gerekli' de. "
    "Git-crypt anahtarı, özel klon veya şifreli mount isteme/önerme. "
    "Geçici taslağı kanonik wiki kaydı olarak sunma; public sözleşme ve kodla çalış.]"
)


def unlocked_index(payload):
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    base = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    p = base / "index.md"
    try:
        if p.is_file():
            with p.open("rb") as stream:
                return stream.read(10) != b"\x00GITCRYPT\x00"
    except OSError:
        pass
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    context = LOCAL_CONTEXT if unlocked_index(payload) else RESTRICTED_CONTEXT
    print(json.dumps({"context": context}, ensure_ascii=False))


if __name__ == "__main__":
    main()
