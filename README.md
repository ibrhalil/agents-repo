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

## Anahtar yedekleme protokolü

git-crypt anahtarı kaybolursa şifreli içerik **kurtarılamaz**. Koşullar (ADR-7):
repo public olduğundan güvenlik modeli anahtara dayanır; yedek GitHub ekosisteminde
(hesap, gist, Codespaces, secret deposu) tutulmaz — sızma tek hat üzerinde birleşmesin.

1. `git-crypt export-key /guvenli/yer/noma.key` (çevrimdışı ortam: şifreli USB /
   disk; ~/.noma-gitcrypt.key working kopyası değildir)
2. İkinci bağımsız kopya ayrı fiziksel konumda (ev + başka yer); her ikisi de
   tam disk şifrelemeli ortamda
3. Kağıt yedek opsiyonel: anahtar 32 bayt — base64/hex yazdırılabilir, zarf + kasa
4. Test: yedekten `git-crypt unlock` ile temiz klonu aç (yılda bir hatırlatma, lint)
5. Rotasyon yok (git-crypt re-key geçmişi yeniden yazar) → yedek disiplini tek savunma

## Kritik kurulum notları

1. **git-crypt anahtarını yedekle** — protokol yukarıda
2. **Yeni düğüm kurulumu:** klonla → `git-crypt unlock <key>` → `.env` doldur
3. **Obsidian:** vault olarak repo kökünü kullanabilirsin; grafik gürültüsünü
   "Excluded files" ile yönet (öneri: `raw/`, `atoms/`, `docs/`, `deploy/`,
   `skills/`, `mcp/`, `sdata/`, `plans/` dışla). `.obsidian/` gitignore'dır

Ayrıntılı mimari ve karar gerekçeleri: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
