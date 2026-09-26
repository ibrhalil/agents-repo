#!/usr/bin/env bash
# Düğüm kurulum desteği (ROADMAP B1-B4): git-crypt denetimi ve .env hazırlığı.
# Git mutation yapmaz; commit/conflict çözümü cron'a aittir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id) [[ $# -ge 2 ]] || { echo "eksik değer: $1" >&2; exit 1; }; id="$2"; shift 2 ;;
    *) echo "kullanım: noma-bootstrap.sh --id <kimlik>" >&2; exit 1 ;;
  esac
done
[[ -n "$id" ]] || { echo "kullanım: noma-bootstrap.sh --id <kimlik>" >&2; exit 1; }
[[ "$id" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "hata: --id ASCII kebab-case olmalı" >&2; exit 1; }
[[ -d "$ROOT/.git" ]] || { echo "hata: $ROOT bir git repo değil" >&2; exit 1; }

command -v git-crypt >/dev/null || echo "UYARI: git-crypt kurulu değil — şifreli dizinler okunamaz." >&2
# Kilit denetimi: gerçek sihir '\x00GITCRYPT\x00' (tire yok). Her özel dizinden
# birer örnek yoksa denetlenmez; parola yazdırılmaz, yalnız sürüm/yol denetlenir.
locked=0
for target in "$ROOT/index.md" "$(find "$ROOT/raw" "$ROOT/wiki" "$ROOT/log" -name '*.md' -type f 2>/dev/null | head -n 3)"; do
  if [[ -f "$target" ]] && head -c 10 "$target" | LC_ALL=C grep -q 'GITCRYPT'; then
    locked=1
  fi
done
if [[ "$locked" -eq 1 ]]; then
  echo "HATA: içerik kilitli — önce 'git-crypt unlock' çalıştır." >&2
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  ( umask 077 && cp "$ROOT/.env.example" "$ROOT/.env" )
  chmod 600 "$ROOT/.env"
  python3 - "$ROOT/.env" "$id" <<'PY'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding='utf-8')
new, n = re.subn(r'(?m)^(\s*(?:export\s+)?NODE_ID\s*=\s*)\S+',
                 lambda m: m.group(1) + sys.argv[2], text)
if not n:
    sys.exit('hata: .env içinde NODE_ID satırı yok — .env.example bozuk')
p.write_text(new, encoding='utf-8')
written = [l for l in p.read_text(encoding='utf-8').splitlines()
           if re.match(r'\s*(?:export\s+)?NODE_ID\s*=', l)]
if len(written) != 1 or not re.fullmatch(
        r'\s*(?:export\s+)?NODE_ID\s*=' + re.escape(sys.argv[2]) + r'(\s.*)?$', written[0]):
    sys.exit('hata: .env içinde NODE_ID=' + sys.argv[2] + ' doğrulanamadı')
PY
  echo ".env oluşturuldu (NODE_ID=$id, mod 0600) — sağlayıcı anahtarlarını doldur."
else
  echo ".env mevcut — dokunulmadı."
fi

echo "sonraki adımlar: (1) .env anahtarlarını doldur  (2) 'pre-commit install' — commit/conflict çözümü cron'a aittir"
