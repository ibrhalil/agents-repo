# scripts/

Sözleşme linter'ı ve agent destek scriptleri. Hepsi stdlib-only'dir ve **git
mutation yapmaz** — yazma akışı serbesttir; commit ve conflict çözümü periyodik
cron job'a aittir.

| Script | İş |
|---|---|
| `lint_repo.py` | lint() mekanik kontrolleri (ERR'de exit 1) |
| `run_lint.sh` | lint() tam set: sözleşme linter + pre-commit |
| `lib_repo.py` | paylaşılan yardımcılar (frontmatter, slugify, log) — doğrudan çalıştırılmaz |
| `new_note.py` | şablondan yeni wiki notu iskeleti üretir (AGENTS R5) |
| `ingest.py` | kaynağı `raw/`'a verbatim kopyalar + wiki notu üretir + log yazar |
| `find.py` | retrieval: metadata filtre → full-text (rg) → wikilink traversal |
| `wiki.py` | insan yüzü arama CLI: `search/pick/hub/recent/links/stats` — skorlı, Türkçe katlamalı; yalnız yol+başlık+metadata basar (R4) |
| `bootstrap_node.sh` | düğüm kurulum desteği: git-crypt denetimi, `.env`, `docs/nodes/` kaydı |
| `build_index.py` | `index.md` üretici (cron): wiki `## Links` (özelden genele) yönünden ağaç |

## Örnekler

```bash
python3 scripts/new_note.py kafka-temel-kavramlar --title "Kafka Temel Kavramlar" --type concept --tags kafka
printf 'not içeriği' | python3 scripts/ingest.py - --kind inbox --slug yeni-fikir --title "Yeni Fikir"
python3 scripts/ingest.py ~/Downloads/makale.html --kind clippings --title "Makale"
python3 scripts/find.py --stage inbox --limit 10
python3 scripts/find.py 'kafka|rabbitmq' --hop 2
alias w='python3 scripts/wiki.py'
w s context hafiza --tag agent
w p model
w hub kisisel-bilgi-sistemi
w recent --limit 5
w links llm-sistem-ilkeleri --hop 2
w stats
bash scripts/bootstrap_node.sh --id hermes-vps --runtime Hermes --model "GLM (z.ai)" --role "7/24 cron düğümü"
```

Notlar:

- `ingest.py` olası injection desenlerinde uyarır ve log'da `[flag]` işaretler
  (ADR-9); `raw/` üzerine asla yazmaz (append-only).
- `find.py` yalnız yol/başlık/metadata basar — not gövdesi stdout'a çıkmaz
  (AGENTS R4). `wiki.py` aynı kuralı izler.
- `wiki.py` Türkçe karakter katlar: `w s hafiza` → "Hafıza" başlıklı notları
  bulur. Skor ağırlığı: slug > başlık > tag > özet > gövde (+14 gün tazelik
  bonusu). `pick` numaralı listeler; seçilen notun detay kartı (metadata +
  out/in linkler) basar, gövde basmaz. `--json` agent kullanımı içindir.
- Log satırları SCHEMA §5 formatındadır: `HH:mm <op> @<node> | mesaj ≤120`.
- Enum varsayılanları: `new_note` → `concept/common/inbox`; `ingest` →
  `resource/common/inbox`. Değerler SCHEMA §3'teki listelerle doğrulanır.

Kök: [[index]]
