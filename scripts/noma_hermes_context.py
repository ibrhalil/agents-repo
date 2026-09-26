#!/usr/bin/env python3
"""Hermes pre_llm_call: yerel gezinme veya kısıtlı düğüm talimatı döndürür.

Wiki başlığı, özeti veya indeks gövdesi hook stdout'una ve her model çağrısına
taşınmaz. Yerel düğüm ihtiyaç duyduğu hub'ı read_file ile açar.
"""
import json
import sys
from pathlib import Path

CRYPT_MAGIC = b"\x00GITCRYPT\x00"
# Hook'un ait olduğu düğüm kökü; testler bu bağıyı mock'lar (payload cwd DEĞİLDİR).
SCRIPT_ROOT = Path(__file__).resolve().parent.parent

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


def is_plaintext(path):
    """Dosya okunabilir ve şifreli git-crypt blob değilse True."""
    try:
        if not path.is_file():
            return False
        with path.open("rb") as stream:
            return stream.read(len(CRYPT_MAGIC)) != CRYPT_MAGIC
    except OSError:
        return False


def repo_roots(payload):
    """Kök = hook'un ait olduğu düğüm (script konumu). Payload cwd'si ve süreç cwd'si
    saldırgan etkisinde olabilir; yalnız yedek aday oldukları için ASLA kullanılmaz."""
    return SCRIPT_ROOT


def unlocked_vault(base):
    """index.md düz metin VE wiki/ düğümleri şifreli değilse yerel gezinme açılır.
    index düz ama wiki şifreliyse LOCAL dal yanlış olur (read_file binary gürültü verir)."""
    if not is_plaintext(base / "index.md"):
        return False
    for note in sorted((base / "wiki").glob("*.md")):
        return is_plaintext(note)
    return True


def unlocked_index(payload):
    return unlocked_vault(repo_roots(payload))


def read_payload():
    """TTY'de veya bozuk akışta sonsuz bekleme; boş yük döndür."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def main():
    # B9: hook asla traceback basmaz; her beklenmedik girdide kısıtlı talimat + 0.
    try:
        context = LOCAL_CONTEXT if unlocked_index(read_payload()) else RESTRICTED_CONTEXT
    except Exception:
        context = RESTRICTED_CONTEXT
    print(json.dumps({"context": context}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
