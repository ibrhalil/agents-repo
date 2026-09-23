---
node: laptop-opencode
runtime: opencode
model: GLM (z.ai)
role: etkileşimli geliştirme düğümü — sözleşme bakımı, araç geliştirme, ingest/tend
status: active
added: 2026-09-23
---

# Laptop — opencode

- **Kanallar:** CLI (insan ile doğrudan oturum)
- **Erişim:** repo read/write (serbest yazma; commit ve conflict çözümü cron'da — bkz. `[[main-insana-aittir]]`); `raw/` append-only
- **Kısıtlar:** ADR-8 uyumlu; şifreli içerik yalnız LLM context'ine (AGENTS R4)
- **Notlar:** İlk kayıtlı düğüm. macOS çalışma klonu; git-crypt açık.
