# SCHEMA.md — Veri Sözleşmesi

agents-repo'nun normatif veri tanımları: insan ve agent'lerin ortak okuduğu/yazdığı
her dosya formatı burada. Çelişkide bu dosya kazanır; değişiklik = insan onayı (MR).

## 1. Dizin anlamları

| Dizin | Rol | Yazma kuralı |
|---|---|---|
| `raw/` | Ham kaynaklar: konuşmalar, clippings, inbox düşmeleri | APPEND-ONLY — sonradan asla değişmez/silinmez |
| `atoms/` | Atomik gerçekler: 1 dosya = 1 iddia | APPEND-ONLY — düzeltme = supersede eden yeni atom |
| `wiki/` | Derlenmiş, bağlantılı bilgi tabanı (Obsidian vault) | Agent: MR ile; insan: serbest |
| `memory/` | Kullanıcı profili — kanonik kaynak | MR ile |
| `plans/` | Uzun işlerin plan dosyaları (AGENTS.md §Uzun İşler) | MR ile |
| `sdata/` | Yapılandırılmış uygulama verisi (JSON/YAML) | Agent serbest |
| `data/` | Üretilen index, embedding, cache | gitignore — her zaman yeniden üretilebilir |
| `soul/` `skills/` `mcp/` `deploy/` `docs/` | Runtime katmanları | Normal geliştirme akışı |

## 2. Bilgi hattı

`raw ─çıkarım→ atoms ─derleme→ wiki`; wiki her zaman atoms'tan, atoms raw'dan
yeniden üretilebilir. Index/embedding/vector DB **asla** truth değildir.

## 3. Wiki not formatı

```yaml
---
id: Bilgi Hattı                    # zorunlu; benzersiz = dosya adı (insan-okur başlık)
title: Bilgi hattı raw → atoms → wiki olarak kuruldu   # zorunlu; açıklayıcı
adr: 1                             # yalnız decisions/; en yüksekten devam, back-fill yok
type: decision                     # person|project|area|concept|resource|decision|task|issue
stage: done                        # inbox|next|in_progress|waiting|done|archived (opsiyonel)
status: established                # unverified | established | stub (epistemik; ADR-5)
scope: systems                     # work|personal|learning|systems|creator|media|common
priority: high                     # opsiyonel: high | medium | low | none
date: 2026-09-20                   # opsiyonel; task/issue: teslim; diğer: inceleme
url: https://ornek.com             # opsiyonel; resource: orijinal kaynak
parent: Üst Not Başlığı            # opsiyonel tek üst-link; children index'ten türetilir
created: 2026-09-20                # değiştirilmez
updated: 2026-09-20                # her düzenlemede bump (lint)
tags: [mimari, bilgi-sistemi]      # kısa ASCII; scope değeri tekrarlanmaz (lint)
locked: false                      # opsiyonel; true → agent dokunmaz
---
```

**Adlandırma:** wiki dosya adı = insan-okur Türkçe başlık (Unicode serbest); `id` =
dosya adı; ASCII yalnız tag/atom-id/branch'te (ADR-4). **type ↔ dizin:** `people/
projects/ areas/ concepts/ resources/ decisions/ tasks/ issues/` — ADR sırası `adr:`
alanındadır; `scope:` yaşam alanıdır (frontmatter filtresi, dizin değil).

**status (epistemik) × stage (iş akışı) — ortogonal boyutlar (ADR-5):** `status`:
`unverified` → `established` yalnız ikinci bağımsız kaynak/insan onayıyla; `stub` =
iskelet (tend adayı). `stage`: `inbox` = işlenmemiş (eski `imported` buraya birleşti);
task/issue `inbox`'tan başlar. **Dondurulmuş kararlar:** `decision` + `established`
yeniden tartışılmaz; çelişkide yeni ADR yazılır, eskiyi supersede eder.

**Yapısal ilk-okuma kuralı:** navigasyon bloğu gövdeden önce — `frontmatter →
# Başlık → özet → ## İlişkili → gövde`; her kısmi okuma (grep penceresi, cold-open,
subagent özet) isim+tags+scope+özet+ilişkileri kendi kendine görür; lint denetler (ADR-4).

**updated kuralı:** her wiki/memory düzenlemesi `updated:`'i bump eder; bump'sız
değişen not = lint bulgusu. Geri alma: `git log <dosya>` + MR diff.

**Link:** `[[Başlık]]` — hedefin dosya adı; dizin yolu içermez (Obsidian uyumu).
Kırık link lint bulgusudur. `## İlişkili` girdisi: `- [[Başlık]] — mikro açıklama`.

**Yalın düğüm ilkesi (ADR-6):** bir not tek fikre odaklanır; gövde kısadır — detay
büyürse child nota bölünür ya da atoms'ta bırakılır. İlişkiler **tek yönlü** yazılır
(yön: özelden genele); reciprocal back-link yazılmaz — graph kenarı zaten iki yönlü
çizer. Aynı şeyi söyleyen notlar birleştirilir (MR).

**Master Note DB eşlemesi (ingest normalizasyonu):** Type:Raw→`stage:inbox` ·
Note→`concept` · Issue→`issue` · Resource→`resource` · Task&Ticket→`task` ·
Project→`project`; Area→`scope` · Status→`stage` · Priority→`priority` · URL→`url` ·
Parent/Children→`parent:` (tek yön) · ID/Identity→`id = dosya adı` (ADR-4).

## 4. Atom formatı

```yaml
---
id: a-0007                         # opak sıralı ASCII id; tarih yalnız date: alanında
claim: Örnek tek cümlelik iddia.   # tek cümlelik iddia (Türkçe)
source: raw/conversations/2026-09-20-1707.md   # tercihen raw/ yolu
date: 2026-09-20
confidence: high                   # high | medium | low
status: established
superseded_by:                     # opsiyonel; geçersiz kılan yeni atomun id'si
---
```

Atom asla düzenlenmez; düzeltme = yeni atom + `superseded_by` işareti (lint).

## 5. raw/ adlandırma

- `conversations/YYYY-MM-DD-HHmm.md` · `clippings/c-<NNNN>.md` — yollar nötrdür
- `inbox/*` — işlenmemiş düşme; işlenince asıl yerine taşınır, hedef `log.md`'ye

## 6. wiki/ özel dosyaları

| Dosya | Rol | Kural |
|---|---|---|
| `index.md` | Katalog | **ÜRETİLİR** (build_index, Faz 3) — wikilink'siz, yol bazlı |
| `hot.md` | Çalışma özeti | ≤50 satır; her oturumda yüklenir; aşım = lint bulgusu |
| `log.md` | Operasyon günlüğü | append-only; tek satır kayıtlar; geçmiş asla düzenlenmez |

`log.md` formatı: `## [YYYY-MM-DD HH:mm] <ingest|query|tend|lint|sync> | tek satır özet`

## 7. memory/profile.md

Bölümler: Kimlik · İletişim tercihlerim · Çalışma tarzım · Öncelikler ve sınırlar.
Hermes'in yerleşik hafızası bu dosyanın düğüm-lokal önbelleğidir; kanonik kaynak burası.

## 8. sdata/

Küçük JSON/YAML dosyaları; programatik uygulama verisi (habit, görev). Bilgi
tabanının parçası değildir; şema dosyanın kendisinde belgelenir.

## 9. Öncelik

**SCHEMA.md > AGENTS.md > not içerikleri.** Kural değişikliği = MR.

## 10. Dil ve Yol Politikası

- Gövde/atom/cevap dili: **Türkçe**; anlam bozan köklü terim/kalıp İngilizce kalabilir.
- Başka dil yok — **dil öğrenme hariç** (`lang:` alanı, `wiki/resources/<dil>/`).
- `raw/` **verbatim** — kaynak hangi dildeyse öyle saklanır; dönüşüm atoms/wiki'de.
- Tag/slug/id: **kısa ASCII** (wiki dosya adları hariç — bkz. §3).
- Yollar fact-düzeyi kişisel bilgi taşımaz (kimlik/sağlık/finans/alışkanlık);
  konu-düzeyi serbest — kişisel fact nötr ad + şifreli içerikle yaşar.

## 11. Token verimliliği (format kuralları)

- Frontmatter'a yalnız anlamlı alanlar yazılır; her not tek paragraf özetle başlar
  (§3); büyük notlar heading-bazlı dilimlenir — context'e tamamı girmez.
- `log.md` kaydı tek satır; atom `claim` tek cümle.
- ripgrep .gitignore'a saygılıdır → `data/` aramalardan doğal dışlanır;
  tam-proje taraması yalnızca cron'da (AGENTS.md, ADR-4).
- Türkçe+İngilizce karışımı: eklemeli Türkçe BPE'de kelime başına daha çok token'a
  parçalanır; köklü terimi İngilizce bırakmak anlamı ve token yoğunluğunu korur.
