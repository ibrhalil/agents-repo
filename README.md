# agents-repo — Noma

İnsan + agent ortak bahçesi. Kişisel asistanın tek doğruluk kaynağı: bilgi hattı,
hafıza, persona, yetenekler ve sözleşmeler bu repoda yaşar. Herhangi bir düğüm
(VPS'te Hermes, evde Ollama ajanı, herhangi bir MCP uyumlu agent) bu reponun bir
klonu + git-crypt unlock + MCP bağlantısıyla aynı asistana dönüşür.

## Harita

| Yol | İçerik |
|---|---|
| `AGENTS.md` | Agent davranış sözleşmesi: operasyonlar, yazma şeritleri, MR protokolü |
| `SCHEMA.md` | Veri sözleşmesi: frontmatter, tipler, link sözdizimi, dizin anlamları |
| `soul/SOUL.md` | Persona: Noma kim, nasıl konuşur |
| `raw/ → atoms/ → wiki/` | Bilgi hattı [git-crypt] |
| `memory/` | Taşınabilir kullanıcı profili [git-crypt] |
| `sdata/` | Yapılandırılmış uygulama verisi — habit, sayaç [git-crypt] |
| `skills/` · `mcp/` | Hermes skill'leri · knowledge MCP sunucusu |
| `deploy/` · `docs/` | Düğüm kurulumları · mimari dokümantasyon |

## Kritik kurulum notları

1. **git-crypt anahtarını yedekle** (kaybolursa şifreli içerik kurtarılamaz):
   `git-crypt export-key /guvenli/yer/noma.key`
2. **Yeni düğüm kurulumu:** klonla → `git-crypt unlock <key>` → `.env` doldur
3. **Obsidian:** vault olarak repo kökünü kullanabilirsin; grafik gürültüsünü
   "Excluded files" ile yönet (öneri: `raw/`, `atoms/`, `docs/`, `deploy/`,
   `skills/`, `mcp/`, `sdata/`, `plans/` dışla). `.obsidian/` gitignore'dır

Ayrıntılı mimari ve karar gerekçeleri: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
