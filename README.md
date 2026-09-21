# agents-repo — Noma

İnsan + agent ortak bahçesi. Kişisel asistanın tek doğruluk kaynağı: bilgi tabanı,
hafıza, yetenekler ve sözleşmeler bu repoda yaşar. Herhangi bir düğüm (VPS'te Hermes,
evde Ollama ajanı, herhangi bir MCP uyumlu agent) bu reponun bir klonu + git-crypt
unlock + bağlantıyla aynı asistana dönüşür.

## Harita

| Yol | İçerik |
|---|---|
| `AGENTS.md` | Agent davranış sözleşmesi: operasyonlar, görünürlük, yazma akışı |
| `SCHEMA.md` | Veri sözleşmesi: dizinler, frontmatter, link sözdizimi |
| `raw/ → wiki/` | Bilgi hattı (iki katman) [git-crypt] |
| `memories/` | Agent'ın kalıcı hafızası / kullanıcı profili [git-crypt] |
| `agent/prompts/` · `agent/sessions/` | Prompt hazırlama · session özetleri [git-crypt] |
| `plans/` · `log/` | Uzun iş planları · operasyonel log [git-crypt] |
| `agent/` `workspace/` `tools/` `skills/` `scripts/` | Agent altyapısı · geçici alan · yetenekler |
| `config/` `web/` `docs/` | Konfigürasyon (secret yok) · web UI · dokümantasyon |

**Görünürlük:** repo public'tir; kişisel içerik git-crypt ile şifrelenir
(`raw/ wiki/ memories/ agent/prompts/ agent/sessions/ plans/ log/`). Public
dizinlere kişisel veri yazılmaz. Ayrıntı: SCHEMA §1.

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
   "Excluded files" ile yönet (öneri: `raw/`, `docs/`, `plans/`, `log/` dışla).
   `.obsidian/` gitignore'dır

Ayrıntılı mimari ve karar gerekçeleri: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Standartlar ve Katkı

### Şablon zorunluluğu (AGENTS.md §Sert kurallar 9)

Yeni bir wiki notu oluştururken sıfırdan format üretilmez; şablon kopyalanır:
[`docs/templates/wiki_note.md`](docs/templates/wiki_note.md)

### Dosya adı kuralı (SCHEMA §3)

Wiki dosyaları `kebab-case.md` ASCII slug'dır (dosya adı = stable kimlik; insan-okur
başlık `title` alanında). `_v2`, `_yeni` gibi sürüm ekleri **yasaktır** — bilgi
değişiyorsa mevcut dosya güncellenir.

### Branch ve PR akışı

- Branch: `agent/<operasyon>-<slug>-<YYYY-MM-DD>`
- Commit prefix: `ingest:` · `query:` · `tend:` · `lint:` · `sync:`
- Her PR = 1 mantıksal değişiklik; gövdede özet + kaynak path'leri
- `log/` kaydı değişiklikle aynı commit'te güncellenir
- **main'e doğrudan commit/push yasak** — tüm değişiklikler PR ile (ADR-10)

### Lokal lint çalıştırma

```bash
# pre-commit kurulu değilse:
pip install pre-commit
pre-commit install

# Tüm dosyaları kontrol et:
bash scripts/run_lint.sh

# veya doğrudan:
pre-commit run --all-files
```
