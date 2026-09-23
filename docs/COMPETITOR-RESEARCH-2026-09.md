> **Tarihsel belge (2026-09):** Bu rapor eski 3-katmanlı yapıyı (atoms katmanı,
> `soul/`, `sdata/`, `hot.md`) tarif eder — güncel mimariyle çelişir. Güncel durum:
> `docs/ARCHITECTURE.md` ve `wiki/yeni-agent-yapisi.md`.

Bağ: [[index]] · [[wiki/yeni-agent-yapisi|Yeni Agent Yapısı]]

# Benzer Projeler Araştırması — Agent-Entegre "İkinci Beyin" Sistemleri

Bu alan 2025-2026'da hızla olgunlaştı. Ortak kalıp **"LLM Wiki"** olarak adlandırılıyor. Noma tam da bu kalıbın disiplinli bir uygulaması.

## İncelenen Projeler ve Noma İçin Dersler

### 1. COG (Cognition + Obsidian + Git)
- **Yaklaşım:** Vault + Skills + Worker/Verifier agent ayrımı.
- **Ders:** Noma'ya "Worker/Verifier" mantığıyla "Post-ingest verification" adımı eklenebilir. İnsan ilişkileri takibi için People CRM pratikleri incelenebilir.

### 2. Karpathy LLM Wiki Kalıbı
- **Yaklaşım:** Stop Retrieving, Start Compiling. Ham kaynakları derlenmiş markdown sayfalarına dönüştür.
- **Durum:** Noma zaten bu kalıbın uygulayıcısı, üzerine 3. katman olarak "atoms" ve ADR kültürünü ekliyor.

### 3. Second Brain Starter (coleam00)
- **Yaklaşım:** Claude Code'a özgü, proactive heartbeat, memory hygiene.
- **Ders:** `hot.md` yönetimi için "Memory decay scoring" (yaş, erişim sıklığı) yaklaşımı Noma'ya uyarlanabilir.

### 4. gptme
- **Yaklaşım:** Terminal-native, Git-backed memory (journal/tasks).
- **Ders:** `git blame` üzerinden öğrenme izleme felsefesi Noma'nın atoms yapısıyla örtüşüyor.

### 5. Letta (MemGPT)
- **Yaklaşım:** MemFS, Git branch/merge ile multi-agent collaboration, sleep-time consolidation.
- **Ders:** Faz 4 çoklu düğüm için branch/merge çatışma çözümü ve gece konsolidasyonunun `tend()` operasyonlarıyla yapılması çok değerli bir referans.

### 6. ai-memory (akitaonrails)
- **Yaklaşım:** Rust tabanlı çapraz agent MCP bellek katmanı.
- **Ders:** Faz 2 MCP sunucu tasarımı için "cross-agent handoff" mimarisi ve çoklu düğüm için "attribution" (node identity) mekanizması örnek alınabilir.

### 7. dsebastien Obsidian Starter Kit (OSK v4)
- **Yaklaşım:** Agentic Knowledge Management (AKM), uzman agent rolleri (Skeptic, Editor vs.).
- **Ders:** Oturum profilleri (ADR-9 K1) genişletilerek `ingest-agent`, `tend-agent` veya "Skeptic" gibi özel roller formalize edilebilir.

### 8. Google Open Knowledge Format (OKF)
- **Yaklaşım:** Markdown + YAML frontmatter standardı (type, trust tiers, lifecycle, provenance).
- **Ders:** Noma'nın SCHEMA'sı OKF v0.2'ye çok yakın (status=trust, stage=lifecycle, updated=freshness). İleride tam taşınabilirlik için uyumluluk ADR'si yazılabilir.

## Sentez
Noma, 3 katmanlı bilgi hattı, git-crypt ile public repo modeli ve koçluk boyutuyla rakiplerinden ayrışıyor. Rakiplerden alınacak en değerli pratikler: MCP cross-agent handoff, multi-agent branching (çatışma çözümü) ve decay scoring tabanlı bellek yönetimi.
