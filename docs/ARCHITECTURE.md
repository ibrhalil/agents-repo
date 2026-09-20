# Mimari — Noma Kişisel Asistan Sistemi

Kararlı tasarımın kalıcı kaydı. Mimari değişiklikler ADR olarak
(`wiki/decisions/`) wiki'ye işlenir; bu doküman genel bakışı tutar.

## İlkeler
1. **Markdown source of truth** — index/embedding yeniden üretilebilir önbnektir;
   kendi veritabanı formatına kilitlenme yok, Obsidian doğrudan okur.
2. **Runtime-bağımsız çekirdek** — bir agent'in "Noma" olması için gereken her şey
   repoda: sözleşmeler (AGENTS/SCHEMA), bilgi hattı, memory, persona, MCP.
3. **Git = kontrol mekanizması** — iki şeritli yazma; wiki değişiklikleri MR ile.
4. **Token optimizasyonu** — retrieval ucuzdan pahalıya; context bütçeli montaj.
5. **Local-first dostu, bulut esnek** — direkt çoklu provider + Ollama düğümü.

## Bilgi hattı ve retrieval
Üretim tarafı: `raw → atoms → wiki`. Sorgu tarafı:

```
User Query
  → Query Parser
  → Metadata/Type/Tag filtresi
  → Keyword (ripgrep)
  → Wiki Graph (1-2 hop [[link]])
  → (yetersizse) Semantic (yerel embedding)
  → Ranking/Merge
  → Token-bütçeli Context Builder
  → LLM
```

Vector DB truth değildir. Türkçe'nin eklemeli yapısı naif keyword search'i
zayıflattığından graph + semantic katmanları ortalama bir kurulumdan daha fazla
iş taşır. Epistemik hijyen: her cevap `[atoms/...]` atıflı; `unverified →
established` yükseltmesi ikinci bağımsız kaynak ya da insan onayı ister.

## Düğümler
- **VPS (7/24 birincil):** Hermes + Telegram gateway + cron (gece konsolidasyon,
  haftalık lint, sabah bülteni). Workspace = bu reponun klonu.
- **Ev (test/local):** Ollama provider, aynı repo klonu, aynı SCHEMA.
- **İnsan düğümü:** Obsidian ile `wiki/` doğrudan düzenleme.
- **Senkron:** git (`pull --rebase → merge → commit → push`); append-only tasarım
  çoklu yazıcıda çatışmaları seyrekleştirir.

## Faz durumu
Canlı yol haritası (kalan işler + tamamlanan fazlar): `docs/ROADMAP.md`.

## Teknoloji gerekçeleri (özet)
- **Hermes hibrit:** agent loop / cron / gateway / model yönetimi yeniden yazılmaz;
  özel geliştirme bilgi sistemine odaklanır. Sıfırdan runtime değerlendirildi ve
  reddedildi (aylarca sürecek, tek kişi için bakımsız).
- **MCP:** taşınabilirlik katmanı — düğüm ne olursa olsun aynı retrieval.
- **git-crypt:** kişisel veri için; retrofit git history yeniden yazma gerektirdiğinden
  günden bir kuruldu.
- **index.md üretimi:** LLM disiplinine değil deterministik araca dayanır (drift yok).
- **`memory/` repo içinde:** Hermes yerleşik hafizası düğüm-lokal olduğundan çok
  düğümlü senaryoda kanonik profil repoya taşındı.
- **forgesys aktarımları:** plan dosyası protokolü (resume + step contract), ROADMAP,
  dondurulmuş karar kuralı, dokümantasyon satır bütçeleri ve dil politikasının token
  optimizasyonu gerekçesi — olgun bir çok-agent deposundan (forgesys) devralındı.
