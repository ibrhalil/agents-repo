# scripts/

Noma sözleşme linter'ı ve agent destek scriptleri. `noma_*` scriptleri stdlib-only'dir ve **git
mutation yapmaz** — yazma akışı serbesttir; commit ve conflict çözümü bugün
**elle** yapılır, zamanlanmış cron işi ROADMAP B5'e bağlıdır (henüz yok).
`laya_*` scriptleri repo `.venv`'inde `laya[serve]` ister (System One pilotu;
`wiki/laya-gate-servisi.md`).

Adlandırma: Python `noma_` (snake), shell `noma-` (kebab) ön eklidir; compose
dosyası Hermes imaj adıyla eşleştiği için ön eksiz kalır.

| Script | İş |
|---|---|
| `noma_lint.py` | lint() mekanik kontrolleri: append-only (HEAD + staged silme/değişim), tüm özel staged blob'ların gerçekten şifreli olması, kırık link, orphan, enum, tz-bilinçli updated-bump, satır bütçeleri, `.gitattributes` tutarlılığı, genel döngü (CYCLE), bayat stage (STALE), bölüm sırası (STRUCT), board biçimi ve yeni staged board'da aktif kayıt yasağı; özel satır içerikleri ve metadata değerleri basılmaz |
| `noma-run-lint.sh` | lint() tam set: sözleşme linter + pre-commit (linter aynı zamanda pre-commit kancasıdır) |
| `noma_lib.py` | paylaşılan yardımcılar (frontmatter, slugify, log, ISO zaman) — doğrudan çalıştırılmaz |
| `noma_board.py` | aynı checkout'ta atomik begin/claim/release/finish; salt-okunur status; kısa OS kilidi, JSON durum sinyali; dosya/Git değişikliklerini kendiliğinden sahiplenmez veya geri almaz |
| `test_noma_board.py` | sentetik ayrı süreçlerle mükerrer iş, dosya/dizin claim yarışı, kapanış, bozuk durum ve staged board regresyonları |
| `noma_new_note.py` | şablondan frontmatter/bölüm/yer tutucu iskeleti üretir; gövdeye davranış yönergesi kopyalamaz; içerik bellede üretilir, yarım not bırakılmaz; done/archived iskelet reddedilir |
| `noma_ingest.py` | girdileri kalıcı yazmadan ÖNCE doğrular (slug/aktör/stage); kaynağı `raw/`'a yalnız-yeni-dosya modunda kopyalar (EN+TR injection `[flag]` + base64 taraması); not bellede üretilip doğrulanır ve atomik yayınlanır — doğrulama hatasında not inbox'a iner (`[verify-fail]`/`NO-HUB`; içerik basılmaz) |
| `noma_find.py` | metadata filtre → regex (rg) → ortak aday sıralaması → wikilink traversal; varsayılan çıktı yalnız yol, başlık/metadata `--human` ile |
| `noma_wiki.py` | `root/hub` yalnız ilgili şifreli harita sayfasını okur (`_basliklar`/`_uncategorized` dâhil); arama Türkçe katlamalıdır; tüm modlarda varsayılan çıktı yalnız yol, başlık/metadata `--human` ile; agent JSON yalnız yol/puan/sayfa işaretçisi taşır |
| `noma-bootstrap.sh` | düğüm kurulum desteği: git-crypt kilit denetimi (tüm özel dizinlerden örnek, yollar tek tek) ve `.env` hazırlığı |
| `noma_build_index.py` | `index.md` küçük kök + `index/hubs/` altında 32 yapraklık şifreli sayfalar + `_basliklar/` damıtma sözlüğü |
| `noma_build_graph.py` | wiki `[[wikilink]]`'lerinden `web/data/graph.{json,js}` türev graph verisi üretir (deterministik; kırık hedef `exists=false`, self-link/mükerrer kenar üretmez; stdout yalnız sayı/yol; `--check` bayatlık denetimi; görünüm `web/index.html`) |
| `noma_bench_index.py` | gerçek wiki okumayan sentetik 1K/10K/100K indeks maliyeti ölçümü; yalnız sayısal çıktı |
| `docker-compose.hermes.yml` | Hermes Agent runtime compose (yerel doğrulandı; VPS Faz 1 B2-B4 notları dosyada) |
| `noma_hermes_context.py` | Hermes `pre_llm_call`: yalnız sabit gezinme talimatı; kilit kararında TÜM wiki notları denetlenir (kısmi kasa kısıtlı sayılır); özel wiki gövdesini stdout'a vermez |
| `noma_test_node.py` | LLM'siz indeks/compose/hook/lint smoke testi; `tmp/` altına sentetik fixture yazar (tam salt-okunur değildir), Docker/dashboard yoksa WARN |
| `test_noma_guardrails.py` | Sentetik, model çağrısız raw yarış / mevcut not / log gizliliği regresyonları |
| `test_noma_retrieval.py` | Sentetik Türkçe sorgu, hub filtresi, sıralama ve çıktı regresyonları |
| `test_noma_context.py` | Üst hub seçimi ile gerekçeli gövde çağrışımının sentetik regresyonları |
| `noma_eval_retrieval.py` | Şifreli plandaki temsilî sorguların toplu ilk-3/ikinci-rota isabetini ölçer (içerik basmaz) |
| `noma_verify_citations.py` | Yanıt atıflarını mekanik doğrular: kırık-atıf FAIL (exit 1), ilgisiz/okunamayan-atıf WARN, negatif iddia hatırlatması; `--json`. Tetikleyici politikanın kanonik sahibi `wiki/epistemik-hijyen.md`'dir; burası yalnız kullanım dokümanıdır. Web citation doğrulayıcısı değildir |
| `noma_tend_report.py` | Bakım adayları: HUB-FULL (>32 yaprak), INBOX kuyruğu, NO-HUB, STALE; `--json` (cron'a hazır), koşusu log'a yazar. Kategorileri `FM/LINK` lint bulgularının yerine geçmez (`wiki/bakim-disiplini.md`) |
| `noma_eval_context.py` | Çekirdek erişim deneyi: Tree (A) ve gövde-çağrışımı (B) aday kapsamasını toplu ölçer |
| `laya_eval.py` | System One (Laya) pilot eval: stratified 50/20/30 bölme, koşum, metrik (acc/HF/ECE/P50-P95), opsiyon süpürmesi (`--model` local path alır; `wiki/system-one-olcum-plani.md`) |
| `test_laya_eval.py` | Model gerektirmeyen metrik regresyonları: confidence tahmin edilen sınıftan gelir (gold'dan değil), sweep seçenek kümesi gold route'u daima içerir |
| `laya_finetune.py` | Laya multilingual tabanı Noma görev verisiyle RLCD+CE fine-tune eder; calib bölmesinden temperature fit eder, `models/` altına yazar |
| `laya_gate_serve.py` | Yerel `needs_web` kapı servisi (127.0.0.1:8791, yalnız eşik geçen soru, fail-open; LaunchAgent `com.noma.laya-gate` ile kalıcı) |
| `data/laya_eval_set.json` | 84 örneklik etiketli eval/fine-tune seti (TR ağırlıklı + kısa Latin tuzakları; bölme seed 42) |

## Agent Koordinasyonu

`BOARD.md` tek durum kaynağıdır; kayıtları elle düzenlemek yerine yardımcıyı
kullanın. Boş durum JSON `[]`'dır. Komutlar repo kökünü script konumundan bulur;
yalnız bu checkout'u koordine eder. Varsayılan çıktı JSON'dur, ek paket gerekmez.

```bash
python3 -B scripts/noma_board.py status
python3 -B scripts/noma_board.py begin update-fixture
# Use the returned run_id in all following calls.
python3 -B scripts/noma_board.py claim run-example scripts/fixture.py
python3 -B scripts/noma_board.py release run-example scripts/fixture.py
python3 -B scripts/noma_board.py finish run-example
```

- `begin <task-key> [--source manual|cron] [--run-id <own-run-id>]`: task anahtarı
  genel ASCII kebab-case, aynı iş için kararlı olmalıdır. Varsayılan kimlik/zaman
  üretilir; `--run-id` yalnız kendi bilinen işini idempotent sürdürmek içindir.
  Başka kaydın duplicate yanıtındaki kimliğini kullanmak devir değildir.
- `claim <run-id> <paths...>`: ilk yazımdan hemen önce repo-relative yolları
  sahiplenir. Çoklu claim all-or-nothing'dir. Dizin ve alt yolları çatışır;
  örneğin `index/hubs/`, altındaki bütün sayfaları kapsar. Absolute/traversal,
  symlink, `BOARD.md`, `.git` ve `tmp/` claim'leri reddedilir. Rename'de iki yol
  da claim edilir; aynı sahibi tekrar claim etmek güvenlidir.
- `release <run-id> <paths...>`: yalnız verilen claim'leri kaldırır; dizin claim'i
  için aynı dizin yolunu kullanın. Kendi yarım işini sahipsiz bırakmayın.
- `finish <run-id>`: yalnız o kaydı kaldırır; tekrar çağrı güvenlidir. Çalışma
  dosyalarını veya Git index'i değiştirmez. Log/test/teslim hazırlığı bittiğinde
  çağrılır; commit yapılması gerekmez.
- `status`: kimlik, task anahtarı ve claim yollarını okur; hiçbir dosya veya kilit
  oluşturmaz. Serbest görev metni ve özel içerik/metadata board'a taşınmaz.

| Exit | Durum | Eylem |
|---|---|---|
| `0` | `started`, `already-active`, `claimed`, `released`, `finished`, `already-finished`, `ok` | İlgili adım tamamlandı. |
| `3` | `duplicate` | Aynı işi yeniden başlatma. |
| `3` | `conflict` | Bildirilen yollara yazma; bağımsız işi sürdür veya somut engelle kapan. |
| `3` | `busy` | Kilit en fazla iki saniye beklendi; bir kez yeniden dene, sonsuz bekleme döngüsü kurma. |
| `2` | `error` | Biçim/kimlik/IO hatası; sabit `rule` kodunu değerlendir, board'u boşaltarak onarma. |

Board güncellemesi `tmp/.noma-board.lock` altında read/check/atomic-replace
işlemidir; kilit dosyası silinmez. Hata board'un önceki sürümünü korur. Yardımcı,
protokolü atlayan editörleri engellemez ve ani oturum ölümünde kaydı otomatik
silmez; yaş tek başına devir izni değildir. Boş legacy board yeni JSON biçimine
geçirilirken aktif kayıt varsa korunmalıdır; araç bilinmeyen biçimi dönüştürmez.

Ortak çıktı kullanımı: günlük log yalnız `noma_lib.append_log` kilitli append'iyle
yazılır, uzun süreli özel claim'e alınmaz. İndeks üretiminde `index.md` ve
`index/hubs/` birlikte, graph üretiminde `web/data/` claim edilir; üretim bitince
bu türev claim'leri release edilebilir. `tmp/` fixture'ları benzersiz geçici dizin
ve cleanup kullanır. Board bookkeeping ve geçici fixture ayrı log üretmez.

Mekanik regresyonlar:

```bash
python3 -B -m unittest discover -s scripts -p 'test_noma_board.py'
```

Agent davranış kabulü: `docs/agent-workflow-checks.md`.

## Örnekler

```bash
python3 scripts/noma_new_note.py kafka-temel-kavramlar --title "Kafka Temel Kavramlar" --type concept --tags kafka
printf 'not içeriği' | python3 scripts/noma_ingest.py - --kind inbox --slug yeni-fikir --title "Yeni Fikir"
python3 scripts/noma_ingest.py ~/Downloads/makale.html --kind clippings --title "Makale"
python3 scripts/noma_find.py --stage inbox --limit 10
python3 scripts/noma_find.py 'kafka|rabbitmq' --hop 2 --human   # --human olmadan yalnız yol
alias w='python3 scripts/noma_wiki.py'
w root --json
w s context                                # varsayılan: yalnız yol
w s context --human
w s agent --hub ai-agent-teknolojileri --json
w p model                                 # seçim için stdin tty olmalı
w hub _basliklar --json                    # terim sözlüğü (başlıklar)
w hub kisisel-bilgi-sistemi --json
w recent --limit 5
w links llm-sistem-ilkeleri --hop 2 --human
w stats
bash scripts/noma-bootstrap.sh --id hermes-vps
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/noma_eval_retrieval.py
printf 'yanıt ... (wiki/slug.md)' | python3 scripts/noma_verify_citations.py
python3 scripts/noma_tend_report.py
python3 scripts/noma_build_graph.py              # graph verisi → web/data/
python3 -B scripts/noma_eval_context.py
python3 -B scripts/noma_eval_context.py --fresh
python3 -B scripts/noma_bench_index.py 1000 10000
python3 -B scripts/noma_bench_index.py 100000 --search
python3 -B scripts/noma_test_node.py --no-llm
```

Notlar:

- `noma_lint.py` aynı zamanda pre-commit kancasıdır (`.pre-commit-config.yaml`,
  `local/noma-lint`): normal commit akışında sözleşme denetimi otomatik koşar.
  Kilitli düğümde bilinçli olarak ERR CRYPT ile durur (sahte yeşil yok).
- `noma_ingest.py` olası injection desenlerinde uyarır ve log'da `[flag]` işaretler
  (ADR-9); `raw/` üzerine asla yazmaz (eşzamanlı çağrıda da append-only).
- Bulut Hermes compose'u yalnız public read-only dosyaları mount eder; içinde
  `wiki/`, `index.md`, `index/`, `.env` veya `.git` yoktur. Bu CLI'ları gerçek wiki için
  kilidi açılmış yerel çalışma alanında çalıştırın.
- `noma_find.py` ve `noma_wiki.py` varsayılan olarak **yalnız yol** basar; başlık,
  tag, tarih ve link hedefi yalnız `--human` ile basılır (AGENTS.md gizlilik/stdout
  sınırı: metadata da gizlidir — `wiki/r4-stdout-read-ayrimi.md`). `--human` yalnız güvenilir yerel terminal içindir; agent/cron
  stdout'una kullanılmaz. Not gövdesi hiçbir modda basılmaz.
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
- `docs/templates/wiki_note.md` bir yapı iskeletidir: `{{Summary}}` ve
  `{{Content}}` doldurulacak bölgelerdir. Renderer şablon gövdesini aynen aktarır;
  şablonda not yönetimi veya agent çalışma yönergesi bulunmaz. Hedef/kapsam
  politikasının sahibi `wiki/yalin-dugum-ilkesi.md`, policy yerleşiminin sahibi
  `wiki/agent-policy.md`'dir.
- Ingest CLI yalnız raw kopyası ve wiki iskeleti hazırlar; mevcut wiki kaydını
  merge etmez ve kaynak içeriğini semantik olarak aktarmaz. Exit 0 ve lint
  başarısı kapsam onayı değildir. Agent, `wiki/wiki-kapsam-butunlugu.md`
  uyarınca kaynak/rapor ve kavram/ayrıntı kayıtlarını doldurup bölüm/ek → wiki
  kapsam eşlemesini karşılaştırır. Depodaki raw yeniden kopyalanmaz; eski notlar
  ilgili içeriksel çalışmada aşamalı tamamlanır.

Kök: [[index]]
