# scripts/

Noma sözleşme linter'ı ve agent destek scriptleri. Hepsi stdlib-only'dir ve **git
mutation yapmaz** — yazma akışı serbesttir; commit ve conflict çözümü periyodik
cron job'a aittir.

Adlandırma: Python `noma_` (snake), shell `noma-` (kebab) ön eklidir; compose
dosyası Hermes imaj adıyla eşleştiği için ön eksiz kalır.

| Script | İş |
|---|---|
| `noma_lint.py` | lint() mekanik kontrolleri: append-only, şifreli kök/sayfalar, güncel metadata; özel satır içerikleri basılmaz |
| `noma-run-lint.sh` | lint() tam set: sözleşme linter + pre-commit |
| `noma_lib.py` | paylaşılan yardımcılar (frontmatter, slugify, log) — doğrudan çalıştırılmaz |
| `noma_new_note.py` | şablondan yeni wiki notu iskeleti üretir (AGENTS R5) |
| `noma_ingest.py` | kaynağı `raw/`'a yalnız-yeni-dosya modunda kopyalar (EN+TR injection `[flag]` + base64 taraması) + şablondan not üretir + mekanik post-ingest doğrulama (`[verify-fail]`/`NO-HUB`; içerik basılmaz) + log |
| `noma_find.py` | metadata filtre → regex (rg) → ortak aday sıralaması → wikilink traversal |
| `noma_wiki.py` | `root/hub` yalnız ilgili şifreli harita sayfasını okur; arama Türkçe katlamalıdır; agent JSON yalnız yol/puan/sayfa işaretçisi taşır |
| `noma-bootstrap.sh` | düğüm kurulum desteği: git-crypt denetimi ve `.env` hazırlığı |
| `noma_build_index.py` | `index.md` küçük kök + `index/hubs/` altında 32 yapraklık şifreli sayfalar + `_basliklar/` damıtma sözlüğü |
| `noma_bench_index.py` | gerçek wiki okumayan sentetik 1K/10K/100K indeks maliyeti ölçümü; yalnız sayısal çıktı |
| `docker-compose.hermes.yml` | Hermes Agent runtime compose (yerel doğrulandı; VPS Faz 1 B2-B4 notları dosyada) |
| `noma_hermes_context.py` | Hermes `pre_llm_call`: yalnız sabit gezinme talimatı; özel wiki gövdesini stdout'a vermez |
| `noma_test_node.py` | Salt-okunur, LLM'siz indeks/compose/hook/lint smoke testi; dashboard yoksa WARN |
| `test_noma_guardrails.py` | Sentetik, model çağrısız raw yarış / mevcut not / log gizliliği regresyonları |
| `test_noma_retrieval.py` | Sentetik Türkçe sorgu, hub filtresi, sıralama ve çıktı regresyonları |
| `test_noma_context.py` | Üst hub seçimi ile gerekçeli gövde çağrışımının sentetik regresyonları |
| `noma_eval_retrieval.py` | Şifreli plandaki temsilî sorguların toplu ilk-3/ikinci-rota isabetini ölçer (içerik basmaz) |
| `noma_eval_context.py` | Çekirdek erişim deneyi: Tree (A) ve gövde-çağrışımı (B) aday kapsamasını toplu ölçer |

## Örnekler

```bash
python3 scripts/noma_new_note.py kafka-temel-kavramlar --title "Kafka Temel Kavramlar" --type concept --tags kafka
printf 'not içeriği' | python3 scripts/noma_ingest.py - --kind inbox --slug yeni-fikir --title "Yeni Fikir"
python3 scripts/noma_ingest.py ~/Downloads/makale.html --kind clippings --title "Makale"
python3 scripts/noma_find.py --stage inbox --limit 10
python3 scripts/noma_find.py 'kafka|rabbitmq' --hop 2
alias w='python3 scripts/noma_wiki.py'
w root --json
w s context
w s agent --hub ai-agent-teknolojileri --json
w p model
w hub kisisel-bilgi-sistemi
w hub kisisel-bilgi-sistemi --json
w recent --limit 5
w links llm-sistem-ilkeleri --hop 2
w stats
bash scripts/noma-bootstrap.sh --id hermes-vps
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/noma_eval_retrieval.py
python3 -B scripts/noma_eval_context.py
python3 -B scripts/noma_eval_context.py --fresh
python3 -B scripts/noma_bench_index.py 1000 10000
python3 -B scripts/noma_bench_index.py 100000 --search
python3 -B scripts/noma_test_node.py --no-llm
```

Notlar:

- `noma_ingest.py` olası injection desenlerinde uyarır ve log'da `[flag]` işaretler
  (ADR-9); `raw/` üzerine asla yazmaz (eşzamanlı çağrıda da append-only).
- Bulut Hermes compose'u yalnız public read-only dosyaları mount eder; içinde
  `wiki/`, `index.md`, `index/`, `.env` veya `.git` yoktur. Bu CLI'ları gerçek wiki için
  kilidi açılmış yerel çalışma alanında çalıştırın.
- `noma_find.py` yalnız yol/başlık/metadata basar — not gövdesi stdout'a çıkmaz
  (AGENTS R4). `noma_wiki.py` aynı kuralı izler.
- Agent'ın kalıcı bağlamı yalnız rotayı tutar: `w root --json` (`index.md`'nin
  kök hub'ları) → `w hub <slug> --json` (en fazla 32 yol, varsa `next_page` için
  `--page N`) → seçilen notun üst bölgesi → ilgili başlık.
  Kök 8 KiB, tek hub sayfası 16 KiB sınırındadır; yüklenecek not metni CLI
  çıktısından değil seçilen `wiki/` dosyasından okunur.
- `--search` sentetik tam taramayı da ölçer: üretim ve genel arama hâlâ bütün
  wiki'yi tarar; sayfalar yalnız gezinmeyi O(tek sayfa) yapar.
  Belirsizse soru önce 2-4 kavrama damıtılır: `w s <kavramlar> --json [--hub <slug>]`;
  zayıf sonuçta kısa kök terimlerle bir kez yinele.
  Kısmi eşleşme kanıt değil, okunacak adaydır (bkz. `wiki/cekirdek-bilgi-erisimi.md`).
- `noma_wiki.py` Türkçe karakter katlar: `w s hafiza` → "Hafıza" başlıklı notları
  bulur. Skor: slug > başlık > tag > özet > gövde; tam kelime eşleşmesi yoksa
  kısmi adayları gösterir. Güncellik yalnız eşitlik çözümüdür; `status`/`stage`
  daha önce kontrol edilir. `pick` numaralı listeler; seçilen notun detay kartı
  (metadata + out/in linkler) basar, gövde basmaz. Agent JSON çıktısı yalnız yol,
  skor ve tam/kısmi eşleşme işareti taşır; içerik seçilen nottan okunur.
- Log satırları SCHEMA §5 formatındadır: `HH:mm <op> @<node> <aktör> | mesaj ≤120`.
- Enum varsayılanları: `noma_new_note` → `concept/common/inbox`; `noma_ingest`
  → `resource/common/inbox`. Değerler SCHEMA §3'teki listelerle doğrulanır.

Kök: [[index]]
