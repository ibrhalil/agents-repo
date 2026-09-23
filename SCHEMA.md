# SCHEMA.md — Veri Sözleşmesi
ZORUNLU: Makine okuması için optimize edilmiştir. Detaylar/gerekçeler için wiki'ye (örn: [[agent-policy]]) bakınız. Çelişkide SCHEMA kazanır.
## 1. Dizinler ve Rolleri
`raw/` (Şifreli): Ham kaynaklar (inbox, conversations). APPEND-ONLY.
`wiki/` (Şifreli): Kanonik ağaç (Tree). Alt klasör YOKTUR.
`memories/` (Şifreli): Agent kalıcı hafıza ve kullanıcı profili.
`agent/prompts/` & `agent/sessions/` (Şifreli): Prompt hazırlık ve session özetleri (`YYYY-MM-DD-<kısa-slug>.md`).
`plans/` (Şifreli): Çok adımlı uzun işlerin durum dosyaları.
`log/` (Şifreli): Günlük operasyonel loglar (Append-only).
`tmp/` (Şifreli/Gitignore): Geçici (scratch) işlem dizini. Kalıcı çöp bırakılmaz.
`agent/` (Public): Agent root altyapısı.
`skills/` & `scripts/` (Public): Yetenek tanımları ve çalıştırılabilir kodlar.
`docs/` (Public): Mimari kararlar, şablonlar, yol haritası.
## 2. Bilgi Hattı ve Keşif
Üretim: `raw/` -> `wiki/` (2 katman).
Harita: Tek kanonik giriş `index.md`'dir. `index.md` cron tarafından wiki'deki `## Links` yönünden (özelden genele) otomatik üretilir.
## 3. Wiki Not Formatı (Frontmatter)
ZORUNLU ŞABLON: `docs/templates/wiki_note.md`
```yaml
---
title: "İnsan okur başlık" # ZORUNLU
type: concept # ZORUNLU (concept | project | task | issue | resource | person | decision)
stage: done # ZORUNLU (inbox | next | in_progress | waiting | done | archived)
scope: systems # ZORUNLU (work | personal | learning | systems | creator | media | common)
status: established # OPSİYONEL (unverified | established | stub)
tags: [kisa, ascii] # OPSİYONEL (scope tekrarı YASAKTIR)
created: 2026-09-23T15:42:00+03:00 # ZORUNLU (ISO 8601)
updated: 2026-09-23T15:42:00+03:00 # ZORUNLU (ISO 8601, her değişimde bump edilir)
locked: false # OPSİYONEL (true ise model dokunamaz)
---
```
## 4. Dosya İsimlendirme ve İçerik
KİMLİK: Global ID yoktur, dosya adı = kimlik (`kebab-case-ascii.md`).
YAPI: `frontmatter` -> `# Başlık` -> `## Links` -> `## Summary` -> `Gövde`. `---` ile Summary sonu arasında boş satır YASAKTIR.
LİNK: `## Links` altında virgülle ayrılmış düz liste kullanılır. Yön ZORUNLU olarak ÖZELDEN GENELE'dir (Yaprak -> Hub). Parent alanı yoktur.
KARARLAR: Yeni kararlar numarasız `type: decision` notudur. Eski kararı supersede eden açıkça belirtir.
## 5. Log Formatı
DOSYA: `log/YYYY-MM-DD.md`
SATIR FORMATI: `HH:mm <op> @<node> | mesaj ≤120 karakter` (op: ingest, query, tend, lint, sync).
## 6. Dil ve Optimizasyon
DİL: Gövde TÜRKÇE. Tag/slug/filename KISA ASCII.
TOKEN: Frontmatter'a gereksiz alan eklemek YASAKTIR. Dosyalar satır bütçelidir. Kök terimler İngilizce kalabilir.
