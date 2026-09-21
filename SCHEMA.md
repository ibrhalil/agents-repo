# SCHEMA.md — Veri Sözleşmesi

Normatif veri tanımları: insan ve agent'lerin ortak okuduğu/yazdığı her format burada.
Çelişkide bu dosya kazanır; değişiklik = insan onayı (MR). Mimari kararların temel
kaynağı: `plans/Yeni Agent Yapısı.md` — orada "henüz karar verilmedi" denilen konular
burada da kararlaştırılmış sayılmaz.

## 1. Dizinler ve görünürlük (public repo)

| Dizin | Görünürlük | Rol | Yazma kuralı |
|---|---|---|---|
| `raw/` | şifreli | Ham kaynaklar: inbox, conversations, clippings | APPEND-ONLY — sonradan değiştirilmez/silinmez |
| `wiki/` | şifreli | Kanonik knowledge garden — **düz**, alt klasörsüz | Agent: MR ile; insan: serbest |
| `memories/` | şifreli | Agent'ın kalıcı hafızası / kullanıcı profili | MR ile |
| `agent/prompts/` | şifreli | Prompt hazırlama / normalizasyon | MR ile |
| `agent/sessions/` | şifreli | Session summary (transcript **değil**) | MR ile |
| `plans/` | şifreli | Uzun iş plan dosyaları | MR ile |
| `log/` | şifreli | Operasyonel log (commit edilen kayıtlar) | append-only |
| `agent/` (kök) | public | Agent altyapısı | normal geliştirme |
| `workspace/` | public | Geçici çalışma alanı — canonical değil | serbest; kalıcı değer canonical alana taşınır |
| `tools/` `skills/` `scripts/` | public | Tool tanımı · çalışma yöntemi · executable | normal geliştirme |
| `config/` | public | Konfigürasyon — **secret plaintext yasak** | normal geliştirme |
| `web/` | public | Web UI — presentation layer, truth değil | normal geliştirme |
| `docs/` | public | Teknik dokümantasyon, şablonlar | normal geliştirme |

Public dizinlere kişisel/fact-düzeyi veri yazılmaz (AGENTS §Görünürlük).

## 2. Bilgi hattı

`raw ─derleme→ wiki` (iki katman; `atoms/` kaldırıldı — [[yeni-agent-yapisi|Yeni
Agent Yapısı]] kararı). Wiki tek kanonik tabandır; index/graph/view'lar türetilir,
silinse yeniden üretilebilir — **asla truth değildir**.

## 3. Wiki not formatı

```yaml
---
title: "Tam ve açıklayıcı başlık"  # zorunlu; insan-okur, Unicode serbest
type: concept                      # zorunlu; concept|project|task|issue|resource|person|decision
stage: done                        # zorunlu; inbox|next|in_progress|waiting|done|archived
scope: systems                     # zorunlu; work|personal|learning|systems|creator|media|common
status: established                # opsiyonel; unverified|established|stub
priority: none                     # opsiyonel; high|medium|low|none
custom_date:                       # opsiyonel; kullanıcı-anlamlı tarih (format HENÜZ KARAR VERİLMEDİ)
url: https://...                   # opsiyonel; kaynak/bookmark — type bağımsız
tags: [kisa, ascii]                # opsiyonel; scope değeri tekrarlanmaz (lint)
created: 2026-09-20                # system-managed; değiştirilmez
updated: 2026-09-21                # system-managed; anlamlı değişiklikte bump (lint)
locked: false                      # opsiyonel; true → agent mutation + otomatik bakım dışı
---
```

**Kimlik:** global `id` yok — **dosya adı = stable kimlik**.

**Adlandırma:** `kebab-case.md` — küçük harf ASCII slug (translit: ı/İ→i, ş→s,
ğ→g, ü→u, ö→o, ç→c; boşluk→tire). Filename kişisel bilgi/secret taşımaz; `title` ≠
filename serbesttir. `_v2`/`_yeni` gibi sürüm ekleri yasak — bilgi değişirse mevcut
dosya güncellenir.

**type:** klasör yok; classification yalnız metadatada (`note`/`area` type'ı yok —
domain `scope`'ta). Yeni type ancak gerçek ihtiyaçla eklenir.

**stage × status — ortogonal:** `stage` iş/lifecycle; `status` epistemik.
`unverified → established` yalnız ikinci bağımsız kaynak/insan onayıyla; `stub` =
iskelet (tend adayı). `stage` kayıt içeriğinden değerlendirilerek atanır — type→stage
otomatik eşlemesi yoktur; çıkarılamıyorsa `inbox`.

**Yapısal ilk-okuma kuralı:** `frontmatter → # Başlık → ## Links → ## Summary →
gövde` — her kısmi okuma (grep penceresi, subagent özeti) kendi kendine yeter; lint
denetler.

**Link:** `[[slug|Görünen Başlık]]` — hedef filename, alias görüneni korur. Kırık
link lint bulgusudur. İlişkiler **tek yönlü** yazılır (özelden genele); reciprocal
back-link yazılmaz; `parent:` alanı yok — graph kenarı zaten iki yönlü çizer. Bir
not tek fikre odaklanır (yalın düğüm); aynı şeyi söyleyen notlar birleştirilir (MR).

**`created`/`updated`:** system-managed — kullanıcıya manuel yönettirilmez;
düzenleyen agent bump eder, lint bump'sız değişimi bulur. Geri alma: `git log
<dosya>` + MR diff.

## 4. Karar kayıtları

Eski `adr:` numaraları (ADR-1..10) tarihsel referans olarak title'da yaşar. Yeni
kararlar **numarasız** `type: decision` kaydıdır. Bir kararı geçersiz kılan yeni
kayıt, supersede edilen notun gövdesinde açıkça belirtilir — sessiz unutma yok.
Dondurulmuş kararlar (established decision) yeniden tartışılmaz; çelişkide yeni
karar kaydı yazılır.

## 5. raw/ adlandırma

- `conversations/YYYY-MM-DD-HHmm.md` · `clippings/c-<NNNN>.md` · `inbox/*` — yollar nötr
- İşlenme işaretleme/taşıma **henüz karar verilmedi**; dosya append-only yerinde kalır, hedefi log'a kaydedilir.

## 6. memories/

`memories/profile.md` — kanonik kullanıcı profili (Kimlik · İletişim · Çalışma
tarzı · Öncelikler/sınırlar). Wiki genel bilgi bahçesidir; memories agent'ın kalıcı
hafızasıdır — birbirinin yerine kullanılmaz.

## 7. agent/sessions/

Session summary: kararlar, önemli sonuçlar, değişen kurallar, follow-up'lar, sonraki
agent için bağlam. Raw chat transcript kalıcı saklanmaz; adlandırma kuralı ilk
gerçek session'da kararlaştırılacak.

## 8. log/

Operasyonel log. Hedef format Spring-Boot benzeri satır (`timestamp level component
message`) ama implementasyon **henüz tasarlanmadı**. Mevcut `log/log.md` geçmiş kayıtları
**verbatim** korunur; yeni kayıtlar aynı formatta eklenir. Runtime logların tamamının
commit'i hedeflenmez.

## 9. Öncelik

**SCHEMA.md > AGENTS.md > not içerikleri.** Kural değişikliği = MR.

## 10. Dil ve yol politikası

- Gövde/cevap dili: **Türkçe**; anlam bozan köklü terim/kalıp İngilizce kalabilir.
- Başka dil yok — **dil öğrenme notları hariç** (`lang:` alanı).
- `raw/` **verbatim** — kaynak hangi dildeyse öyle saklanır; dönüşüm wiki'de.
- Tag/slug/filename: **kısa ASCII**. Yollar fact-düzeyi kişisel bilgi taşımaz
  (kimlik/sağlık/finans/alışkanlık); kişisel fact nötr ad + şifreli içerikle yaşar.

## 11. Token verimliliği

- Frontmatter'a yalnız anlamlı alanlar; her not özetle başlar; büyük notlar
  heading-bazlı dilimlenir — context'e tamamı girmez.
- Log kaydı tek satır. ripgrep .gitignore'a saygılıdır → `data/` aramalardan doğal
  dışlanır; tam-proje taraması yalnızca cron'da. Türkçe+İngilizce karışımı: köklü
  terimi İngilizce bırakmak anlamı ve token yoğunluğunu korur.

## 12. Henüz karar verilmedi (plans/Yeni Agent Yapısı.md §45)

`custom_date` formatı · yeni not filename üretim algoritması · raw işlenme işareti ·
maintenance job frekansı · Master DB · graph/index · search/embedding · Docker
sandbox güvenlik modeli · tools/skills/MCP sınırları · config dosya formatı · web
teknolojisi · SOUL/USER gibi context dosyaları · log runtime implementasyonu ·
`data/`/`sdata/`/`deploy/` gibi ek dizinlerin geleceği. Bunlar hakkında konuşurken
"henüz karar verilmedi" kabul et.
