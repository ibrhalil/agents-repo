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
| `bootstrap_node.sh` | düğüm kurulum desteği: git-crypt denetimi, `.env`, `docs/nodes/` kaydı |
| `build_index.py` | `index.md` üretici (cron): wiki `## Links` (özelden genele) yönünden ağaç |

## Örnekler

```bash
python3 scripts/new_note.py kafka-temel-kavramlar --title "Kafka Temel Kavramlar" --type concept --tags kafka
printf 'not içeriği' | python3 scripts/ingest.py - --kind inbox --slug yeni-fikir --title "Yeni Fikir"
python3 scripts/ingest.py ~/Downloads/makale.html --kind clippings --title "Makale"
python3 scripts/find.py --stage inbox --limit 10
python3 scripts/find.py 'kafka|rabbitmq' --hop 2
bash scripts/bootstrap_node.sh --id hermes-vps --runtime Hermes --model "GLM (z.ai)" --role "7/24 cron düğümü"
```

Notlar:

- `ingest.py` olası injection desenlerinde uyarır ve log'da `[flag]` işaretler
  (ADR-9); `raw/` üzerine asla yazmaz (append-only).
- `find.py` yalnız yol/başlık/metadata basar — not gövdesi stdout'a çıkmaz
  (AGENTS R4).
- Log satırları SCHEMA §5 formatındadır: `HH:mm <op> @<node> | mesaj ≤120`.
- Enum varsayılanları: `new_note` → `concept/common/inbox`; `ingest` →
  `resource/common/inbox`. Değerler SCHEMA §3'teki listelerle doğrulanır.
