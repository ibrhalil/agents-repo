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
- [ ] Branch protection aktifleştirme (ADR-10 koşulu; GitHub ayarı)

---

## Faz 2 — Ingest Hattı

- [ ] `raw/inbox/` akışı canlı: inbox → anlama → wiki MR
- [ ] Post-ingest verification — ingest sonrası otomatik format/link denetimi
- [ ] Ingest regex ön-taraması (injection flag; ADR-9 K3)
- [ ] FreshRSS kurulumu (Docker) + saatlik keyword push (regex, LLM'siz)
- [ ] Sabah gündem digest'i; değerli içerik yolu: digest → `raw/clippings/` → wiki MR

---

## Faz 3 — Bakım Döngüsü

- [ ] `lint()` tam set: kırık link, orphan, enum, updated-bump, satır bütçeleri,
      `.gitattributes` ↔ şifreli dizin tutarlılığı, public dizin kişisel veri taraması
- [ ] `tend()` + `consolidate()` cron'da canlı
- [x] `agent/sessions/` adlandırma kuralı + özet şablonu (2026-09-23): adlandırma
      SCHEMA §7; şablon `docs/templates/session_summary.md`
- [x] `log/` logging tasarımı kararlaştı (2026-09-23): günlük `YYYY-MM-DD.md` dosyaları,
      `HH:mm <op> @<node> | mesaj ≤120`; runtime loglar commit edilmez (SCHEMA §8)
- [ ] Kararlaştırılmayı bekleyen mimariler (wiki/yeni-agent-yapisi.md §45):
      Master DB view'ları, graph/index, search/embedding — gerçek ihtiyaç
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
- [ ] Sözleşme kompakt versiyonu (token verimliliği)
- [ ] `web/` UI: view katmanı tasarımı (tech seçimi §45-13 ile)
