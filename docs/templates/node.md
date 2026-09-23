---
node: kisa-ascii-kimlik            # ör: hermes-vps, ev-ollama, laptop-opencode
runtime: <agent yazılımı>          # ör: Hermes, opencode, başka bir CLI agent
model: <model / sağlayıcı>         # ör: GLM (z.ai), llama3 (Ollama)
role: <rol>                        # ör: 7/24 cron düğümü, etkileşimli asistan
status: active                     # active | retired
added: YYYY-MM-DD
---

# <Düğüm adı>

- **Kanallar:** <CLI / Telegram / cron / ...>
- **Erişim:** repo read/write (serbest yazma; commit ve conflict çözümü cron'da — bkz. `[[main-insana-aittir]]`); `raw/` append-only
- **Kısıtlar:** <ör: hassas scope yalnız yerel model — ADR-8 uyum beyanı>
- **Notlar:** kurulum özellikleri; sırlar asla burada (yalnız `.env`)

Kök: [[index]]
