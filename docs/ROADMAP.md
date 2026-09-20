# Yol Haritası (Roadmap)

> Kalan işler planı — agent bunu canlı sürdürür. Tamamlananların özeti aşağıda;
  karar/kayıt detayları `wiki/decisions/`, mimari `docs/ARCHITECTURE.md`.

## Mevcut Durum

Faz 0 tamam (2026-09-20): repo iskeleti, sözleşmeler (AGENTS/SCHEMA), bilgi hattı
iskeleti (raw/atoms/wiki), git-crypt şifreleme, persona ve profil şablonları, örnek
içerik, dil politikası + token optimizasyonu kuralları, plan dosyası protokolü.

## Tamamlananlar

| Faz | Kapsam | Tarih |
|---|---|---|
| 0 — İskelet | sözleşmeler, bilgi hattı, git-crypt, SOUL.md, örnek ADR/atom; dil politikası + token kuralları + plan protokolü (revizyon paketi) | 2026-09-20 |

## Kalan İşler

### Faz 1 — Canlıya alınma
- [ ] Private GitHub repo oluştur (MR akışı için) + ilk push + `git-crypt export-key` yedeği
- [ ] VPS hazırlığı: SSH anahtar, firewall, güncellemeler
- [ ] Hermes kurulumu (VPS) + çoklu direkt provider (`.env`) + Telegram bot + DM pairing
- [ ] Workspace = repo klonu; cron kurulumu: gece konsolidasyon, haftalık lint, sabah bülteni
- [ ] Mac klonu + Obsidian vault = `wiki/`

### Faz 2 — Knowledge MCP v1 (vektörsüz)
- [ ] `mcp/knowledge`: frontmatter kataloğu, rg search, `[[link]]` graph (≤2 hop / ≤5 komşu),
      token-bütçeli context builder (4K default, özet-first, dedup, stabil→uçucu sıra)
- [ ] `ingest` skill'i + inbox akışı canlı (Telegram dosya → inbox)

### Faz 3 — Bakım döngüsü
- [ ] `tend` operasyonu (stub/orphan/imported/duplicate)
- [ ] `build_index` — üretilen `wiki/index.md`
- [ ] hot.md disiplini + lint kuralları tam set (satır bütçeleri dahil)

### Faz 4 — Anlamsal katman + çoklu düğüm
- [ ] On-demand semantic: yerel embedding (VPS CPU) + sqlite-vec, `data/` cache
- [ ] Ev düğümü: Ollama provider, aynı repo klonu
- [ ] Model fallback değerlendirmesi: Hermes konfig → LiteLLM proxy → özel kod
- [ ] Claims tablosu değerlendirmesi (paralel düğüm yoğunluğu oluşursa)

### Faz 5 — Genişleme
- [ ] WhatsApp/Signal gateway + sesli not transkripsiyonu
- [ ] Ek integration'lar (takvim/CalDAV, RSS, e-posta) — talep-kapılı
