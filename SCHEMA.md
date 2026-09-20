# SCHEMA.md — Veri Sözleşmesi

Bu dosya agents-repo'nun normatif veri tanımlarıdır: insan ve agent'lerin ortak
okuduğu/yazdığı her dosya formatı burada tanımlanır. Çelişkide bu dosya kazanır;
değişiklik yalnız insan onayıyla (MR).

## 1. Dizin anlamları

| Dizin | Rol | Yazma kuralı |
|---|---|---|
| `raw/` | Ham kaynaklar: konuşmalar, clippings, inbox düşmeleri | APPEND-ONLY — sonradan asla değişmez/silinmez |
| `atoms/` | Atomik gerçekler: 1 dosya = 1 iddia | APPEND-ONLY — düzeltme = supersede eden yeni atom |
| `wiki/` | Derlenmiş, bağlantılı bilgi tabanı (Obsidian vault) | Agent: MR ile; insan: serbest |
| `memory/` | Kullanıcı profili — kanonik kaynak | MR ile |
| `plans/` | Uzun işlerin plan dosyaları (AGENTS.md §Uzun İşler) | HIZLI şerit |
| `sdata/` | Yapılandırılmış uygulama verisi (JSON/YAML) | Agent serbest |
| `data/` | Üretilen index, embedding, cache | gitignore — her zaman yeniden üretilebilir |
| `soul/` `skills/` `mcp/` `deploy/` `docs/` | Runtime katmanları | Normal geliştirme akışı |

## 2. Bilgi hattı

`raw ─çıkarım→ atoms ─derleme→ wiki`. Wiki her zaman atoms'tan, atoms raw'dan
yeniden üretilebilir olmalıdır. Index/embedding/vector DB **asla** truth değildir.

## 3. Wiki not formatı

```yaml
---
id: spring-transactional        # zorunlu; benzersiz slug = dosya adı; ASCII
title: Spring Transactional     # zorunlu
type: concept                   # person | project | area | concept | resource | decision
status: established             # unverified | established | imported | stub
created: 2026-09-20
updated: 2026-09-20
tags: [transaction, spring]     # kısa ASCII; lint yakın-çoğaltmayı bayraklar
scope: [software-development]   # opsiyonel hiyerarşik alan; v1'de araç desteği yok
locked: false                   # opsiyonel; true → agent dokunmaz
---
```

**status kuralları:** `unverified` (tek gözlem) → `established` yalnızca ikinci bağımsız
kaynak veya insan onayıyla yükseltilir. `imported` = inbox'tan mekanik geçti, işlenmedi.
`stub` = iskelet. Son ikisi tend operasyonunun adaylarıdır.

**Dondurulmuş kararlar:** `type: decision` + `status: established` notlar tekrar
tartışılmaz/tersine çevrilmez; çelişki görürsen yeni ADR yaz, eskiyi supersede et.

**Bölüm düzeni:** `# Başlık` → **tek paragraf özet (zorunlu** — context builder'ın
birincil malzemesi) → gövde → `## Related`.

**Link sözdizimi:** `[[slug]]` — dizin yolu içermez (taşınabilirlik + Obsidian uyumu);
kırık link lint bulgusudur. **type ↔ dizin:** `people/` `projects/` `areas/` `concepts/`
`resources/` `decisions/` (ADR: `NNNN-slug.md`; numara boşlukları back-fill edilmez).

## 4. Atom formatı

```yaml
---
id: 2026-09-20-jarvis-faz0-onaylandi   # benzersiz; tarih önekli önerilir
claim: Faz 0 onaylandı.                # tek cümlelik iddia (Türkçe)
source: raw/conversations/2026-09-20-1200.md   # tercihen raw/ yolu
date: 2026-09-20
confidence: high                # high | medium | low
status: established
superseded_by:                  # opsiyonel; geçersiz kılan yeni atomun id'si
---
```

Atom asla düzenlenmez; iddia değişirse yeni atom yazılır, eskisinin `superseded_by`
alanı lint/mutasyon aracı tarafından işaretlenir.

## 5. raw/ adlandırma

- `conversations/YYYY-MM-DD-HHmm.md` — oturum dökümleri
- `clippings/<slug>-<YYYYMMDD>.md` — dışarıdan alınan içerik
- `inbox/*` — işlenmemiş düşme; işlenince asıl yerine taşınır, hedef `log.md`'ye yazılır

## 6. wiki/ özel dosyaları

| Dosya | Rol | Kural |
|---|---|---|
| `index.md` | Katalog | **ÜRETİLİR** (build_index aracı, Faz 3) — elle düzenlenmez |
| `hot.md` | Çalışma özeti | ≤50 satır; her oturumda yüklenir; aşım = lint bulgusu |
| `log.md` | Operasyon günlüğü | append-only; tek satır kayıtlar; geçmiş asla düzenlenmez |

`log.md` formatı: `## [YYYY-MM-DD HH:mm] <ingest|query|tend|lint|sync> | tek satır özet`

## 7. memory/profile.md

Bölümler: `## Kimlik` · `## İletişim tercihlerim` · `## Çalışma tarzım` ·
`## Öncelikler ve sınırlar`. Hermes'in yerleşik hafızası bu dosyanın düğüm-lokal
önbelleğidir; kanonik kaynak burasıdır.

## 8. sdata/

Küçük JSON/YAML dosyaları; programatik uygulama verisi (habit, görev). Bilgi tabanının
parçası değildir; şema dosyanın kendisinde belgelenir.

## 9. Öncelik

**SCHEMA.md > AGENTS.md > not içerikleri.** Kural değişikliği = MR.

## 10. Dil Politikası

- Gövde/atom/cevap dili: **Türkçe**; anlam bozan köklü terim/kalıp İngilizce kalabilir.
- Başka dilde not yazılmaz — **dil öğrenme notları hariç**: opsiyonel `lang:`
  frontmatter alanı + ad alanı önerisi `wiki/resources/<dil>/` (ör. `resources/japanese/`).
- `raw/` **verbatim** — kaynak hangi dildeyse öyle saklanır; dil dönüşümü yalnızca
  atoms/wiki katmanında yapılır.
- Tag/slug/id: **kısa ASCII** (dil serbest; Türkçe karakterler normalize edilir).

## 11. Token verimliliği (format kuralları)

- Frontmatter'a yalnız anlamlı alanlar yazılır; boş opsiyonel alan yazılmaz.
- Her wiki notu tek paragraf özetle başlar (§3); büyük notlar heading-bazlı dilimlenir —
  context'e tamamı değil ilgili bölümü girer.
- `log.md` kaydı tek satır; atom `claim` tek cümle.
- Türkçe + İngilizce karışımın gerekçesi: eklemeli Türkçe BPE tokenizer'da kelime
  başına daha çok token'a parçalanır; köklü terimi İngilizce bırakmak anlamı ve token
  yoğunluğunu korur.
