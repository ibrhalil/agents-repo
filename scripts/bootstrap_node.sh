#!/usr/bin/env bash
# Düğüm kurulum desteği (ROADMAP B1-B4): git-crypt denetimi, .env hazırlığı,
# docs/nodes/ kaydı üretimi. Git mutation yapmaz; commit/conflict çözümü cron'a aittir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
id=""; runtime=""; model=""; role=""

while [[ $# -gt 0 ]]; do
  [[ $# -ge 2 ]] || { echo "eksik değer: $1" >&2; exit 1; }
  case "$1" in
    --id) id="$2"; shift 2 ;;
    --runtime) runtime="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --role) role="$2"; shift 2 ;;
    *) echo "kullanım: bootstrap_node.sh --id <kimlik> [--runtime v] [--model v] [--role v]" >&2; exit 1 ;;
  esac
done
[[ -n "$id" ]] || { echo "kullanım: bootstrap_node.sh --id <kimlik> [--runtime v] [--model v] [--role v]" >&2; exit 1; }
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

out="$ROOT/docs/nodes/$id.md"
if [[ -e "$out" ]]; then
  echo "zaten var: docs/nodes/$id.md"
  exit 0
fi
python3 - "$ROOT/docs/templates/node.md" "$out" "$id" "$runtime" "$model" "$role" <<'PY'
import datetime, pathlib, sys
vals = sys.argv[1:]
tpl_p, out_p, nid = vals[0], vals[1], vals[2]
runtime, model, role = (vals[3:6] + [''] * 3)[:3]
t = pathlib.Path(tpl_p).read_text(encoding='utf-8')
t = t.replace('kisa-ascii-kimlik', nid)
t = t.replace('<Düğüm adı>', nid)
t = t.replace('<agent yazılımı>', runtime or 'belirtilmedi')
t = t.replace('<model / sağlayıcı>', model or 'belirtilmedi')
t = t.replace('<rol>', role or 'belirtilmedi')
t = t.replace('YYYY-MM-DD', datetime.date.today().isoformat())
pathlib.Path(out_p).write_text(t, encoding='utf-8')
PY
echo "üretildi: docs/nodes/$id.md"
echo "sonraki adımlar: (1) .env anahtarlarını doldur  (2) 'pre-commit install'  (3) node kaydını doldur — commit/conflict çözümü cron'a aittir"
