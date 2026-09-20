# Yol Haritası (Roadmap)

> İki araştırmanın (proje analizi + benzer projeler) sentezi sonucu oluşturulmuştur.
> Karar kayıtları `wiki/decisions/`, mimari `docs/ARCHITECTURE.md`.

---

## Mevcut Durum

Faz 0 tamam (2026-09-20). Faz 1 kısmen başladı (A0-A4 tamam, VPS erişimi bekleniyor).

## Tamamlananlar

| Faz | Kapsam | Tarih |
|---|---|---|
| 0 — İskelet | Sözleşmeler, bilgi hattı, git-crypt, SOUL.md, 10 ADR, örnek atom/wiki; dil+token+plan protokolü | 2026-09-20 |

---

## Faz 0.5 — Sözleşme Hijyeni *(yeni — VPS beklenmeden yapılabilir)*

- [ ] **ADR-10 ↔ sdata çelişkisini çöz**
  - Karar: `sdata/` agent'ın doğrudan yazdığı programatik veri — branch gerektirmez (ADR-10 istisnası).
- [ ] **Branch protection aktifleştir (GitHub)**
  - `main` dalında: require PR review, no direct push.
- [ ] **ADR-2'ye `superseded_by: 10` ekle**
- [ ] **Atom ID çakışma politikası**
  - Düğüm prefixi sistemi → `a-H-NNNN` (Hermes), `a-L-NNNN` (local).
- [ ] **`consolidate()` operasyonunu tanımla**
  - AGENTS.md'ye ekle: `consolidate() = cron tetikli ingest(inbox) + tend() + hot.md budget check`.
- [ ] **Log.md düğüm kimliği**
  - Log formatını genişlet: `## [YYYY-MM-DD HH:mm] <op>@<node> | özet`
- [ ] **Index.md'ye `tasks/` ve `issues/` placeholder**

---

## Faz 1 — Canlıya Alınma *(güncellendi)*

- [x] ~~A0 Kilitli-klon testi~~ PASSED
- [x] ~~A1 Plan dosyası~~
- [ ] A2 Obsidian vault ayarı *(kullanıcı tarafı)*
  - Ek: Obsidian ayar rehberi yazılacak (`docs/obsidian-recommended.md`)
- [x] ~~A3 Güvenlik ADR paketi~~ (ADR-7..10)
- [x] ~~A4 README anahtar yedekleme protokolü~~
- [ ] B1 VPS hazırlığı
- [ ] B2 Hermes kurulumu
- [ ] B3 `.env` oluşturma + **`NODE_ID` ve provider endpoint'leri**
- [ ] B4 Workspace klonu
- [ ] B5 Cron job'lar (consolidate eklendi)
- [ ] B6 Telegram (sonraya atıldı)
- [ ] Güvenlik advisory: LUKS + Obsidian plugin denetimi

---

## Faz 2 — Knowledge MCP v1 + Ingest Hattı

### 2A — MCP Sunucu
- [ ] `mcp/knowledge` sunucusu: frontmatter kataloğu, ripgrep search, `[[link]]` graph.
- [ ] Token-bütçeli context builder (özet-first, dedup).
- [ ] **Cross-agent handoff desteği** — farklı runtime'lar aynı MCP'den okuyabilmeli.
- [ ] MCP default bind: localhost / Unix socket.

### 2B — Ingest Skill
- [ ] `skills/ingest`: inbox akışı canlı.
- [ ] Master Note DB alan normalizasyonu.
- [ ] **Post-ingest verification** — ingest sonrası otomatik format/link denetimi.
- [ ] **Atom → wiki atıf haritası** — orphan atom tespiti.

### 2C — Güvenlik
- [ ] Runtime araç allowlist + oturum profilleri.
- [ ] Ingest regex ön-taraması (injection flag).

### 2D — Bilgi Akışı (paralel)
- [ ] FreshRSS kurulumu (Docker) + freshrss-x.
- [ ] `sdata/digest.json` şablonu.
- [ ] Saatlik keyword push (regex, LLM'siz).
- [ ] Sabah gündem digest'i.
- [ ] Değerli içerik yolu: digest → `raw/clippings/` → atoms → wiki MR.

---

## Faz 3 — Bakım Döngüsü + Ölçeklenme Altyapısı

### 3A — Operasyonlar
- [ ] `tend()` operasyonu: stub genişletme, orphan bağlama.
- [ ] `build_index` — deterministik `wiki/index.md` üretimi (`tasks/` ve `issues/` dahil).
- [ ] `lint()` tam set:
  - Kırık link, orphan sayfa, atoms↔wiki tutarlılığı.
  - `hot.md` satır bütçesi + **taşma mekanizması (ilgili sayfaya taşıma)**.
  - Güvenlik lint: hassas glob GITCRYPT kontrolü.

### 3B — Ölçeklenme Hazırlığı
- [ ] **Log rotasyonu** — `log.md` aktif + arşiv dizini.
- [ ] **hot.md decay mekanizması** — yaş/erişim bazlı öncelik skoru.
- [ ] **`wiki/resources/` iskeleti** — dil alt dizinleri.
- [ ] **Mevcut kararların scope tamamlanması** — ADR-1..6'ya `scope:` ekle.
- [ ] **People dizini politikası** — kanıt bazlı profiller, `memory/profile.md` ile ayrım.
- [ ] **`raw/conversations/` çakışma koruması** — `YYYY-MM-DD-HHmmss.md`.

---

## Faz 4 — Anlamsal Katman + Çoklu Düğüm

### 4A — Semantic Search
- [ ] On-demand semantic: yerel embedding + sqlite-vec, `data/` cache.

### 4B — Çoklu Düğüm
- [ ] Ev düğümü: Ollama provider, aynı repo klonu.
- [ ] **Katman bazlı çatışma çözüm politikası** (Git branch/merge mekanizmaları).
- [ ] **Uzman agent rolleri** (Skeptic, Editor vs.) oturum profilleri.

### 4C — Yedeklilik
- [ ] İkinci bare-mirror (şifreli disk) + anahtar escrow.
- [ ] Model fallback.

### 4D — OKF Uyumluluk Değerlendirmesi
- [ ] Noma SCHEMA ↔ Google OKF v0.2 alan eşlemesi ve dönüşüm analizi.

---

## Faz 5 — Genişleme
- [ ] WhatsApp/Signal gateway + sesli not transkripsiyonu.
- [ ] Ek integration'lar (takvim, RSS e-posta).
- [ ] **Sözleşme kompakt versiyonu** — token verimliliği için AGENTS+SCHEMA özeti.
- [ ] **Profile MCP entegrasyonu** — `memory/profile.md`'nin query ile çekilmesi.
