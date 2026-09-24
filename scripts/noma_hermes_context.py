#!/usr/bin/env python3
"""Hermes pre_llm_call: yalnız statik gezinme talimatı döndürür.

Wiki başlığı, özeti veya indeks gövdesi hook stdout'una ve her model çağrısına
taşınmaz. Yerel düğüm ihtiyaç duyduğu hub'ı read_file ile açar.
"""
import json
import sys
from pathlib import Path


LOCAL_CONTEXT = (
    "[Noma: kanonik giriş index.md. Bilgi sorusunda önce index.md dosyasını "
    "read_file ile aç; yalnız ilgili hub/yaprağı takip et ve wiki/slug.md yoluyla "
    "atıf ver. Ağaçta yanıt yoksa 'wiki'de kayıtlı değil' de. "
    "Kişisel/sağlık/finans notları yalnız yerel modelde işlenir.]"
)
RESTRICTED_CONTEXT = (
    "[Noma: bu düğümde şifreli wiki erişimi yoktur. Kişisel veya wiki kaynaklı "
    "bilgi sorusunu yanıtlama; 'wiki erişimi için yerel düğüm gerekli' de. "
    "Burada yalnız public sözleşmeler ve araç kodu mevcuttur.]"
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
