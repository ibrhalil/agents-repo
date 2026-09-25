# Yol Haritası (Roadmap)

> İki araştırmanın (proje analizi + benzer projeler) sentezinden doğdu; yeni yapı
> migrasyonuyla (2026-09-21) güncellendi. Karar kayıtları `wiki/` (decision),
> mimari `docs/ARCHITECTURE.md`, kararlaştırılmamış konular
> `wiki/yeni-agent-yapisi.md` §45.

Bağ: [[index]] · [[wiki/yeni-agent-yapisi|Yeni Agent Yapısı]]

---

## Mevcut Durum

Faz 0 tamam (2026-09-20); yeni agent yapısı migrasyonu tamam (2026-09-21). Faz 1
kısmen başladı (A0-A4 tamam, VPS erişimi bekleniyor).

## Tamamlananlar

| Faz | Kapsam | Tarih |
|---|---|---|
| 0 — İskelet | Sözleşmeler, bilgi hattı, git-crypt, 10 ADR, dil+token+plan protokolü | 2026-09-20 |
| 0.7 — Yeni yapı migrasyonu | atoms kaldırıldı; düz wiki + kebab-case; 12-alan şema; agent/workspace/tools/config/log/web dizinleri; public/şifreli split; yeni-agent-yapisi kararı | 2026-09-21 |

---

## Faz 1 — Canlıya Alınma

- [x] ~~A0 Kilitli-klon testi~~ PASSED
- [x] ~~A1 Plan dosyası~~
- [ ] A2 Obsidian vault ayarı *(kullanıcı tarafı; `docs/obsidian-recommended.md` yazılacak)*
- [x] ~~A3 Güvenlik ADR paketi~~ (ADR-7..10)
- [x] ~~A4 README anahtar yedekleme protokolü~~
- [ ] B1 VPS hazırlığı
- [ ] B2 Hermes kurulumu
- [ ] B3 `.env` oluşturma + **`NODE_ID` ve provider endpoint'leri**
- [ ] B4 Workspace klonu
- [ ] B5 Cron job'lar (consolidate, lint, sabah bülteni)
- [ ] B6 Telegram (sonraya atıldı)
- [ ] Güvenlik advisory: LUKS + Obsidian plugin denetimi
- [x] `index.md` git-crypt kapsamına alındı; eski açık indeks geçmişinin
      içerik incelemesi ayrı karar (otomatik history rewrite yok)
- [x] Bulut Hermes mount'u public-only/read-only yapıldı; yerel özel erişim
      için yerel provider düğümü henüz kurulacak
- [x] ~~Branch protection aktifleştirme~~ (gerek kalmadı — PR darboğazı kaldırıldı,
      commit/conflict çözümü cron'a devredildi; bkz. `wiki/main-insana-aittir.md`)

---

## Faz 2 — Ingest Hattı

- [x] `raw/inbox/` akışı **yerel uçtan uca** doğrulandı (2026-09-25): gerçek kaynak
      (system-one-karar-modelleri) inbox → ingest → verify → doldurma → hub bağlama →
      build/lint turu tam çalıştı; cron canlılığı VPS'e (B5) bağlı
- [x] Post-ingest verification (2026-09-25): `noma_ingest.py` yeni notu mekanik doğrular
      (enum/slug/STRUCT/link hedefi); hata → `[verify-fail]` log + not `stage: inbox` kalır;
      bağlantısız not `NO-HUB` uyarısı verir — içerik hiçbir çıktıya taşınmaz
- [x] Ingest regex ön-taraması (ADR-9 K3): EN+TR injection desenleri + uzun base64 bloğu —
      yalnız `[flag]` uyarır, bloklamaz (yetki sınırı ADR-9'un kendisi)
- [ ] FreshRSS kurulumu (Docker) + saatlik keyword push (regex, LLM'siz)
- [ ] Sabah gündem digest'i; değerli içerik yolu: digest → `raw/clippings/` → wiki (serbest yazma)

---

## Faz 3 — Bakım Döngüsü

- [ ] `lint()` tam set: kırık link, orphan, enum, updated-bump, satır bütçeleri,
      `.gitattributes` ↔ şifreli dizin tutarlılığı, public dizin kişisel veri taraması,
      döngüsel Links (CYCLE), bayat stage (STALE), bölüm sırası (STRUCT) —
      CYCLE/STALE 2026-09-23'te, STRUCT 2026-09-24'te eklendi
       (`llm-wiki-deseni` notundan adaptasyon)
- [x] `raw/` append-only eşzamanlı ingest, mevcut notu koruyan smoke,
      gizli log satırı basmayan linter ve şifreli indeksi doğrulayan smoke testi
- [x] Filed-back query kuralı kabul edildi (2026-09-23): değerli sentez atomik not
      olarak wiki'ye geri dosyalanır; log'a `-> filed: wiki/slug.md` kaydı
      (AGENTS §2, SCHEMA §2; [[llm-wiki-deseni]] adaptasyonu)
- [ ] `tend()` + `consolidate()` cron'da canlı — mekanik rapor yerelde hazır
      (2026-09-25, `scripts/noma_tend_report.py`: HUB-FULL/INBOX/NO-HUB/STALE);
      cron koşusu VPS'e (B5) bağlı
- [x] `agent/sessions/` adlandırma kuralı + özet şablonu (2026-09-23): adlandırma
      SCHEMA §1; şablon `docs/templates/session_summary.md`
- [x] `log/` logging tasarımı kararlaştı (2026-09-23): günlük `YYYY-MM-DD.md` dosyaları,
      `HH:mm <op> @<node> | mesaj ≤120`; runtime loglar commit edilmez (SCHEMA §5)
- [x] Kök indeks küçük girişe, hub haritaları şifreli/sayfalı türeve ayrıldı
      (`wiki/sayfali-turetilmis-indeks.md`); `root`/`hub` yalnız ilgili sayfayı okur.
- [ ] Kararlaştırılmayı bekleyen mimariler (wiki/yeni-agent-yapisi.md §45):
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
