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
probe="$(find "$ROOT/raw" "$ROOT/wiki" -name '*.md' -type f 2>/dev/null | head -n 1)"
if [[ -n "$probe" ]] && head -c 10 "$probe" | grep -q 'GIT-CRYPT'; then
  echo "HATA: içerik kilitli — önce 'git-crypt unlock' çalıştır." >&2
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  python3 - "$ROOT/.env" "$id" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text(encoding='utf-8').replace('NODE_ID=hermes', f'NODE_ID={sys.argv[2]}'), encoding='utf-8')
PY
  echo ".env oluşturuldu (NODE_ID=$id) — sağlayıcı anahtarlarını doldur."
else
  echo ".env mevcut — dokunulmadı."
fi

echo "sonraki adımlar: (1) .env anahtarlarını doldur  (2) 'pre-commit install' — commit/conflict çözümü cron'a aittir"
