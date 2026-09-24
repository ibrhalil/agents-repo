# scripts/

Noma sözleşme linter'ı ve agent destek scriptleri. Hepsi stdlib-only'dir ve **git
mutation yapmaz** — yazma akışı serbesttir; commit ve conflict çözümü periyodik
cron job'a aittir.

Adlandırma: Python `noma_` (snake), shell `noma-` (kebab) ön eklidir; compose
dosyası Hermes imaj adıyla eşleştiği için ön eksiz kalır.

| Script | İş |
|---|---|
| `noma_lint.py` | lint() mekanik kontrolleri: append-only, şifreli index, güncel metadata; özel satır içerikleri basılmaz |
| `noma-run-lint.sh` | lint() tam set: sözleşme linter + pre-commit |
| `noma_lib.py` | paylaşılan yardımcılar (frontmatter, slugify, log) — doğrudan çalıştırılmaz |
| `noma_new_note.py` | şablondan yeni wiki notu iskeleti üretir (AGENTS R5) |
| `noma_ingest.py` | kaynağı `raw/`'a yalnız-yeni-dosya modunda kopyalar (inbox/clippings: verbatim; conversations: elle özet) + wiki notu + log |
| `noma_find.py` | retrieval: metadata filtre → full-text (rg) → wikilink traversal |
| `noma_wiki.py` | insan yüzü arama CLI: `search/pick/hub/recent/links/stats` — skorlı, Türkçe katlamalı; yalnız yol+başlık+metadata basar (R4) |
| `noma-bootstrap.sh` | düğüm kurulum desteği: git-crypt denetimi ve `.env` hazırlığı |
| `noma_build_index.py` | `index.md` üretici (cron): wiki `## Links` (özelden genele) yönünden ağaç |
| `docker-compose.hermes.yml` | Hermes Agent runtime compose (yerel doğrulandı; VPS Faz 1 B2-B4 notları dosyada) |
| `noma_hermes_context.py` | Hermes `pre_llm_call`: yalnız sabit gezinme talimatı; özel wiki gövdesini stdout'a vermez |
| `noma_test_node.py` | Salt-okunur, LLM'siz indeks/compose/hook/lint smoke testi; dashboard yoksa WARN |
| `test_noma_guardrails.py` | Sentetik, model çağrısız raw yarış / mevcut not / log gizliliği regresyonları |

## Örnekler

```bash
python3 scripts/noma_new_note.py kafka-temel-kavramlar --title "Kafka Temel Kavramlar" --type concept --tags kafka
printf 'not içeriği' | python3 scripts/noma_ingest.py - --kind inbox --slug yeni-fikir --title "Yeni Fikir"
python3 scripts/noma_ingest.py ~/Downloads/makale.html --kind clippings --title "Makale"
python3 scripts/noma_find.py --stage inbox --limit 10
python3 scripts/noma_find.py 'kafka|rabbitmq' --hop 2
alias w='python3 scripts/noma_wiki.py'
w s context hafiza --tag agent
w p model
w hub kisisel-bilgi-sistemi
w recent --limit 5
w links llm-sistem-ilkeleri --hop 2
w stats
bash scripts/noma-bootstrap.sh --id hermes-vps
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/noma_test_node.py --no-llm
```

Notlar:

- `noma_ingest.py` olası injection desenlerinde uyarır ve log'da `[flag]` işaretler
  (ADR-9); `raw/` üzerine asla yazmaz (eşzamanlı çağrıda da append-only).
- Bulut Hermes compose'u yalnız public read-only dosyaları mount eder; içinde
  `wiki/`, `index.md`, `.env` veya `.git` yoktur. Bu CLI'ları gerçek wiki için
  kilidi açılmış yerel çalışma alanında çalıştırın.
- `noma_find.py` yalnız yol/başlık/metadata basar — not gövdesi stdout'a çıkmaz
  (AGENTS R4). `noma_wiki.py` aynı kuralı izler.
- `noma_wiki.py` Türkçe karakter katlar: `w s hafiza` → "Hafıza" başlıklı notları
  bulur. Skor ağırlığı: slug > başlık > tag > özet > gövde (+14 gün tazelik
  bonusu). `pick` numaralı listeler; seçilen notun detay kartı (metadata +
  out/in linkler) basar, gövde basmaz. `--json` agent kullanımı içindir.
- Log satırları SCHEMA §5 formatındadır: `HH:mm <op> @<node> <aktör> | mesaj ≤120`.
- Enum varsayılanları: `noma_new_note` → `concept/common/inbox`; `noma_ingest`
  → `resource/common/inbox`. Değerler SCHEMA §3'teki listelerle doğrulanır.

Kök: [[index]]
