# mcp/knowledge — Knowledge MCP Sunucusu

Bilgi hattına runtime-bağımsız erişim: her MCP uyumlu agent (Hermes, opencode,
Claude, özel agent) bu sunucuya bağlanarak retrieval yapar.

Faz 2 kapsamı (vektörsüz v1):
- frontmatter kataloğu + type/tag/scope/stage/priority/date filtresi
- ripgrep tabanlı keyword search
- `[[link]]` graph genişletmesi: ≤2 hop, ≤5 komşu
- token-bütçeli context builder:
  - **sert bütçe** (default 4K token, ayarlanabilir); taşmada en düşük rank düşürülür
  - **özet-first**: önce frontmatter + özet paragrafı; büyük notlarda heading-bazlı
    ilgili bölüm, tamamı değil
  - **dedup**: aynı bilgiyi taşıyan notlar → tek en-iyi kaynak + `[[link]]`
  - **sıra stabil → uçucu**: sözleşmeler → hot.md → sorgu sonuçları (prefix-cache dostu)

Tarama politikası: index/embedding yenilemesi cron tetikler; sorgu anında tam
tarama yok — MCP sorguları mevcut katalog/önbnek üzerinden çalışır (ADR-4).

Faz 4: on-demand semantic (yerel embedding + sqlite-vec, `data/` altında cache).
