# Mimari — Noma Kişisel Asistan Sistemi

Kararlı tasarımın kalıcı kaydı. Mimari değişiklikler `type: decision` kayıtları
olarak wiki'ye işlenir (eski ADR-1..10 numaraları tarihsel referanstır); bu doküman
genel bakışı tutar.

## İlkeler
1. **Markdown source of truth** — index/graph/view'lar yeniden üretilebilir; kendi
   veritabanı formatına kilitlenme yok, Obsidian doğrudan okur.
2. **Runtime-bağımsız çekirdek** — herhangi bir agent'ın "Noma" olması için gereken
   her şey repoda: sözleşmeler (AGENTS/SCHEMA), bilgi hattı, kullanıcı profili
   (`wiki/kullanici-profili.md`), yetenekler.
3. **Git = kontrol mekanizması** — Agent'lar serbestçe çalışır, commit ve conflict çözümü periyodik cron job ile yönetilir (ADR-10 Güncellendi).
4. **Token optimizasyonu** — retrieval ucuzdan pahalıya; context bütçeli montaj. Sözleşmeler LLM-optimize edilmiştir.
5. **Local-first dostu, bulut esnek** — direkt çoklu provider + Ollama düğümü (ADR-8).
6. **Gereksiz complexity yok** — yeni katman/alan/dizin gerçek ihtiyaç ister
   (wiki/yeni-agent-yapisi.md §44).

## Bilgi hattı ve retrieval
Üretim tarafı: `raw → wiki` (iki katman; atoms kaldırıldı — [[wiki/yeni-agent-yapisi]]).
Sorgu tarafı motor-bağımsızdır:

```text
metadata filtre (type/stage/scope/tags)
  → full-text (ripgrep)
  → gerektiğinde [[wikilink]] traversal (1-2 hop)
  → yalnız gerekli context'i modele getir
```

Graph/search/embedding mimarisi henüz kararlaşmadı (§45-8/9) — belirli motor
varsayılmaz. Epistemik hijyen: her cevap kaynak path'iyle atıflı (`wiki/slug.md`,
`raw/...`); `unverified → established` yükseltmesi ikinci bağımsız kaynak ya da
insan onayı ister.

## Görünürlük ve güvenlik
Repo bilinçli public (ADR-7): kod/mimari/dokümantasyon açık; kişisel knowledge
git-crypt ile şifreli (`raw/ wiki/ agent/prompts/ agent/sessions/ plans/
log/ tmp/`). Kabul edilen sızıntı şifreli blob metadata'sıdır; fact-düzeyi kişisel
veri yol adlarında bile yaşamaz. Hassas kapsam yalnız yerel model
(ADR-8); prompt injection savunması katmanlı (ADR-9).

## Düğümler
Düğüm = bu repoyu sözleşmeye bağlı kullanan her agent/model (kayıt dizini
`docs/nodes/` 2026-09-23'te kaldırıldı; düğüm envanteri bu bölümde yaşar).
- **Laptop (aktif):** opencode — etkileşimli geliştirme düğümü.
- **VPS (7/24 birincil, planlı):** ilk runtime adayı Hermes + Telegram gateway +
  cron (gece konsolidasyon, haftalık lint, sabah bülteni). Workspace = klon.
- **Ev (test/local):** Ollama provider, aynı repo klonu, aynı SCHEMA.
- **İnsan düğümü:** Obsidian ile `wiki/` doğrudan düzenleme.
- **Senkron:** git; düğümler serbest yazar, commit ve conflict çözümü periyodik
  cron job'a aittir ([[wiki/main-insana-aittir]] kararı, 2026-09-23); append-only
  tasarım çoklu yazıcıda çatışmaları seyrekleştirir.

## Faz durumu
Canlı yol haritası (kalan işler + tamamlanan fazlar): `docs/ROADMAP.md`.

## Teknoloji gerekçeleri (özet)
- **Hermes (VPS düğümü runtime adayı):** agent loop / cron / gateway / model
  yönetimi yeniden yazılmaz; özel geliştirme bilgi sistemine odaklanır. Sıfırdan
  runtime değerlendirildi ve reddedildi (aylarca sürecek, tek kişi için bakımsız).
- **MCP:** taşınabilirlik katmanı adayı; nihai kullanımı/sınırları henüz kararlaşmadı
  (§45-11) — ihtiyaç yokken katman eklenmez.
- **git-crypt:** kişisel veri için; retrofit git history yeniden yazma gerektirdiğinden
  günden bir kuruldu.
- **graph/index üretimi:** `index.md`, cron tarafından (`scripts/build_index.py` aracılığıyla) wiki notlarının `## Links` bölümündeki "özelden genele" yönleri taranarak deterministik olarak üretilir.
- **Kanonik profil wiki'de:** Hermes yerleşik hafızası düğüm-lokal olduğundan çok
  düğümlü senaryoda kanonik profil repoda taşınır; `memories/` dizini 2026-09-23'te
  kaldırıldı — profil `wiki/kullanici-profili.md` olarak yaşar, tüm düğümlere
  şifreli sync olur.
- **forgesys aktarımları:** plan dosyası protokolü (resume + step contract), ROADMAP,
  dondurulmuş karar kuralı, dokümantasyon satır bütçeleri ve dil politikasının token
  optimizasyonu gerekçesi — olgun bir çok-agent deposundan (forgesys) devralındı.

Kök: [[index]]
