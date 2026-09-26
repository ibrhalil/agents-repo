# Yol Haritası (Roadmap)

> İki araştırmanın (proje analizi + benzer projeler) sentezinden doğdu; yeni yapı
> migrasyonuyla (2026-09-21) güncellendi. Karar kayıtları `wiki/` (decision),
> mimari `docs/ARCHITECTURE.md`, kararlaştırılmamış konular
> `wiki/agent-talimati.md` §45.

Bağ: [[index]] · [[wiki/agent-yapisi|Agent Yapısı]]

---

## Mevcut Durum

Faz 0 tamam (2026-09-20); yeni agent yapısı migrasyonu tamam (2026-09-21). Faz 1
yalnız belge/prep adımlarında ilerledi (A0-A4 tamam);
**canlı düğüm henüz yok** — Noma çalışma ortamı (home Proxmox QEMU VM) kurulmadı,
bulut Hermes mount'u public-only kaldı. Bakım döngüsü CLI'da çalışır; zamanlanmış
iş (cron) henüz yok, commit ve conflict çözümü elle yapılır (bkz. B5).

## Tamamlananlar

| Faz | Kapsam | Tarih |
|---|---|---|
| 0 — İskelet | Sözleşmeler, bilgi hattı, git-crypt, 10 ADR, dil+token+plan protokolü | 2026-09-20 |
| 0.7 — Yeni yapı migrasyonu | atoms kaldırıldı; düz wiki + kebab-case; 12-alan şema; `agent/prompts/` + `agent/sessions/` + `log/` dizinleri; public/şifreli split; agent-yapisi kararı | 2026-09-21 |
| 0.8 — Güvenlik/eşzamanlılık sertleştirme | `raw/` append-only koruması, gizli log sızdırmayan çıktı, şifreli indeks smoke; `noma_eval_context.py` çıkış kodu düzeltildi; 101 test (`python3 -B -m unittest discover -s scripts -p 'test_*.py'`), lint 0 ERR/0 WRN | 2026-09-26 |
| 0.9 — Commit kapısı ve doğrulama sertleştirme | lint: tüm özel staged blob şifreme denetimi, staged silme/append denetimi, okunamayan HEAD/index ayrımı, genel CYCLE, tz-bilinçli updated-bump, metadata sızdırmayan tanılar; ingest/new_note: yazım öncesi doğrulama + atomik not; atıf doğrulayıcıda okunamayan-atıf WARN; hook kısmi-kasa düzeltmesi; `noma_lint` pre-commit kancası; 119 test yeşil, lint 0 ERR/0 WRN | 2026-09-26 |

---

## Faz 1 — Canlıya Alınma

- [x] ~~A0 Kilitli-klon testi~~ PASSED
- [x] ~~A1 Plan dosyası~~
- [x] A2 Obsidian vault rehberi (2026-09-26: `docs/obsidian-recommended.md`)
- [ ] A2b Vault'un uygulanması (kullanıcı tarafı: unlock sonrası filtre ayarı)
- [x] ~~A3 Güvenlik ADR paketi~~ (ADR-7..10)
- [x] ~~A4 README anahtar yedekleme protokolü~~
- [ ] B1 Home Proxmox QEMU VM hazırlığı (düğüm planı VPS'ten bu VM'e döndü;
      kanonik yol `wiki/proxmox-noma-kurulum.md`)
- [ ] B2 Hermes kurulumu (VM içi; `wiki/noma-hermes-vm-docker.md`)
- [ ] B3 `.env` oluşturma + **`NODE_ID` ve provider endpoint'leri**
- [ ] B4 Workspace klonu
- [ ] B5 Zamanlanmış iş (cron) — kullanıcı onayına bağlı; henüz yok
- [ ] B6 Telegram (sonraya atıldı)
- [ ] Güvenlik advisory: LUKS + Obsidian plugin denetimi
- [x] `index.md` git-crypt kapsamına alındı; eski açık indeks geçmişinin
      içerik incelemesi ayrı karar (otomatik history rewrite yok)
- [x] Bulut Hermes mount'u public-only/read-only yapıldı; yerel özel erişim
      için yerel provider düğümü henüz kurulacak
- [x] ~~Branch protection aktifleştirme~~ (gerek kalmadı — PR darboğazı kaldırıldı,
      commit/conflict çözümü B5'e bağlandı; bkz. `wiki/git-akisi-ve-conflict.md`)

---

## Faz 2 — Ingest Hattı

- [x] `raw/inbox/` akışı **yerel uçtan uca** doğrulandı (2026-09-25): gerçek kaynak
      (system-one-karar-modelleri) inbox → ingest → verify → doldurma → hub bağlama →
      build/lint turu tam çalıştı; zamanlanmış koşu B5'e bağlı
- [x] Post-ingest verification (2026-09-25): `noma_ingest.py` yeni notu mekanik doğrular
      (enum/slug/STRUCT/link hedefi); hata → `[verify-fail]` log + not `stage: inbox` kalır;
      bağlantısız not `NO-HUB` uyarısı verir — içerik hiçbir çıktıya taşınmaz
- [x] Ingest regex ön-taraması (ADR-9 K3): EN+TR injection desenleri + uzun base64 bloğu —
      yalnız `[flag]` uyarır, bloklamaz (yetki sınırı ADR-9'un kendisi)
- [ ] FreshRSS kurulumu (Docker) + saatlik keyword push (regex, LLM'siz)
- [ ] Sabah gündem digest'i; değerli içerik yolu: digest → `raw/clippings/` → wiki (serbest yazma)

---

## Faz 3 — Bakım Döngüsü

- [x] `lint()` on denetim mevcut ve test kapsamında (2026-09-26): kırık link,
      orphan, enum, updated-bump, satır bütçeleri, `.gitattributes` ↔ şifreli
      dizin tutarlılığı, public dizin kişisel veri taraması, döngüsel Links
      (CYCLE), bayat stage (STALE), bölüm sırası (STRUCT) — CYCLE/STALE
      2026-09-23'te, STRUCT 2026-09-24'te eklendi; 0.9'da CYCLE genel döngüye
      genişletildi, updated-bump tz-bilinçli oldu ve staged blob/silme denetimi
      eklendi (119 test yeşil)
- [ ] `lint()` kalan: ORPHAN şiddeti yalnız INFO; satır bütçesi kapsamı 2
      dosyada — genişletme gerekçe ister
- [x] `raw/` append-only eşzamanlı ingest, mevcut notu koruyan smoke,
      gizli log satırı basmayan linter ve şifreli indeksi doğrulayan smoke testi
- [x] Filed-back query kuralı kabul edildi (2026-09-23): değerli sentez atomik not
      olarak wiki'ye geri dosyalanır; log'a `-> filed: wiki/slug.md` kaydı
      (AGENTS §2, SCHEMA §2; [[llm-wiki-deseni]] adaptasyonu)
- [ ] Zamanlanmış `tend()` koşusu — mekanik rapor yerelde hazır ve temiz
      (2026-09-26: `scripts/noma_tend_report.py --no-log` → HUB-FULL/INBOX/
      NO-HUB/STALE = 0); iki hub notundaki `stage: inbox` tıkanıklığı aynı
      tarihte çözüldü. Zamanlanmış iş B5'e bağlı. `consolidate()` **yok**
      (uygulama ve rapor aracı mevcut değil)
- [x] `agent/sessions/` adlandırma kuralı + özet şablonu (2026-09-23): adlandırma
      SCHEMA §1; şablon `docs/templates/session_summary.md`
- [x] `log/` logging tasarımı kararlaştır (2026-09-23): günlük `YYYY-MM-DD.md`
      dosyaları, `HH:mm <op> @<node> <aktör> | mesaj ≤120` (SCHEMA §5);
      `log/*.md` **git-tracked**, append-only kuralı lint tarafından HEAD'e
      karşı diff ile mekanik olarak zorlanır
- [x] Kök indeks küçük girişe, hub haritaları şifreli/sayfalı türeve ayrıldı
      (`wiki/sayfali-turetilmis-indeks.md`); `root`/`hub` yalnız ilgili sayfayı okur.
- [ ] Kararlaştırılmayı bekleyen mimariler (`wiki/agent-talimati.md` §45):
      Master DB view'ları, graph, indekslenmiş arama/embedding — gerçek ihtiyaç
      ortaya çıktığında tasarım önerisiyle ele alınır

---

## Faz 4 — Semantic + Çoklu Düğüm

- [ ] Ev düğümü: Ollama provider, aynı repo klonu (ADR-8 hassas kapsam yerelde)
- [ ] On-demand semantic search (yerel embedding; mimari §45-9 ile kararlaştırılacak)
- [ ] Katman bazlı çatışma çözüm politikası
- [ ] İkinci bare-mirror (şifreli disk) + anahtar escrow; model fallback

---

## Faz 5 — Genişleme

- [ ] WhatsApp/Signal gateway + sesli not transkripsiyonu
- [ ] Ek integration'lar (takvim, RSS e-posta)
- [x] ~~Sözleşme kompakt versiyonu (token verimliliği)~~ (2026-09-23: AGENTS/SCHEMA
      makine-okunur kompakt formda yeniden yazıldı)
- [ ] Web UI: view katmanı tasarımı (tech seçimi §45-13 ile; `web/` iskeleti
      2026-09-23'te kaldırıldı — gerekirse yeniden kurulur)
